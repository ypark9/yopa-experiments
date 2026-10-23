# Git cliffs before Scion

Code and raw output behind the post
"Anthropic Left Git at 30,000 Merges a Day. Here Is Where Git Bent First on One Machine."

## What it runs

Everything is local: synthetic bare repos on disk, clones over `file://` (pack protocol v2,
`--no-local` so the real transfer path is used). No network, no hosted forge, no cloud.
Cost: local compute and about 6 GB of temporary disk.

- `gen_repo.py <bare> <files> <commits>`: builds a bare repo with `git fast-import`.
  100 top-level dirs, ~250-byte unique files, an initial commit plus 500 commits
  that each rewrite 20 random files. Fixed seed and timestamps.
  Built at 10k, 100k, 300k and 1M files.
- `measure.py <repos> <work> <test>...`: `status`, `clone`, `lazy`, `push`, `repack`.
  Every row goes to `results/raw.log` as JSON.
- `summarize.py`: prints the tables below from `raw.log` (`results/tables.md`).

## Results

See `results/tables.md` for every column. Short form:

- **Push race (`push`, r10k).** K clones each commit one new file and push to `main` at the
  same moment. In every trial exactly one push landed and K-1 were rejected with
  `cannot lock ref 'refs/heads/main'` (sample: `results/push-sample-4-agents.txt`).
  With a `pull --rebase` + push retry loop, all K landed; total attempts were
  1/3/9-10/35-36/135-136/519-528 for K = 1/2/4/8/16/32 (K(K+1)/2 = 528 at K=32), median
  retry wall time 10.16 s at K=32.
- **Working tree size (`status`).** Warm `git status` median of 5: 0.036 s at 10k files,
  0.908 s at 1M. `-uno` 0.285 s, untracked cache 0.308 s at 1M. Index 88.2 MB at 1M.
  `git fsmonitor--daemon start`: `fatal: fsmonitor--daemon not supported on this platform`.
  `sparse-checkout set` to one of 100 dirs took 17.12 s at 1M.
- **Partial clone with a full checkout (`clone`).** `--filter=blob:none` then checking out
  every file was slower than a full clone: 11.42 s vs 2.69 s at 100k, 92.55 s vs 9.32 s at
  300k, and did not finish in 900 s at 1M (full: 29.88 s). A first attempt at 1M was killed
  by hand after 798 s. `blob:none` + `--sparse` + one dir: 0.49 s at 100k, 3.31 s at 1M.
- **History on partial clones (`lazy`, r100k).** `git log -p -n 100`: 0 lazy fetches /
  0.068 s on a full clone, 100 / 1.801 s on blob:none, 200 / 29.349 s on tree:0.
  `git log --oneline -- d000` on tree:0: 500 lazy fetches, 109.954 s (full: 0.008 s).
  `blame` on tree:0: 63 fetches, 17.017 s.
- **Maintenance (`repack`).** `git repack -a -d -f` 13.27 s and `gc` 5.61 s on the 1M bare repo.

## Corrections made during the run (kept in raw.log)

- The first `lazy` pass counted 0 fetches (trace2 argv filter bug) and its pack count was
  capped at 50 by auto-gc. Rerun with `gc.auto=0` and the fixed filter; the summary uses the rerun.
- The first 1M `blob:none` clone was killed by hand at 798 s; rerun with a 900 s timeout.

## What it does not prove

- One machine, git 2.47.3, `file://`. A hosted forge over HTTPS adds latency per round trip,
  so the push race window and per-object lazy fetches would likely cost more, but that was not measured.
- Synthetic history is short (500 commits) relative to the tree, which is the opposite of
  Anthropic's reported ratio (about 100 GB history vs 25 GB working copy). `--depth 1` and
  `blob:none` look worse here than they would on a history-heavy repo.
- Warm cache only; no `drop_caches` on a shared machine. No `index.sparse`, no Scalar,
  no `git maintenance` schedule, no newer git.
- Nothing here measures Scion.
