# Agent control panel: what one port line exposes

Code and raw output behind the post
"Your Agent Panel Defaults to 127.0.0.1. Your Compose File Doesn't."

## What it runs

Everything runs on one Linux machine. The "other machine" is a network
namespace (`panelclient`) joined to the host by a veth pair on `10.250.0.0/30`.
No external host is contacted; the only network download is the
`python:3.13-alpine` image pull.

- `panel.py`: a stand-in for an agent control panel. No authentication, `GET /projects`
  returns a fake list, `--host` defaults to `127.0.0.1` (the same default as `cairn serve`).
  It is not Cairn.
- `run_matrix.sh` (root): six cases, read-only evidence (`ss`, `lsof`, `docker port`,
  the Docker NAT rule), then `curl` from loopback and from the namespace.
- `check-listeners.sh`: read-only. Prints every TCP listener and Docker published port
  that is not on loopback, exits 1 if there is one.

It creates: one netns, one veth pair, three containers, two temporary iptables INPUT
DROP rules. All are removed on exit (trap). Cost: none beyond local compute.

Box-specific: the test machine had a leftover `iptables-legacy` ruleset with FORWARD
policy DROP, which drops forwarded traffic to containers (the first run,
`results/run0-stale-legacy-forward-drop.tsv`, timed out on b04/b06 for that reason).
`run_matrix.sh` adds two scoped `DOCKER-USER` ACCEPT rules (veth-host <-> docker0)
only when that legacy table exists, and removes them on exit.

## Results (`results/matrix.tsv`)

| Case | Setup | Listener (ss) | loopback | from namespace |
|---|---|---|---|---|
| b01 | host process `--host 127.0.0.1` | `127.0.0.1:18001` | 200 | refused (curl 7) |
| b02 | host process `--host 0.0.0.0` | `0.0.0.0:18002` | 200 | **200** |
| b03 | container, app on 127.0.0.1, `-p 18003:8000` | `0.0.0.0` + `[::]` (docker-proxy) | reset (curl 56) | refused (curl 7) |
| b04 | container, app on 0.0.0.0, `-p 18004:8000` | `0.0.0.0` + `[::]` (docker-proxy) | 200 | **200** |
| b05 | container, app on 0.0.0.0, `-p 127.0.0.1:18005:8000` | `127.0.0.1:18005` | 200 | refused (curl 7) |
| b06 | INPUT DROP on 18002 and 18004 | | | 18002 timeout (curl 28); **18004 still 200** |

`check-listeners.sh` exit codes: b01 0, b02 1, b03 1, b04 1, b05 0 (`results/evidence.log`).

## What it does not prove

- Docker 26.1.5 (Debian package) with the iptables backend only. Docker documents that
  releases older than 28.0.0 let hosts on the same L2 segment reach ports published to
  localhost (moby/moby#45610); that path was not tested here.
- No ufw, firewalld, nftables-backend Docker, rootless Docker, Podman, or IPv6 client.
- Not Cairn itself, and not any real exposed panel.
