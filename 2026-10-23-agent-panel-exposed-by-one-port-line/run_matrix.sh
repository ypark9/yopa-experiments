#!/usr/bin/env bash
# Runs every case on this one machine. Needs root (netns, iptables, docker).
# The only "other machine" is a network namespace called panelclient,
# joined to the host by a veth pair on 10.250.0.0/30. Nothing leaves the box
# except the one-time image pull.
set -euo pipefail
cd "$(dirname "$0")"
IMG=python:3.13-alpine
R=results; mkdir -p "$R"; : > "$R/matrix.tsv"
HOST_IP=10.250.0.1   # host end of the veth, as seen from the client namespace
scrub() { sed -e "s/$(hostname)/HOST/g" -e "s#$PWD#.#g"; }

setup_ns() {
  ip netns add panelclient
  ip link add veth-host type veth peer name veth-client
  ip link set veth-client netns panelclient
  ip addr add $HOST_IP/30 dev veth-host; ip link set veth-host up
  ip -n panelclient addr add 10.250.0.2/30 dev veth-client
  ip -n panelclient link set veth-client up; ip -n panelclient link set lo up
}
cleanup() {
  docker rm -f p03 p04 p05 >/dev/null 2>&1 || true
  pkill -f "panel.py --host" 2>/dev/null || true
  iptables -D INPUT -p tcp --dport 18002 -j DROP 2>/dev/null || true
  iptables -D INPUT -p tcp --dport 18004 -j DROP 2>/dev/null || true
  if [ "${LEGACY_FIX:-0}" = 1 ]; then
    iptables-legacy -D DOCKER-USER -i veth-host -o docker0 -j ACCEPT 2>/dev/null || true
    iptables-legacy -D DOCKER-USER -i docker0 -o veth-host -j ACCEPT 2>/dev/null || true
  fi
  ip netns del panelclient 2>/dev/null || true
  ip link del veth-host 2>/dev/null || true
}
trap cleanup EXIT
cleanup; setup_ns
# Box-specific: a leftover iptables-legacy ruleset on the test machine has
# FORWARD policy DROP, which a clean Docker host does not have. Allow only
# veth-host -> docker0 for the length of the run; removed in cleanup.
if command -v iptables-legacy >/dev/null && iptables-legacy -S DOCKER-USER >/dev/null 2>&1; then
  iptables-legacy -I DOCKER-USER -i veth-host -o docker0 -j ACCEPT
  iptables-legacy -I DOCKER-USER -i docker0 -o veth-host -j ACCEPT
  LEGACY_FIX=1
fi

probe() { # case where port -> prints "http=<code> curl_exit=<n>"
  local c=$1 where=$2 port=$3 out rc
  if [ "$where" = loopback ]; then
    out=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:$port/projects) && rc=0 || rc=$?
  else
    out=$(ip netns exec panelclient curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://$HOST_IP:$port/projects) && rc=0 || rc=$?
  fi
  printf '%s\t%s\t%s\thttp=%s\tcurl_exit=%s\n' "$c" "$where" "$port" "$out" "$rc" | tee -a "$R/matrix.tsv"
}
snap() { # case port -> read-only evidence
  local c=$1 port=$2
  { echo "## $c  input: $3"
    echo '$ ss -H -ltnp "sport = :'$port'"'; ss -H -ltnp "sport = :$port" | sed -E 's/pid=[0-9]+/pid=N/g; s/fd=[0-9]+/fd=N/g'
    echo '$ lsof -nP -iTCP:'$port' -sTCP:LISTEN'; lsof -nP -iTCP:$port -sTCP:LISTEN | awk '{print $1, $5, $8, $9, $10}' || true
    if docker ps -q --filter name=$c | grep -q .; then
      echo '$ docker port '$c; docker port $c
      echo '$ iptables -t nat -S DOCKER | grep '$port; iptables -t nat -S DOCKER 2>/dev/null | grep -- "--dport $port" || true
    fi
    echo "\$ ./check-listeners.sh $port"; ./check-listeners.sh $port && echo "exit=0" || echo "exit=$?"
    echo; } 2>&1 | scrub >> "$R/evidence.log"
}
wait_port() { for _ in $(seq 50); do ss -H -ltn "sport = :$1" | grep -q . && return 0; sleep 0.1; done; echo "port $1 never listened" >&2; exit 1; }
: > "$R/evidence.log"

# b01 host process, loopback bind (the `cairn serve` default)
python3 panel.py --host 127.0.0.1 --port 18001 & wait_port 18001
snap b01 18001 "python3 panel.py --host 127.0.0.1 --port 18001"
probe b01 loopback 18001; probe b01 netns 18001

# b02 host process, all-interfaces bind
python3 panel.py --host 0.0.0.0 --port 18002 & wait_port 18002
snap b02 18002 "python3 panel.py --host 0.0.0.0 --port 18002"
probe b02 loopback 18002; probe b02 netns 18002

# b03 container, app binds 127.0.0.1 inside, port published
docker run -d --name p03 -p 18003:8000 -v "$PWD/panel.py:/panel.py:ro" $IMG python /panel.py --host 127.0.0.1 --port 8000 >/dev/null
wait_port 18003; sleep 1
snap p03 18003 "docker run -p 18003:8000 ... --host 127.0.0.1"
probe b03 loopback 18003; probe b03 netns 18003

# b04 container, the shape of the recommended Compose file: --host 0.0.0.0 and "8000:8000"
docker run -d --name p04 -p 18004:8000 -v "$PWD/panel.py:/panel.py:ro" $IMG python /panel.py --host 0.0.0.0 --port 8000 >/dev/null
wait_port 18004; sleep 1
snap p04 18004 "docker run -p 18004:8000 ... --host 0.0.0.0"
probe b04 loopback 18004; probe b04 netns 18004

# b05 same container, published on loopback only
docker run -d --name p05 -p 127.0.0.1:18005:8000 -v "$PWD/panel.py:/panel.py:ro" $IMG python /panel.py --host 0.0.0.0 --port 8000 >/dev/null
wait_port 18005; sleep 1
snap p05 18005 "docker run -p 127.0.0.1:18005:8000 ... --host 0.0.0.0"
probe b05 loopback 18005; probe b05 netns 18005

# b06 host firewall: an INPUT drop rule (what a ufw deny adds) on both exposed ports
iptables -I INPUT -p tcp --dport 18002 -j DROP
iptables -I INPUT -p tcp --dport 18004 -j DROP
{ echo "## b06 input: iptables -I INPUT -p tcp --dport 18002 -j DROP; same for 18004"; iptables -S INPUT 2>/dev/null | grep -E "1800[24]"; echo; } >> "$R/evidence.log"
probe b06-host-process netns 18002
probe b06-container netns 18004

# environment
{ echo "date: $(date -Is)"; uname -sr; docker version --format 'docker client {{.Client.Version}} server {{.Server.Version}}'
  docker info --format 'iptables={{.BridgeNfIptables}} cgroup={{.CgroupVersion}}'
  docker image inspect $IMG --format 'image {{index .RepoDigests 0}}'
  python3 --version; curl --version | head -1; ss --version 2>&1 | head -1; lsof -v 2>&1 | grep -m1 revision; iptables --version; } | scrub > "$R/environment.txt"
echo done
