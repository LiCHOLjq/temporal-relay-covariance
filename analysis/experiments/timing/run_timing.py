"""Paired, sequential, single-worker timing study. See README.md for commands."""
import argparse
import csv
import hashlib
import itertools
import json
import os
import platform
import random
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

P = argparse.ArgumentParser(description=__doc__)
P.add_argument("--lib", type=Path, required=True)
P.add_argument("--data", type=Path, required=True)
P.add_argument("--out", type=Path, required=True)
P.add_argument("--trials", type=int, default=12)
P.add_argument("--cpu", type=int)
args = P.parse_args()
sys.path.insert(0, str(args.lib.resolve()))
import benchmark
import groups
import sql_check

FIFTH = "sx-mathoverflow-a2q.txt.gz"
HASHES = {
    "CollegeMsg.txt.gz": "50ae2d98ed3bad9ddb18dbd495a89e5e10cfb8f7e86932827db29fc41b41f9fa",
    "email-Eu-core-temporal.txt.gz": "f6cc93249978e59d1aba111b55ea10ec553917419a3be1210012b5db3580efa6",
    "soc-sign-bitcoinotc.csv.gz": "6424ac981dad3a019f697fc1b9fcd85c19d8d9f039797758e9ffb6fea100c373",
    "soc-sign-bitcoinalpha.csv.gz": "3a178611b9c2f39c9a0dc75936f28557317f1733319b49da4838232b3757cd76",
    FIFTH: "1e160dcd3e685f7467f4869451899bae0299016080ae994895a900b57812ca78",
}

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def clock():
    return time.perf_counter_ns()

def elapsed(call):
    start = clock()
    value = call()
    return value, (clock() - start) / 1e6

def proc_ticks():
    entries = {}
    for line in Path("/proc/stat").read_text().splitlines():
        words = line.split()
        if words and words[0].startswith("cpu") and words[0][3:].isdigit():
            values = [int(x) for x in words[1:9]]
            entries[int(words[0][3:])] = (sum(values), sum(values[3:5]))
    return entries

def fraction_busy(first, last):
    total = last[0] - first[0]
    return 1 - (last[1] - first[1]) / total if total else 0.

def siblings(cpu):
    topo = Path("/sys/devices/system/cpu") / f"cpu{cpu}" / "topology" / "thread_siblings_list"
    result = []
    for interval in topo.read_text().strip().split(","):
        bounds = list(map(int, interval.split("-")))
        result.extend(range(bounds[0], bounds[-1] + 1))
    return result

def choose_cpu():
    allowed = sorted(os.sched_getaffinity(0))
    first = proc_ticks()
    time.sleep(2)
    last = proc_ticks()
    busy = {i: fraction_busy(first[i], last[i]) for i in first}
    selected = args.cpu if args.cpu is not None else min(allowed, key=lambda i: (max(busy[j] for j in siblings(i)),busy[i],i))
    os.sched_setaffinity(0, {selected})
    return selected, allowed, busy

def snapshot():
    sched = [int(x) for x in Path("/proc/self/schedstat").read_text().split()]
    return time.monotonic(), proc_ticks(), sched

def load_interval(before, dataset, phase, trial):
    end, tick1, sched1 = snapshot()
    start, tick0, sched0 = before
    duration = end - start
    others = [j for j in siblings(cpu) if j != cpu]
    wait_ms = (sched1[1] - sched0[1])/1e6
    return dict(dataset=dataset,phase=phase,trial=trial,wall_s=duration,
                worker_scheduled_s=(sched1[0]-sched0[0])/1e9,runnable_wait_ms=wait_ms,
                sibling_max_busy=max([fraction_busy(tick0[j],tick1[j]) for j in others], default=None))

def write_csv(name, rows):
    with (args.out/name).open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def endpoint_exact(edges, mode):
    # Same all-relay mean and exact variance numerators as explicit().
    counts = Counter(edges)
    inc, out = Counter(), Counter()
    for (u, v), n in counts.items():
        inc[v] += n
        out[u] += n
    mean2 = mass = squared_imbalance = 0
    for (u, v), n in counts.items():
        back = counts[v, u]
        a = out[v] - back
        b = inc[u] - back
        w = benchmark.weight(v, mode)
        mean2 += n * w * a
        mass += n * w * w * a
        squared_imbalance += n * (w * a - benchmark.weight(u, mode) * b) ** 2
    return mean2, mass + squared_imbalance

def order(methods, r):
    # Every method occupies every position equally often across 12 trials.
    n = len(methods)
    shift = r % n
    seq = methods[shift:]+methods[:shift]
    return seq if (r//n)%2==0 or n==2 else seq[::-1]

def single(dataset, bins):
    names = ["enumerate", "endpoint_exact", "endpoint_full"]
    fn = dict(enumerate=benchmark.explicit, endpoint_exact=endpoint_exact, endpoint_full=benchmark.endpoint)
    for r in range(-1,args.trials):
        actual = {}
        before = snapshot()
        for pos, method in enumerate(order(names,r)):
            output, ms = elapsed(lambda:[fn[method](edges,"all") for edges in bins])
            actual[method] = output
            if r>=0:
                times.append(dict(dataset=dataset,experiment="single",trial=r+1,position=pos+1,
                                  method=method,n=1,build_ms=0.,eval_ms=ms,total_ms=ms))
        if r>=0: activity.append(load_interval(before,dataset,"single",r+1))
        assert actual["enumerate"]==actual["endpoint_exact"]==[x[:2] for x in actual["endpoint_full"]]

def batch(dataset, bins):
    ids=sorted({v for b in bins for e in b for v in e})
    rng=random.Random(5917)
    weights=[{v:rng.choice((-1,0,1)) for v in ids} for _ in range(64)]
    expected=None
    for r in range(-1,args.trials):
        before=snapshot()
        for pos,method in enumerate(order(["cache","matrix"],r)):
            if method=="cache":
                obj,build=elapsed(lambda:list(itertools.chain.from_iterable(groups.coefficients(b) for b in bins)))
                evaluate=groups.evaluate
                sizes.setdefault(dataset,{})["cached_terms"]=len(obj)
            else:
                obj,build=elapsed(lambda:groups.compile_matrix(bins))
                evaluate=groups.query_matrix
                sizes.setdefault(dataset,{}).update(diagonal=len(obj[0]),unordered_cross=len(obj[1]))
            cumulative=[]
            output=[]
            start=clock()
            for w in weights:
                output.append(evaluate(obj,w))
                cumulative.append((clock()-start)/1e6)
            if expected is None: expected=output
            assert output==expected
            if r>=0:
                for n,ms in enumerate(cumulative,1):
                    times.append(dict(dataset=dataset,experiment="batch",trial=r+1,position=pos+1,
                                      method=method,n=n,build_ms=build,eval_ms=ms,total_ms=build+ms))
            del obj
        if r>=0: activity.append(load_interval(before,dataset,"batch",r+1))

def sql_study(dataset, records, bins):
    diag,cross=groups.compile_matrix(bins)
    gold={(v,v):k for v,k in diag}
    gold.update({(u,v):k for u,v,k in cross})
    plans={"sql_neighbors":sql_check.DIRECT,"sql_degrees":sql_check.ENDPOINT}
    for r in range(-1,args.trials):
        before=snapshot()
        db=sqlite3.connect(":memory:")
        db.execute("PRAGMA temp_store=MEMORY")
        _,build=elapsed(lambda:sql_check.prepare(db,records))
        for pos,name in enumerate(order(list(plans),r)):
            values,ms=elapsed(lambda:sql_check.query(db,plans[name]))
            assert values==gold
            if r>=0:
                times.append(dict(dataset=dataset,experiment="sql",trial=r+1,position=pos+1,
                                  method=name,n=1,build_ms=build,eval_ms=ms,total_ms=build+ms))
        db.close()
        if r>=0: activity.append(load_interval(before,dataset,"sql",r+1))

if args.trials<7:
    raise ValueError("Use at least seven trials.")
args.out.mkdir(parents=True,exist_ok=True)
if any(args.out.iterdir()):
    raise ValueError("Choose an empty output directory.")
for name,digest in HASHES.items():
    assert hashlib.sha256((args.data/name).read_bytes()).hexdigest()==digest
cpu,allowed,idle_sample=choose_cpu()
cpuinfo=Path("/proc/cpuinfo").read_text()
model=next(line.partition(":")[2].strip() for line in cpuinfo.splitlines() if line.startswith("model name"))
meta=dict(start_utc=utcnow(),model=model,os=platform.system(),release=platform.release(),
          machine=platform.machine(),python=platform.python_version(),sqlite=sqlite3.sqlite_version,
          allowed_cpu_count=len(allowed),affinity=sorted(os.sched_getaffinity(0)),cpu_siblings=siblings(cpu),
          two_second_initial_busy={i:idle_sample[i] for i in siblings(cpu)},seed=5917,
          timed_trials=args.trials,warmup_trials=1,sha256=HASHES,
          code_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in
                       [Path(__file__),*(args.lib/f for f in ("benchmark.py","groups.py","sql_check.py"))]})
times,activity,sizes=[],[],{}
for name,filename in dict(benchmark.SOURCES,MathOverflowA2Q=FIFTH).items():
    print("starting",name,flush=True)
    records,_=benchmark.load(args.data/filename)
    bins=[[(u,v) for _,u,v in g] for _,g in itertools.groupby(records,key=lambda x:int(x[0]//3600))]
    if name in benchmark.SOURCES:
        single(name,bins)
        batch(name,bins)
    sql_study(name,records,bins)
for k in (16,64,256,1024):
    edges=[(i,0) for i in range(1,k+1)]+[(0,i) for i in range(k+1,2*k+1)]
    single(f"Hub_{k}",[edges])
meta["end_utc"]=utcnow()
write_csv("raw_timings.csv",times)
write_csv("scheduler.csv",activity)
(args.out/"environment.json").write_text(json.dumps(meta,indent=2)+"\n")
(args.out/"sizes.json").write_text(json.dumps(sizes,indent=2)+"\n")
print("COMPLETED",len(times),"measurements",flush=True)

