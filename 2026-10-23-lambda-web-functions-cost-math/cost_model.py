"""Desk math for Lambda Web Functions vs Event Functions. No AWS calls.
Prices: US East (N. Virginia), first tier, free tier excluded, fetched 2026-10-23 from
https://aws.amazon.com/lambda/pricing/ (Web, worked examples) and the page's public price map
https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/lambda/USD/current/lambda.json (Event)."""
import json, math
WEB_VCPU_S, WEB_GB_S, WEB_REQ = 0.0000276944, 0.0000036667, 0.30e-6
EV = {"x86": (0.0000166667, 0.20e-6), "arm": (0.0000133334, 0.20e-6)}
MONTH = 2_592_000                        # 30-day month, as in AWS's examples
VCPU_MB = 1769                           # "At 1,769 MB, a function has the equivalent of one vCPU"
EX = [  # AWS's four worked examples: requests, end-to-end s, active CPU s, memory GB
    ("1 SSR web app",       15e6, 0.150, 0.040, 0.49),
    ("2 I/O-heavy API",     10e6, 0.200, 0.050, 0.29),
    ("3 Auth middleware",  100e6, 0.050, 0.012, 0.14),
    ("4 LLM streaming",      5e6, 3.000, 0.200, 0.50),
]
def web(n, cpu, gb, envs=1.0):
    return n * cpu * WEB_VCPU_S + envs * gb * MONTH * WEB_GB_S + n * WEB_REQ
def event(n, dur, cpu, gb, arch, cpu_scaled=False):
    p_gb, p_req = EV[arch]
    if cpu_scaled:  # a sub-1-vCPU Event function stretches the CPU part of the request
        share = min(1.0, gb * 1024 / VCPU_MB)
        dur = (dur - cpu) + cpu / share
    return n * dur * gb * p_gb + n * p_req, dur
rows = []
for name, n, dur, cpu, gb in EX:
    r = {"example": name, "web_aws_assumption": round(web(n, cpu, gb), 2)}
    for arch in ("arm", "x86"):
        r[f"event_{arch}"] = round(event(n, dur, cpu, gb, arch)[0], 2)
        c, d2 = event(n, dur, cpu, gb, arch, cpu_scaled=True)
        r[f"event_{arch}_cpu_scaled"] = round(c, 2); r["scaled_duration_ms"] = round(d2 * 1000)
    # what if the fleet is not "exactly one environment at all times"?
    r["web_memory_one_env"] = round(gb * MONTH * WEB_GB_S, 2)
    r["web_with_3_envs"] = round(web(n, cpu, gb, envs=3), 2)
    rows.append(r)
# request-fee floor: Web charges $0.10/M more per request than Event, before any compute.
# Memory sizes are MB / 1024 (binary GB), the conversion AWS bills with: 128 MB = 0.125 GB.
floor = {f"{arch}_{mb}MB_ms": round(0.10e-6 / (EV[arch][0] * mb / 1024) * 1000, 1)
         for arch in ("arm", "x86") for mb in (128, 512, 1024)}
# break-even CPU share: Event(arm) wall-time cost vs Web CPU cost, per request, memory ignored
be = {f"{mb}MB": round(mb / 1024 * EV["arm"][0] / WEB_VCPU_S, 3) for mb in (128, 512, 1024, 2048)}
# one always-on environment's memory cost per month
env_month = {f"{gb}GB": round(gb * MONTH * WEB_GB_S, 2) for gb in (0.25, 0.5, 1.0, 2.0)}
out = {"examples": rows, "request_fee_floor_event_cheaper_if_duration_below": floor,
       "cpu_share_breakeven_web_cheaper_below__memory_ignored": be, "one_env_memory_per_month": env_month}
if __name__ == "__main__":
    print(json.dumps(out, indent=1)); json.dump(out, open("result-cost-model.json", "w"), indent=1)
