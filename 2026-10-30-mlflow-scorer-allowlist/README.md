# MLflow third-party scorer allow-list: prefix match vs exact match

Local, network-free experiment for the yopa.page draft on GHSA-26p8-2jq9-3vq9
(MLflow 3.12.0 to before 3.17.0: unauthenticated code execution through
third-party scorer deserialization).

Nothing here installs MLflow, starts a server, opens a network connection, or
touches a cloud account. The "caller-placed" module only writes a random marker
string to a temp directory.

## Files

- `run.py` rebuilds the allow-list check as written in MLflow 3.16.1 (prefix
  match) and 3.17.0 (exact match) and tries three module paths against each.
- `fromlist_check.py` checks the Python behavior behind the new
  `metric_name.isidentifier()` check in 3.17.0.
- `source-check.txt` shows the matching lines from the real MLflow 3.16.1 and
  3.17.0 source distributions on PyPI, with their SHA-256 hashes.
- `run-output.json` and `fromlist-output.json` are the raw outputs.

## Run

```sh
python3 run.py
python3 fromlist_check.py
```

Run on Python 3.13.5. Standard library only.

## What it does not show

It does not run a real MLflow server or the advisory's proof of concept, and it
does not exploit the deepeval path. `fromlist_check.py` shows only that a dotted
name in `__import__(..., fromlist=[...])` imports a submodule placed under the
package.
