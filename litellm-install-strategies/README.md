# LiteLLM-style install strategies (local fixture)

Replays which Python install lines would have pulled a two-hour malicious release,
using a local package `supplydemo` (never downloads real `litellm==1.107.0`).

## Incident anchors (read-only)

- https://docs.litellm.ai/blog/security-incident-oct-21-2026
- https://safedep.io/litellm-pypi-compromise-credential-stealer-backdoor/
- Simulated window: `2026-10-21T11:39:51Z` start; mid probe `12:00:00Z`
- Clean fixture `1.0.0` upload-time `10:44:22Z`; tampered `1.1.0` at `11:40:00Z`

## Run

```bash
python3 scripts/build_fixtures.py
python3 scripts/index_server.py &   # 127.0.0.1:8765
python3 scripts/run_strategies.py
kill %1
cat results/matrix.md
```

Tampered wheel only plants `cook.pth` + a marker file. No network exfil, no credential access.

## Results (this run)

See `results/matrix.md`. Summary: unpinned and mid-window time gates install tampered;
`==` pin to a known-clean version, hash pin to clean, and time gates cut off before the
bad upload install clean or refuse.
