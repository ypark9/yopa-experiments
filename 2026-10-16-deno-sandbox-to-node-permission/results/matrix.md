# Probe matrix (3 runs, identical: True)

Versions: deno 2.9.7 (stable, release, x86_64-unknown-linux-gnu), v22.23.3, v24.22.0, v26.12.0

P0 = no grants (yt-dlp style). P1 = read+write grant on the work dir only. "allowed" means the probe got through;
for the two sibling probes it means the sibling process actually opened its inspector. "n/a" = fails even with full access.

| probe | deno/P0 | node22/P0 | node24/P0 | node26/P0 | deno/P1 | node22/P1 | node24/P1 | node26/P1 |
|---|---|---|---|---|---|---|---|---|
| fs_read_outside | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |
| fs_write_outside | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |
| fs_write_workdir | blocked | blocked | blocked | blocked | allowed | allowed | allowed | allowed |
| fs_read_via_symlink_in_workdir | blocked | blocked | blocked | blocked | allowed | allowed | allowed | allowed |
| env_secret | blocked | allowed | allowed | allowed | blocked | allowed | allowed | allowed |
| net_fetch_localhost | blocked | allowed | allowed | blocked | blocked | allowed | allowed | blocked |
| net_tcp_localhost | blocked | allowed | allowed | blocked | blocked | allowed | allowed | blocked |
| child_process | blocked | blocked | blocked | blocked | blocked | blocked | blocked | blocked |
| sqlite_read_outside | blocked | allowed | allowed | allowed | blocked | allowed | allowed | allowed |
| sqlite_write_outside | blocked | allowed | allowed | allowed | blocked | allowed | allowed | allowed |
| inherited_fd_read | n/a | allowed | allowed | allowed | n/a | allowed | allowed | allowed |
| debug_process_sibling | blocked | allowed | allowed | allowed | blocked | allowed | allowed | allowed |
| signal_sibling_sigusr1 | blocked | allowed | allowed | allowed | blocked | allowed | allowed | allowed |

## Counts: probes that Deno blocks but Node allows

- P0 node22: 7 (env_secret, net_fetch_localhost, net_tcp_localhost, sqlite_read_outside, sqlite_write_outside, debug_process_sibling, signal_sibling_sigusr1)
- P0 node24: 7 (env_secret, net_fetch_localhost, net_tcp_localhost, sqlite_read_outside, sqlite_write_outside, debug_process_sibling, signal_sibling_sigusr1)
- P0 node26: 5 (env_secret, sqlite_read_outside, sqlite_write_outside, debug_process_sibling, signal_sibling_sigusr1)
- P1 node22: 7 (env_secret, net_fetch_localhost, net_tcp_localhost, sqlite_read_outside, sqlite_write_outside, debug_process_sibling, signal_sibling_sigusr1)
- P1 node24: 7 (env_secret, net_fetch_localhost, net_tcp_localhost, sqlite_read_outside, sqlite_write_outside, debug_process_sibling, signal_sibling_sigusr1)
- P1 node26: 5 (env_secret, sqlite_read_outside, sqlite_write_outside, debug_process_sibling, signal_sibling_sigusr1)

## Memory: heap cap 128 MB, then try to hold 512 MB

| runtime/mode | exit code | heap OOM message | allocated | peak RSS MB |
|---|---|---|---|---|
| deno/heap | -5 | True | - | 211 |
| deno/arraybuffer | 0 | False | {"allocated_mb":512} | 549 |
| node22/heap | -6 | True | - | 202 |
| node22/arraybuffer | 0 | False | {"allocated_mb":512} | 557 |
| node24/heap | -6 | True | - | 258 |
| node24/arraybuffer | 0 | False | {"allocated_mb":512} | 557 |
| node26/heap | -6 | True | - | 226 |
| node26/arraybuffer | 0 | False | {"allocated_mb":512} | 557 |
