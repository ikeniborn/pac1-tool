import json
import os
import re
import threading
import time
from pathlib import Path

import anthropic
import httpx
from openai import OpenAI
from pydantic import BaseModel

from google.protobuf.json_format import MessageToDict

from bitgn.vm.pcm_connect import PcmRuntimeClientSync
from bitgn.vm.pcm_pb2 import (
    AnswerRequest,
    ContextRequest,
    DeleteRequest,
    FindRequest,
    ListRequest,
    MkDirRequest,
    MoveRequest,
    Outcome,
    ReadRequest,
    SearchRequest,
    TreeRequest,
    WriteRequest,
)

from .models import (
    ReportTaskCompletion,
    Req_Context,
    Req_Delete,
    Req_Find,
    Req_List,
    Req_MkDir,
    Req_Move,
    Req_Read,
    Req_Search,
    Req_Tree,
    Req_Write,
)



# ---------------------------------------------------------------------------
# Secrets loader
# ---------------------------------------------------------------------------

def _load_secrets(path: str = ".secrets") -> None:
    secrets_file = Path(path)
    if not secrets_file.exists():
        return
    for line in secrets_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip inline comments: split on unescaped '#' (e.g. "300   # comment")
        value = value.split("#")[0].strip() if "#" in value else value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_secrets(".env")   # model names (no credentials) — loads first; .secrets and real env vars override
_load_secrets()         # credentials (.secrets)


# ---------------------------------------------------------------------------
# LLM clients
# ---------------------------------------------------------------------------

_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
_OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
_CC_ENABLED = os.environ.get("CC_ENABLED") == "1"  # Claude Code tier (iclaude subprocess)

# FIX-215: explicit HTTP timeout — OpenAI SDK defaults to 600s; Ollama local can hang
# silently on stuck sockets (observed 40+ min hang during COPRO). Read-timeout 180s keeps
# us under TASK_TIMEOUT_S and lets TRANSIENT_KWS retry loop recover from stalled requests.
try:
    _HTTP_READ_TIMEOUT_S = float(os.environ.get("LLM_HTTP_READ_TIMEOUT_S", "180"))
except ValueError:
    _HTTP_READ_TIMEOUT_S = 180.0
try:
    _HTTP_CONNECT_TIMEOUT_S = float(os.environ.get("LLM_HTTP_CONNECT_TIMEOUT_S", "10"))
except ValueError:
    _HTTP_CONNECT_TIMEOUT_S = 10.0
_HTTP_TIMEOUT = httpx.Timeout(
    timeout=_HTTP_READ_TIMEOUT_S,
    connect=_HTTP_CONNECT_TIMEOUT_S,
)

# Primary: Anthropic SDK for Claude models
anthropic_client: anthropic.Anthropic | None = (
    anthropic.Anthropic(api_key=_ANTHROPIC_KEY, timeout=_HTTP_READ_TIMEOUT_S)
    if _ANTHROPIC_KEY else None
)

# Tier 2: OpenRouter (Claude + open models via cloud)
openrouter_client: OpenAI | None = (
    OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=_OPENROUTER_KEY,
        timeout=_HTTP_TIMEOUT,
        default_headers={
            "HTTP-Referer": "http://localhost",
            "X-Title": "bitgn-agent",
        },
    )
    if _OPENROUTER_KEY
    else None
)

# Tier 3: Ollama via OpenAI-compatible API (local fallback)
ollama_client = OpenAI(base_url=_OLLAMA_URL, api_key="ollama", timeout=_HTTP_TIMEOUT)

# Tier 1b: Claude Code CLI (subprocess, OAuth via iclaude). Enabled via CC_ENABLED=1.
# Only reachable when a model config declares provider="claude-code" — interleaves
# with Anthropic tier (not a fallback), see call_llm_raw().
from .cc_client import cc_complete as _cc_complete  # noqa: E402

_active = "anthropic" if _ANTHROPIC_KEY else ("openrouter" if _OPENROUTER_KEY else "ollama")
print(
    f"[dispatch] Active backend: {_active} "
    f"(anthropic={'✓' if _ANTHROPIC_KEY else '✗'}, "
    f"openrouter={'✓' if _OPENROUTER_KEY else '✗'}, "
    f"ollama=✓, "
    f"claude-code={'✓' if _CC_ENABLED else '✗'})"
)


# ---------------------------------------------------------------------------
# Model capability detection
# ---------------------------------------------------------------------------

# Static capability hints: model name substring → response_format mode
# Checked in order; first match wins. Values: "json_object" | "json_schema" | "none"
_STATIC_HINTS: dict[str, str] = {
    "anthropic/claude": "json_object",
    "qwen/qwen":        "json_object",
    "meta-llama/":      "json_object",
    "mistralai/":       "json_object",
    "google/gemma":     "json_object",
    "google/gemini":    "json_object",
    "deepseek/":        "json_object",
    "openai/gpt":       "json_object",
    "gpt-4":            "json_object",
    "gpt-3.5":          "json_object",
    "perplexity/":      "none",
}

# Cached NextStep JSON schema (computed once; used for json_schema response_format)
def _nextstep_json_schema() -> dict:
    from .models import NextStep
    return NextStep.model_json_schema()

_NEXTSTEP_SCHEMA: dict | None = None

# FIX-213: Persist capability cache to disk — avoid re-probing on restart
_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "capability_cache.json"
_CACHE_TTL_S = 7 * 86400  # 7 days


def _load_capability_cache() -> dict[str, str]:
    """Load persisted cache, filtering stale entries (>7 days)."""
    try:
        data = json.loads(_CACHE_FILE.read_text())
        now = time.time()
        return {k: v["mode"] for k, v in data.items()
                if isinstance(v, dict) and now - v.get("ts", 0) < _CACHE_TTL_S}
    except Exception:
        return {}


def _save_capability_cache() -> None:
    """Persist current cache to disk. Non-critical — failure is silently ignored."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {k: {"mode": v, "ts": time.time()} for k, v in _CAPABILITY_CACHE.items()}
        _CACHE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


# Runtime cache: model name → detected format mode
_CAPABILITY_CACHE: dict[str, str] = _load_capability_cache()  # FIX-213
_CAPABILITY_CACHE_LOCK = threading.Lock()


def _get_static_hint(model: str) -> str | None:
    m = model.lower()
    for substring, fmt in _STATIC_HINTS.items():
        if substring in m:
            return fmt
    return None


def probe_structured_output(client: OpenAI, model: str, hint: str | None = None) -> str:
    """Detect if model supports response_format. Returns 'json_object' or 'none'.
    Checks hint → static table → runtime probe (cached per model name).
    Thread-safe: double-checked locking — lock held only for cache read/write,
    not during the HTTP probe call."""
    with _CAPABILITY_CACHE_LOCK:
        if model in _CAPABILITY_CACHE:
            return _CAPABILITY_CACHE[model]

    # --- probe outside lock (slow HTTP call) ---
    mode = hint or _get_static_hint(model)
    if mode is None:
        print(f"[capability] Probing {model} for structured output support...")
        try:
            client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": 'Reply with valid JSON: {"ok": true}'}],
                max_completion_tokens=20,
            )
            mode = "json_object"
        except Exception as e:
            err = str(e).lower()
            if any(kw in err for kw in ("response_format", "unsupported", "not supported", "invalid_request")):
                mode = "none"
            else:
                mode = "json_object"  # transient error — assume supported
        label = "probed"
    else:
        label = "static hint"

    with _CAPABILITY_CACHE_LOCK:
        _CAPABILITY_CACHE[model] = mode
        _save_capability_cache()  # FIX-213
    print(f"[capability] {model}: {mode} ({label})")
    return mode


def get_response_format(mode: str) -> dict | None:
    """Build response_format dict for the given mode, or None if mode='none'."""
    global _NEXTSTEP_SCHEMA
    if mode == "json_object":
        return {"type": "json_object"}
    if mode == "json_schema":
        if _NEXTSTEP_SCHEMA is None:
            _NEXTSTEP_SCHEMA = _nextstep_json_schema()
        return {"type": "json_schema", "json_schema": {"name": "NextStep", "strict": True, "schema": _NEXTSTEP_SCHEMA}}
    return None


# ---------------------------------------------------------------------------
# Lightweight raw LLM call (used by classify_task_llm in classifier.py)
# ---------------------------------------------------------------------------

# Transient error keywords — single source of truth; imported by loop.py
# FIX-215: added timeout/timed out — httpx/OpenAI timeouts should retry
TRANSIENT_KWS = (
    "503", "502", "429", "NoneType", "overloaded",
    "unavailable", "server error", "rate limit", "rate-limit",
    "timeout", "timed out", "read timeout",
    "apitimeouterror", "connecttimeout", "readtimeout",
)

# FIX-416: hard connection errors — not retried 3 times like soft transients.
# These indicate the socket is dead; one immediate retry is sufficient before
# falling through to MODEL_FALLBACK. Kept separate so loop.py can cap retries at 1.
# FIX-416b: "connection reset" (ECONNRESET) is a dead-socket condition, same as broken pipe.
HARD_CONNECTION_KWS = (
    "broken pipe", "errno 32", "connection aborted",
    "connection reset", "connection refused", "remotedisconnected", "incompleteread",
)

# FIX-417: fallback model used when all tiers of primary model fail completely.
# Set MODEL_FALLBACK to any supported model string (same format as MODEL_DEFAULT).
_FALLBACK_MODEL = os.environ.get("MODEL_FALLBACK", "")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()  # DEBUG → log think blocks


def is_ollama_model(model: str) -> bool:
    """True for Ollama-format models (name:tag, no slash).
    Examples: qwen3.5:9b, deepseek-v3.1:671b-cloud, qwen3.5:cloud.
    These must be routed directly to Ollama tier, skipping OpenRouter."""
    return ":" in model and "/" not in model


_VALID_PROVIDERS = frozenset({"anthropic", "claude-code", "openrouter", "ollama"})


def is_claude_code_model(model: str) -> bool:
    """True for claude-code/* aliases routed to iclaude subprocess."""
    return model.lower().startswith("claude-code/")


def get_provider(model: str, cfg: dict) -> str:
    """Determine LLM provider for a model call.
    Explicit cfg['provider'] wins; falls back to name heuristics for backward compat.
    Values: 'anthropic' | 'claude-code' | 'openrouter' | 'ollama'."""
    explicit = cfg.get("provider", "")
    if explicit in _VALID_PROVIDERS:
        return explicit
    # Heuristic fallback — existing models follow naming conventions
    if is_claude_code_model(model):
        return "claude-code"
    if is_claude_model(model):
        return "anthropic"
    if is_ollama_model(model):
        return "ollama"
    return "openrouter"


def _call_raw_single_model(
    system: str,
    user_msg: str,
    model: str,
    cfg: dict,
    max_tokens: int = 20,
    think: bool | None = None,  # None=use cfg, False=disable, True=enable
    max_retries: int = 3,  # classifier passes 0 → 1 attempt, no retries
    plain_text: bool = False,  # FIX-181: skip response_format (for code generation, not JSON)
    token_out: dict | None = None,  # if provided, populated with {"input": N, "output": N}
    logprobs: bool = False,  # GEPA ConfidenceAdapter: request logprobs (OpenRouter/Ollama only)
) -> str | None:
    """Lightweight LLM call with 3-tier routing and transient-error retry.
    Returns raw text (think blocks stripped), or None if all tiers fail.
    Used by classify_task_llm(); caller handles JSON parsing and fallback.
    max_retries controls retry count per tier (0 = 1 attempt only).
    plain_text=True skips response_format constraints (use for code generation)."""

    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    # FIX-197: extract seed for cross-tier forwarding (Anthropic has no seed param)
    _seed = None
    _opts = cfg.get("ollama_options")
    if isinstance(_opts, dict):
        _seed = _opts.get("seed")

    _provider = get_provider(model, cfg)

    # --- Tier 1: Anthropic SDK ---
    # FIX-197: Anthropic SDK has no seed param; temperature from cfg (FIX-187) is the best determinism lever
    if _provider == "anthropic" and anthropic_client is not None:
        ant_model = get_anthropic_model_id(model)
        for attempt in range(max_retries + 1):
            try:
                _create_kw: dict = dict(
                    model=ant_model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user_msg}],
                )
                _ant_temp = cfg.get("temperature")  # FIX-187: pass temperature for non-thinking calls
                if _ant_temp is not None:
                    _create_kw["temperature"] = _ant_temp
                resp = anthropic_client.messages.create(**_create_kw)
                # Iterate blocks — take first type="text" (skip thinking blocks)
                for block in resp.content:
                    if getattr(block, "type", None) == "text" and block.text.strip():
                        if token_out is not None:
                            token_out["input"] = getattr(resp.usage, "input_tokens", 0)
                            token_out["output"] = getattr(resp.usage, "output_tokens", 0)
                        return block.text.strip()
                if attempt < max_retries:
                    print(f"[Anthropic] Empty response (attempt {attempt + 1}) — retrying")
                    continue
                print("[Anthropic] Empty after all retries — falling through to next tier")
                break  # do not return "" — let next tier try
            except Exception as e:
                # FIX-416: hard connection errors capped at 1 retry
                _es = str(e).lower()
                _is_hard = any(kw.lower() in _es for kw in HARD_CONNECTION_KWS)
                _is_transient = any(kw.lower() in _es for kw in TRANSIENT_KWS)
                _max_att = 1 if _is_hard else max_retries
                if (_is_hard or _is_transient) and attempt < _max_att:
                    _delay = 2 if _is_hard else 4
                    print(f"[Anthropic] {'Hard connection' if _is_hard else 'Transient'} (attempt {attempt + 1}): {e} — retrying in {_delay}s")
                    time.sleep(_delay)
                    continue
                print(f"[Anthropic] Error: {e}")
                break

    # --- Tier 1b: Claude Code CLI (iclaude subprocess) ---
    # Replaces Anthropic tier when provider='claude-code'. Does NOT cascade into
    # OpenRouter/Ollama on failure — returns None so the caller can retry the
    # whole step (matches chosen strategy "None → loop retry").
    if _provider == "claude-code":
        if not _CC_ENABLED:
            print("[ClaudeCode] Skipped — CC_ENABLED != 1")
            return None
        raw = _cc_complete(
            system, user_msg,
            cfg=cfg,
            max_tokens=max_tokens,
            plain_text=plain_text,
            token_out=token_out,
        )
        if raw:
            return raw
        print("[ClaudeCode] Failed after internal retries — returning None")
        return None

    # --- Tier 2: OpenRouter (skip Ollama models) ---
    if openrouter_client is not None and _provider != "ollama":
        so_mode = probe_structured_output(openrouter_client, model, hint=cfg.get("response_format_hint"))
        rf = {"type": "json_object"} if (so_mode == "json_object" and not plain_text) else None  # FIX-181
        for attempt in range(max_retries + 1):
            try:
                create_kwargs: dict = dict(model=model, max_tokens=max_tokens, messages=msgs)
                # FIX-211: pass temperature to OpenRouter tier
                _temp = cfg.get("temperature")
                if _temp is None:
                    _temp = (cfg.get("ollama_options") or {}).get("temperature")
                if _temp is not None:
                    create_kwargs["temperature"] = _temp
                if rf is not None:
                    create_kwargs["response_format"] = rf
                if _seed is not None:
                    create_kwargs["seed"] = _seed  # FIX-197
                if logprobs:
                    create_kwargs["logprobs"] = True
                    create_kwargs["top_logprobs"] = 1
                resp = openrouter_client.chat.completions.create(**create_kwargs)
                _content = resp.choices[0].message.content or ""
                if _LOG_LEVEL == "DEBUG":
                    _m = re.search(r"<think>(.*?)</think>", _content, re.DOTALL)
                    if _m:
                        print(f"[OpenRouter][THINK]: {_m.group(1).strip()}")
                raw = _THINK_RE.sub("", _content).strip()
                if not raw:
                    if attempt < max_retries:
                        print(f"[OpenRouter] Empty response (attempt {attempt + 1}) — retrying")
                        continue
                    print("[OpenRouter] Empty after all retries — falling through to next tier")
                    break  # do not return "" — let next tier try
                if token_out is not None:
                    _u = resp.usage
                    token_out["input"] = getattr(_u, "prompt_tokens", 0)
                    token_out["output"] = getattr(_u, "completion_tokens", 0)
                return raw
            except Exception as e:
                # FIX-416: hard connection errors capped at 1 retry
                _es = str(e).lower()
                _is_hard = any(kw.lower() in _es for kw in HARD_CONNECTION_KWS)
                _is_transient = any(kw.lower() in _es for kw in TRANSIENT_KWS)
                _max_att = 1 if _is_hard else max_retries
                if (_is_hard or _is_transient) and attempt < _max_att:
                    _delay = 2 if _is_hard else 4
                    print(f"[OpenRouter] {'Hard connection' if _is_hard else 'Transient'} (attempt {attempt + 1}): {e} — retrying in {_delay}s")
                    time.sleep(_delay)
                    continue
                print(f"[OpenRouter] Error: {e}")
                break

    # --- Tier 3: Ollama (local fallback) ---
    ollama_model = cfg.get("ollama_model") or os.environ.get("OLLAMA_MODEL", model)
    # explicit think= overrides cfg; None means use cfg default
    _think_flag = think if think is not None else cfg.get("ollama_think")
    _ollama_extra: dict = {}
    if _think_flag is not None:
        _ollama_extra["think"] = _think_flag
    _opts = cfg.get("ollama_options")
    if _opts is not None:  # None=not configured; {}=valid (though empty) — use `is not None`
        _ollama_extra["options"] = _opts
    if logprobs:
        _ollama_extra.setdefault("options", {})["logprobs"] = 1
    for attempt in range(max_retries + 1):
        try:
            # Do not pass max_tokens to Ollama — output is short (~8 tokens); the model stops
            # naturally; explicit cap causes empty responses under GPU load.
            _create_kw: dict = dict(
                model=ollama_model,
                messages=msgs,
            )
            if not plain_text:  # FIX-181: skip json_object for code generation
                _create_kw["response_format"] = {"type": "json_object"}
            if _ollama_extra:
                _create_kw["extra_body"] = _ollama_extra
            resp = ollama_client.chat.completions.create(**_create_kw)
            _content = resp.choices[0].message.content or ""
            if _LOG_LEVEL == "DEBUG":
                _m = re.search(r"<think>(.*?)</think>", _content, re.DOTALL)
                if _m:
                    print(f"[Ollama][THINK]: {_m.group(1).strip()}")
            raw = _THINK_RE.sub("", _content).strip()
            if not raw:
                if attempt < max_retries:
                    print(f"[Ollama] Empty response (attempt {attempt + 1}) — retrying")
                    continue
                print("[Ollama] Empty after all retries — returning None")
                break  # do not return "" — fall through to return None
            if token_out is not None:
                _u = resp.usage
                token_out["input"] = getattr(_u, "prompt_tokens", 0)
                token_out["output"] = getattr(_u, "completion_tokens", 0)
            return raw
        except Exception as e:
            # FIX-416: hard connection errors capped at 1 retry
            _es = str(e).lower()
            _is_hard = any(kw.lower() in _es for kw in HARD_CONNECTION_KWS)
            _is_transient = any(kw.lower() in _es for kw in TRANSIENT_KWS)
            _max_att = 1 if _is_hard else max_retries
            if (_is_hard or _is_transient) and attempt < _max_att:
                _delay = 2 if _is_hard else 4
                print(f"[Ollama] {'Hard connection' if _is_hard else 'Transient'} (attempt {attempt + 1}): {e} — retrying in {_delay}s")
                time.sleep(_delay)
                continue
            print(f"[Ollama] Error: {e}")
            break

    # Plain-text retry — if all json_object attempts failed, try without response_format
    try:
        _pt_kw: dict = dict(model=ollama_model, messages=msgs)  # no max_tokens
        if _ollama_extra:
            _pt_kw["extra_body"] = _ollama_extra
        resp = ollama_client.chat.completions.create(**_pt_kw)
        _content = resp.choices[0].message.content or ""
        if _LOG_LEVEL == "DEBUG":
            _m = re.search(r"<think>(.*?)</think>", _content, re.DOTALL)
            if _m:
                print(f"[Ollama-pt][THINK]: {_m.group(1).strip()}")
        raw = _THINK_RE.sub("", _content).strip()
        if raw:
            print(f"[Ollama] Plain-text retry succeeded: {raw[:60]!r}")
            if token_out is not None:
                _u = resp.usage
                token_out["input"] = getattr(_u, "prompt_tokens", 0)
                token_out["output"] = getattr(_u, "completion_tokens", 0)
            return raw
    except Exception as e:
        print(f"[Ollama] Plain-text retry failed: {e}")

    return None


def call_llm_raw(
    system: str,
    user_msg: str,
    model: str,
    cfg: dict,
    max_tokens: int = 20,
    think: bool | None = None,
    max_retries: int = 3,
    plain_text: bool = False,
    token_out: dict | None = None,
    logprobs: bool = False,
) -> str | None:
    """Call LLM with MODEL_FALLBACK retry (FIX-417). Primary model through all tiers first."""
    result = _call_raw_single_model(
        system, user_msg, model, cfg,
        max_tokens=max_tokens, think=think, max_retries=max_retries,
        plain_text=plain_text, token_out=token_out, logprobs=logprobs,
    )
    if result is None and _FALLBACK_MODEL and _FALLBACK_MODEL != model:
        print(f"[dispatch] Primary exhausted — retrying with MODEL_FALLBACK={_FALLBACK_MODEL}")
        result = _call_raw_single_model(
            system, user_msg, _FALLBACK_MODEL, {},
            max_tokens=max_tokens, think=think, max_retries=1,
            plain_text=plain_text, token_out=token_out, logprobs=logprobs,
        )
    return result


# ---------------------------------------------------------------------------
# Model routing helpers
# ---------------------------------------------------------------------------

_ANTHROPIC_MODEL_MAP = {
    "claude-haiku-4.5": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-sonnet-4.6": "claude-sonnet-4-6",
    "claude-opus-4.6": "claude-opus-4-6",
}


def is_claude_model(model: str) -> bool:
    return "claude" in model.lower()


def get_anthropic_model_id(model: str) -> str:
    """Map alias (e.g. 'anthropic/claude-haiku-4.5') to Anthropic API model ID."""
    clean = model.removeprefix("anthropic/").lower()
    return _ANTHROPIC_MODEL_MAP.get(clean, clean)


# ---------------------------------------------------------------------------
# CLI colors
# ---------------------------------------------------------------------------

CLI_RED = "\x1B[31m"
CLI_GREEN = "\x1B[32m"
CLI_CLR = "\x1B[0m"
CLI_BLUE = "\x1B[34m"
CLI_YELLOW = "\x1B[33m"


# ---------------------------------------------------------------------------
# Outcome map
# ---------------------------------------------------------------------------

OUTCOME_BY_NAME = {
    "OUTCOME_OK": Outcome.OUTCOME_OK,
    "OUTCOME_DENIED_SECURITY": Outcome.OUTCOME_DENIED_SECURITY,
    "OUTCOME_NONE_CLARIFICATION": Outcome.OUTCOME_NONE_CLARIFICATION,
    "OUTCOME_NONE_UNSUPPORTED": Outcome.OUTCOME_NONE_UNSUPPORTED,
    "OUTCOME_ERR_INTERNAL": Outcome.OUTCOME_ERR_INTERNAL,
}


# ---------------------------------------------------------------------------
# Dispatch: Pydantic models -> PCM runtime methods
# ---------------------------------------------------------------------------

# FIX-205: code-level write scope enforcement — paths that must never be written/deleted by agent.
# AGENTS.MD is the vault rulebook; docs/channels/ contains trust level definitions.
# Exception: otp.txt deletion is allowed (part of OTP consumption workflow, FIX-154).
_PROTECTED_WRITE = frozenset({"/AGENTS.MD", "/AGENTS.md"})
_PROTECTED_PREFIX = ("/docs/channels/",)
_OTP_PATH = "/docs/channels/otp.txt"


def dispatch(vm: PcmRuntimeClientSync, cmd: BaseModel):
    # FIX-205: code-level write scope enforcement
    if isinstance(cmd, (Req_Write, Req_Delete, Req_Move)):
        _target = getattr(cmd, "path", None) or getattr(cmd, "to_name", "")
        _from = getattr(cmd, "from_name", "")
        for _p in (_target, _from):
            if not _p:
                continue
            if _p in _PROTECTED_WRITE or any(_p.startswith(pfx) for pfx in _PROTECTED_PREFIX):
                # Exception: otp.txt can be deleted or rewritten (OTP consumption flow, FIX-154)
                # Delete = last token; Write = rewrite without consumed token (multi-token file)
                if _p == _OTP_PATH and isinstance(cmd, (Req_Delete, Req_Write)):
                    continue
                return f"ERROR: Write/delete/move to protected path '{_p}' is not allowed (FIX-205)"

    if isinstance(cmd, Req_Context):
        return vm.context(ContextRequest())
    if isinstance(cmd, Req_Tree):
        return vm.tree(TreeRequest(root=cmd.root, level=cmd.level))
    if isinstance(cmd, Req_Find):
        return vm.find(
            FindRequest(
                root=cmd.root,
                name=cmd.name,
                type={"all": 0, "files": 1, "dirs": 2}[cmd.kind],
                limit=cmd.limit,
            )
        )
    if isinstance(cmd, Req_Search):
        return vm.search(SearchRequest(root=cmd.root, pattern=cmd.pattern, limit=cmd.limit))
    if isinstance(cmd, Req_List):
        return vm.list(ListRequest(name=cmd.path))
    if isinstance(cmd, Req_Read):
        return vm.read(ReadRequest(
            path=cmd.path,
            number=cmd.number,
            start_line=cmd.start_line,
            end_line=cmd.end_line,
        ))
    if isinstance(cmd, Req_Write):
        return vm.write(WriteRequest(
            path=cmd.path,
            content=cmd.content,
            start_line=cmd.start_line,
            end_line=cmd.end_line,
        ))
    if isinstance(cmd, Req_Delete):
        return vm.delete(DeleteRequest(path=cmd.path))
    if isinstance(cmd, Req_MkDir):
        return vm.mk_dir(MkDirRequest(path=cmd.path))
    if isinstance(cmd, Req_Move):
        return vm.move(MoveRequest(from_name=cmd.from_name, to_name=cmd.to_name))
    if isinstance(cmd, ReportTaskCompletion):
        # AICODE-NOTE: Keep the report-completion schema aligned with
        # `bitgn.vm.pcm.AnswerRequest`: PAC1 grading consumes the recorded outcome,
        # so the agent must choose one explicitly instead of relying on local-only status.
        return vm.answer(
            AnswerRequest(
                message=cmd.message,
                outcome=OUTCOME_BY_NAME[cmd.outcome],
                refs=cmd.grounding_refs,
            )
        )

    raise ValueError(f"Unknown command: {cmd}")
