"""Task type classifier and model router for multi-model PAC1 agent."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import dspy

from .dispatch import call_llm_raw
from .dspy_lm import DispatchLM

_JSON_TYPE_RE = re.compile(r'\{[^}]*"type"\s*:\s*"(\w+)"[^}]*\}')  # extract type from partial/wrapped JSON

if TYPE_CHECKING:
    from .prephase import PrephaseResult

# Task type literals
TASK_DEFAULT = "default"
TASK_QUEUE = "queue"
TASK_CAPTURE = "capture"
TASK_CRM = "crm"
TASK_TEMPORAL = "temporal"
TASK_PREJECT = "preject"
TASK_EMAIL = "email"
TASK_LOOKUP = "lookup"
TASK_INBOX = "inbox"
TASK_DISTILL = "distill"

# Fast-path regexes — only for types detectable with near-zero false positives before LLM
_PREJECT_RE = re.compile(
    r"\b(calendar\s+invite|create\s+(a\s+)?(meeting|event|ticket)"
    r"|sync\s+(to|with)\s+\w+|upload\s+to\s+https?"
    r"|salesforce|hubspot|zendesk|jira|external\s+(api|crm|url)"
    r"|send\s+to\s+https?)\b",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(
    r"\b(send|compose|write|email)\b.*\b(to|recipient|subject)\b"
    r"|\bemail\s+(?!(?:address|of|from|in)\b)[A-Za-z]+\s+(a\b|an\b|brief\b|reminder\b|summary\b|short\b)",
    re.IGNORECASE,
)


def classify_task(task_text: str) -> str:
    """High-confidence regex fast-path; everything else deferred to DSPy classifier."""
    if _PREJECT_RE.search(task_text):
        return TASK_PREJECT
    if _EMAIL_RE.search(task_text):
        return TASK_EMAIL
    return TASK_DEFAULT


# ---------------------------------------------------------------------------
# LLM-based task classification (pre-requisite before agent start)
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = (
    "You are a task router. Classify the task into exactly one type. "
    'Reply ONLY with valid JSON: {"type": "<type>"} where <type> is one of: '
    "preject, queue, capture, crm, temporal, email, lookup, inbox, distill, default.\n"
    "preject = calendar invites, sync to external CRM/service, upload to external URL\n"
    "queue = work through / take care of / handle the incoming queue or all inbox items\n"
    "inbox = process/check/handle/review single inbox or inbound note\n"
    "email = send/compose/write email to a recipient\n"
    "lookup = find, count, or query vault data (contacts, files, channels) with no write action\n"
    "capture = capture explicit snippet/content from source into a specific vault path\n"
    "crm = reschedule follow-up, reconnect date, fix follow-up regression, date arithmetic + write\n"
    "temporal = date-relative queries needing datetime arithmetic (N days ago, in N days, what date)\n"
    "distill = analysis/reasoning AND writing a card/note/summary\n"
    "default = everything else (read, write, create, delete, move, standard tasks)"
)

_VALID_TYPES = frozenset({
    TASK_PREJECT, TASK_QUEUE, TASK_CAPTURE, TASK_CRM, TASK_TEMPORAL,
    TASK_DEFAULT, TASK_EMAIL, TASK_LOOKUP, TASK_INBOX, TASK_DISTILL,
})

_CLASSIFIER_PROGRAM_PATH = Path(__file__).parent.parent / "data" / "classifier_program.json"


class ClassifyTask(dspy.Signature):
    """You are a task router. Classify the task into exactly one type.

    preject = calendar invites, sync to external CRM/service, upload to external URL
    queue = work through / take care of / handle the incoming queue or all inbox items
    inbox = process/check/handle/review single inbox or inbound note
    email = send/compose/write email to a recipient
    lookup = find, count, or query vault data (contacts, files, channels) with no write action
    capture = capture explicit snippet/content from source into a specific vault path
    crm = reschedule follow-up, reconnect date, fix follow-up regression, date arithmetic + write
    temporal = date-relative queries needing datetime arithmetic (N days ago, in N days, what date)
    distill = analysis/reasoning AND writing a card/note/summary
    default = everything else (read, write, create, delete, move, standard tasks)
    """
    task_text: str = dspy.InputField(desc="Task description to classify")
    vault_hint: str = dspy.InputField(desc="Optional vault context: AGENTS.MD excerpt and folder structure. Empty string if unavailable.")
    task_type: str = dspy.OutputField(
        desc="Exactly one of: preject, queue, inbox, email, lookup, capture, crm, temporal, distill, default"
    )


_classifier_program: dspy.Module | None = None
_classifier_program_loaded: bool = False


def _load_classifier_program() -> dspy.Module | None:
    global _classifier_program, _classifier_program_loaded
    if _classifier_program_loaded:
        return _classifier_program
    _classifier_program_loaded = True
    if _CLASSIFIER_PROGRAM_PATH.exists():
        try:
            prog = dspy.ChainOfThought(ClassifyTask)
            prog.load(str(_CLASSIFIER_PROGRAM_PATH))
            _classifier_program = prog
            print(f"[MODEL_ROUTER] Loaded compiled classifier from {_CLASSIFIER_PROGRAM_PATH.name}")
        except Exception as exc:
            print(f"[MODEL_ROUTER] Failed to load classifier program: {exc}")
    return _classifier_program

# Ordered keyword → task_type table for plain-text LLM response fallback.
_PLAINTEXT_FALLBACK: list[tuple[tuple[str, ...], str]] = [
    (("preject",),  TASK_PREJECT),
    (("queue",),    TASK_QUEUE),
    (("inbox",),    TASK_INBOX),
    (("email",),    TASK_EMAIL),
    (("capture",),  TASK_CAPTURE),
    (("crm",),      TASK_CRM),
    (("temporal",), TASK_TEMPORAL),
    (("lookup",),   TASK_LOOKUP),
    (("distill",),  TASK_DISTILL),
    (("default",),  TASK_DEFAULT),
]


_INSIGHTS_RE = re.compile(r'## Task-Type Specific Insights(.+?)(?=^##(?!#)|\Z)', re.DOTALL | re.MULTILINE)
_BULLET_HINT_RE = re.compile(r'^- \*\*(.+?)\*\*[:\s]+(.+)', re.MULTILINE)


def _extract_type_hints(wiki_text: str, max_chars: int = 200) -> str:
    """Extract classification-relevant content from Task-Type Specific Insights."""
    m = _INSIGHTS_RE.search(wiki_text)
    section = m.group(1) if m else wiki_text
    # Grab the first subsection title + its first two bullets (each truncated to 80 chars)
    parts = re.split(r'^(### .+)', section, flags=re.MULTILINE)
    if len(parts) >= 3:
        title = parts[1].lstrip('#').strip()
        bullets = _BULLET_HINT_RE.findall(parts[2])
        if bullets:
            hints = "; ".join(f"{k}: {v[:80]}" for k, v in bullets[:2])
            return f"[{title}] {hints}"[:max_chars]
    bullets = _BULLET_HINT_RE.findall(section)
    if not bullets:
        return section.strip()[:max_chars]
    return "; ".join(f"{k}: {v[:80]}" for k, v in bullets[:2])[:max_chars]


def _count_tree_files(prephase_log: list) -> int:
    """Extract tree text from prephase log and count file entries (non-directory lines)."""
    for msg in prephase_log:
        if msg.get("role") == "user" and "VAULT STRUCTURE:" in msg.get("content", ""):
            tree_block = msg["content"]
            break
    else:
        return 0
    file_lines = [
        ln for ln in tree_block.splitlines()
        if ("─" in ln or "└" in ln or "├" in ln) and not ln.rstrip().endswith("/")
    ]
    return len(file_lines)


def _classify_task_llm_once(task_text: str, model: str, model_config: dict,
                            vault_hint: str | None = None) -> str:
    """Single classification attempt. Returns a valid type or '' on failure."""
    _base_opts = model_config.get("ollama_options_classifier") or model_config.get("ollama_options", {})
    _cls_opts = {k: v for k, v in _base_opts.items() if k in ("num_ctx", "temperature", "seed")}
    _cls_cfg = {
        **model_config,
        "max_completion_tokens": min(model_config.get("max_completion_tokens", 512), 512),
        "ollama_options": _cls_opts or None,
    }
    # FIX-N+1: on CC tier — override cc_options with the model's classifier-specific
    # profile (low effort + json_schema → constrains output to {"task_type": <enum>}).
    # Resolved from model_config["cc_options_classifier"] (set via models.json +
    # main.py FIX-119 profile resolution). Falls back to the main cc_options if absent.
    _cc_cls = model_config.get("cc_options_classifier")
    if _cc_cls:
        _cls_cfg["cc_options"] = _cc_cls
    _prog = _load_classifier_program()
    if _prog is not None:
        try:
            # FIX-324: CLASSIFIER_MAX_TOKENS — CoT needs tokens for reasoning before the output field
            _cls_max_tok = int(os.environ.get("CLASSIFIER_MAX_TOKENS", 256))
            _lm = DispatchLM(model, _cls_cfg, max_tokens=_cls_max_tok, json_mode=False)
            with dspy.context(lm=_lm):
                pred = _prog(task_text=task_text[:300], vault_hint=vault_hint or "")
            detected = (pred.task_type or "").strip().lower()
            # FIX-324: retry once when model returns empty string (truncated CoT)
            if not detected:
                with dspy.context(lm=_lm):
                    pred = _prog(task_text=task_text[:300], vault_hint=vault_hint or "")
                detected = (pred.task_type or "").strip().lower()
            if detected in _VALID_TYPES:
                print(f"[MODEL_ROUTER] DSPy classifier: '{detected}'")
                return detected
            print(f"[MODEL_ROUTER] DSPy classifier returned invalid type '{detected}', falling back to LLM")
        except Exception as exc:
            print(f"[MODEL_ROUTER] DSPy classifier failed ({exc}), falling back to LLM")
    user_msg = f"Task: {task_text[:150]}"
    if vault_hint:
        user_msg += f"\nContext: {vault_hint[:800]}"
    try:
        raw = call_llm_raw(_CLASSIFY_SYSTEM, user_msg, model, _cls_cfg,
                           max_tokens=_cls_cfg["max_completion_tokens"],
                           think=False,
                           max_retries=1)
        if not raw:
            print("[MODEL_ROUTER] All LLM tiers failed or empty")
            return ""
        try:
            detected = str(json.loads(raw).get("type", "")).strip()
        except (json.JSONDecodeError, AttributeError):
            m = _JSON_TYPE_RE.search(raw)
            detected = m.group(1).strip() if m else ""
            if detected:
                print(f"[MODEL_ROUTER] Extracted type via regex from: {raw!r}")
        if not detected:
            raw_lower = raw.lower()
            for keywords, task_type in _PLAINTEXT_FALLBACK:
                if any(kw in raw_lower for kw in keywords):
                    detected = task_type
                    print(f"[MODEL_ROUTER] Extracted type {task_type!r} from plain text: {raw[:60]!r}")
                    break
        if detected in _VALID_TYPES:
            print(f"[MODEL_ROUTER] LLM classified task as '{detected}'")
            return detected
        print(f"[MODEL_ROUTER] LLM returned unknown type '{detected}'")
    except Exception as exc:
        print(f"[MODEL_ROUTER] LLM classification failed ({exc})")
    return ""


def classify_task_llm(task_text: str, model: str, model_config: dict,
                      vault_hint: str | None = None) -> str:
    """Classify task type with regex fast-path, optional majority-vote on CC tier,
    and regex fallback on total failure.

    FIX-N+2: on CC tier (provider='claude-code'), when CLASSIFIER_VOTES>=2, the
    underlying LLM classification is run N times and the mode is returned. This
    mitigates CC non-determinism (no --seed/--temperature). Votes that fail or
    return invalid types are discarded; if all fail, falls back to regex.
    """
    _HIGH_CONF_TYPES = frozenset({TASK_PREJECT, TASK_EMAIL})
    _regex_pre = classify_task(task_text)
    if _regex_pre in _HIGH_CONF_TYPES:
        print(f"[MODEL_ROUTER] Regex-confident type={_regex_pre!r}, skipping LLM")
        return _regex_pre

    is_cc = model_config.get("provider") == "claude-code"
    # FIX-N+2: default to 3 votes on CC tier (non-deterministic, no --seed),
    # 1 vote elsewhere (deterministic with seed+temperature=0). User can override
    # via CLASSIFIER_VOTES env var.
    _default_votes = "3" if is_cc else "1"
    try:
        votes = int(os.environ.get("CLASSIFIER_VOTES", _default_votes))
    except ValueError:
        votes = int(_default_votes)

    if not is_cc or votes < 2:
        result = _classify_task_llm_once(task_text, model, model_config, vault_hint)
        return result if result in _VALID_TYPES else classify_task(task_text)

    tally: list[str] = []
    for i in range(votes):
        r = _classify_task_llm_once(task_text, model, model_config, vault_hint)
        if r in _VALID_TYPES:
            tally.append(r)
            print(f"[MODEL_ROUTER] CC vote {i + 1}/{votes}: {r}")
        else:
            print(f"[MODEL_ROUTER] CC vote {i + 1}/{votes}: invalid, discarded")
    if not tally:
        print("[MODEL_ROUTER] All CC votes failed, falling back to regex")
        return classify_task(task_text)
    counts = Counter(tally)
    top, top_n = counts.most_common(1)[0]
    print(f"[MODEL_ROUTER] CC majority-vote: {top} ({top_n}/{len(tally)}, tally={dict(counts)})")
    return top


@dataclass
class ModelRouter:
    """Routes tasks to appropriate models based on task type classification."""
    default: str
    classifier: str
    # Optional per-type overrides — fall back to default if not provided
    email: str = ""
    lookup: str = ""
    inbox: str = ""
    queue: str = ""
    capture: str = ""
    crm: str = ""
    temporal: str = ""
    preject: str = ""
    evaluator: str = ""
    prompt_builder: str = ""
    configs: dict[str, dict] = field(default_factory=dict)

    def _select_model(self, task_type: str) -> str:
        return {
            TASK_EMAIL:    self.email    or self.default,
            TASK_LOOKUP:   self.lookup   or self.default,
            TASK_INBOX:    self.inbox    or self.default,
            TASK_QUEUE:    self.queue    or self.inbox or self.default,
            TASK_CAPTURE:  self.capture  or self.default,
            TASK_CRM:      self.crm      or self.default,
            TASK_TEMPORAL: self.temporal or self.lookup or self.default,
            TASK_PREJECT:  self.preject  or self.default,
            TASK_DISTILL:  self.default,
        }.get(task_type, self.default)

    def resolve(self, task_text: str) -> tuple[str, dict, str]:
        """Return (model_id, model_config, task_type) using regex-only classification."""
        task_type = classify_task(task_text)
        model_id = self._select_model(task_type)
        print(f"[MODEL_ROUTER] type={task_type} → model={model_id}")
        return model_id, self.configs.get(model_id, {}), task_type

    def _adapt_config(self, cfg: dict, task_type: str) -> dict:
        """Apply task-type specific ollama_options overlay (shallow merge)."""
        key = f"ollama_options_{task_type}"
        override = cfg.get(key)
        if not override:
            return cfg
        adapted = {**cfg, "ollama_options": {**cfg.get("ollama_options", {}), **override}}
        print(f"[MODEL_ROUTER] Adapted ollama_options for type={task_type}: {adapted['ollama_options']}")
        return adapted

    def resolve_after_prephase(self, task_text: str, pre: "PrephaseResult") -> tuple[str, dict, str]:
        """Classify once after prephase using AGENTS.MD content as context."""
        file_count = _count_tree_files(pre.log)
        vault_hint = None
        if pre.agents_md_content:
            vault_hint = f"AGENTS.MD:\n{pre.agents_md_content}\nvault files: {file_count}"
        if classify_task(task_text) not in {TASK_PREJECT, TASK_EMAIL}:
            try:
                from .wiki import load_wiki_patterns as _load_wiki
                wiki_hints = []
                for _tp in ("inbox", "queue"):
                    _content = _load_wiki(_tp)
                    if _content:
                        _hint = _extract_type_hints(_content)
                        if _hint:
                            wiki_hints.append(f"{_tp}: {_hint}")
                if wiki_hints:
                    vault_hint = (vault_hint or "") + "\n\nWIKI TYPE HINTS:\n" + "\n".join(wiki_hints)
            except Exception:
                pass  # fail-open: wiki may not exist yet
        task_type = classify_task_llm(
            task_text, self.classifier, self.configs.get(self.classifier, {}),
            vault_hint=vault_hint,
        )
        model_id = self._select_model(task_type)
        print(f"[MODEL_ROUTER] type={task_type} → model={model_id}")
        adapted_cfg = self._adapt_config(self.configs.get(model_id, {}), task_type)
        return model_id, adapted_cfg, task_type
