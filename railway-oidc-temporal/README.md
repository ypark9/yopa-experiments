# Railway's two configuration hops, measured locally (2026-11-20)

Companion code for the yopa.page post on Railway's October 2026 incident report.
Nothing here is Railway's real configuration. Railway's report does not say which CI,
which cloud, or which OIDC claim was wrong; these are common shapes.

**Cost:** local CPU only. No AWS call, no GitHub token, no paid API. No CI job beyond this
repo's own identifier-check.

## 1. `oidc/` - which GitHub Actions subjects would a role trust policy accept?

`python3 oidc/matcher.py` (stdlib only) writes `oidc/results/matrix.json` and `matrix.txt`.

- Documentation-based, **not an AWS call** and **not a real GitHub token**.
- Subject formats: GitHub OIDC reference (copy saved as `oidc/results/github-oidc-reference-2026-11-20.md`),
  including the immutable `repo:OWNER@OWNER-ID/REPO@REPO-ID:...` format for repositories created after 2026-07-15.
- Matching: IAM StringEquals (exact, case-sensitive) and StringLike (`*`, `?`, case-sensitive).
- `passes_iam_create_time_guard_by_docs`: IAM user guide rule that the `sub` key must be
  present and "not solely a wildcard character (* and ?) or null".
- Not modeled: the OIDC provider's audience list, other STS checks, session policies.
- Why no real tokens: the token this run pushed with has no `workflow` scope, so no
  workflow file could be added. Use a workflow that prints decoded claims (never the raw
  token) if you want to confirm the formats on your own repo.

## 2. `temporal/` - where does a secret land in workflow history?

Versions in `temporal/results/versions.txt` (temporal CLI 1.10.1 / Server 1.32.2, Python SDK 1.36.1).

```bash
temporal server start-dev --headless --port 7233        # local, in-memory, no auth
temporal operator search-attribute create --name BuildNote --type Keyword
python temporal/cases.py                 # 7 workflows, each with a fake marker FAKE-tN-sk-000...
python temporal/read_as_other_client.py  # plain temporal CLI, no codec key
```

`read_as_other_client.py` dumps `workflow show` and `workflow describe` as JSON, base64-decodes
every string it can, and searches for the marker. Results: `other_client_view.json` and
`other_client_summary.txt`. Example histories: `history-t1.json` (no codec), `history-t3.json`
(codec), `history-t4.json` (codec, failure message). `worker_and_owner_client.log` is the
worker's own stderr, which shows the marker in a traceback even when history was clean.
Worker identities in the JSON were redacted to `PID@box`.

Case IDs (t1-t7) are only used in this repo; the article describes each case in words.
