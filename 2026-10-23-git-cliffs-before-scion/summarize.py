#!/usr/bin/env python3
"""Turn results/raw.log into the markdown tables in README.md. For a test that
was rerun, rows after the last 'note' line for that test win."""
import json, os, statistics
rows = [json.loads(l) for l in open(os.path.join(os.path.dirname(__file__), "results", "raw.log"))]
last_note = max(i for i, r in enumerate(rows) if r["test"] == "note")
lazy = [r for i, r in enumerate(rows) if r["test"] == "lazy" and i > last_note]
def tab(h, rs): print("| " + " | ".join(h) + " |\n|" + "---|" * len(h)); [print("| " + " | ".join(str(x) for x in r) + " |") for r in rs]; print()
tab(["repo", "files", "clone+checkout s", "index MB", "status s", "status -uno s", "status untracked cache s", "status after 1 edit s", "sparse set (1 dir) s", "files after sparse", "status sparse s"],
    [[r["repo"], r["files_on_disk"], r["clone_checkout_s"], round(r["index_bytes"]/1e6, 1), r["status_default_s"], r["status_uno_s"], r["status_untracked_cache_s"], r["status_one_edit_s"], r["sparse_set_s"], r["sparse_files_on_disk"], r["status_sparse_s"]] for r in rows if r["test"] == "status"])
print("fsmonitor:", {r["fsmonitor_daemon_start"] for r in rows if r["test"] == "status"}, "\n")
tab(["repo", "variant", "clone s", "sparse set s", ".git MB", "objects", "files on disk"],
    [[r["repo"], r["variant"], r["clone_s"], r.get("sparse_set_s", ""), round(r["git_dir_bytes"]/1e6, 1), r.get("objects_in_pack", ""), r.get("files_on_disk", "")] for r in rows if r["test"] == "clone"])
tab(["clone", "command", "time s", "lazy fetches", "new packs"], [[r["clone"], "`git " + r["cmd"] + "`", r["time_s"], r["fetch_processes"], r["new_packs"]] for r in lazy])
by = {}
for r in rows:
    if r["test"] == "push": by.setdefault(r["agents"], []).append(r)
tab(["agents", "trials", "landed on first try (each trial)", "first-try rejections", "total push attempts (each trial)", "max attempts by one agent", "retry wall s (median)"],
    [[k, len(v), ", ".join(str(t["first_round"].get("ok", 0)) for t in v), ", ".join(str(k - t["first_round"].get("ok", 0)) for t in v),
      ", ".join(str(t["total_push_attempts"]) for t in v), max(t["max_attempts_one_agent"] for t in v), statistics.median(t["retry_wall_s"] for t in v)] for k, v in sorted(by.items())])
tab(["repo", "bytes after clone MB", "repack -adf s", "after repack MB", "commit-graph s", "gc s"],
    [[r["repo"], round(r["bytes_after_clone"]/1e6, 1), r["repack_adf_s"], round(r["bytes_after_repack"]/1e6, 1), r["commit_graph_s"], r["gc_s"]] for r in rows if r["test"] == "repack"])
