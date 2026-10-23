import json, sys
from anthropic import transform_schema
from schemas import CASES
from lint import lint
rows = []
for M in CASES:
    raw = M.model_json_schema()
    tr = transform_schema(M)
    rows.append({"model": M.__name__, "raw_problems": lint(raw), "transformed_problems": lint(tr),
                 "raw": raw, "transformed": tr})
for r in rows:
    print(f"{r['model']:14} raw: {r['raw_problems'] or 'OK'}\n{'':14} sdk: {r['transformed_problems'] or 'OK'}")
json.dump(rows, open("result-lint.json", "w"), indent=1)
