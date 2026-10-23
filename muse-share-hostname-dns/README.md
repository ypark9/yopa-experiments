# Muse-style share URL: hostname token vs path token

Local DNS query logger comparing two share URL schemes.

- Scheme A: `http://{title}-{id}.share.test/` (title lands in DNS)
- Scheme B: `http://share.test/s/{title}/{id}` (DNS sees only `share.test`)

Does not query commercial passive DNS and does not contact Meta Muse hosts.
Models the leak channel described by Claroc / Ars Technica / The Verge (Oct 2026).

## Run

```bash
python3 scripts/dns_logger.py &
python3 scripts/http_shares.py &
python3 scripts/run_demo.py
kill %1 %2
cat results/comparison.md
```
