def test_dispatch_module_deleted():
    import importlib
    import pytest
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("agent.dispatch")


def test_llm_module_exports():
    from agent.llm import call_llm_raw, OUTCOME_BY_NAME
    assert callable(call_llm_raw)
    assert "OUTCOME_OK" in OUTCOME_BY_NAME


def test_llm_exports_cli_colors():
    from agent.llm import CLI_RED, CLI_GREEN, CLI_CLR, CLI_BLUE, CLI_YELLOW
    assert CLI_CLR == "\x1B[0m"


def test_dispatch_function_removed():
    import agent.llm as llm
    assert not hasattr(llm, "dispatch"), "dispatch() should be removed from llm.py"
