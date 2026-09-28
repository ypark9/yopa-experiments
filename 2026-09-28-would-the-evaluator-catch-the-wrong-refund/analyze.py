import json, sys, collections
rows=[json.loads(l) for f in sys.argv[1:] for l in open(f)]
by=collections.defaultdict(lambda: collections.defaultdict(list)); dollars=collections.defaultdict(collections.Counter); errs=0
for r in rows:
    dollars[r['cond']][",".join(r['dollars'])]+=1
    for k,v in r['scores'].items():
        for x in v:
            if x.get('value') is None: errs+=1; continue
            by[r['cond']][k].append(x['value'])
print("answers:", {c:dict(v) for c,v in dollars.items()}); print("errors:",errs)
keys=["correctness_no_gt","faithfulness","helpfulness","goal_no_gt","correctness_gt","goal_assert"]
print(f"{'evaluator':20}"+"".join(f"{c:>22}" for c in by))
for k in keys:
    line=f"{k:20}"
    for c in by:
        v=by[c][k]; p=sum(1 for x in v if x>=0.7)
        line+=f"{f'mean {sum(v)/len(v):.2f} pass {p}/{len(v)}':>22}"
    print(line)
tok=sum(x['tokenUsage']['totalTokens'] for r in rows for v in r['scores'].values() for x in v if x.get('tokenUsage'))
print("judge tokens:",tok, "evaluate calls:", sum(len(r['scores']) for r in rows))
