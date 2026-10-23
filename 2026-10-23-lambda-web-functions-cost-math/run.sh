#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
node sse_cpu.mjs upstream > .port & UP=$!
trap 'kill $UP 2>/dev/null || true' EXIT
for i in $(seq 50); do [ -s .port ] && break; sleep 0.1; done
node --version
node sse_cpu.mjs "$(cat .port)" | tee results/result-sse-cpu.jsonl
