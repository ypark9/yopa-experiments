# Deno flags vs Node `--permission` as a sandbox for untrusted JavaScript

Companion to the yopa.page post "Deno Is Winding Down. Can Node's `--permission` Replace It as a Sandbox?" (2026-10-16).

Deno's team is joining Cloudflare and the Deno runtime gets about 12 months of bugfix and security releases before development ends. Some tools use Deno as a cage for code they did not write; yt-dlp runs YouTube's player JavaScript under Deno with no grants and ships a Node `--permission` path as the alternative. This experiment runs one probe battery under both and records what each blocks.

Everything is local: temp directories, a fake secret (`fake-secret-not-real-0000`), and an HTTP server on 127.0.0.1. No cloud account, no paid API.

## Runtimes

Deno 2.9.7, Node 22.23.3, Node 24.22.0, Node 26.12.0 (official linux-x64 builds; checksums checked against the published SHASUMS files). Linux x86_64.

## Profiles

- `control`: full access (`deno run -A`, plain `node`). Proves every probe can succeed; a probe that fails here is reported as `n/a`.
- `P0`: no grants. Deno gets yt-dlp's exact option list; Node gets `--permission` (or `--experimental-permission` below 23.5.0, the same rule yt-dlp uses).
- `P1`: read and write grant on one work directory only.

The script is piped on stdin, like yt-dlp does. The child gets `PATH`, `HOME`, and `PROBE_FAKE_SECRET` in its environment, and the secret file as an open fd 3.

## Probes

| probe | what it tries |
|---|---|
| fs_read_outside / fs_write_outside | read or write a file outside the work dir with `node:fs` |
| fs_write_workdir | write inside the work dir (should pass only in P1) |
| fs_read_via_symlink_in_workdir | read a symlink inside the work dir that points outside |
| env_secret | read `PROBE_FAKE_SECRET` |
| net_fetch_localhost / net_tcp_localhost | `fetch` and a raw `node:net` socket to the local server |
| child_process | run `/bin/echo` |
| sqlite_read_outside / sqlite_write_outside | open a SQLite file outside the work dir with `node:sqlite`, read a row, insert a row |
| inherited_fd_read | read the already-open fd 3 |
| debug_process_sibling | `process._debugProcess(pid)` on another, unrestricted Node process |
| signal_sibling_sigusr1 | `process.kill(pid, 'SIGUSR1')` on another unrestricted Node process |

For the two sibling probes, "allowed" means the sibling actually printed `Debugger listening`, i.e. its inspector opened. Disk effects (files written, SQLite row count) are checked by the harness separately from what the probe reports.

Memory: heap cap 128 MB (`--max-old-space-size=128`, or `--v8-flags=` for Deno), then try to hold 512 MB either as ordinary JS arrays (heap) or as `Uint8Array`s (outside the heap).

## Run

```sh
python3 run.py --deno PATH/deno --node22 PATH/node --node24 PATH/node --node26 PATH/node --name raw-run1.json
python3 summarize.py      # writes results/matrix.md and fails if runs disagree
```

`check-node-sandbox.sh` is the read-only self-test from the post (`NODE=path/to/node sh check-node-sandbox.sh`).

## Results

See `results/matrix.md` (3 runs, identical). Summary:

- Deno blocked every probe in P0 except the fd probe, which is `n/a` (Deno's `node:fs` could not read inherited fd 3 even with `-A`).
- Node blocked direct file access and child processes on all three versions.
- Node allowed, on all three versions: reading the env secret, `node:sqlite` read and write outside the granted paths, reading the inherited fd, and turning on another Node process's inspector (both `_debugProcess` and plain `SIGUSR1`).
- Network: allowed on Node 22 and 24 (they have no network permission), blocked on Node 26.
- Probes Deno blocks and Node allows: 7 of 13 on Node 22 and 24, 5 of 13 on Node 26, in both P0 and P1.
- Same in both runtimes: a symlink inside a granted directory reads a file outside it (P1), and a 128 MB heap cap kills heap growth but lets 512 MB of `Uint8Array` through (peak RSS 549-557 MB).

## Not tested

Bun, macOS and Windows, Deno workers with reduced permissions, OS-level isolation (separate users, cgroups, seccomp), and any real yt-dlp run.
