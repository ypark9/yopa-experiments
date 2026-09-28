#!/bin/bash
# usage: AWS_PROFILE=<your-profile> ./go.sh N OUTNAME [conditions]
# conditions: stale,fresh (default) or fee
set -euo pipefail
cd "$(dirname "$0")"
aws sts get-caller-identity --query Arn --output text >/dev/null
python -u run.py --n "$1" --out "results/$2.jsonl" --conditions "${3:-stale,fresh}"
