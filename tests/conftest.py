"""Test configuration — mock heavy dependencies so unit tests run without gRPC/API libs."""
import sys
import types
from unittest.mock import MagicMock

# Stub out heavy external modules before any agent imports.
# pydantic, annotated_types, and openai are real installed dependencies — NOT mocked.
# openai must NOT be mocked: dspy → litellm → openai._models imports it at module level.
_STUB_MODULES = [
    "google", "google.protobuf", "google.protobuf.json_format",
    "connectrpc", "connectrpc.errors",
    "anthropic",
    "bitgn", "bitgn.vm", "bitgn.vm.ecom", "bitgn.vm.ecom.ecom_connect", "bitgn.vm.ecom.ecom_pb2",
    "fastapi",
    "fastapi.testclient",
    "fastapi.responses",
    "fastapi.staticfiles",
]

for mod_name in _STUB_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

# Provide Outcome enum stub for ecom_pb2
_ecom_pb2 = sys.modules["bitgn.vm.ecom.ecom_pb2"]
_ecom_pb2.Outcome = types.SimpleNamespace(
    OUTCOME_UNSPECIFIED=0,
    OUTCOME_OK=1,
    OUTCOME_DENIED_SECURITY=2,
    OUTCOME_NONE_CLARIFICATION=3,
    OUTCOME_NONE_UNSUPPORTED=4,
    OUTCOME_ERR_INTERNAL=5,
)
_ecom_pb2.NodeKind = types.SimpleNamespace(
    NODE_KIND_UNSPECIFIED=0,
    NODE_KIND_FILE=1,
    NODE_KIND_DIR=2,
)
_ecom_pb2.ActionStatus = types.SimpleNamespace(
    ACTION_STATUS_UNSPECIFIED=0,
    ACTION_STATUS_NOT_ACTION=1,
    ACTION_STATUS_ACCEPTED=2,
    ACTION_STATUS_REJECTED=3,
)
_ecom_pb2.AnswerRequest = MagicMock
_ecom_pb2.ListRequest = MagicMock
_ecom_pb2.ReadRequest = MagicMock
_ecom_pb2.WriteRequest = MagicMock
_ecom_pb2.StatRequest = MagicMock
_ecom_pb2.ExecRequest = MagicMock

# Provide MessageToDict stub
sys.modules["google.protobuf.json_format"].MessageToDict = lambda x: {}

# Provide ConnectError stub
sys.modules["connectrpc.errors"].ConnectError = type("ConnectError", (Exception,), {})


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: slow integration smoke tests")
