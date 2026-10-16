#!/bin/sh
# Read-only self-test of a Node --permission launch line. Writes nothing, changes nothing.
set -eu
NODE=${NODE:-node}
command -v "$NODE" >/dev/null 2>&1 || { echo "FAIL: $NODE not found" >&2; exit 1; }

# 1. Does this Node build have a network permission at all? (Node 22 and 24 do not.)
if ! "$NODE" --help | grep -q -- '--allow-net'; then
  echo "FAIL: $("$NODE" --version) has no --allow-net, so --permission does not block network" >&2
  exit 1
fi

# 2. Run the exact launch line once with a tiny script: it must be denied the network
#    (not just refused by a closed port) and must see an empty environment.
SELFTEST='fetch("http://127.0.0.1:65535").then(
  () => process.exit(2),
  (e) => process.exit(e.cause && e.cause.code === "ERR_ACCESS_DENIED"
    ? (Object.keys(process.env).length <= 1 ? 0 : 3) : 4))'
status=0
printf '%s' "$SELFTEST" | env -i PATH=/usr/bin:/bin "$NODE" --permission - || status=$?
case $status in
  0) echo "OK: network denied, environment empty (PATH only)" ;;
  3) echo "FAIL: network denied but environment variables are visible" >&2; exit 1 ;;
  *) echo "FAIL: network was not denied by the permission model (exit $status)" >&2; exit 1 ;;
esac
