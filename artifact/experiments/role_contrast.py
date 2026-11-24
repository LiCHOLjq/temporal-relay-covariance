"""Secondary case study on five traces. Select roles before the evaluation hours."""
from collections import Counter
import itertools
import json
from pathlib import Path

from benchmark import SOURCES, load
from groups import compile_matrix, query_matrix


def main():
    result={}
    for name,file in dict(SOURCES,MathOverflowA2Q='sx-mathoverflow-a2q.txt.gz').items():
        events,_=load(Path('data')/file)
        split=int(events[len(events)//2][0]//3600)
        earlier=[(u,v) for t,u,v in events if int(t//3600)<split]
        later=[e for e in events if int(e[0]//3600)>=split]
        balance=Counter()
        for u,v in earlier:
            balance[u]+=1
            balance[v]-=1
        ids={k for _,u,v in later for k in (u,v)}
        sign={k:(balance[k]>0)-(balance[k]<0) for k in ids}
        send={k:int(s>0) for k,s in sign.items()}
        receive={k:int(s<0) for k,s in sign.items()}
        buckets=[[(u,v) for _,u,v in group] for _,group in
                 itertools.groupby(later,key=lambda e:int(e[0]//3600))]
        matrix=compile_matrix(buckets)
        vs,vr,contrast=[query_matrix(matrix,w) for w in (send,receive,sign)]
        assert contrast>=vs+vr
        result[name]=dict(cutoff_hour=split,history_events=len(earlier),evaluation_events=len(later),
                          roles=dict(Counter(sign.values())),sender_var12=vs,
                          receiver_var12=vr,contrast_var12=contrast,
                          group_cov12=(vs+vr-contrast)//2)
    Path('results/role_contrast.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
