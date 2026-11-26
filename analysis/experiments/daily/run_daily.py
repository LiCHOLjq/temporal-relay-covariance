"""Sequential timing of all hourly buckets, all daily buckets, and selected real days."""
import argparse
import csv
import hashlib
import itertools
import json
import os
import platform
from fractions import Fraction
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


def make_bins(records,width):
    grouped=itertools.groupby(records,key=lambda e:int(e[0]//width))
    return [(key,[(u,v) for _,u,v in group]) for key,group in grouped]


def measure(name,width,scope,buckets):
    keys=[key for key,_ in buckets]
    bins=[b for _,b in buckets]
    expected=[endpoint_exact(edges,"all") for edges in bins]
    contacts=sum(map(len,bins))
    total_pairs=sum(p for p,_ in expected)
    workloads.append(dict(dataset=name,width_s=width,scope=scope,occupied=len(bins),
                          bucket=keys[0] if len(keys)==1 else "",contacts=contacts,m=total_pairs,
                          pairs_per_contact=total_pairs/contacts,var12=sum(v for _,v in expected)))
    methods=[("enumerate",benchmark.explicit),("endpoint_exact",endpoint_exact)]
    for tick in range(-1,args.trials):
        before=snapshot()
        observed=[]
        for pos,(method,fn) in enumerate(methods[::1 if tick%2==0 else -1],1):
            values,ms=elapsed(lambda:[fn(edges,"all") for edges in bins])
            observed.append(values)
            if tick>=0:
                raw.append(dict(dataset=name,width_s=width,scope=scope,trial=tick+1,
                                position=pos,method=method,elapsed_ms=ms))
        if tick>=0:
            logs.append(load_interval(before,name,f"{scope}_{width}",tick+1))
        assert all(values==expected for values in observed)


def daily_choices(buckets):
    profiles=[(key,edges,endpoint_exact(edges,"all")[0]) for key,edges in buckets]
    pair_max=max(profiles,key=lambda r:(r[2],-r[0]))
    density_max=max(profiles,key=lambda r:(Fraction(r[2],len(r[1])),-r[0]))
    if pair_max[0]==density_max[0]:
        return [("max_pairs_and_density",pair_max[:2])]
    return [("max_pairs",pair_max[:2]),("max_density",density_max[:2])]


if args.trials!=12:
    raise ValueError("The declared protocol uses 12 timed trials.")
args.out.mkdir(parents=True,exist_ok=True)
if any(args.out.iterdir()):
    raise ValueError("Use a fresh empty output directory.")
for name,digest in HASHES.items():
    assert hashlib.sha256((args.data/name).read_bytes()).hexdigest()==digest
cpu,allowed,idle_sample=choose_cpu()
model=next(line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
           if line.startswith("model name"))
meta=dict(start_utc=utcnow(),model=model,os=platform.system(),release=platform.release(),
          machine=platform.machine(),python=platform.python_version(),allowed_cpu_count=len(allowed),
          affinity=sorted(os.sched_getaffinity(0)),cpu_siblings=siblings(cpu),
          two_second_initial_busy={i:idle_sample[i] for i in siblings(cpu)},
          timed_trials=args.trials,warmup_trials=1,sha256=HASHES,
          code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [Path(__file__),args.lib/"benchmark.py"]})
raw,logs,workloads=[],[],[]
for name,filename in dict(benchmark.SOURCES,MathOverflowA2Q=FIFTH).items():
    print("starting",name,flush=True)
    records,_=benchmark.load(args.data/filename)
    for width in (3600,86400):
        buckets=make_bins(records,width)
        measure(name,width,"full",buckets)
    if name in ("CollegeMsg","EmailEU"):
        for label,day in daily_choices(buckets):
            measure(name,86400,label,[day])
meta["end_utc"]=utcnow()
write_csv("raw_timings.csv",raw)
write_csv("workloads.csv",workloads)
write_csv("scheduler.csv",logs)
(args.out/"environment.json").write_text(json.dumps(meta,indent=2)+"\n")
print("COMPLETED",len(raw),"timing records",flush=True)
