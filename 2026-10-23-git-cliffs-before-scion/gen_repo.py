#!/usr/bin/env python3
"""Build a synthetic bare repo with git fast-import.
usage: gen_repo.py <bare-dir> <files> <history-commits> [seed]
Layout: d000/ .. d099/ (100 top-level dirs), files spread evenly, ~200-byte unique text each.
Each history commit rewrites 20 random files. Deterministic for a given seed."""
import random, subprocess, sys, os
bare, n, hist = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rnd = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 1)
subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
p = subprocess.Popen(["git", "-C", bare, "fast-import", "--quiet"], stdin=subprocess.PIPE)
w = p.stdin.write
paths = [f"d{i % 100:03d}/s{(i // 100) % 50:02d}/f{i:07d}.txt" for i in range(n)]
def blob(path, gen):
    body = (f"{path} gen {gen}\n" + "".join(f"line {k} {rnd.getrandbits(64):016x}\n" for k in range(6))).encode()
    return body
t = 1767225600  # 2026-01-01T00:00:00Z, fixed so object ids are reproducible
def commit(msg, files, gen, first=False):
    global t
    t += 60
    w(b"commit refs/heads/main\n")
    w(f"committer Synthetic <synthetic@example.invalid> {t} +0000\n".encode())
    m = msg.encode(); w(b"data %d\n" % len(m) + m + b"\n")
    for path in files:
        b = blob(path, gen)
        w(f"M 100644 inline {path}\n".encode()); w(b"data %d\n" % len(b) + b + b"\n")
    w(b"\n")
commit("initial", paths, 0, True)
for c in range(1, hist + 1):
    commit(f"change {c}", rnd.sample(paths, 20), c)
p.stdin.close()
sys.exit(p.wait())
