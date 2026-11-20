"""Where does a secret end up in Temporal workflow history?
Runs against a local `temporal server start-dev` (no auth, in-memory). Every secret is a
fake marker string (FAKE-...); nothing real is used. A second, key-less client then reads
history with the temporal CLI (see read_as_other_client.py)."""
import asyncio, base64, dataclasses, json, os, sys
from datetime import timedelta
from cryptography.fernet import Fernet
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import SearchAttributeKey, TypedSearchAttributes, SearchAttributePair, RetryPolicy
from temporalio.converter import (DataConverter, PayloadCodec, DefaultFailureConverterWithEncodedAttributes)
from temporalio.api.common.v1 import Payload
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions

KEY = Fernet.generate_key()  # lives only in this process; the "other client" never sees it

class FernetCodec(PayloadCodec):
    def __init__(self): self.f = Fernet(KEY)
    async def encode(self, payloads):
        return [Payload(metadata={"encoding": b"binary/encrypted"},
                        data=self.f.encrypt(p.SerializeToString())) for p in payloads]
    async def decode(self, payloads):
        out = []
        for p in payloads:
            if p.metadata.get("encoding") != b"binary/encrypted": out.append(p); continue
            q = Payload(); q.ParseFromString(self.f.decrypt(p.data)); out.append(q)
        return out

SECRET_STORE = {}  # stands in for a secrets manager the activity can read by name

@activity.defn
async def build_with_env(env: dict) -> str:
    return f"built with {len(env)} variables"

@activity.defn
async def build_with_ref(secret_name: str) -> str:
    value = SECRET_STORE[secret_name]          # fetched inside the activity
    return f"built, used {secret_name} ({len(value)} chars)"

@activity.defn
async def build_that_fails(env: dict) -> str:
    # a typical careless error message that echoes the value
    raise ApplicationError(f"provider rejected key {env['OPENAI_API_KEY']}", non_retryable=True)

@workflow.defn
class Build:
    @workflow.run
    async def run(self, mode: str, payload: dict) -> str:
        opts = dict(start_to_close_timeout=timedelta(seconds=10), retry_policy=RetryPolicy(maximum_attempts=1))
        if mode == "env":
            return await workflow.execute_activity(build_with_env, payload["env"], **opts)
        if mode == "ref":
            return await workflow.execute_activity(build_with_ref, payload["secret_name"], **opts)
        if mode == "fail":
            try:
                return await workflow.execute_activity(build_that_fails, payload["env"], **opts)
            except Exception as e:
                return "build failed"
        return "noop"

def conv(codec: bool, encode_failures: bool):
    kw = {}
    if codec: kw["payload_codec"] = FernetCodec()
    if encode_failures: kw["failure_converter_class"] = DefaultFailureConverterWithEncodedAttributes
    return dataclasses.replace(DataConverter.default, **kw)

SA = SearchAttributeKey.for_keyword("BuildNote")

CASES = [
 # id, description, codec, encode_failures, mode, where the secret is placed
 ("t1", "secret inside workflow input, no codec", False, False, "env", "input"),
 ("t2", "only a secret name in workflow input; activity reads the value itself, no codec", False, False, "ref", "ref"),
 ("t3", "secret inside workflow input, encryption codec on", True, False, "env", "input"),
 ("t4", "codec on, activity error message echoes the secret (default failure converter)", True, False, "fail", "input"),
 ("t5", "codec on plus encoded failure attributes, same failing activity", True, True, "fail", "input"),
 ("t6", "codec on, secret placed in workflow memo", True, False, "noop", "memo"),
 ("t7", "codec on, secret placed in a custom search attribute", True, False, "noop", "search_attr"),
]

async def main():
    results = []
    for cid, desc, codec, encfail, mode, where in CASES:
        marker = f"FAKE-{cid}-sk-0000000000000000"
        SECRET_STORE["OPENAI_API_KEY"] = marker
        client = await Client.connect("localhost:7233", data_converter=conv(codec, encfail))
        tq = f"tq-{cid}"
        payload = {"repo": "example/app", "env": {"OPENAI_API_KEY": marker, "NODE_ENV": "production"}} \
            if where == "input" else {"repo": "example/app", "secret_name": "OPENAI_API_KEY"}
        start_kw = {}
        if where == "memo": start_kw["memo"] = {"note": f"key={marker}"}
        if where == "search_attr":
            start_kw["search_attributes"] = TypedSearchAttributes([SearchAttributePair(SA, f"key={marker}")])
        async with Worker(client, task_queue=tq, workflows=[Build],
                          activities=[build_with_env, build_with_ref, build_that_fails],
                          workflow_runner=SandboxedWorkflowRunner(restrictions=SandboxRestrictions.default.with_passthrough_modules("cryptography"))):
            out = await client.execute_workflow(Build.run, args=[mode, payload], id=f"build-{cid}",
                                                task_queue=tq, **start_kw)
        results.append({"case": cid, "description": desc, "codec": codec, "encoded_failures": encfail,
                        "marker": marker, "workflow_result_seen_by_owner": out})
        print(cid, out, flush=True)
    json.dump(results, open("results/cases_run.json", "w"), indent=2)

if __name__ == "__main__":
    os.makedirs("results", exist_ok=True)
    asyncio.run(main())
