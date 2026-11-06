#!/usr/bin/env bash
# Run agentcore migrate against local fixtures. No AWS calls.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURES="$ROOT/fixtures"
OUT="$ROOT/results"
mkdir -p "$OUT/plans" "$OUT/help"

unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE AWS_DEFAULT_REGION AWS_REGION || true
export AWS_EC2_METADATA_DISABLED=true
export AWS_CONFIG_FILE=/dev/null
export AWS_SHARED_CREDENTIALS_FILE=/dev/null

# Install CLI 1.0.1 into a local prefix (or reuse AGENTCORE_BIN)
PREFIX="$ROOT/.cli-prefix"
mkdir -p "$PREFIX"
if [[ -z "${AGENTCORE_BIN:-}" ]]; then
  if [[ ! -x "$PREFIX/node_modules/@aws/agentcore/dist/index.js" ]]; then
    npm pack @aws/agentcore@1.0.1 --pack-destination "$PREFIX" >/dev/null
    (cd "$PREFIX" && npm install --ignore-scripts --no-save ./aws-agentcore-1.0.1.tgz >/dev/null)
  fi
  AGENTCORE_BIN="$PREFIX/node_modules/@aws/agentcore/dist/index.js"
fi

"$AGENTCORE_BIN" --version | tee "$OUT/help/version.txt"
"$AGENTCORE_BIN" migrate --help >"$OUT/help/migrate.txt" 2>&1 || true
"$AGENTCORE_BIN" create --help >"$OUT/help/create.txt" 2>&1 || true
"$AGENTCORE_BIN" status --help >"$OUT/help/status.txt" 2>&1 || true
"$AGENTCORE_BIN" add --help >"$OUT/help/add.txt" 2>&1 || true
"$AGENTCORE_BIN" add harness --help >"$OUT/help/add-harness.txt" 2>&1 || true
"$AGENTCORE_BIN" add runtime --help >"$OUT/help/add-runtime.txt" 2>&1 || true
set +e
"$AGENTCORE_BIN" add knowledge-base >"$OUT/help/add-knowledge-base.txt" 2>&1
"$AGENTCORE_BIN" add knowledge-base --help >"$OUT/help/add-knowledge-base-help.txt" 2>&1
set -e

printf 'fixture\texit\tstdout_stderr\n' >"$OUT/summary.tsv"

run_one() {
  local name="$1"
  local dir="$FIXTURES/$name"
  # ready_local_minimal needs a git repo; recreate if missing
  if [[ "$name" == "ready_local_minimal" && ! -d "$dir/.git" ]]; then
    (
      cd "$dir"
      git init -q
      git config user.email 'exp@example.com'
      git config user.name 'exp'
      git add -A
      git commit -q -m 'fixture'
    )
  fi
  (
    cd "$dir"
    set +e
    out=$("$AGENTCORE_BIN" migrate 2>&1)
    ec=$?
    set -e
    printf '%s\n' "$out" >"$OUT/${name}.txt"
    oneline=$(printf '%s' "$out" | tr '\n' ' ' | tr '\t' ' ')
    printf '%s\t%s\t%s\n' "$name" "$ec" "$oneline" >>"$OUT/summary.tsv"
    if [[ -d agentcore/.cli/migrate ]]; then
      mkdir -p "$OUT/plans/$name"
      cp -a agentcore/.cli/migrate/. "$OUT/plans/$name/" || true
    fi
    echo "$name exit=$ec"
  )
}

for d in "$FIXTURES"/*; do
  [[ -d "$d" ]] || continue
  run_one "$(basename "$d")"
done

echo "Wrote $OUT/summary.tsv"
