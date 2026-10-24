"""Validate owner_run.py's request shapes against the local botocore service model. No network."""
import json, botocore, botocore.session
from botocore.validate import ParamValidator
m = botocore.session.get_session().get_service_model("bedrock-agentcore-control")
P, F = "primary-model-id", "fallback-model-id"
def actions(fbt, extra=None):
    fb = {"circuitBreaker": {"mode": "ENABLED"},
          "triggerOn": {"statusCodes": ["429", "5XX"], "errors": ["CONNECTION_ERROR", "FIRST_BYTE_TIMEOUT"]},
          "firstByteTimeoutMilliseconds": fbt, "targetFallback": [{"targetName": "bedrock", "model": F}]}
    if extra: fb.update(extra)
    return [{"routeToTarget": {"staticRoute": {"targetName": "bedrock", "model": P, "fallback": fb}}}]
cases = {
    "create_gateway": ("CreateGateway", {"name": "yopa-agw-fallback-abcd1234", "roleArn": "arn:aws:iam::123456789012:role/x", "authorizerType": "AWS_IAM"}),
    "create_target": ("CreateGatewayTarget", {"gatewayIdentifier": "gw", "name": "bedrock",
        "targetConfiguration": {"inference": {"connector": {"source": {"connectorId": "bedrock-runtime"}}}},
        "credentialProviderConfigurations": [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]}),
    "rule_fbt50": ("CreateGatewayRule", {"gatewayIdentifier": "gw", "priority": 100, "conditions": [{"matchModels": {"anyOf": [{"value": P}]}}], "actions": actions(50)}),
    "rule_fbt30000": ("UpdateGatewayRule", {"gatewayIdentifier": "gw", "ruleId": "11111111-2222-3333-4444-123456789012", "priority": 100, "conditions": [{"matchModels": {"anyOf": [{"value": P}]}}], "actions": actions(30000)}),
    "neg_fbt49": ("CreateGatewayRule", {"gatewayIdentifier": "gw", "priority": 100, "actions": actions(49)}),
    "neg_3_fallbacks_model_max_2": ("CreateGatewayRule", {"gatewayIdentifier": "gw", "priority": 100, "actions": actions(5000, {"targetFallback": [{"targetName": "a"}, {"targetName": "b"}, {"targetName": "c"}]})}),
    "neg_breaker_threshold": ("CreateGatewayRule", {"gatewayIdentifier": "gw", "priority": 100, "actions": actions(5000, {"circuitBreaker": {"mode": "ENABLED", "failureThreshold": 5}})}),
    "neg_error_not_in_enum": ("CreateGatewayRule", {"gatewayIdentifier": "gw", "priority": 100, "actions": actions(5000, {"triggerOn": {"errors": ["READ_TIMEOUT"]}})}),
}
res = {"botocore": botocore.__version__}
for k, (op, params) in cases.items():
    r = ParamValidator().validate(params, m.operation_model(op).input_shape)
    res[k] = "valid" if not r.has_errors() else r.generate_report().replace("\n", " | ")
print(json.dumps(res, indent=1))
