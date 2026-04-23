"""Claude Code tier — spawn iclaude CLI as stateless LLM.

Bypasses applied (all required to isolate iclaude from the host project):
  - cwd=<tmpdir>        → no project CLAUDE.md auto-discovery
  - --no-save           → no session history written under ~/.claude/projects
  - --strict-mcp-config → block user ~/.claude MCP servers from loading
  - --mcp-config <empty> → no tools exposed to the model (stateless LLM use)
  - --print             → headless non-interactive mode
  - --output-format json → parseable envelope with result + usage
  - env stripped        → ANTHROPIC_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY
                          removed when CC_STRIP_PROJECT_ENV=1 so iclaude uses OAuth

The CLI has no --seed and no response_format flag; JSON-only output is requested
via a system-prompt trailer. Caller handles JSON parsing (dispatch / loop).
"""
from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path


_CC_ENABLED = os.environ.get("CC_ENABLED") == "1"
_ICLAUDE_CMD = os.environ.get("ICLAUDE_CMD", "iclaude")
_CC_STRIP_PROJECT_ENV = os.environ.get("CC_STRIP_PROJECT_ENV", "1") == "1"
try:
    _CC_MAX_RETRIES = int(os.environ.get("CC_MAX_RETRIES", "2"))
except ValueError:
    _CC_MAX_RETRIES = 2
try:
    _CC_RETRY_DELAY_S = float(os.environ.get("CC_RETRY_DELAY_S", "4"))
except ValueError:
    _CC_RETRY_DELAY_S = 4.0

_STRIPPED_ENV_KEYS = frozenset({
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
})


def _build_env() -> dict[str, str]:
    if _CC_STRIP_PROJECT_ENV:
        return {k: v for k, v in os.environ.items() if k not in _STRIPPED_ENV_KEYS}
    return dict(os.environ)


def _collect_stdout(pipe, buf: list[str]) -> None:
    try:
        for line in pipe:
            buf.append(line)
    except Exception:
        pass


def _parse_envelope(lines: list[str]) -> tuple[str, int, int, int, int]:
    """Extract result text and token usage from iclaude --output-format json.
    Envelope shape: {"type":"result","subtype":"success","result":"...",
                     "usage":{"input_tokens":N,"cache_creation_input_tokens":N,
                              "cache_read_input_tokens":N,"output_tokens":N},
                     "modelUsage":{"<model>":{"inputTokens":N,"outputTokens":N,
                                              "cacheCreationInputTokens":N,
                                              "cacheReadInputTokens":N}}}.
    Returns (text, fresh_in_tok, out_tok, cache_creation, cache_read).
    FIX-N: separates fresh input from cached tokens (Claude API semantics —
    usage.input_tokens is ONLY the non-cached portion of the last message).
    Scans lines in reverse for the last success envelope."""
    for line in reversed(lines):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if obj.get("type") != "result" or obj.get("subtype") != "success":
            continue
        text = obj.get("result", "")
        if not isinstance(text, str):
            continue
        in_tok = 0
        out_tok = 0
        cache_cr = 0
        cache_rd = 0
        usage = obj.get("usage")
        if isinstance(usage, dict):
            in_tok = int(usage.get("input_tokens") or 0)
            out_tok = int(usage.get("output_tokens") or 0)
            cache_cr = int(usage.get("cache_creation_input_tokens") or 0)
            cache_rd = int(usage.get("cache_read_input_tokens") or 0)
        if not in_tok and not out_tok and not cache_cr and not cache_rd:
            mu = obj.get("modelUsage")
            if isinstance(mu, dict):
                for per_model in mu.values():
                    if isinstance(per_model, dict):
                        in_tok += int(per_model.get("inputTokens") or 0)
                        out_tok += int(per_model.get("outputTokens") or 0)
                        cache_cr += int(per_model.get("cacheCreationInputTokens") or 0)
                        cache_rd += int(per_model.get("cacheReadInputTokens") or 0)
        return text, in_tok, out_tok, cache_cr, cache_rd
    return "", 0, 0, 0, 0


def _spawn_once(
    cmd: list[str],
    cwd: str,
    env: dict[str, str],
    timeout_s: int,
) -> tuple[list[str], int, str]:
    """Spawn iclaude once. Returns (stdout_lines, exit_code, fail_reason).
    fail_reason: 'ok' | 'timeout' | 'error'."""
    stdout_lines: list[str] = []
    fail_reason = "ok"
    exit_code = -1
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        t = threading.Thread(
            target=_collect_stdout,
            args=(proc.stdout, stdout_lines),
            daemon=True,
        )
        t.start()
        t.join(timeout=timeout_s)
        if proc.poll() is None:
            fail_reason = "timeout"
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                proc.terminate()
            t.join(timeout=5)
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    proc.kill()
                t.join(timeout=5)
        else:
            t.join(timeout=30)
        exit_code = proc.wait()
    except Exception as e:
        fail_reason = "error"
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
        print(f"[CC] spawn error: {e}")
    return stdout_lines, exit_code, fail_reason


def cc_complete(
    system: str,
    user_msg: str,
    *,
    cfg: dict,
    max_tokens: int,
    plain_text: bool = False,
    token_out: dict | None = None,
) -> str | None:
    """Stateless LLM call via iclaude subprocess.

    Returns assistant text (JSON string when plain_text=False; freeform otherwise),
    or None after CC_MAX_RETRIES+1 failed attempts. The caller parses JSON.

    max_tokens is ignored — iclaude has no equivalent flag; CC stops naturally.
    """
    if not _CC_ENABLED:
        return None

    cc_model = cfg.get("cc_model") or os.environ.get("CC_DEFAULT_MODEL", "")
    cc_opts = cfg.get("cc_options") or {}
    if isinstance(cc_opts, str):
        cc_opts = {}
    cc_effort = cc_opts.get("cc_effort") or os.environ.get("CC_DEFAULT_EFFORT", "")
    try:
        cc_timeout = int(cc_opts.get("cc_timeout_s") or os.environ.get("CC_DEFAULT_TIMEOUT_S", "180"))
    except (TypeError, ValueError):
        cc_timeout = 180

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="cc_mcp_"
    ) as f:
        json.dump({"mcpServers": {}}, f)
        cfg_path = f.name

    cwd = tempfile.mkdtemp(prefix="cc_cwd_")

    sys_prompt = system or ""
    if not plain_text:
        sys_prompt += (
            "\n\n# Output format\n"
            "Return ONLY a valid JSON object. "
            "No preamble, no code fences, no commentary."
        )

    cmd = [
        *shlex.split(_ICLAUDE_CMD),
        "--no-save",
        "--print",
        "--strict-mcp-config",
        "--mcp-config", cfg_path,
        "--system-prompt", sys_prompt,
        "--output-format", "json",
    ]
    if cc_model:
        cmd.extend(["--model", cc_model])
    if cc_effort:
        cmd.extend(["--effort", cc_effort])

    # FIX-N+1: pass-through CC flags from cc_options (OAuth-compatible only;
    # --bare is intentionally NOT supported — it forces ANTHROPIC_API_KEY/apiKeyHelper
    # and disables OAuth / keychain reads, breaking iclaude's auth model).
    cc_fallback = cc_opts.get("cc_fallback_model") or os.environ.get("CC_DEFAULT_FALLBACK_MODEL", "")
    if cc_fallback:
        cmd.extend(["--fallback-model", cc_fallback])

    _exclude_dyn = cc_opts.get("cc_exclude_dynamic")
    if _exclude_dyn is None:
        _exclude_dyn = os.environ.get("CC_DEFAULT_EXCLUDE_DYNAMIC") == "1"
    if _exclude_dyn:
        cmd.append("--exclude-dynamic-system-prompt-sections")

    _schema = cc_opts.get("cc_json_schema")
    if _schema and not plain_text:
        # FIX-325: when schema constrains task_type.enum, override with the live
        # registry values so adding a type to data/task_types.json takes effect
        # without touching models.json.
        try:
            _props = _schema.get("properties") if isinstance(_schema, dict) else None
            _tt_field = _props.get("task_type") if isinstance(_props, dict) else None
            if isinstance(_tt_field, dict) and "enum" in _tt_field:
                from .task_types import build_cc_json_schema_enum
                _schema = json.loads(json.dumps(_schema))  # deep-copy via json round-trip
                _schema["properties"]["task_type"]["enum"] = build_cc_json_schema_enum()
        except Exception as _exc:
            print(f"[CC] failed to inject registry enum into cc_json_schema ({_exc}) — using static schema")
        try:
            cmd.extend(["--json-schema", json.dumps(_schema, ensure_ascii=False)])
        except (TypeError, ValueError) as _exc:
            print(f"[CC] cc_json_schema is not JSON-serializable ({_exc}) — ignored")

    cmd.append(user_msg)

    env = _build_env()

    try:
        for attempt in range(_CC_MAX_RETRIES + 1):
            stdout_lines, exit_code, fail_reason = _spawn_once(cmd, cwd, env, cc_timeout)
            text, in_tok, out_tok, cache_cr, cache_rd = _parse_envelope(stdout_lines)
            if text:
                if token_out is not None:
                    token_out["input"] = in_tok
                    token_out["output"] = out_tok
                    token_out["cache_creation"] = cache_cr  # FIX-N
                    token_out["cache_read"] = cache_rd      # FIX-N
                return text

            # FIX-N+4: diagnostic — dump tail of stdout so we can distinguish
            # "iclaude crashed silently" vs "envelope parse failed" vs "rate-limited".
            _debug = os.environ.get("CC_DEBUG_EMPTY") == "1"
            if _debug or attempt >= _CC_MAX_RETRIES:
                tail = "".join(stdout_lines[-8:]).rstrip()[:800] or "<empty>"
                print(f"[CC] stdout tail (last {min(8, len(stdout_lines))} lines):\n{tail}")
            if attempt < _CC_MAX_RETRIES:
                print(
                    f"[CC] {fail_reason} or empty "
                    f"(attempt {attempt + 1}/{_CC_MAX_RETRIES + 1}, exit={exit_code}) "
                    f"— retrying in {_CC_RETRY_DELAY_S}s"
                )
                time.sleep(_CC_RETRY_DELAY_S)
            else:
                print(
                    f"[CC] Failed after {_CC_MAX_RETRIES + 1} attempts "
                    f"(last fail_reason={fail_reason}, exit={exit_code})"
                )
    finally:
        Path(cfg_path).unlink(missing_ok=True)
        try:
            Path(cwd).rmdir()
        except OSError:
            pass

    return None
