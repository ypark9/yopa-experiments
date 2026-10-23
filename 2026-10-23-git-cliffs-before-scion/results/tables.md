| repo | files | clone+checkout s | index MB | status s | status -uno s | status untracked cache s | status after 1 edit s | sparse set (1 dir) s | files after sparse | status sparse s |
|---|---|---|---|---|---|---|---|---|---|---|
| r10k.git | 10000 | 0.63 | 1.0 | 0.036 | 0.016 | 0.026 | 0.026 | 0.21 | 100 | 0.005 |
| r100k.git | 100000 | 2.7 | 8.9 | 0.088 | 0.034 | 0.038 | 0.038 | 1.52 | 1000 | 0.061 |
| r300k.git | 300000 | 7.97 | 26.5 | 0.206 | 0.086 | 0.096 | 0.084 | 4.87 | 3000 | 0.172 |
| r1000k.git | 1000000 | 30.16 | 88.2 | 0.908 | 0.285 | 0.308 | 0.301 | 17.12 | 10000 | 0.187 |

fsmonitor: {'exit=128 fatal: fsmonitor--daemon not supported on this platform'} 

| repo | variant | clone s | sparse set s | .git MB | objects | files on disk |
|---|---|---|---|---|---|---|
| r100k.git | full | 2.69 | 0.0 | 31.4 | 135139 | 100000 |
| r100k.git | depth1 | 2.55 | 0.0 | 27.8 | 105102 | 100000 |
| r100k.git | blob_none | 11.42 | 0.0 | 38.0 | 125139 | 100000 |
| r100k.git | blob_none_sparse_d000 | 0.49 | 0.17 | 14.2 | 26139 | 1000 |
| r100k.git | tree0 | 11.13 | 0.0 | 36.1 | 105602 | 100000 |
| r1000k.git | full | 29.88 | 0.0 | 274.3 | 1035217 | 1000000 |
| r1000k.git | depth1 | 29.04 | 0.0 | 270.7 | 1005102 | 1000000 |
| r300k.git | full | 9.32 | 0.0 | 85.4 | 335193 | 300000 |
| r300k.git | blob_none | 92.55 | 0.0 | 108.4 | 325193 | 300000 |
| r1000k.git | blob_none | timeout>900 |  | 26.4 |  |  |
| r1000k.git | blob_none_sparse_d000 | 3.31 | 1.96 | 117.0 | 35217 | 10000 |

| clone | command | time s | lazy fetches | new packs |
|---|---|---|---|---|
| full | `git log -p -n 100` | 0.068 | 0 | 0 |
| full | `git log --oneline -- d000` | 0.008 | 0 | 0 |
| full | `git blame d001/s22/f0017201.txt` | 0.027 | 0 | 0 |
| full | `git diff --stat HEAD~200 HEAD` | 0.107 | 0 | 0 |
| blob_none | `git log -p -n 100` | 1.801 | 100 | 100 |
| blob_none | `git log --oneline -- d000` | 0.007 | 0 | 0 |
| blob_none | `git blame d001/s22/f0017201.txt` | 0.065 | 1 | 1 |
| blob_none | `git diff --stat HEAD~200 HEAD` | 0.215 | 1 | 1 |
| tree0 | `git log -p -n 100` | 29.349 | 200 | 200 |
| tree0 | `git log --oneline -- d000` | 109.954 | 500 | 500 |
| tree0 | `git blame d001/s22/f0017201.txt` | 17.017 | 63 | 63 |
| tree0 | `git diff --stat HEAD~200 HEAD` | 0.403 | 2 | 2 |

| agents | trials | landed on first try (each trial) | first-try rejections | total push attempts (each trial) | max attempts by one agent | retry wall s (median) |
|---|---|---|---|---|---|---|
| 1 | 3 | 1, 1, 1 | 0, 0, 0 | 1, 1, 1 | 1 | 0.0 |
| 2 | 3 | 1, 1, 1 | 1, 1, 1 | 3, 3, 3 | 2 | 0.23 |
| 4 | 3 | 1, 1, 1 | 3, 3, 3 | 10, 10, 9 | 4 | 0.43 |
| 8 | 3 | 1, 1, 1 | 7, 7, 7 | 36, 36, 35 | 8 | 1.16 |
| 16 | 3 | 1, 1, 1 | 15, 15, 15 | 135, 135, 136 | 16 | 2.97 |
| 32 | 3 | 1, 1, 1 | 31, 31, 31 | 528, 519, 525 | 32 | 10.16 |

| repo | bytes after clone MB | repack -adf s | after repack MB | commit-graph s | gc s |
|---|---|---|---|---|---|
| r100k.git | 22.4 | 1.55 | 23.4 | 0.01 | 0.69 |
| r1000k.git | 186.1 | 13.27 | 192.2 | 0.01 | 5.61 |

