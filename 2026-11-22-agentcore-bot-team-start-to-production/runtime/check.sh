#!/usr/bin/env bash
# Starts the server on a local port, sends four requests, prints what came back, stops the server.
# Local only: no AWS calls, no cost.
set -euo pipefail
cd "$(dirname "$0")"
PORT=18080
PORT=$PORT node index.js &
pid=$!
trap 'kill $pid 2>/dev/null || true' EXIT
for _ in $(seq 1 20); do curl -s -o /dev/null "http://127.0.0.1:$PORT/ping" && break; sleep 0.2; done

echo '## 1. GET /ping'
curl -s -i "http://127.0.0.1:$PORT/ping" | tr -d '\r' | grep -E '^(HTTP|content-type)|Healthy'
echo
echo '## 2. POST /invocations with the session header and a custom user header'
curl -s -i -N -X POST "http://127.0.0.1:$PORT/invocations" \
  -H 'content-type: application/json' \
  -H 'x-amzn-bedrock-agentcore-runtime-session-id: 3f6c2b1e-0d9a-4c55-9a51-7b2f0e8c1d42' \
  -H 'x-amzn-bedrock-agentcore-runtime-custom-user: user-1' \
  -d '{"prompt":"hello bot team"}' | tr -d '\r' | grep -E '^(HTTP|content-type)|^data:'
echo
echo '## 3. POST /invocations without the session header'
curl -s -i -X POST "http://127.0.0.1:$PORT/invocations" -H 'content-type: application/json' -d '{"prompt":"x"}' \
  | tr -d '\r' | grep -E '^HTTP|error'
echo
echo '## 4. POST /invocations with a body that is not JSON'
curl -s -i -X POST "http://127.0.0.1:$PORT/invocations" \
  -H 'x-amzn-bedrock-agentcore-runtime-session-id: 3f6c2b1e-0d9a-4c55-9a51-7b2f0e8c1d42' -d 'not json' \
  | tr -d '\r' | grep -E '^HTTP|error'
