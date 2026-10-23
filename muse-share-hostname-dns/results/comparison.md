# Hostname token vs path token — local DNS log

Scheme A URL: `http://q3-budget-review-4d7a19e2.share.test:8766/`

Scheme B URL: `http://share.test:8766/s/q3-budget-review/4d7a19e2`

## DNS queries observed

- `1792762615.723	q3-budget-review-4d7a19e2.share.test	qtype=1`
- `1792762615.731	share.test	qtype=1`

## Outcome

- Queries containing the conversation title `q3-budget-review`: ['q3-budget-review-4d7a19e2.share.test']
- Scheme A (title in hostname) published title to DNS: **yes**
- Scheme B (title in path only) published title to DNS: **no**
- Scheme B host query was: `['share.test']`

## HTTP checks

- A: exit=0 body=`ok host=q3-budget-review-4d7a19e2.share.test path=/`
- B: exit=0 body=`ok host=share.test path=/s/q3-budget-review/4d7a19e2`

## Note

This is a local model of the leak channel (DNS query logging). It does not query commercial passive DNS and does not touch Meta Muse hosts.
