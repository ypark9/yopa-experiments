"""Which GitHub Actions OIDC subjects would an AWS role trust policy accept?
Local, documentation-based simulation. No AWS call, no GitHub token.
- Subject formats come from GitHub's OIDC reference ("Example subject claims",
  "Immutable subject claims"), fetched 2026-11-20.
- Matching follows IAM's documented condition operators: StringEquals is exact and
  case-sensitive; StringLike is case-sensitive with * (any run of characters, including
  '/' and ':') and ? (one character).
- create_time_guard() follows the IAM user guide rule for GitHub as the trusted IdP:
  the sub condition must be present and not solely a wildcard (* and ?) or null.
This does NOT model the OIDC provider's audience (client ID) list, session policies,
or anything else STS checks."""
import json, re

def string_like(pattern, value):
    rx = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    return re.fullmatch(rx, value, flags=re.S) is not None

def matches(policy, sub):
    op, pats = policy["op"], policy["sub"]
    pats = pats if isinstance(pats, list) else [pats]
    if op == "StringEquals": return any(sub == p for p in pats)
    if op == "StringLike": return any(string_like(p, sub) for p in pats)
    raise ValueError(op)

def create_time_guard(policy):
    pats = policy["sub"] if isinstance(policy["sub"], list) else [policy["sub"]]
    return all(p and set(p) - set("*?") for p in pats)

ORG, REPO, OID, RID = "acme", "deploy-infra", "1111111", "2222222"
legacy = f"repo:{ORG}/{REPO}"
immut = f"repo:{ORG}@{OID}/{REPO}@{RID}"
TOKENS = [
 ("main_push",        "Push to main in acme/deploy-infra", f"{legacy}:ref:refs/heads/main"),
 ("feature_push",     "Push to any other branch in the same repo", f"{legacy}:ref:refs/heads/try-something"),
 ("pull_request",     "A pull_request run in the same repo", f"{legacy}:pull_request"),
 ("tag_push",         "A tag push in the same repo", f"{legacy}:ref:refs/tags/v1.2.3"),
 ("env_prod_main",    "Job with environment: production, run from main", f"{legacy}:environment:production"),
 ("env_prod_feature", "Job with environment: production, run from a feature branch (same sub)", f"{legacy}:environment:production"),
 ("other_repo",       "Push to main in another repo of the same org (acme/website)", f"repo:{ORG}/website:ref:refs/heads/main"),
 ("lookalike_org",    "Push to main in a different owner whose name starts with acme (acme-labs/x)", "repo:acme-labs/x:ref:refs/heads/main"),
 ("immutable_main",   "Push to main, repo on the immutable sub format (created after 2026-07-15 or opted in)", f"{immut}:ref:refs/heads/main"),
 ("immutable_lookalike", "Lookalike owner on the immutable format (acme-labs@9999999/x@8888888)", "repo:acme-labs@9999999/x@8888888:ref:refs/heads/main"),
]
POLICIES = [
 ("exact_branch",   "StringEquals, exact branch (AWS docs first example)", "StringEquals", f"{legacy}:ref:refs/heads/main"),
 ("repo_any",       "StringLike repo:acme/deploy-infra:* (AWS docs 'any branch' example)", "StringLike", f"{legacy}:*"),
 ("org_any",        "StringLike repo:acme/* (AWS docs org-wide example)", "StringLike", f"repo:{ORG}/*"),
 ("org_prefix_typo","StringLike repo:acme* (slash forgotten)", "StringLike", f"repo:{ORG}*"),
 ("env_exact",      "StringEquals repo:acme/deploy-infra:environment:production", "StringEquals", f"{legacy}:environment:production"),
 ("immutable_exact","StringEquals on the immutable format, exact branch", "StringEquals", f"{immut}:ref:refs/heads/main"),
 ("immutable_org",  "StringLike repo:acme@1111111/* (immutable, org pinned by ID)", "StringLike", f"repo:{ORG}@{OID}/*"),
]
rows = []
for pid, pdesc, op, sub in POLICIES:
    pol = {"op": op, "sub": sub}
    rows.append({"policy": pid, "description": pdesc, "operator": op, "sub_condition": sub,
                 "passes_iam_create_time_guard_by_docs": create_time_guard(pol),
                 "accepts": {tid: matches(pol, tsub) for tid, _, tsub in TOKENS}})
out = {"tokens": [{"id": t, "description": d, "sub": s} for t, d, s in TOKENS], "matrix": rows}
json.dump(out, open("results/matrix.json", "w"), indent=2)
w = max(len(t[0]) for t in TOKENS)
print("policy".ljust(16), "guard", " ".join(t[0][:8].ljust(8) for t in TOKENS))
for r in rows:
    print(r["policy"].ljust(16), str(r["passes_iam_create_time_guard_by_docs"]).ljust(5),
          " ".join(("YES" if r["accepts"][t[0]] else "-").ljust(8) for t in TOKENS))
