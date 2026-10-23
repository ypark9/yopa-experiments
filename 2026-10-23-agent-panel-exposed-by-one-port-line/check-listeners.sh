#!/usr/bin/env bash
# Read-only. Lists TCP listeners that accept connections from beyond loopback,
# plus Docker published ports that are not bound to 127.0.0.1.
# Exit 1 if anything in the allowlisted port range is exposed.
# usage: check-listeners.sh [port ...]   (no ports = report every port)
set -euo pipefail
ports=" $* "
bad=0
# ss -H -ltn prints: State Recv-Q Send-Q Local:Port Peer:Port
while read -r _ _ _ local _; do
  addr=${local%:*}; port=${local##*:}
  [ "$#" -eq 0 ] || [[ "$ports" == *" $port "* ]] || continue
  case "$addr" in
    127.*|\[::1\]) echo "ok       $local";;
    *)             echo "EXPOSED  $local"; bad=1;;
  esac
done < <(ss -H -ltn)
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  while read -r name mapping; do
    [ -n "$mapping" ] || continue
    for m in ${mapping//,/ }; do
      hp=${m%%->*}; hp=${hp##*:}
      [ "$#" -eq 0 ] || [[ "$ports" == *" $hp "* ]] || continue
      case "$m" in
        127.0.0.1:*|\[::1\]:*) echo "ok       docker $name $m";;
        *-\>*)                 echo "EXPOSED  docker $name $m"; bad=1;;
      esac
    done
  done < <(docker ps --format '{{.Names}} {{.Ports}}')
fi
exit "$bad"
