#!/usr/bin/env bash
# Free, local-only checks. Needs Java 17+ and DynamoDB Local 3.3.2 (unzipped into ./ddblocal).
set -eu
cd "$(dirname "$0")"
python3 simulate.py > results/result-simulation.json                  # pure model, no network
python3 oldsdk.py                                                     # Stubber, no network
(cd ddblocal && java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar -inMemory -port 8765) &
DDB=$!; trap 'kill $DDB 2>/dev/null || true' EXIT
sleep 3
DDB_ENDPOINT=http://127.0.0.1:8765 python3 probe.py > results/result-botocore-$(python3 -c 'import botocore;print(botocore.__version__)').json
