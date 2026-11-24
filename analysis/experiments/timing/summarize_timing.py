"""Build timing tables, derived CSVs and the manuscript figure from recorded trials."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median, quantiles

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
NAMES = {"CollegeMsg":"CollegeMsg", "EmailEU":"Email EU",
         "BitcoinOTC":"Bitcoin OTC", "BitcoinAlpha":"Bitcoin Alpha"}
HUBS = ["Hub_16", "Hub_64", "Hub_256", "Hub_1024"]

def qsummary(values):
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    return median(values), q1, q3

def format_time(value):
    return (f"{value:.1f}" if value >= 1 else
            f"{value:.2f}" if value >= 0.1 else f"{value:.3f}")

def cell(summary, formatter=format_time):
    m, a, b = (formatter(v) for v in summary)
    return rf"{m} [{a}, {b}]"

def save_csv(path,rows):
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def sustained(values):
    return max([i for i,well in enumerate(values,1) if not well], default=0)+1

def write_rows(name, lines):
    # Export native LaTeX rows for authors refreshing a table after rerunning.
    target=HERE/"derived"/"tables"
    target.mkdir(parents=True,exist_ok=True)
    rows="\n".join(" & ".join(line)+r"\\" for line in lines)
    (target/name).write_text(rows+"\n",encoding="utf-8")

def summarize(source):
    raw=list(csv.DictReader((source/"raw_timings.csv").open(encoding="utf-8")))
    data=defaultdict(dict)
    for row in raw:
        key=row["experiment"],row["dataset"],row["method"],int(row["n"])
        data[key][int(row["trial"])]=[float(row[column]) for column in ("build_ms","eval_ms","total_ms")]
    def values(exp,ds,method,n,field):
        d=data[exp,ds,method,n]
        return [d[r][field] for r in sorted(d)]
    def summary(exp,ds,method,n,field):
        return qsummary(values(exp,ds,method,n,field))
    (HERE/"derived").mkdir(exist_ok=True)
    statistics=[]
    for (exp,ds,method,n),trials in data.items():
        for ix,phase in enumerate(("build","evaluation","total")):
            m,lo,hi=summary(exp,ds,method,n,ix)
            statistics.append(dict(experiment=exp,dataset=ds,method=method,n=n,phase=phase,
                               trials=len(trials),median_ms=m,q1_ms=lo,q3_ms=hi))
    save_csv(HERE/"derived"/"summaries.csv",statistics)
    kernel=[]
    for ds,title in NAMES.items():
        kernel.append([title]+[cell(summary("single",ds,met,1,2)) for met in ("enumerate","endpoint_exact","endpoint_full")])
    write_rows("single.tex",kernel)

    sizes=json.loads((source/"sizes.json").read_text())
    batch=[]
    support=[]
    crossover=[]
    ratios={}
    for ds,title in NAMES.items():
        ratio_series=[]; paired_series=[]
        for n in range(1,65):
            cache=values("batch",ds,"cache",n,2)
            matrix=values("batch",ds,"matrix",n,2)
            ratio_series.append(median(cache)/median(matrix))
            paired_series.append([t/u for t,u in zip(cache,matrix)])
        population=sustained(x>1 for x in ratio_series)
        trials=[sustained(row[i]>1 for row in paired_series) for i in range(len(cache))]
        q1,_,q3=quantiles(paired_series[-1], n=4,method="inclusive")
        ratios[ds]=(ratio_series,[qsummary(x)[1:] for x in paired_series])
        scan=[summary("batch",ds,met,64,1)[0]/64 for met in ("cache","matrix")]
        crossover.append(dict(dataset=ds,median_curve_sustained=population,min_trial=min(trials),max_trial=max(trials),
            paired_crossovers=" ".join(map(str,trials)),ratio_of_medians_64=ratio_series[-1],
            paired_q1_64=q1,paired_q3_64=q3,paired_matrix_wins_64=sum(x>1 for x in paired_series[-1]),
            cache_ms_per_query_64=scan[0],matrix_ms_per_query_64=scan[1]))
        sz=sizes[ds]
        support.append([title,f'{sz["cached_terms"]:,}',f'{sz["diagonal"]:,}',f'{sz["unordered_cross"]:,}',
                        f"{population} [{min(trials)}, {max(trials)}]",
                        cell((ratio_series[-1],q1,q3),lambda v:f"{v:.2f}")])
        for n in (1,8,64):
            for met in ("cache","matrix"):
                batch.append([title,str(n),met.capitalize()]+[cell(summary("batch",ds,met,n,i)) for i in range(3)])
    save_csv(HERE/"derived"/"crossover.csv",crossover)
    write_rows("batch.tex",batch)
    write_rows("support.tex",support)

    sql=[]
    for ds,title in dict(NAMES,MathOverflowA2Q="MathOverflow").items():
        sql.append([title,cell(summary("sql",ds,"sql_neighbors",1,0)),
                    cell(summary("sql",ds,"sql_neighbors",1,1)),cell(summary("sql",ds,"sql_degrees",1,1))])
    write_rows("sql.tex",sql)
    hub=[]
    for name in HUBS:
        k=int(name.partition("_")[2])
        hub.append([f"{k:,}",f"{k*k:,}"]+[cell(summary("single",name,m,1,1)) for m in
                   ("enumerate","endpoint_exact","endpoint_full")])
    write_rows("hub.tex",hub)
    legacy=json.loads((PROJECT.parent/"artifact"/"experiments"/"results"/"timings.json").read_text())
    write_rows("legacy.tex",[[title]+[cell(qsummary([1000*x for x in legacy[ds][method]]))
                                   for method in ("explicit","endpoint")] for ds,title in NAMES.items()])
    previous=json.loads((PROJECT.parent/"artifact"/"experiments"/"results"/"groups.json").read_text())
    old_rows=[]
    old_csv=[]
    for ds,title in NAMES.items():
        samples=[r for r in previous[ds]["measurements"] if r["method"]=="matrix" and r["n"]==64]
        old_rows.append([title]+[cell(qsummary([1000*r[field] for r in samples]))
                               for field in ("build","query","total")])
        for r in samples:
            old_csv.append(dict(dataset=ds,trial=r["round"]+1,
                                build_ms=1000*r["build"],eval_ms=1000*r["query"],total_ms=1000*r["total"]))
    write_rows("legacy_matrix64.tex",old_rows)
    save_csv(HERE/"derived"/"legacy_matrix64.csv",old_csv)
    active=list(csv.DictReader((source/"scheduler.csv").open(encoding="utf-8")))
    wait=sum(float(r["runnable_wait_ms"]) for r in active)
    wall=sum(float(r["wall_s"]) for r in active)
    sib=[float(r["sibling_max_busy"]) for r in active if r["sibling_max_busy"]]
    telemetry=dict(intervals=len(active),observed_wall_s=wall,runnable_wait_ms=wait,
                   wait_fraction=wait/(1000*wall),sibling_busy_median=median(sib) if sib else None,
                   sibling_busy_max=max(sib) if sib else None)
    (HERE/"derived"/"scheduler_summary.json").write_text(json.dumps(telemetry,indent=2)+"\n")
    return ratios,summary

def plot(source):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import NullLocator
    ratios,summary=summarize(source)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8.7,"pdf.fonttype":42,
                        "axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#24384a",
                        "axes.labelcolor":"#24384a","text.color":"#24384a","axes.linewidth":0.7})
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.6,3.10))
    fig.subplots_adjust(left=.085,right=.98,bottom=.31,top=.85,wspace=.36)
    ax.set_title("(a) Single query on a synthetic hub",loc="left",fontsize=9.7,weight="bold")
    for key, color, sym, label in [("enumerate","#ad592b","s","Enumerate pairs"),
                                   ("endpoint_exact","#286486","o","Endpoint, exact only")]:
        sq=[summary("single",ds,key,1,1) for ds in HUBS]
        x=[int(k.partition("_")[2]) for k in HUBS]
        ax.errorbar(x,[r[0] for r in sq],yerr=[[r[0]-r[1] for r in sq],[r[2]-r[0] for r in sq]],
                    color=color,marker=sym,mfc="white",capsize=2.5,linewidth=1.3,label=label)
    ax.set_xscale("log",base=2);ax.set_yscale("log")
    ax.set(xticks=x,xticklabels=[str(i) for i in x],xlabel="Spokes per direction",ylabel="Time (ms)",
           yticks=[.01,.1,1,10,100],yticklabels=["0.01","0.1","1","10","100"])
    ax.yaxis.set_minor_locator(NullLocator());ax.grid(axis="y",lw=.5,color="#dce2e5")
    ax.legend(frameon=False,loc="upper center",bbox_to_anchor=(.49,-.27),ncol=1,fontsize=8,
              borderaxespad=0,handlelength=1.5)
    bx.set_title("(b) Repeated queries on hourly bins",loc="left",fontsize=9.7,weight="bold")
    for (ds,name),color,style,sym in zip(NAMES.items(),["#286486","#ad592b","#28796c","#71548a"],
                                       ["-","--","-.",":"],["o","s","^","D"]):
        curve,uncertainty=ratios[ds]
        x=list(range(1,65))
        bx.plot(x,curve,linestyle=style,linewidth=1.3,marker=sym,markersize=3.3,mfc="white",
                markevery=[0,3,7,15,31,63],color=color,label=name)
        bx.fill_between(x,[w[0] for w in uncertainty],[w[1] for w in uncertainty],alpha=.11,
                        color=color,lw=0)
    bx.set_xscale("log",base=2);bx.set(xticks=[1,2,4,8,16,32,64],xticklabels=["1","2","4","8","16","32","64"],
               xlabel="Queries per batch",ylabel="Cache time / matrix time")
    bx.axhline(1,color="#667884",linestyle="--",zorder=0,linewidth=.8)
    bx.legend(frameon=False,loc="upper center",bbox_to_anchor=(.5,-.27),ncol=2,columnspacing=1.1,
              fontsize=8,borderaxespad=0,handlelength=1.5)
    fig.savefig(PROJECT/"figures"/"query_costs.pdf",metadata={"CreationDate":None,"ModDate":None})
    plt.close(fig)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=HERE/"results")
    plot(p.parse_args().source)
