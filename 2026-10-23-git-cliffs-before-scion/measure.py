#!/usr/bin/env python3
"""Local git measurements. Everything is file:// on one machine; no network.
usage: measure.py <repos-dir> <work-dir> <test> ...   tests: status clone lazy push repack
<repos-dir> holds r10k.git r100k.git r300k.git r1000k.git from gen_repo.py."""
import json, os, re, shutil, statistics, subprocess, sys, threading, time
REPOS, WORK = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(WORK, exist_ok=True); os.makedirs(OUT, exist_ok=True)
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", HOME=WORK, GIT_AUTHOR_NAME="Agent",
           GIT_AUTHOR_EMAIL="agent@example.invalid", GIT_COMMITTER_NAME="Agent",
           GIT_COMMITTER_EMAIL="agent@example.invalid", GIT_PROTOCOL="version=2")

def scrub(s): return s.replace(WORK, "$WORK").replace(REPOS, "$REPOS")
def run(args, cwd=None, check=True, env=None, timeout=None):
    t = time.perf_counter()
    p = subprocess.run(args, cwd=cwd, env=env or ENV, capture_output=True, text=True, timeout=timeout)
    dt = time.perf_counter() - t
    if check and p.returncode: raise SystemExit(f"FAILED {scrub(' '.join(args))}\n{scrub(p.stderr)}")
    return dt, p
def git(*a, cwd=None, check=True, env=None, timeout=None): return run(["git", *a], cwd=cwd, check=check, env=env, timeout=timeout)
def du(path):
    return int(subprocess.run(["du", "-sb", path], capture_output=True, text=True).stdout.split()[0])
def nfiles(path):
    return sum(len(f) for r, d, f in os.walk(path) if "/.git" not in r + "/" and not r.endswith(".git"))
def url(name): return "file://" + os.path.join(REPOS, name)
def fresh(p):
    shutil.rmtree(p, ignore_errors=True); return p
log = open(os.path.join(OUT, "raw.log"), "a")
def rec(test, row):
    row = {"test": test, **row}; print(json.dumps(row)); log.write(json.dumps(row) + "\n"); log.flush()
for r in os.listdir(REPOS):  # server side: allow filters and lazy fetch by object id
    git("-C", os.path.join(REPOS, r), "config", "uploadpack.allowFilter", "true")
    git("-C", os.path.join(REPOS, r), "config", "uploadpack.allowAnySHA1InWant", "true")

def median_status(wt, *extra, n=5):
    git("status", "--porcelain", *extra, cwd=wt)  # warm-up
    return statistics.median(git("status", "--porcelain", *extra, cwd=wt)[0] for _ in range(n))

def t_status():
    for name in ["r10k.git", "r100k.git", "r300k.git", "r1000k.git"]:
        wt = fresh(os.path.join(WORK, "st-" + name))
        dt, _ = git("clone", "-q", url(name), wt)
        row = {"repo": name, "files_on_disk": nfiles(wt), "clone_checkout_s": round(dt, 2),
               "index_bytes": os.path.getsize(os.path.join(wt, ".git", "index"))}
        row["status_default_s"] = round(median_status(wt), 3)
        row["status_uno_s"] = round(median_status(wt, "-uno"), 3)
        git("config", "core.untrackedCache", "true", cwd=wt); git("update-index", "--untracked-cache", cwd=wt)
        row["status_untracked_cache_s"] = round(median_status(wt), 3)
        _, p = git("fsmonitor--daemon", "start", cwd=wt, check=False)
        row["fsmonitor_daemon_start"] = f"exit={p.returncode} " + scrub((p.stderr or p.stdout).strip())[:160]
        with open(os.path.join(wt, "d000/s00/f0000000.txt"), "a") as f: f.write("edit\n")
        row["status_one_edit_s"] = round(median_status(wt), 3)
        git("checkout", "-q", "--", ".", cwd=wt)
        dt, _ = git("sparse-checkout", "set", "--cone", "d000", cwd=wt)
        row["sparse_set_s"] = round(dt, 2); row["sparse_files_on_disk"] = nfiles(wt)
        row["status_sparse_s"] = round(median_status(wt), 3)
        rec("status", row); shutil.rmtree(wt)

CLONE_REPOS = os.environ.get("CLONE_REPOS", "r100k.git r1000k.git").split()
CLONE_VARIANTS = os.environ.get("CLONE_VARIANTS", "").split()
CLONE_TIMEOUT = int(os.environ.get("CLONE_TIMEOUT", "900"))
def t_clone():
    variants = {"full": [], "depth1": ["--depth", "1"], "blob_none": ["--filter=blob:none"],
                "blob_none_sparse_d000": ["--filter=blob:none", "--sparse"], "tree0": ["--filter=tree:0"]}
    for name in CLONE_REPOS:
        for v, extra in variants.items():
            if CLONE_VARIANTS and v not in CLONE_VARIANTS: continue
            wt = fresh(os.path.join(WORK, f"cl-{name}-{v}"))
            try:
                dt, _ = git("clone", "-q", "--no-local", *extra, url(name), wt, timeout=CLONE_TIMEOUT)
            except subprocess.TimeoutExpired:
                subprocess.run(["pkill", "-f", wt]); time.sleep(1)
                rec("clone", {"repo": name, "variant": v, "clone_s": f"timeout>{CLONE_TIMEOUT}",
                              "git_dir_bytes": du(os.path.join(wt, ".git"))})
                shutil.rmtree(wt, ignore_errors=True); continue
            sdt = 0.0
            if v.endswith("sparse_d000"):
                sdt, _ = git("sparse-checkout", "set", "--cone", "d000", cwd=wt)
            _, p = git("count-objects", "-v", cwd=wt)
            co = dict(l.split(": ") for l in p.stdout.strip().splitlines())
            rec("clone", {"repo": name, "variant": v, "clone_s": round(dt, 2), "sparse_set_s": round(sdt, 2),
                          "git_dir_bytes": du(os.path.join(wt, ".git")), "objects_in_pack": int(co["in-pack"]),
                          "files_on_disk": nfiles(wt)})
            if name != "r100k.git" or v not in ("full", "blob_none", "tree0"):
                shutil.rmtree(wt)

def count_fetches(wt, *args):
    ev = os.path.join(WORK, "trace2.json")
    if os.path.exists(ev): os.remove(ev)
    env = dict(ENV, GIT_TRACE2_EVENT=ev)
    packs0 = len([f for f in os.listdir(os.path.join(wt, ".git/objects/pack")) if f.endswith(".pack")])
    git("config", "gc.auto", "0", cwd=wt)  # otherwise auto-gc merges packs after 50 and hides the count
    git("config", "maintenance.auto", "false", cwd=wt)
    dt, p = git(*args, cwd=wt, env=env)
    fetches = 0
    with open(ev) as f:
        for line in f:
            e = json.loads(line)
            if e.get("event") == "child_start" and "fetch" in e.get("argv", []): fetches += 1
    packs1 = len([f for f in os.listdir(os.path.join(wt, ".git/objects/pack")) if f.endswith(".pack")])
    return round(dt, 3), fetches, packs1 - packs0, len(p.stdout)

def t_lazy():
    name = "r100k.git"
    _, p = git("-C", os.path.join(REPOS, name), "log", "--format=", "--name-only")
    counts = {}
    for l in p.stdout.split():
        counts[l] = counts.get(l, 0) + 1
    hot = max(sorted(counts), key=lambda k: counts[k])
    cmds = {"log_p_100": ["log", "-p", "-n", "100"],
            "log_path_d000": ["log", "--oneline", "--", "d000"],
            "blame_hot_file": ["blame", hot],
            "diff_HEAD~200": ["diff", "--stat", "HEAD~200", "HEAD"]}
    for v in ["full", "blob_none", "tree0"]:
        src = os.path.join(WORK, f"cl-{name}-{v}")
        for c, args in cmds.items():
            wt = fresh(os.path.join(WORK, "lz"))
            shutil.copytree(src, wt, symlinks=True)
            dt, fetches, newpacks, outlen = count_fetches(wt, *args)
            rec("lazy", {"repo": name, "clone": v, "cmd": " ".join(args), "hot_file_changes": counts[hot] if c == "blame_hot_file" else "",
                         "time_s": dt, "fetch_processes": fetches, "new_packs": newpacks, "stdout_bytes": outlen})
            shutil.rmtree(wt)

def t_push():
    name = "r10k.git"
    for k in [1, 2, 4, 8, 16, 32]:
        for trial in range(1, 4):
            srv = fresh(os.path.join(WORK, "push-srv.git"))
            git("clone", "-q", "--bare", "--no-local", url(name), srv)
            agents = []
            for i in range(k):
                a = fresh(os.path.join(WORK, f"push-a{i:02d}"))
                git("clone", "-q", "--no-local", "file://" + srv, a)
                with open(os.path.join(a, f"d{i % 100:03d}/agent-{i:02d}.txt"), "w") as f: f.write(f"agent {i}\n")
                git("add", "-A", cwd=a); git("commit", "-q", "-m", f"agent {i}", cwd=a)
                agents.append(a)
            # round 1: everyone pushes at once, no retry
            bar = threading.Barrier(k); res = [None] * k
            def once(i):
                bar.wait(); _, p = git("push", "-q", "origin", "HEAD:main", cwd=agents[i], check=False)
                err = p.stderr
                why = "ok" if p.returncode == 0 else ("fetch first" if "fetch first" in err else
                      "lock" if "lock" in err else "non-fast-forward" if "non-fast-forward" in err else "other")
                res[i] = why
            ts = [threading.Thread(target=once, args=(i,)) for i in range(k)]
            [t.start() for t in ts]; [t.join() for t in ts]
            first = {w: res.count(w) for w in set(res)}
            # round 2: losers retry with pull --rebase until they land
            attempts = [1] * k; done = [r == "ok" for r in res]
            bar2 = threading.Barrier(k)
            def retry(i):
                bar2.wait()
                while not done[i]:
                    git("pull", "-q", "--rebase", "origin", "main", cwd=agents[i], check=False)
                    attempts[i] += 1
                    _, p = git("push", "-q", "origin", "HEAD:main", cwd=agents[i], check=False)
                    done[i] = p.returncode == 0
                    if attempts[i] > 200: break
            t0 = time.perf_counter()
            ts = [threading.Thread(target=retry, args=(i,)) for i in range(k)]
            [t.start() for t in ts]; [t.join() for t in ts]
            wall = time.perf_counter() - t0
            _, p = git("-C", srv, "rev-list", "--count", "main")
            _, p0 = git("-C", os.path.join(REPOS, name), "rev-list", "--count", "main")
            rec("push", {"agents": k, "trial": trial, "first_round": first, "landed": sum(done),
                         "commits_added": int(p.stdout) - int(p0.stdout), "total_push_attempts": sum(attempts),
                         "max_attempts_one_agent": max(attempts), "retry_wall_s": round(wall, 2)})
            for a in agents: shutil.rmtree(a)

def t_repack():
    for name in ["r100k.git", "r1000k.git"]:
        srv = fresh(os.path.join(WORK, "rp-" + name))
        git("clone", "-q", "--bare", "--no-local", url(name), srv)
        b0 = du(srv)
        dt, _ = git("-C", srv, "repack", "-a", "-d", "-f", "--quiet")
        b1 = du(srv)
        dt2, _ = git("-C", srv, "commit-graph", "write", "--reachable")
        dt3, _ = git("-C", srv, "gc", "--quiet")
        rec("repack", {"repo": name, "bytes_after_clone": b0, "repack_adf_s": round(dt, 2), "bytes_after_repack": b1,
                       "commit_graph_s": round(dt2, 2), "gc_s": round(dt3, 2), "bytes_after_gc": du(srv)})
        shutil.rmtree(srv)

for t in sys.argv[3:]: globals()["t_" + t]()
