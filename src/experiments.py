"""Repeat mixed-error experiments and isolate error families at scaled probabilities.

30 independent mixed-data seeds; isolated scenarios share truth seed 42 and
corruption seed 10042. Multipliers scale baseline probabilities, not a uniform
percentage of erroneous records. Summaries include bootstrap intervals for means.
"""
import argparse
import random
import sqlite3
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from checks import load, run_checks
from clean import clean
from evaluate import accuracy, kpis
from generate_data import make_truth, corrupt, save

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ['duplicate','missing','outdated','inconsistent_code','inconsistent_format',
            'invalid','orphan_fk','inconsistent_temporal']



def one(seed, family, scale):
    truth=dict(zip(('students','courses','enrolments'),make_truth(random.Random(seed))))
    s,c,e,log=corrupt(*truth.values(),random.Random(seed+10000),scale=scale,
                       error_types=None if family=='mixed' else {family})
    with tempfile.TemporaryDirectory() as d:
        source,target=Path(d)/'dirty.sqlite',Path(d)/'cleaned.sqlite'
        save(source,students=s,courses=c,enrolments=e)
        clean(source,target)
        dirty,cleaned=load(source),load(target)
        with sqlite3.connect(target) as con:
            queued=con.execute('select count(*) from review_queue').fetchone()[0]
        kt=kpis(truth)
        rows=[]
        for stage,db in [('dirty',dirty),('cleaned',cleaned)]:
            for name,value in kpis(db).items():
                rows.append({'seed':seed,'family':family,'multiplier':scale,'stage':stage,
                             'metric':name,'value':value,'truth':kt[name],
                             'absolute_error':abs(value-kt[name]),
                             'relative_error':abs(value-kt[name])/abs(kt[name]) if kt[name] else float('nan')})
        acc=[]
        for stage,db in [('dirty',dirty),('cleaned',cleaned)]:
            for item in accuracy(truth,db).to_dict('records'):
                acc.append(dict(seed=seed,family=family,multiplier=scale,stage=stage,**item))
        return rows,acc,{'seed':seed,'family':family,'multiplier':scale,
                         'logged_injections':len(log),'review_queue_records':queued}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',type=int,default=30)
    args=parser.parse_args()
    if args.seeds<2:
        parser.error('--seeds must be at least 2')
    scenarios=[(seed,'mixed',1.0) for seed in range(42,42+args.seeds)]
    scenarios += [(42,family,scale) for family in FAMILIES for scale in (.25,1.0,2.0)]
    scenarios += [(42,'mixed',0.0)]
    rows,acc,meta=[],[],[]
    for i,(seed,family,scale) in enumerate(scenarios,1):
        a,b,c=one(seed,family,scale)
        rows.extend(a);acc.extend(b);meta.append(c)
        print(f'{i}/{len(scenarios)} seed={seed} family={family} multiplier={scale}',flush=True)
    res=ROOT/'results';res.mkdir(exist_ok=True)
    frame=pd.DataFrame(rows)
    frame.to_csv(res/'experiment_kpis.csv',index=False)
    pd.DataFrame(acc).to_csv(res/'experiment_accuracy.csv',index=False)
    pd.DataFrame(meta).to_csv(res/'experiment_scenarios.csv',index=False)
    summary=[]
    rng=np.random.default_rng(42)
    for (stage,metric),group in frame[(frame.family=='mixed') & (frame.multiplier==1)].groupby(['stage','metric']):
        values=group.relative_error.to_numpy()
        means=rng.choice(values,size=(2000,len(values)),replace=True).mean(axis=1)
        lo,hi=np.quantile(means,[.025,.975])
        summary.append({'stage':stage,'metric':metric,'runs':len(values),
                        'mean_relative_error':values.mean(),'ci95_low':lo,'ci95_high':hi})
    pd.DataFrame(summary).to_csv(res/'experiment_summary.csv',index=False)

if __name__=='__main__':
    main()
