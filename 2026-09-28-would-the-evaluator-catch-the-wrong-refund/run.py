"""Would the built-in evaluators catch the $40 refund?

A Strands agent answers a refund question using a policy-search tool.
- stale: the tool returns last quarter's policy ($40). The answer is wrong.
- fresh: the tool returns the current policy ($140). The answer is right.

Each run's spans are captured in memory (nothing goes to CloudWatch) and scored
by the AgentCore Evaluate API, with and without ground truth.

AWS calls made: bedrock-runtime Converse (agent + nothing else) and
bedrock-agentcore Evaluate. No resources are created.
"""

import argparse
import json
import os
import re
import sys
import time
import uuid

import boto3
from botocore.config import Config
from strands import Agent, tool
from strands.models import BedrockModel
from strands_evals.telemetry import StrandsEvalsTelemetry
from bedrock_agentcore.evaluation.span_to_adot_serializer import convert_strands_to_adot

REGION = os.environ.get("EV_REGION", "us-east-1")
MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
QUESTION = ("I'm on the Pro plan and I cancelled 10 days after my renewal. "
            "How much refund am I owed?")
CURRENT = "$140"

DOCS = {
    "stale": ("Refund policy, version 2026-Q2 (effective 2026-04-01).\n"
              "Pro plan: if you cancel within 30 days of renewal, you get a refund of $40.\n"
              "Refunds are paid to the original payment method within 5 business days."),
    "fresh": ("Refund policy, version 2026-Q3 (effective 2026-07-01).\n"
              "Pro plan: if you cancel within 30 days of renewal, you get a refund of $140.\n"
              "Refunds are paid to the original payment method within 5 business days."),
}

CONDITION = {"doc": "stale"}


@tool
def search_policy_docs(query: str) -> str:
    """Search the company's policy documents and return the best match."""
    return DOCS["fresh" if CONDITION["doc"] == "fee" else CONDITION["doc"]]


BASE_PROMPT = ("You are a customer support agent for a software company. "
               "Always look up the refund policy with the tool before answering.")
# Positive control: the agent contradicts its own source (the doc says $140,
# the prompt makes it deduct a fee the doc never mentions).
FEE_PROMPT = BASE_PROMPT + (" Company practice: always deduct a $20 processing fee from any refund "
                            "and state the final amount only.")


# (label, evaluator id, which ground truth to send)
EVALS = [
    ("correctness_no_gt", "Builtin.Correctness", None),
    ("correctness_gt", "Builtin.Correctness", "expected"),
    ("faithfulness", "Builtin.Faithfulness", None),
    ("helpfulness", "Builtin.Helpfulness", None),
    ("goal_no_gt", "Builtin.GoalSuccessRate", None),
    ("goal_assert", "Builtin.GoalSuccessRate", "assert"),
]


def run_agent(telemetry, session_id):
    telemetry.in_memory_exporter.clear()
    agent = Agent(
        model=BedrockModel(model_id=MODEL, region_name="us-east-1", temperature=0.3),
        tools=[search_policy_docs],
        system_prompt=FEE_PROMPT if CONDITION["doc"] == "fee" else BASE_PROMPT,
        trace_attributes={"session.id": session_id},
        callback_handler=None,
    )
    out = str(agent(QUESTION))
    spans = list(telemetry.in_memory_exporter.get_finished_spans())
    return out, spans


def evaluate(client, eval_id, adot, session_id, trace_id, gt):
    kw = {"evaluatorId": eval_id, "evaluationInput": {"sessionSpans": adot}}
    if gt == "expected":
        kw["evaluationReferenceInputs"] = [{
            "context": {"spanContext": {"sessionId": session_id, "traceId": trace_id}},
            "expectedResponse": {"text": f"You are owed a refund of {CURRENT}."},
        }]
    elif gt == "assert":
        kw["evaluationReferenceInputs"] = [{
            "context": {"spanContext": {"sessionId": session_id}},
            "assertions": [{"text": f"The agent told the customer they are owed {CURRENT}."}],
        }]
    for attempt in range(4):
        try:
            return client.evaluate(**kw)["evaluationResults"]
        except client.exceptions.ThrottlingException:
            time.sleep(5 * (attempt + 1))
    return [{"errorCode": "Throttled", "errorMessage": "gave up after 4 tries"}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--conditions", default="stale,fresh")
    a = ap.parse_args()

    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    client = boto3.client("bedrock-agentcore", region_name=REGION,
                          config=Config(read_timeout=300, retries={"max_attempts": 3, "mode": "adaptive"}))
    with open(a.out, "x") as f:  # refuse to overwrite an earlier run
        for cond in a.conditions.split(","):
            CONDITION["doc"] = cond
            for i in range(a.n):
                sid = f"refund-{cond}-{i}-{uuid.uuid4().hex[:8]}"
                answer, spans = run_agent(telemetry, sid)
                adot = convert_strands_to_adot(spans)
                trace_id = next((d["traceId"] for d in adot if "traceId" in d), None)
                said = sorted(set(re.findall(r"\$\d+", answer)))
                row = {"cond": cond, "i": i, "session": sid, "trace": trace_id,
                       "answer": answer, "dollars": said, "n_spans": len(spans),
                       "n_adot": len(adot), "scores": {}}
                for label, eid, gt in EVALS:
                    res = evaluate(client, eid, adot, sid, trace_id, gt)
                    row["scores"][label] = [
                        {k: r.get(k) for k in ("value", "label", "explanation", "errorCode",
                                               "errorMessage", "ignoredReferenceInputFields", "tokenUsage")}
                        for r in res]
                f.write(json.dumps(row) + "\n"); f.flush()
                brief = {k: [(r["value"], r["label"]) for r in v] for k, v in row["scores"].items()}
                print(cond, i, said, brief, flush=True)
    print("## done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
