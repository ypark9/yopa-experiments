#!/usr/bin/env bash
# Pack the stand-in packages into ./registry (local only, no network).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
out="$here/registry"
rm -rf "$out" && mkdir -p "$out"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
pack() { # dir version
  local src="$1" ver="$2" w="$tmp/$(basename "$1")-$2"
  cp -r "$src" "$w"
  node -e 'const f=process.argv[1],v=process.argv[2];const p=require(f);p.version=v;require("fs").writeFileSync(f,JSON.stringify(p,null,2)+"\n")' "$w/package.json" "$ver"
  (cd "$w" && npm pack --silent --pack-destination "$out" >/dev/null)
}
pack "$here/fixtures/nativedemo" 1.0.0
pack "$here/fixtures/nativedemo" 1.0.1
pack "$here/fixtures/postdemo" 1.0.0
ls "$out"
