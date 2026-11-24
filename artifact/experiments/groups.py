"""Run alongside benchmark.py from the data directory's parent."""
import itertools
import json
import random
from collections import Counter
from pathlib import Path

from benchmark import SOURCES, load, timed


def coefficients(edges):
    counts = Counter(edges)
    inc, out = Counter(), Counter()
    for (u,v), n in counts.items():
        inc[v] += n
        out[u] += n
    for (u,v), n in counts.items():
        back = counts[v,u]
        a, b = out[v] - back, inc[u] - back
        if a or b:
            yield u,v,n,a,b


def evaluate(terms, weights):
    total = 0
    for u,v,n,a,b in terms:
        wu, wv = weights[u], weights[v]
        total += n*(wv*wv*a + (wv*a-wu*b)**2)
    return total


def compile_matrix(bins):
    diag, cross = Counter(), Counter()
    for edges in bins:
        for u,v,n,a,b in coefficients(edges):
            if a:
                diag[v] += n*(a+a*a)
            if b:
                diag[u] += n*b*b
            if a and b:
                cross[min(u,v),max(u,v)] -= 2*n*a*b
    return list(diag.items()), [(u,v,k) for (u,v),k in cross.items()]


def query_matrix(matrix, weights):
    diag, cross = matrix
    return (sum(d*weights[v]**2 for v,d in diag)
            + sum(c*weights[u]*weights[v] for u,v,c in cross))


def run(bins, weights, n, method):
    if method == 'matrix':
        obj, build = timed(lambda: compile_matrix(bins))
        result, query = timed(lambda:[query_matrix(obj,w) for w in weights[:n]])
        size = list(map(len,obj))
    elif method == 'cache':
        obj, build = timed(lambda:list(itertools.chain.from_iterable(coefficients(b) for b in bins)))
        result, query = timed(lambda:[evaluate(obj,w) for w in weights[:n]])
        size = len(obj)
    else:
        build, size = 0, None
        result, query = timed(lambda:[sum(evaluate(coefficients(b),w) for b in bins) for w in weights[:n]])
    return result,dict(build=build,query=query,total=build+query,entries=size)


def main():
    data={}
    for name,file in SOURCES.items():
        records,_ = load(Path('data')/file)
        bins=[[(u,v) for _,u,v in g] for _,g in itertools.groupby(records,key=lambda x:int(x[0]//3600))]
        ids=sorted({v for b in bins for edge in b for v in edge})
        rng=random.Random(5917)
        weights=[{v:rng.choice((-1,0,1)) for v in ids} for _ in range(64)]
        methods=['direct','cache','matrix']
        rows=[]
        for n in (1,8,64):
            for r in range(3):
                previous=None
                for method in methods[r:]+methods[:r]:
                    values,stats=run(bins,weights,n,method)
                    assert previous is None or previous==values
                    previous=values
                    rows.append(dict(n=n,round=r,method=method,**stats))
        data[name]=dict(vertices=len(ids),measurements=rows,variance_numerators=previous)
        print(name,flush=True)
        Path('results').mkdir(exist_ok=True)
        Path('results/groups.json').write_text(json.dumps(data,indent=2))


if __name__=='__main__':
    main()
