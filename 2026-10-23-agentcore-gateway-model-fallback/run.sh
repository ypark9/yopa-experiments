#!/usr/bin/env bash
# Free, local, no network. Python 3.10+ stdlib for the mock; botocore>=1.43.118 for the shape check.
set -euo pipefail
cd "$(dirname "$0")"
python3 gateway_mock.py results/result-mock.json
python3 validate_shapes.py > results/result-validate-shapes.json
