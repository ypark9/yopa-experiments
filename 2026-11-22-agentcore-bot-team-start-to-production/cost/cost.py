"""Turns the usage measured on my prototype (6 days, 2026-11-17 to 11-22) into dollars.

The inputs are counts read from the prototype's runtime logs and CloudWatch metrics. The prices are the
public list prices on 2026-11-22. Arithmetic only: this script makes no AWS or model calls.
"""
M = 1_000_000

# Measured usage (whole 6 days)
OPUS_IN, OPUS_OUT = 321_191, 63_710        # model-call spans, Claude Opus 5.5 (50 calls)
SONNET_IN, SONNET_OUT = 398, 676           # model-call spans, Claude Sonnet 5.5 (7 calls)
RUN_IN, RUN_OUT = 326_029, 68_813          # agent-run spans (32 runs); a little more than the model calls
VCPU_HOURS, GB_HOURS = 0.048827, 3.31473   # CloudWatch CPUUsed-vCPUHours, MemoryUsed-GBHours
MEMORY_EVENTS = 112                        # AgentCore Memory CreateEvent

# One chain: a lead bot and three specialists, 121 seconds end to end
CHAIN = [("lead", 21_194, 2_945), ("monitor", 9_267, 4_185),
         ("root-cause 1", 22_976, 4_363), ("root-cause 2", 21_245, 4_556)]

# Public prices, 2026-11-22
OPUS = (4.00, 20.00)       # $ per 1M input / output tokens (Anthropic pricing page)
SONNET = (2.00, 10.00)
REGIONAL = 1.10            # regional ("us.") endpoints cost 10% more than global on Bedrock
VCPU_HOUR, GB_HOUR = 0.0895, 0.00945   # AgentCore Runtime, v1 platform
MEMORY_PER_GB = 1.00       # AgentCore Memory ingestion; each event counts as 12 KB to 64 KB

def tokens(inp, out, price):
    return inp * price[0] / M + out * price[1] / M

model_low = tokens(OPUS_IN, OPUS_OUT, OPUS) + tokens(SONNET_IN, SONNET_OUT, SONNET)
gap_in, gap_out = RUN_IN - OPUS_IN - SONNET_IN, RUN_OUT - OPUS_OUT - SONNET_OUT
model_high = (model_low + tokens(gap_in, gap_out, OPUS)) * REGIONAL
runtime = VCPU_HOURS * VCPU_HOUR + GB_HOURS * GB_HOUR
mem_low = MEMORY_EVENTS * 12 * 1024 / 1024**3 * MEMORY_PER_GB
mem_high = MEMORY_EVENTS * 64 * 1024 / 1024**3 * MEMORY_PER_GB

print("## Six days of my prototype")
print(f"agent runs: 32, model calls: 57, tokens: {RUN_IN + RUN_OUT:,} ({RUN_IN:,} in, {RUN_OUT:,} out)")
print(f"unmatched tokens priced as Opus in the high case: {gap_in:,} in, {gap_out:,} out")
print(f"model tokens   ${model_low:.2f} to ${model_high:.2f}")
print(f"runtime        ${runtime:.3f}  ({VCPU_HOURS} vCPU-h x ${VCPU_HOUR} + {GB_HOURS} GB-h x ${GB_HOUR})")
print(f"memory         ${mem_low:.3f} to ${mem_high:.3f}  ({MEMORY_EVENTS} events)")
low, high = model_low + runtime + mem_low, model_high + runtime + mem_high
print(f"total          ${low:.2f} to ${high:.2f}; model share {model_low / low:.1%} to {model_high / high:.1%}")

print()
print("## One chain (lead + 3 specialists, Opus 5.5)")
total_in = total_out = 0
for name, i, o in CHAIN:
    total_in, total_out = total_in + i, total_out + o
    print(f"{name:<13} {i:>7,} in {o:>6,} out  ${tokens(i, o, OPUS):.3f} to ${tokens(i, o, OPUS) * REGIONAL:.3f}")
c = tokens(total_in, total_out, OPUS)
print(f"{'total':<13} {total_in:>7,} in {total_out:>6,} out  ${c:.2f} to ${c * REGIONAL:.2f}")
print(f"runtime per session (average of 15): ${(VCPU_HOURS * VCPU_HOUR + GB_HOURS * GB_HOUR) / 15:.4f}")
