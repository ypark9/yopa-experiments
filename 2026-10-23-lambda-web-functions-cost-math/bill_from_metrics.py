"""Turn the free AWS/Lambda/Web metrics from an owner run into an estimated bill. No AWS calls.
Usage: python bill_from_metrics.py <ExecutedRequests> <EnvironmentCPUTime_ms> <EnvironmentActiveTime_ms> <EnvironmentMaxMemoryUsage_MB>
Memory uses the PEAK per-environment usage, so the memory line is an upper bound."""
import sys
from cost_model import WEB_VCPU_S, WEB_GB_S, WEB_REQ, EV
req, cpu_ms, active_ms, mem_mb = map(float, sys.argv[1:5])
cpu = cpu_ms / 1000 * WEB_VCPU_S
mem = active_ms / 1000 * (mem_mb / 1024) * WEB_GB_S
fee = req * WEB_REQ
print(f"requests {req:.0f}: ${fee:.6f}\nactive vCPU {cpu_ms/1000:.1f} s: ${cpu:.6f}\n"
      f"memory {active_ms/1000:.0f} env-s x {mem_mb:.0f} MB (peak): <= ${mem:.6f}\n"
      f"total <= ${fee+cpu+mem:.6f}   |   CPU per request: {cpu_ms/max(req,1):.2f} ms")
