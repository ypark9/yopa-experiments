#!/usr/bin/env bash
# Runs every case in a fresh temp project and writes results/*.log + results/matrix.tsv.
# Needs: node 24 on PATH, npm 11.21.1 / 12.0.0 / 12.2.1 prefixes (see README), g++/make for node-gyp.
# Network: fixture cases use only the 127.0.0.1 registry; the "real" cases download public
# packages from registry.npmjs.org (and, after approval, prebuilt binaries from GitHub). Nothing is published.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
res="$here/results"; mkdir -p "$res"; : > "$res/matrix.tsv"
NPM11="${NPM11:?set NPM11 to npm 11.21.1 bin}"; NPM12="${NPM12:?set NPM12 to npm 12.2.1 bin}"; NPM1200="${NPM1200:?set NPM1200 to npm 12.0.0 bin}"
REG="http://127.0.0.1:4873/"
work="$(mktemp -d)"; trap 'rm -rf "$work"; kill $regpid 2>/dev/null || true' EXIT
node "$here/scripts/registry_server.mjs" "$here/registry" 4873 >/dev/null 2>&1 & regpid=$!
for i in $(seq 1 50); do curl -fs "$REG/nativedemo" >/dev/null && break; sleep 0.1; done

newproj() { # dir deps-json
  rm -rf "$1"; mkdir -p "$1"
  printf '{"name":"app","version":"1.0.0","private":true,"dependencies":%s}\n' "$2" > "$1/package.json"
}
smoke_fixture() { node -e '
  const r = {};
  try { r.native = require("nativedemo").hello(); } catch (e) { r.native = "FAIL: " + e.message.split("\n")[0]; }
  try { r.post = require("postdemo"); } catch (e) { r.post = "FAIL: " + e.message.split("\n")[0]; }
  console.log(JSON.stringify(r));'; }
# record case npm-version command exit warn-lines smoke
record() { printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$@" >> "$res/matrix.tsv"; }
run() { # case-id logfile cmd...  -> sets RC
  local id="$1" log="$res/$1.log"; shift
  { echo "\$ $*"; } > "$log"
  set +e; "$@" >> "$log" 2>&1; RC=$?; set -e
  echo "[exit $RC]" >> "$log"
}
F="--registry $REG --no-audit --no-fund"
DEPS='{"nativedemo":"1.0.0","postdemo":"1.0.0"}'

# 1. npm 11 baseline
p="$work/c01"; newproj "$p" "$DEPS"; cd "$p"
run c01-npm11-install "$NPM11" install $F --cache "$work/cache11"
record c01 "$("$NPM11" -v)" "npm install" "$RC" "$(grep -c 'warn' "$res/c01-npm11-install.log" || true)" "$(smoke_fixture)"
cp package-lock.json "$work/lock-from-npm11.json"

# 2. npm 12 default install
p="$work/c02"; newproj "$p" "$DEPS"; cd "$p"
run c02-npm12-install "$NPM12" install $F --cache "$work/cache12"
record c02 "$("$NPM12" -v)" "npm install" "$RC" "$(grep -c 'install-scripts' "$res/c02-npm12-install.log" || true)" "$(smoke_fixture)"

# 3. npm 12 ci --silent using the lockfile npm 11 wrote (typical CI after a toolchain bump)
p="$work/c03"; newproj "$p" "$DEPS"; cd "$p"; cp "$work/lock-from-npm11.json" package-lock.json
run c03-npm12-ci-silent "$NPM12" ci --silent $F --cache "$work/cache12"
record c03 "$("$NPM12" -v)" "npm ci --silent (npm 11 lockfile)" "$RC" "$(grep -c 'install-scripts' "$res/c03-npm12-ci-silent.log" || true)" "$(smoke_fixture)"

# 4. read-only detection: does 'install-scripts ls' fail when something is pending?
run c04-npm12-ls "$NPM12" install-scripts ls $F
record c04 "$("$NPM12" -v)" "npm install-scripts ls (2 pending)" "$RC" "-" "-"
grep -o '"hasInstallScript": true' package-lock.json | wc -l > "$res/c04-lockfile-hasInstallScript-count.txt"

# 5. strict mode
p="$work/c05"; newproj "$p" "$DEPS"; cd "$p"
run c05-npm12-strict "$NPM12" install --strict-allow-scripts $F --cache "$work/cache12"
record c05 "$("$NPM12" -v)" "npm install --strict-allow-scripts" "$RC" "-" "$( [ -d node_modules ] && smoke_fixture || echo '{"node_modules":"absent"}')"

# 6. strict mode via .npmrc on 12.0.0 (version scope check)
p="$work/c06"; newproj "$p" "$DEPS"; cd "$p"; echo "strict-allow-scripts=true" > .npmrc
run c06-npm1200-strict-npmrc "$NPM1200" install $F --cache "$work/cache1200"
record c06 "$("$NPM1200" -v)" "npm install (.npmrc strict-allow-scripts=true)" "$RC" "-" "$( [ -d node_modules ] && smoke_fixture || echo '{"node_modules":"absent"}')"

# 7. fix: approve (pinned) + rebuild
p="$work/c07"; newproj "$p" "$DEPS"; cd "$p"
"$NPM12" install $F --cache "$work/cache12" >/dev/null 2>&1
run c07a-npm12-approve "$NPM12" install-scripts approve nativedemo postdemo $F
cp package.json "$res/c07-package.json-after-approve.json"
run c07b-npm12-rebuild "$NPM12" rebuild $F
record c07 "$("$NPM12" -v)" "install-scripts approve + rebuild" "$RC" "-" "$(smoke_fixture)"

# 8. fresh clone of the approved project: npm ci runs approved scripts
p8="$work/c08"; rm -rf "$p8"; mkdir -p "$p8"; cp package.json package-lock.json "$p8/"; cd "$p8"
run c08-npm12-ci-approved "$NPM12" ci $F --cache "$work/cache12"
record c08 "$("$NPM12" -v)" "npm ci (allowScripts committed)" "$RC" "$(grep -c 'install-scripts' "$res/c08-npm12-ci-approved.log" || true)" "$(smoke_fixture)"

# 9. dependency bump after a pinned approval
run c09-npm12-bump "$NPM12" install nativedemo@1.0.1 $F --cache "$work/cache12"
record c09 "$("$NPM12" -v)" "npm install nativedemo@1.0.1 (approval pinned to 1.0.0)" "$RC" "$(grep -c 'install-scripts' "$res/c09-npm12-bump.log" || true)" "$(smoke_fixture)"
cp package.json "$res/c09-package.json-after-bump.json"

# 10-13. real public packages, npm 11 vs npm 12 (default) -> does require() work?
for pkg in sqlite3@6.0.1 better-sqlite3@13.0.3 esbuild@0.28.2 bcrypt@6.0.0; do
  name="${pkg%@*}"
  for v in 11 12; do
    bin="NPM$v"; p="$work/real-$name-$v"; newproj "$p" "{\"$name\":\"${pkg##*@}\"}"; cd "$p"
    id="real-$name-npm$v"
    run "$id" "${!bin}" install --no-audit --no-fund --cache "$work/cache-real$v"
    smoke="$(node -e '
      const n=process.argv[1]; let r;
      try { const m=require(n);
        if (n==="sqlite3") { new m.Database(":memory:").close(); }
        if (n==="better-sqlite3") { new m(":memory:").close(); }
        if (n==="esbuild") { m.transformSync("let a=1"); }
        if (n==="bcrypt") { m.hashSync("x",4); }
        r="ok"; } catch(e){ r="FAIL: "+e.message.split("\n")[0].slice(0,160); }
      console.log(r)' "$name" 2>&1)"
    record "$id" "$("${!bin}" -v)" "npm install $pkg" "$RC" "$(grep -c 'install-scripts' "$res/$id.log" || true)" "$smoke"
  done
done

# 14. real sqlite3 fix path on npm 12
cd "$work/real-sqlite3-12"
run real-sqlite3-npm12-approve "$NPM12" install-scripts approve sqlite3
run real-sqlite3-npm12-rebuild "$NPM12" rebuild
smoke="$(node -e 'try{const s=require("sqlite3");new s.Database(":memory:").close();console.log("ok")}catch(e){console.log("FAIL: "+e.message.split("\n")[0])}')"
record real-sqlite3-npm12-fixed "$("$NPM12" -v)" "install-scripts approve sqlite3 + rebuild" "$RC" "-" "$smoke"

# scrub local paths from logs so they are safe to publish
for f in "$res"/*.log "$res"/matrix.tsv; do
  sed -i -E "s#$NPM11#npm#g; s#$NPM12#npm#g; s#$NPM1200#npm#g; s#$work#\$TMP#g; s#/tmp/tmp\.[A-Za-z0-9]+#\$TMP#g" "$f"
done
{ echo "node $(node -v)"; echo "npm11 $("$NPM11" -v)"; echo "npm12.0 $("$NPM1200" -v)"; echo "npm12 $("$NPM12" -v)";
  echo "$(g++ --version | head -1)"; echo "$(make --version | head -1)"; echo "os $(uname -sm)"; } > "$res/environment.txt"
cat "$res/matrix.tsv"
