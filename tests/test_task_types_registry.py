"""Regression + schema tests for the dynamic task-type registry (FIX-325)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import task_types as tt


# ---------------------------------------------------------------------------
# Baseline: the 10 pre-registry types must survive the migration.
# ---------------------------------------------------------------------------

LEGACY_TYPES = {
    "default", "preject", "email", "queue", "inbox",
    "lookup", "capture", "crm", "temporal", "distill",
}


def test_all_legacy_types_present() -> None:
    assert LEGACY_TYPES.issubset(tt.VALID_TYPES)


def test_default_type_required() -> None:
    assert "default" in tt.REGISTRY.types


def test_task_constants_dynamic() -> None:
    for name in LEGACY_TYPES:
        assert getattr(tt, f"TASK_{name.upper()}") == name


def test_unknown_constant_raises() -> None:
    with pytest.raises(AttributeError):
        _ = tt.TASK_DOES_NOT_EXIST  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Regex fast-path — must match legacy preject/email patterns.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text,expected",
    [
        ("create a calendar invite for tomorrow", "preject"),
        ("sync to salesforce the new lead", "preject"),
        ("upload to https://drop.example/x", "preject"),
        ("send to https://webhook.example", "preject"),
        ("create a meeting in jira", "preject"),
        ("send an email to alice about the meeting", "email"),
        ("compose a reply to bob", "email"),
        ("email alice a brief summary", "email"),
    ],
)
def test_classify_regex_fast_path(text: str, expected: str) -> None:
    result = tt.classify_regex(text)
    assert result is not None
    assert result[0] == expected
    assert result[1] == "high"


@pytest.mark.parametrize(
    "text",
    [
        "count contacts in the vault",
        "how many messages arrived last week",
        "read the file notes.md",
        "delete the old backup folder",
    ],
)
def test_classify_regex_no_match(text: str) -> None:
    assert tt.classify_regex(text) is None


def test_email_address_not_email_task() -> None:
    # Legacy _EMAIL_RE exclusion: "email address of X" must not trip the fast-path.
    assert tt.classify_regex("find the email address of alice") is None


# ---------------------------------------------------------------------------
# Model resolution — backwards-compat with MODEL_EMAIL / MODEL_LOOKUP / etc.
# ---------------------------------------------------------------------------

def test_resolve_model_explicit_env() -> None:
    got = tt.resolve_model("email", env={"MODEL_EMAIL": "haiku-4.5"}, default_model="sonnet")
    assert got == "haiku-4.5"


def test_resolve_model_fallback_chain_queue_to_inbox() -> None:
    got = tt.resolve_model("queue", env={"MODEL_INBOX": "inbox-m"}, default_model="sonnet")
    assert got == "inbox-m"


def test_resolve_model_fallback_chain_temporal_to_lookup() -> None:
    got = tt.resolve_model("temporal", env={"MODEL_LOOKUP": "lookup-m"}, default_model="sonnet")
    assert got == "lookup-m"


def test_resolve_model_default_when_env_empty() -> None:
    got = tt.resolve_model("distill", env={}, default_model="sonnet")
    assert got == "sonnet"


def test_resolve_model_unknown_type_falls_to_default() -> None:
    # Unknown types route through the 'default' TaskType record.
    got = tt.resolve_model("__never_seen__", env={}, default_model="sonnet")
    assert got == "sonnet"


def test_resolve_model_explicit_override_beats_env() -> None:
    # main.py passes explicit={"email": value} (backwards compat with legacy dataclass).
    got = tt.resolve_model(
        "email",
        env={"MODEL_EMAIL": "env-value"},
        default_model="sonnet",
        explicit={"email": "override-value"},
    )
    assert got == "override-value"


# ---------------------------------------------------------------------------
# Builders — must produce valid content for DSPy / cc_json_schema / system prompt.
# ---------------------------------------------------------------------------

def test_build_cc_json_schema_enum_contains_all_types() -> None:
    enum = tt.build_cc_json_schema_enum()
    assert set(enum) == tt.VALID_TYPES
    # 'default' must be last so it reads naturally as "everything else".
    assert enum[-1] == "default"


def test_build_classifier_system_prompt_mentions_all_types() -> None:
    prompt = tt.build_classifier_system_prompt()
    for name in tt.VALID_TYPES:
        assert name in prompt
    assert "Reply ONLY with valid JSON" in prompt


def test_build_classifier_docstring_mentions_all_types() -> None:
    doc = tt.build_classifier_docstring()
    for name in tt.VALID_TYPES:
        assert name in doc


# ---------------------------------------------------------------------------
# Helpers — wiki_folder_map, builder_types, vault_types, plaintext_fallback_pairs.
# ---------------------------------------------------------------------------

def test_wiki_folder_map_identity_for_legacy_types() -> None:
    # All legacy types used their own name as folder — we preserved that.
    mapping = tt.wiki_folder_map()
    for name in LEGACY_TYPES:
        assert mapping[name] == name


def test_builder_types_excludes_preject() -> None:
    # Legacy _NEEDS_BUILDER excluded preject (single-step immediate rejection).
    assert "preject" not in tt.builder_types()
    assert "default" in tt.builder_types()


def test_vault_types_excludes_default() -> None:
    assert "default" not in tt.vault_types()
    assert tt.vault_types() == tt.VALID_TYPES - {"default"}


def test_plaintext_fallback_pairs_starts_with_fast_path_types() -> None:
    pairs = tt.plaintext_fallback_pairs()
    first_two = {p[1] for p in pairs[:2]}
    assert first_two == {"preject", "email"}


# ---------------------------------------------------------------------------
# Schema validation — bad JSON should raise at load time.
# ---------------------------------------------------------------------------

def test_load_registry_rejects_missing_default(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1, "types": {"foo": {
        "description": "x", "model_env": "MODEL_FOO", "wiki_folder": "foo", "status": "hard"
    }}}))
    with pytest.raises(RuntimeError, match="default"):
        tt._load_registry(bad)


def test_load_registry_rejects_bad_regex(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1, "types": {
        "default": {"description": "x", "model_env": "MODEL_DEFAULT",
                    "wiki_folder": "default", "status": "hard"},
        "foo": {"description": "y", "model_env": "MODEL_FOO",
                "wiki_folder": "foo", "status": "hard",
                "fast_path": {"pattern": "[unclosed"}},
    }}))
    with pytest.raises(ValueError, match="invalid regex"):
        tt._load_registry(bad)


def test_load_registry_rejects_bad_status(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 1, "types": {
        "default": {"description": "x", "model_env": "MODEL_DEFAULT",
                    "wiki_folder": "default", "status": "hard"},
        "foo": {"description": "y", "model_env": "MODEL_FOO",
                "wiki_folder": "foo", "status": "soft-maybe"},
    }}))
    with pytest.raises(ValueError, match="status"):
        tt._load_registry(bad)


def test_regex_flags_compiled() -> None:
    # preject regex should be case-insensitive per JSON config.
    result = tt.classify_regex("SYNC TO SALESFORCE")
    assert result is not None and result[0] == "preject"
