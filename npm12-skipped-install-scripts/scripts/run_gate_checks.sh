#!/usr/bin/env bash
# Extra cases for the CI gate the post recommends. Same local registry as run_matrix.sh.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; res="$here/results"
NPM11="${NPM11:?}"; NPM12="${NPM12:?}"
REG="http://127.0.0.1:4873/"; F="--registry $REG --no-audit --no-fund"
work="$(mktemp -d)"; trap 'rm -rf "$work"; kill $regpid 2>/dev/null || true' EXIT
node "$here/scripts/registry_server.mjs" "$here/registry" 4873 >/dev/null 2>&1 & regpid=$!
for i in $(seq 1 50); do curl -fs "$REG/nativedemo" >/dev/null && break; sleep 0.1; done
: > "$res/gate.tsv"
DEPS='{"nativedemo":"1.0.0","postdemo":"1.0.0"}'
mk() { rm -rf "$1"; mkdir -p "$1"; printf '{"name":"app","version":"1.0.0","private":true,"dependencies":%s%s}\n' "$DEPS" "${2:-}" > "$1/package.json"; }
gate() { # runs scripts/ci-gate.sh (the exact snippet from the post) with npm $1 first on PATH
  local npmbin="$1"; mkdir -p "$work/bin-$$"; ln -sf "$npmbin" "$work/bin-$$/npm"
  PATH="$work/bin-$$:$PATH" npm_config_registry="$REG" npm_config_cache="$work/cache" npm_config_audit=false npm_config_fund=false \
    "$here/scripts/ci-gate.sh" nativedemo postdemo
}
run() { local id="$1"; shift; local log="$res/$id.log"; echo "\$ $*" > "$log"; set +e; "$@" >> "$log" 2>&1; RC=$?; set -e; echo "[exit $RC]" >> "$log"; printf '%s\t%s\n' "$id" "$RC" >> "$res/gate.tsv"; }

# lockfile without approvals
mk "$work/base"; (cd "$work/base" && "$NPM12" install $F --cache "$work/cache" >/dev/null 2>&1)
# g1: npm 12.2.1, unapproved lockfile -> gate must fail
mk "$work/g1"; cp "$work/base/package-lock.json" "$work/g1/"; cd "$work/g1"; run g1-gate-unapproved gate "$NPM12"
# g2: npm 12.2.1, approvals committed -> gate must pass
mk "$work/g2" ',"allowScripts":{"nativedemo@1.0.0":true,"postdemo@1.0.0":true}'; cp "$work/base/package-lock.json" "$work/g2/"; cd "$work/g2"; run g2-gate-approved gate "$NPM12"
# g3: npm 12.2.1, strict set in project .npmrc instead of the flag
mk "$work/g3"; cp "$work/base/package-lock.json" "$work/g3/"; cd "$work/g3"; echo "strict-allow-scripts=true" > .npmrc
run g3-npmrc-strict-12.2.1 "$NPM12" ci $F --cache "$work/cache"
# g4: npm 11.21.1 given the same flag (team still on npm 11 in CI)
mk "$work/g4"; cp "$work/base/package-lock.json" "$work/g4/"; cd "$work/g4"; run g4-npm11-strict-flag "$NPM11" ci --strict-allow-scripts $F --cache "$work/cache"
# g7: preflight refuses a checkout with no lockfile
mk "$work/g7"; cd "$work/g7"; run g7-gate-no-lockfile gate "$NPM12"
# g5: read-only listing before any install (fresh checkout, no node_modules)
mk "$work/g5"; cp "$work/base/package-lock.json" "$work/g5/"; cd "$work/g5"; run g5-ls-before-install "$NPM12" install-scripts ls $F
# g6: one approved, one explicitly denied, strict on -> install passes, denied package stays unbuilt
mk "$work/g6" ',"allowScripts":{"nativedemo@1.0.0":true,"postdemo":false}'; cp "$work/base/package-lock.json" "$work/g6/"; cd "$work/g6"
run g6-strict-with-deny "$NPM12" ci --strict-allow-scripts $F --cache "$work/cache"
node -e 'for (const m of ["nativedemo","postdemo"]) { try { require(m); console.log(m, "ok") } catch (e) { console.log(m, "FAIL:", e.message.split("\n")[0]) } }' >> "$res/g6-strict-with-deny.log" 2>&1
for f in "$res"/g*.log "$res/gate.tsv"; do sed -i -E "s#$NPM11#npm#g; s#$NPM12#npm#g; s#$work#\$TMP#g; s#/tmp/tmp\.[A-Za-z0-9]+#\$TMP#g" "$f"; done
cat "$res/gate.tsv"
