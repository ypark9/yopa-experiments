#!/usr/bin/env bash
# usage: ci-gate.sh <native-module> [<native-module> ...]   e.g. ci-gate.sh sqlite3
set -euo pipefail
[ "$#" -ge 1 ] || { echo "usage: $0 <native-module>..." >&2; exit 2; }
# read-only preflight: npm ci needs a lockfile; print the npm version in the log
test -f package-lock.json || { echo "no package-lock.json; refusing to install" >&2; exit 1; }
echo "npm $(npm --version)"
npm ci --strict-allow-scripts
node -e 'for (const m of process.argv.slice(1)) require(m); console.log("loaded:", process.argv.slice(1).join(" "))' "$@"
