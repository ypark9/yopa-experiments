"""Does the system prompt reach the Evaluate input? One agent run, no Evaluate call."""
import json
import run
from strands_evals.telemetry import StrandsEvalsTelemetry
from bedrock_agentcore.evaluation.span_to_adot_serializer import convert_strands_to_adot

t = StrandsEvalsTelemetry().setup_in_memory_exporter()
run.CONDITION["doc"] = "fee"
ans, spans = run.run_agent(t, "sysprompt-check")
adot = json.dumps(convert_strands_to_adot(spans))
raw = json.dumps([dict(s.attributes or {}) for s in spans] + [[dict(e.attributes or {}) for e in s.events] for s in spans], default=str)
print("answer has $120:", "$120" in ans)
print("'processing fee' in raw OTel spans:", "processing fee" in raw)
print("'processing fee' in ADOT sent to Evaluate:", "processing fee" in adot)
print("'Company practice' in raw OTel:", "Company practice" in raw); print("'Company practice' in ADOT:", "Company practice" in adot)
