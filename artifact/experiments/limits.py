"""Verify tight examples for all-relay approximation ratios."""
import itertools
import json
from pathlib import Path

from benchmark import endpoint, literal


def main():
    rows=[]
    for k in [1,2,3,4,8,16,32,64,128]:
        for family in ('broadcast','cycle'):
            edges=([(0,1)] + [(1,i) for i in range(2,k+2)] if family=='broadcast'
                   else [(0,1),(1,2),(2,0)]*k)
            m,var,iid,diag=endpoint(edges,'all')
            if family=='broadcast':
                assert m==k and var==k*(k+2)
            else:
                assert m==3*k*k and var==m and diag==m*(1+2*k)
            if len(edges)<=7:
                counts=[literal(p,'all') for p in itertools.permutations(edges)]
                n=len(counts)
                assert 12*(n*sum(x*x for x in counts)-sum(counts)**2)==n*n*var
            rows.append(dict(family=family,k=k,m=m,var12=var,iid12=iid,diag12=diag))
    Path('results/limits.json').write_text(json.dumps(rows,indent=2)+'\n')


if __name__=='__main__':
    main()
