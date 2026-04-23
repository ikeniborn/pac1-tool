"""Dynamic task-type registry (FIX-325).

Source of truth: data/task_types.json. Loaded once on import. Consumers should
import VALID_TYPES, TASK_<NAME> constants, classify_regex(), resolve_model(),
or one of the builders for DSPy/system prompt/cc_json_schema.

Adding a new type:
  1. Append entry to data/task_types.json.
  2. Optionally set MODEL_<UPPER> in .env (else falls back via fallback_chain).
  3. Optionally create data/wiki/fragments/<wiki_folder>/ for wiki fragments.
  4. For the compiled DSPy classifier to know the new type, run:
       uv run python optimize_prompts.py --target classifier
     Until then, the new type lives in system-prompt / enum but may not be
     predicted by the COPRO-compiled program (falls back to regex/default).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "task_types.json"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_RE_FLAG_MAP = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE":  re.MULTILINE,
    "DOTALL":     re.DOTALL,
    "VERBOSE":    re.VERBOSE,
    "UNICODE":    re.UNICODE,
}


@dataclass(frozen=True)
class FastPath:
    pattern: re.Pattern
    confidence: str  # "high" | "medium" | "low"


@dataclass(frozen=True)
class TaskType:
    name: str
    description: str
    model_env: str
    fallback_chain: tuple[str, ...]
    wiki_folder: str
    fast_path: FastPath | None
    needs_builder: bool
    status: str  # "hard" | "soft"


@dataclass(frozen=True)
class TaskTypeRegistry:
    types: dict[str, TaskType]
    order: tuple[str, ...]  # stable iteration order (preject/email fast-path first)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self.types.keys())


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _compile_flags(flag_names: list[str] | None) -> int:
    if not flag_names:
        return 0
    flags = 0
    for name in flag_names:
        key = name.upper()
        if key not in _RE_FLAG_MAP:
            raise ValueError(f"Unknown regex flag: {name!r} (allowed: {list(_RE_FLAG_MAP)})")
        flags |= _RE_FLAG_MAP[key]
    return flags


def _parse_task_type(name: str, raw: dict) -> TaskType:
    for required in ("description", "model_env", "wiki_folder", "status"):
        if required not in raw:
            raise ValueError(f"task_types.json: '{name}' missing required field {required!r}")
    fp_raw = raw.get("fast_path")
    fast_path: FastPath | None = None
    if fp_raw is not None:
        if "pattern" not in fp_raw:
            raise ValueError(f"task_types.json: '{name}.fast_path' missing 'pattern'")
        try:
            pattern = re.compile(fp_raw["pattern"], _compile_flags(fp_raw.get("flags")))
        except re.error as e:
            raise ValueError(f"task_types.json: '{name}.fast_path.pattern' invalid regex: {e}")
        fast_path = FastPath(pattern=pattern, confidence=fp_raw.get("confidence", "high"))
    status = raw["status"]
    if status not in {"hard", "soft"}:
        raise ValueError(f"task_types.json: '{name}.status' must be 'hard' or 'soft', got {status!r}")
    return TaskType(
        name=name,
        description=str(raw["description"]).strip(),
        model_env=str(raw["model_env"]),
        fallback_chain=tuple(raw.get("fallback_chain", [])),
        wiki_folder=str(raw["wiki_folder"]),
        fast_path=fast_path,
        needs_builder=bool(raw.get("needs_builder", True)),
        status=status,
    )


def _load_registry(path: Path = _REGISTRY_PATH) -> TaskTypeRegistry:
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise RuntimeError(f"Task-type registry not found: {path}. This file is required.") from None
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Task-type registry {path} is not valid JSON: {e}") from None
    raw_types = data.get("types")
    if not isinstance(raw_types, dict) or not raw_types:
        raise RuntimeError(f"Task-type registry {path} must have non-empty 'types' object")
    if "default" not in raw_types:
        raise RuntimeError(f"Task-type registry {path} must define 'default' type")
    types = {name: _parse_task_type(name, raw) for name, raw in raw_types.items()}
    # Iteration order for regex fast-path: preserve JSON insertion order for
    # types that define fast_path (first match wins; legacy code checked preject
    # before email for cases like "send to https://..." where both patterns hit).
    # Types without fast_path come after, alphabetic (irrelevant for classify_regex
    # but keeps REGISTRY.order deterministic for other consumers).
    fast_path_names = [n for n in types if types[n].fast_path is not None]
    other_names = sorted(n for n in types if types[n].fast_path is None)
    order_names = tuple(fast_path_names + other_names)
    return TaskTypeRegistry(types=types, order=order_names)


REGISTRY: TaskTypeRegistry = _load_registry()

# Public frozenset of valid type names
VALID_TYPES: frozenset[str] = REGISTRY.names


# ---------------------------------------------------------------------------
# Dynamic TASK_<NAME> constants (backwards compat for legacy imports)
# ---------------------------------------------------------------------------

_TASK_CONSTS: dict[str, str] = {f"TASK_{name.upper()}": name for name in REGISTRY.types}


def __getattr__(attr: str) -> str:
    # PEP 562: `from agent.task_types import TASK_EMAIL` resolves here.
    if attr in _TASK_CONSTS:
        return _TASK_CONSTS[attr]
    raise AttributeError(f"module 'agent.task_types' has no attribute {attr!r}")


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_TASK_CONSTS.keys()))


# ---------------------------------------------------------------------------
# Regex fast-path
# ---------------------------------------------------------------------------

def classify_regex(task_text: str) -> tuple[str, str] | None:
    """Return (type, confidence) for the first matching fast_path, else None.

    Iterates in registry order (high-confidence first). Replaces legacy
    _PREJECT_RE / _EMAIL_RE logic.
    """
    for name in REGISTRY.order:
        t = REGISTRY.types[name]
        if t.fast_path is not None and t.fast_path.pattern.search(task_text):
            return (t.name, t.fast_path.confidence)
    return None


# ---------------------------------------------------------------------------
# Builders for classifier / system prompt / cc_json_schema
# ---------------------------------------------------------------------------

def _sorted_type_names() -> list[str]:
    # 'default' last so the docstring reads "everything else" as the tail.
    others = sorted(n for n in REGISTRY.types if n != "default")
    return others + ["default"]


def build_cc_json_schema_enum() -> list[str]:
    """Enum list for cc_json_schema.properties.task_type.enum."""
    return _sorted_type_names()


def build_classifier_system_prompt() -> str:
    """Build the full system prompt for the plain-text LLM classifier fallback."""
    names = _sorted_type_names()
    lines: list[str] = [
        "You are a task router. Classify the task into exactly one type.",
        'Reply ONLY with valid JSON: {"type": "<type>"} where <type> is one of: '
        + ", ".join(names) + ".",
    ]
    for n in names:
        lines.append(f"{n} = {REGISTRY.types[n].description}")
    return "\n".join(lines)


def build_classifier_docstring() -> str:
    """Docstring for dspy.Signature ClassifyTask."""
    names = _sorted_type_names()
    lines = ["You are a task router. Classify the task into exactly one type.", ""]
    for n in names:
        lines.append(f"{n} = {REGISTRY.types[n].description}")
    return "\n".join(lines)


def build_classifier_output_desc() -> str:
    """Description for task_type OutputField."""
    return "Exactly one of: " + ", ".join(_sorted_type_names())


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

def resolve_model(
    type_name: str,
    env: Mapping[str, str] | None = None,
    *,
    default_model: str,
    explicit: Mapping[str, str] | None = None,
) -> str:
    """Resolve model_id for a task type.

    Resolution priority:
      1. `explicit` dict (for backwards-compat: main.py reads MODEL_EMAIL etc.
         into explicit overrides and passes them through).
      2. env[model_env] from the type's own record.
      3. env[model_env] walking the fallback_chain.
      4. default_model.
    """
    env = env if env is not None else os.environ
    explicit = explicit or {}
    t = REGISTRY.types.get(type_name) or REGISTRY.types["default"]
    if type_name in explicit and explicit[type_name]:
        return explicit[type_name]
    for candidate_name in (t.name, *t.fallback_chain):
        candidate = REGISTRY.types.get(candidate_name)
        if candidate is None:
            continue
        if candidate_name in explicit and explicit[candidate_name]:
            return explicit[candidate_name]
        val = env.get(candidate.model_env, "")
        if val:
            return val
    return default_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_wiki_folder(type_name: str) -> str:
    t = REGISTRY.types.get(type_name)
    return t.wiki_folder if t else type_name


def wiki_folder_map() -> dict[str, str]:
    """{type_name: wiki_folder} — replaces legacy _TYPE_TO_PAGE."""
    return {name: t.wiki_folder for name, t in REGISTRY.types.items()}


def builder_types() -> frozenset[str]:
    """Types with needs_builder=True — replaces legacy _NEEDS_BUILDER."""
    return frozenset(name for name, t in REGISTRY.types.items() if t.needs_builder)


def vault_types() -> frozenset[str]:
    """All types except 'default' — replaces legacy _VAULT_TASK_TYPES."""
    return frozenset(name for name in REGISTRY.types if name != "default")


def plaintext_fallback_pairs() -> list[tuple[tuple[str, ...], str]]:
    """Keyword → type list for plain-text LLM response fallback parsing.
    Order: fast-path types first (as in REGISTRY.order)."""
    return [((name,), name) for name in REGISTRY.order]
