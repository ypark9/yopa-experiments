"""Local mock of AgentCore Gateway ordered model fallback with a circuit breaker.

Makes zero network calls. It encodes the DOCUMENTED rules from
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-rules-fallback.html
and makes every UNDOCUMENTED number an explicit, labeled assumption (see ASSUMED).

Documented rules encoded here:
  D1 chain = primary + 1..2 fallbacks, walked in order, each tried once
  D2 a response matching no trigger returns to the caller unchanged; 2xx/3xx never fall back
  D3 if every destination fails, the caller receives the LAST error
  D4 breaker per destination; open = skip; half-open = "a small portion" probes primary
  D5 UNROUTABLE advances the chain but does not feed the breaker
  D6 each outbound attempt = 1 gateway invocation; a skipped destination is not billed
  D7 once a stream has started, no fallback (caller gets partial + error)
  D8 no caller-facing indicator of which destination served the request
"""
from __future__ import annotations
import json, random, statistics, sys
from dataclasses import dataclass, field

GATEWAY_PRICE_PER_INVOCATION = 0.005 / 1000  # AgentCore pricing page, "Gateway API Invocations"

# Everything here is NOT published by AWS. Change it and re-run; the article reports a sweep.
ASSUMED = {
    "window": 20,            # breaker looks at the last N outcomes of a destination
    "min_calls": 10,         # ...needs at least this many before it can open
    "fail_rate_open": 0.5,   # ...opens at this failure rate
    "open_s": 30.0,          # stays open this long before half-open
    "probe_fraction": 0.1,   # half-open: share of requests let through to the destination
    "probes_to_close": 3,    # consecutive probe successes that close it
    "all_open_policy": "try_last",  # when every destination is open: try the last one anyway
    "abandoned_attempt_bills_input": True,  # a FIRST_BYTE_TIMEOUT attempt still bills input tokens
    "body_reports_served_model": True,      # response body `model` names the served model
}

@dataclass
class Outcome:
    kind: str            # ok | status | stall | conn | unroutable | midstream
    ms: float = 0.0
    code: int = 0

@dataclass
class Destination:
    name: str            # "target/model"
    model: str
    cost: float          # model cost units per successful request (illustrative)
    behave: object       # fn(t, rng) -> Outcome
    trigger_codes: tuple = ("429", "5XX")
    trigger_errors: tuple = ("CONNECTION_ERROR", "FIRST_BYTE_TIMEOUT", "UNROUTABLE")
    fbt_ms: float = 5000.0

def code_matches(code: int, pats) -> bool:
    for p in pats:
        if p.endswith("XX") and str(code)[0] == p[0]: return True
        if p == str(code): return True
    return False

class Breaker:
    def __init__(self, name, a, log):
        self.name, self.a, self.log = name, a, log
        self.state, self.hist, self.opened_at, self.probe_ok = "closed", [], 0.0, 0
    def _to(self, t, s, why):
        self.log.append({"t": round(t, 2), "dest": self.name, "from": self.state, "to": s, "why": why})
        self.state = s
    def allow(self, t, rng) -> bool:
        if self.state == "open" and t - self.opened_at >= self.a["open_s"]:
            self._to(t, "half_open", f"{self.a['open_s']:.0f}s open timer elapsed")
            self.probe_ok = 0
        if self.state == "closed": return True
        if self.state == "open": return False
        return rng.random() < self.a["probe_fraction"]
    def record(self, t, ok: bool, why: str):
        if self.state == "half_open":
            if ok:
                self.probe_ok += 1
                if self.probe_ok >= self.a["probes_to_close"]:
                    self._to(t, "closed", f"{self.probe_ok} probe successes"); self.hist = []
            else:
                self.opened_at = t; self._to(t, "open", f"probe failed ({why})")
            return
        self.hist = (self.hist + [ok])[-self.a["window"]:]
        fails = self.hist.count(False)
        if self.state == "closed" and len(self.hist) >= self.a["min_calls"] and fails / len(self.hist) >= self.a["fail_rate_open"]:
            self.opened_at = t; self._to(t, "open", f"{fails}/{len(self.hist)} recent attempts failed (last: {why})")

def gateway_call(t, chain, breakers, rng, a, breaker_on=True, stream=False):
    """One client request through the gateway. Returns dict describing what happened."""
    attempts, elapsed, model_cost, last_err = [], 0.0, 0.0, None
    allowed = [(not breaker_on) or breakers[d.name].allow(t, rng) for d in chain]
    if breaker_on and not any(allowed) and a["all_open_policy"] == "try_last":
        allowed[-1] = True
    for d, ok_to_try in zip(chain, allowed):
        if not ok_to_try:
            attempts.append({"dest": d.name, "result": "skipped_open"}); continue
        o = d.behave(t + elapsed / 1000, rng)
        if o.kind == "unroutable":
            # Not an outbound attempt, so assumed unbilled (D6 bills "outbound" attempts only)
            attempts.append({"dest": d.name, "result": "UNROUTABLE", "billed": False}); elapsed += o.ms
            last_err = "UNROUTABLE"
            if "UNROUTABLE" in d.trigger_errors: continue   # D5: no breaker feed
            break
        if o.kind == "stall":
            elapsed += d.fbt_ms
            if a["abandoned_attempt_bills_input"]: model_cost += d.cost * 0.3
            attempts.append({"dest": d.name, "result": "FIRST_BYTE_TIMEOUT", "billed": True})
            if breaker_on: breakers[d.name].record(t, False, "FIRST_BYTE_TIMEOUT")
            last_err = "FIRST_BYTE_TIMEOUT"; continue
        if o.kind == "conn":
            elapsed += o.ms; attempts.append({"dest": d.name, "result": "CONNECTION_ERROR", "billed": True})
            if breaker_on: breakers[d.name].record(t, False, "CONNECTION_ERROR")
            last_err = "CONNECTION_ERROR"; continue
        if o.kind == "status":
            elapsed += o.ms; attempts.append({"dest": d.name, "result": str(o.code), "billed": True})
            if code_matches(o.code, d.trigger_codes):
                if breaker_on: breakers[d.name].record(t, False, str(o.code))
                last_err = str(o.code); continue
            return dict(t=t, ok=False, err=str(o.code), served=None, ms=elapsed, attempts=attempts, model_cost=model_cost)
        if o.kind == "midstream":   # D7: first byte arrived, then the stream died
            elapsed += o.ms; model_cost += d.cost * 0.6
            attempts.append({"dest": d.name, "result": "200+midstream_error", "billed": True})
            if breaker_on: breakers[d.name].record(t, True, "stream started")
            return dict(t=t, ok=False, err="partial_stream", served=d.name, model=d.model, ms=elapsed, attempts=attempts, model_cost=model_cost)
        elapsed += o.ms; model_cost += d.cost
        attempts.append({"dest": d.name, "result": "200", "billed": True})
        if breaker_on: breakers[d.name].record(t, True, "200")
        return dict(t=t, ok=True, err=None, served=d.name, model=d.model, ms=elapsed, attempts=attempts, model_cost=model_cost)
    return dict(t=t, ok=False, err=last_err, served=None, ms=elapsed, attempts=attempts, model_cost=model_cost)  # D3

# ---- toy model outputs (to show shape drift; not real model behavior) -------------------------
def model_body(model: str, a) -> str:
    content = '{"label": "refund", "confidence": 0.91}' if model == "big" else '```json\n{"label": "refund"}\n```'
    body = {"content": [{"type": "text", "text": content}]}
    if a["body_reports_served_model"]: body["model"] = model
    return json.dumps(body)

def _shape(text):
    try:
        return ("json", tuple(sorted(json.loads(text))))
    except json.JSONDecodeError:
        return ("not-json",)

def client_check(body: str, requested: str, a):
    """Client was written against the requested model's output shape. Returns (shape_ok, model_field_differs)."""
    b = json.loads(body); text = b["content"][0]["text"]
    expected = json.loads(model_body(requested, a))["content"][0]["text"]
    return _shape(text) == _shape(expected), b.get("model", requested) != requested

# ---- SDK retry wrapper (boto3 standard mode retries throttling and transient 5xx) --------------
def sdk_call(t, chain, breakers, rng, a, breaker_on, max_attempts=3):
    total_ms, results = 0.0, []
    for i in range(max_attempts):
        r = gateway_call(t + total_ms / 1000, chain, breakers, rng, a, breaker_on)
        results.append(r); total_ms += r["ms"]
        if r["ok"] or r["err"] not in ("429", "500", "502", "503", "504", "FIRST_BYTE_TIMEOUT", "CONNECTION_ERROR"):
            break
        total_ms += 1000 * min(20, 2 ** i) * 0.5   # mean of full-jitter backoff
    return results, total_ms

def window(t0, t1, bad: Outcome, good_ms=1200):
    return lambda t, rng: bad if t0 <= t < t1 else Outcome("ok", good_ms * rng.uniform(0.8, 1.25))

def healthy(ms=1200):
    return lambda t, rng: Outcome("ok", ms * rng.uniform(0.8, 1.25))

def run(name, chain, a, breaker_on=True, rps=5, dur=300, sdk_retries=False, recover_at=180, requested="big", seed=7):
    rng = random.Random(seed); log = []
    breakers = {d.name: Breaker(d.name, a, log) for d in chain}
    reqs = []
    for k in range(int(rps * dur)):
        t = k / rps
        if sdk_retries:
            rs, ms = sdk_call(t, chain, breakers, rng, a, breaker_on)
            final = rs[-1]; atts = [x for r in rs for x in r["attempts"]]
            mc = sum(r["model_cost"] for r in rs)
        else:
            final = gateway_call(t, chain, breakers, rng, a, breaker_on); ms = final["ms"]
            atts, mc = final["attempts"], final["model_cost"]
        rec = dict(t=t, ok=final["ok"], err=final["err"], served=final["served"], ms=ms,
                   billed=sum(1 for x in atts if x.get("billed")), skipped=sum(1 for x in atts if x["result"] == "skipped_open"),
                   model_cost=mc, attempts=atts)
        if final["ok"]:
            rec["schema_ok"], rec["model_flag"] = client_check(model_body(final["model"], a), requested, a)
        reqs.append(rec)
    return summarize(name, reqs, log, chain, recover_at, breaker_on)

def pct(xs, p):
    xs = sorted(xs); return round(xs[min(len(xs) - 1, int(p / 100 * len(xs)))], 1) if xs else None

def summarize(name, reqs, log, chain, recover_at, breaker_on):
    served = {}
    for r in reqs: served[r["served"] or "ERROR"] = served.get(r["served"] or "ERROR", 0) + 1
    after = [r for r in reqs if r["t"] >= recover_at]
    prim = chain[0].name
    okr = [r for r in reqs if r["ok"]]
    s = {
        "scenario": name, "breaker": "ENABLED" if breaker_on else "DISABLED", "requests": len(reqs),
        "caller_ok": sum(r["ok"] for r in reqs), "caller_errors": sum(not r["ok"] for r in reqs),
        "served_by": served,
        "gateway_invocations_billed": sum(r["billed"] for r in reqs),
        "gateway_cost_usd": round(sum(r["billed"] for r in reqs) * GATEWAY_PRICE_PER_INVOCATION, 6),
        "attempts_skipped_by_breaker": sum(r["skipped"] for r in reqs),
        "model_cost_units": round(sum(r["model_cost"] for r in reqs), 2),
        "latency_ms_p50": pct([r["ms"] for r in reqs], 50), "latency_ms_p95": pct([r["ms"] for r in reqs], 95),
        "latency_ms_max": pct([r["ms"] for r in reqs], 100),
        "served_off_primary_after_recovery": sum(1 for r in after if r["served"] and r["served"] != prim),
        "schema_invalid_among_200s": sum(1 for r in okr if not r["schema_ok"]),
        "flagged_by_model_field": sum(1 for r in okr if r["model_flag"]),
        "breaker_transitions": log,
    }
    return s

def scenarios(a):
    out = []
    # A: primary throttled 60..180 s; fallback is the same model elsewhere
    def chainA():
        return [Destination("bedrock/big", "big", 1.0, window(60, 180, Outcome("status", 60, 429))),
                Destination("openai/big", "big", 1.0, healthy(1400)),
                Destination("bedrock/small", "small", 0.25, healthy(700))]
    for on in (True, False): out.append(run("A_primary_throttled", chainA(), a, on))
    # B: primary stalls (accepts, never sends first byte) 60..180 s
    for fbt in (5000, 1000):
        for on in (True, False):
            c = chainA(); c[0].behave = window(60, 180, Outcome("stall")); c[0].fbt_ms = fbt
            out.append(run(f"B_primary_stalls_fbt{fbt}", c, a, on))
    # C: primary and same-model fallback both down -> silent degrade to the small model
    c = chainA(); c[1].behave = window(60, 180, Outcome("status", 300, 503))
    out.append(run("C_silent_degrade", c, a, True))
    # D: everything throttled (shared account quota / regional event), with SDK retries on top
    for on in (True, False):
        c = [Destination("bedrock/big", "big", 1.0, window(60, 180, Outcome("status", 60, 429))),
             Destination("openai/big", "big", 1.0, window(60, 180, Outcome("status", 80, 429), 1400)),
             Destination("bedrock/small", "small", 0.25, window(60, 180, Outcome("status", 60, 429), 700))]
        out.append(run("D_all_throttled_with_sdk_retries", c, a, on, sdk_retries=True))
    # E: cheap primary that flaps (30% 503s) vs a 4x pricier fallback: the doc's reason to disable the breaker
    def flappy(t, rng):
        if 60 <= t < 180 and rng.random() < 0.3: return Outcome("status", 200, 503)
        return Outcome("ok", 700 * rng.uniform(0.8, 1.25))
    for on in (True, False):
        c = [Destination("bedrock/small", "small", 0.25, flappy), Destination("openai/big", "big", 1.0, healthy(1400))]
        out.append(run("E_cheap_flappy_primary", c, a, on, requested="small"))
    # F: misconfigured primary (target lacks the API path) -> UNROUTABLE every time, never opens
    c = chainA(); c[0].behave = lambda t, rng: Outcome("unroutable", 3)
    out.append(run("F_unroutable_primary", c, a, True, recover_at=0))
    # G: streaming, primary dies mid-stream 60..180 s -> no fallback
    c = chainA(); c[0].behave = window(60, 180, Outcome("midstream", 900))
    out.append(run("G_midstream_failure", c, a, True))
    return out

def sweep(a):
    rows = []
    for open_s in (5, 15, 30, 60):
        for probe in (0.05, 0.1, 0.25):
            b = dict(a, open_s=open_s, probe_fraction=probe)
            ra = run("A_primary_throttled", [Destination("bedrock/big", "big", 1.0, window(60, 180, Outcome("status", 60, 429))),
                                             Destination("openai/big", "big", 1.0, healthy(1400)),
                                             Destination("bedrock/small", "small", 0.25, healthy(700))], b, True)
            def flappy(t, rng):
                if 60 <= t < 180 and rng.random() < 0.3: return Outcome("status", 200, 503)
                return Outcome("ok", 700 * rng.uniform(0.8, 1.25))
            re_ = run("E", [Destination("bedrock/small", "small", 0.25, flappy), Destination("openai/big", "big", 1.0, healthy(1400))], b, True, requested="small")
            rows.append({"open_s": open_s, "probe_fraction": probe,
                         "A_off_primary_after_recovery": ra["served_off_primary_after_recovery"],
                         "A_billed": ra["gateway_invocations_billed"],
                         "E_model_cost_units": re_["model_cost_units"], "E_caller_errors": re_["caller_errors"]})
    return rows

if __name__ == "__main__":
    a = dict(ASSUMED)
    res = {"assumed": a, "gateway_price_per_invocation_usd": GATEWAY_PRICE_PER_INVOCATION,
           "scenarios": scenarios(a), "sweep_open_s_probe": sweep(a)}
    path = sys.argv[1] if len(sys.argv) > 1 else "results/result-mock.json"
    with open(path, "w") as f: json.dump(res, f, indent=1)
    for s in res["scenarios"]:
        k = {x: s[x] for x in ("scenario", "breaker", "caller_ok", "caller_errors", "served_by", "gateway_invocations_billed",
                               "attempts_skipped_by_breaker", "model_cost_units", "latency_ms_p50", "latency_ms_p95",
                               "served_off_primary_after_recovery", "schema_invalid_among_200s", "flagged_by_model_field")}
        k["transitions"] = len(s["breaker_transitions"]); print(json.dumps(k))
    for r in res["sweep_open_s_probe"]: print("SWEEP", json.dumps(r))
