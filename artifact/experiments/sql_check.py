"""SQLite replication. Run after benchmark.py and groups.py are present."""
import hashlib
import itertools
import json
import sqlite3
from pathlib import Path

from benchmark import SOURCES, MODES, endpoint, load, native_mean2, timed
from fetch_snap import fetch
from groups import compile_matrix


DIRECT = """
SELECT g.u,g.v,g.n,
  coalesce((SELECT sum(x.n) FROM g AS x
            WHERE x.h=g.h AND x.u=g.v AND x.v<>g.u),0) AS a,
  coalesce((SELECT sum(x.n) FROM g AS x
            WHERE x.h=g.h AND x.v=g.u AND x.u<>g.v),0) AS b
FROM g
"""
ENDPOINT = """
WITH incoming AS MATERIALIZED (SELECT h,v,sum(n) d FROM g GROUP BY h,v),
outgoing AS MATERIALIZED (SELECT h,u,sum(n) d FROM g GROUP BY h,u)
SELECT g.u,g.v,g.n,coalesce(o.d,0)-coalesce(rev.n,0) AS a,
                   coalesce(i.d,0)-coalesce(rev.n,0) AS b
FROM g
LEFT JOIN incoming i ON (i.h,i.v)=(g.h,g.u)
LEFT JOIN outgoing o ON (o.h,o.u)=(g.h,g.v)
LEFT JOIN g rev ON (rev.h,rev.u,rev.v)=(g.h,g.v,g.u)
"""


def query(db, terms):
    sql = f"""WITH terms AS MATERIALIZED ({terms}),
    coefficients AS (
      SELECT v AS x, v AS y, n*(a+a*a) AS value FROM terms WHERE a>0
      UNION ALL SELECT u,u,n*b*b FROM terms WHERE b>0
      UNION ALL SELECT min(u,v),max(u,v),-2*n*a*b FROM terms WHERE a*b>0)
    SELECT x,y,sum(value) FROM coefficients GROUP BY x,y"""
    return {(x,y):v for x,y,v in db.execute(sql)}


def prepare(db, records):
    db.execute('CREATE TABLE e(h INTEGER,u INTEGER,v INTEGER)')
    db.executemany('INSERT INTO e VALUES(?,?,?)',
                   ((int(t//3600),u,v) for t,u,v in records))
    db.execute('CREATE TABLE g(h INTEGER,u INTEGER,v INTEGER,n INTEGER,PRIMARY KEY(h,u,v)) WITHOUT ROWID')
    db.execute('INSERT INTO g SELECT h,u,v,count(*) FROM e GROUP BY h,u,v')
    db.execute('CREATE INDEX by_v ON g(h,v,u,n)')
    db.commit()


def main():
    extra = 'sx-mathoverflow-a2q.txt.gz'
    Path('data').mkdir(exist_ok=True)
    source = fetch(extra)
    results={'sqlite_version':sqlite3.sqlite_version, 'transfer_source':source, 'datasets':{}}
    for name, filename in [('MathOverflowA2Q',extra),('CollegeMsg',SOURCES['CollegeMsg']),
                           ('EmailEU',SOURCES['EmailEU'])]:
        (records,removed),io=timed(lambda:load(Path('data')/filename))
        bins=[list(g) for _,g in itertools.groupby(records,key=lambda x:int(x[0]//3600))]
        edges=[[(u,v) for _,u,v in group] for group in bins]
        diag, cross=compile_matrix(edges)
        gold={(v,v):x for v,x in diag}
        gold.update({(u,v):x for u,v,x in cross})
        db=sqlite3.connect(':memory:')
        db.execute('PRAGMA temp_store=MEMORY')
        _,setup=timed(lambda:prepare(db,records))
        methods=[('indexed',DIRECT),('endpoint',ENDPOINT)]
        times={k:[] for k,_ in methods}
        for r in range(3):
            for key,sql in methods[::1 if r%2==0 else -1]:
                values,elapsed=timed(lambda:query(db,sql))
                assert values==gold
                times[key].append(elapsed)
        moments={}
        for mode in MODES:
            sums=list(map(sum,zip(*(endpoint(b,mode) for b in edges))))
            moments[mode]=dict(mean2=sums[0],var12=sums[1],iid12=sums[2],diag12=sums[3],
                               native_mean2=sum(native_mean2(b,mode) for b in bins))
        results['datasets'][name]=dict(read_sort_s=io,layout_s=setup,measurements=times,
            matrix_entries=len(gold),nonself=len(records),self_removed=removed,
            bins=len(bins),moments=moments,sha256=hashlib.sha256((Path('data')/filename).read_bytes()).hexdigest())
        db.close()
        print(name,flush=True)
        Path('results').mkdir(exist_ok=True)
        Path('results/sql.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':
    main()
