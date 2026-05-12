"""Minimal agent loop for ecom SQL benchmark."""
import json
import os
import re
import time

from google.protobuf.json_format import MessageToDict
from pydantic import ValidationError

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync

from .dispatch import (
    CLI_RED, CLI_GREEN, CLI_CLR, CLI_YELLOW, CLI_BLUE,
    anthropic_client, openrouter_client, ollama_client,
    get_anthropic_model_id,
    get_provider,
    probe_structured_output,
    get_response_format,
    TRANSIENT_KWS, HARD_CONNECTION_KWS,
    _THINK_RE,
    dispatch,
)
from .json_extract import _extract_json_from_text, _normalize_parsed
from .models import NextStep, ReportTaskCompletion, Req_Write, Req_Delete
from .prephase import PrephaseResult

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
MAX_STEPS = int(os.environ.get("MAX_STEPS", "5"))


def _to_anthropic_messages(log: list) -> tuple[str, list]:
    """Convert OpenAI-format log to (system_prompt, messages) for Anthropic API."""
    system = ""
    messages = []
    for msg in log:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system = content
            continue
        if role not in ("user", "assistant"):
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n\n" + content
        else:
            messages.append({"role": role, "content": content})
    if not messages or messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "(start)"})
    return system, messages


def _call_openai_tier(
    oai_client,
    model: str,
    log: list,
    max_tokens: int | None,
    label: str,
    response_format: dict | None = None,
    temperature: float | None = None,
) -> tuple[NextStep | None, int, int, int, int]:
    """Shared retry loop for OpenAI-compatible tiers (OpenRouter, Ollama).
    Returns (result, elapsed_ms, input_tokens, output_tokens, thinking_tokens)."""
    for attempt in range(4):
        raw = ""
        elapsed_ms = 0
        try:
            started = time.time()
            create_kwargs: dict = dict(
                model=model,
                messages=log,
                **({"max_completion_tokens": max_tokens} if max_tokens is not None else {}),
            )
            if temperature is not None:
                create_kwargs["temperature"] = temperature
            if response_format is not None:
                create_kwargs["response_format"] = response_format
            resp = oai_client.chat.completions.create(**create_kwargs)
            elapsed_ms = int((time.time() - started) * 1000)
            raw = resp.choices[0].message.content or ""
        except Exception as e:
            err_str = str(e)
            is_hard = any(kw.lower() in err_str.lower() for kw in HARD_CONNECTION_KWS)
            is_transient = any(kw.lower() in err_str.lower() for kw in TRANSIENT_KWS)
            max_attempt = 1 if is_hard else 3
            if (is_hard or is_transient) and attempt < max_attempt:
                delay = 2 if is_hard else 4
                print(f"{CLI_YELLOW}[{label}] {'Hard' if is_hard else 'Transient'} error "
                      f"(attempt {attempt + 1}): {e} — retrying in {delay}s{CLI_CLR}")
                time.sleep(delay)
                continue
            print(f"{CLI_RED}[{label}] Error: {e}{CLI_CLR}")
            break
        else:
            in_tok = getattr(getattr(resp, "usage", None), "prompt_tokens", 0)
            out_tok = getattr(getattr(resp, "usage", None), "completion_tokens", 0)
            _me: dict = getattr(resp, "model_extra", None) or {}
            _eval_count = int(_me.get("eval_count", 0) or 0)
            _eval_ms = int(_me.get("eval_duration", 0) or 0) // 1_000_000
            _pr_count = int(_me.get("prompt_eval_count", 0) or 0)
            _pr_ms = int(_me.get("prompt_eval_duration", 0) or 0) // 1_000_000
            if _eval_ms > 0:
                _gen_tps = _eval_count / (_eval_ms / 1000.0)
                _pr_tps = _pr_count / max(_pr_ms, 1) * 1000.0
                print(f"{CLI_YELLOW}[{label}] ollama: gen={_gen_tps:.0f} tok/s  prompt={_pr_tps:.0f} tok/s{CLI_CLR}")
            think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
            think_tok = len(think_match.group(1)) // 4 if think_match else 0
            if _LOG_LEVEL == "DEBUG" and think_match:
                print(f"{CLI_YELLOW}[{label}][THINK]: {think_match.group(1).strip()}{CLI_CLR}")
            raw = _THINK_RE.sub("", raw).strip()
            _raw_limit = None if _LOG_LEVEL == "DEBUG" else 500
            print(f"{CLI_YELLOW}[{label}] RAW: {raw[:_raw_limit]}{CLI_CLR}")

            if response_format is not None:
                try:
                    parsed = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    parsed = _extract_json_from_text(raw)
                    if parsed is None:
                        continue
                    print(f"{CLI_YELLOW}[{label}] JSON extracted from text{CLI_CLR}")
            else:
                parsed = _extract_json_from_text(raw)
                if parsed is None:
                    print(f"{CLI_RED}[{label}] JSON extraction failed{CLI_CLR}")
                    break
                print(f"{CLI_YELLOW}[{label}] JSON extracted from free-form text{CLI_CLR}")

            if isinstance(parsed, dict):
                parsed = _normalize_parsed(parsed)
            try:
                return NextStep.model_validate(parsed), elapsed_ms, in_tok, out_tok, think_tok
            except ValidationError as e:
                print(f"{CLI_RED}[{label}] JSON parse failed: {e}{CLI_CLR}")
                break
    return None, 0, 0, 0, 0


def _call_llm(
    log: list, model: str, max_tokens: int, cfg: dict
) -> tuple[NextStep | None, int, int, int, int]:
    """Call LLM: Anthropic SDK → OpenRouter → Ollama.
    Returns (result, elapsed_ms, input_tokens, output_tokens, thinking_tokens)."""
    if _LOG_LEVEL == "DEBUG":
        print(f"\n{CLI_YELLOW}[DEBUG] Conversation log ({len(log)} messages):{CLI_CLR}")
        for _di, _dm in enumerate(log):
            _role = _dm.get("role", "?")
            _content = _dm.get("content", "")
            print(f"  [{_di}] {_role}: {str(_content)[:200]}{CLI_CLR}")

    provider = get_provider(model, cfg)
    temperature = cfg.get("temperature")

    if provider == "anthropic" and anthropic_client:
        system, messages = _to_anthropic_messages(log)
        anthropic_model = get_anthropic_model_id(model)
        thinking_budget = cfg.get("thinking_budget", 0)
        for attempt in range(4):
            try:
                started = time.time()
                kwargs: dict = dict(model=anthropic_model, max_tokens=max_tokens, messages=messages)
                if system:
                    kwargs["system"] = system
                if thinking_budget > 0:
                    kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
                resp = anthropic_client.messages.create(**kwargs)
                elapsed_ms = int((time.time() - started) * 1000)
                raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
                in_tok = resp.usage.input_tokens if resp.usage else 0
                out_tok = resp.usage.output_tokens if resp.usage else 0
                think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
                think_tok = len(think_match.group(1)) // 4 if think_match else 0
                raw = _THINK_RE.sub("", raw).strip()
                _raw_limit = None if _LOG_LEVEL == "DEBUG" else 500
                print(f"{CLI_YELLOW}[Anthropic] RAW: {raw[:_raw_limit]}{CLI_CLR}")
                parsed = _extract_json_from_text(raw) or {}
                if isinstance(parsed, dict):
                    parsed = _normalize_parsed(parsed)
                try:
                    return NextStep.model_validate(parsed), elapsed_ms, in_tok, out_tok, think_tok
                except ValidationError as e:
                    print(f"{CLI_RED}[Anthropic] Parse failed: {e}{CLI_CLR}")
                    break
            except Exception as e:
                err_str = str(e)
                is_transient = any(kw.lower() in err_str.lower() for kw in TRANSIENT_KWS)
                if is_transient and attempt < 3:
                    print(f"{CLI_YELLOW}[Anthropic] Transient error: {e} — retrying{CLI_CLR}")
                    time.sleep(4)
                    continue
                print(f"{CLI_RED}[Anthropic] Error: {e}{CLI_CLR}")
                break
        return None, 0, 0, 0, 0

    if provider == "ollama" or (provider not in ("anthropic", "openrouter") and not openrouter_client):
        ollama_model = model
        ollama_opts: dict = cfg.get("ollama_options", {}) or {}
        rfmt = get_response_format(probe_structured_output(ollama_client, model))
        temp = temperature if temperature is not None else ollama_opts.get("temperature")
        extra_body: dict | None = {k: v for k, v in ollama_opts.items() if k != "temperature"} or None
        create_kwargs: dict = dict(model=ollama_model, messages=log)
        if max_tokens:
            create_kwargs["max_completion_tokens"] = max_tokens
        if temp is not None:
            create_kwargs["temperature"] = temp
        if rfmt is not None:
            create_kwargs["response_format"] = rfmt
        if extra_body:
            create_kwargs["extra_body"] = extra_body
        result, elapsed_ms, in_tok, out_tok, think_tok = _call_openai_tier(
            ollama_client, ollama_model, log, max_tokens, "Ollama", rfmt, temp
        )
        return result, elapsed_ms, in_tok, out_tok, think_tok

    # OpenRouter
    if openrouter_client:
        rfmt = get_response_format(probe_structured_output(openrouter_client, model))
        return _call_openai_tier(openrouter_client, model, log, max_tokens, "OpenRouter", rfmt, temperature)

    print(f"{CLI_RED}[loop] No LLM client available for provider={provider}{CLI_CLR}")
    return None, 0, 0, 0, 0


def _format_result(result) -> str:
    """Render protobuf result to string for conversation log."""
    if result is None:
        return "{}"
    try:
        d = MessageToDict(result)
        if "root" in d:
            # Compact tree rendering
            def _render(node: dict, indent: int = 0) -> str:
                prefix = "  " * indent
                name = node.get("name", "?")
                children = node.get("children", [])
                line = f"{prefix}{name}"
                if children:
                    return line + "\n" + "\n".join(_render(c, indent + 1) for c in children)
                return line
            return "VAULT STRUCTURE:\n" + _render(d["root"])
        return json.dumps(d, ensure_ascii=False)
    except Exception:
        return str(result)


def run_loop(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
    max_steps: int = MAX_STEPS,
) -> dict:
    """Run agent loop. Returns stats dict."""
    log = pre.log
    max_tokens = cfg.get("max_completion_tokens", 16384)
    total_in_tok = 0
    total_out_tok = 0
    total_elapsed_ms = 0
    step_facts: list[str] = []
    outcome = "OUTCOME_NONE_CLARIFICATION"
    done_ops: list[str] = []

    for step in range(max_steps):
        step_label = f"step_{step + 1}"
        print(f"\n--- {step_label} --- ")

        job, elapsed_ms, in_tok, out_tok, _think = _call_llm(log, model, max_tokens, cfg)
        total_in_tok += in_tok
        total_out_tok += out_tok
        total_elapsed_ms += elapsed_ms

        if job is None:
            print(f"{CLI_RED}[loop] LLM call failed at step {step + 1}{CLI_CLR}")
            break

        cmd = job.function
        action_name = cmd.__class__.__name__
        elapsed_s = elapsed_ms / 1000
        print(f"{action_name} ({elapsed_ms} ms)")

        # Empty path guard
        if hasattr(cmd, "path") and cmd.path == "":
            print(f"{CLI_YELLOW}[loop] Empty path rejected{CLI_CLR}")
            log.append({"role": "user", "content": "ERROR: path cannot be empty. Provide a valid path."})
            continue

        # Duplicate-write guard
        if isinstance(cmd, Req_Write):
            dup_target = f"WRITTEN: {cmd.path}"
            if dup_target in done_ops:
                print(f"{CLI_YELLOW}[loop] Duplicate write blocked: {cmd.path}{CLI_CLR}")
                log.append({"role": "user", "content": f"BLOCKED: '{cmd.path}' already written. Call report_completion."})
                continue

        _tool_args = {k: v for k, v in cmd.model_dump().items() if k != "tool"}
        assistant_msg = f"Action: {action_name}({json.dumps(_tool_args)})"
        log.append({"role": "assistant", "content": assistant_msg})

        if isinstance(cmd, ReportTaskCompletion):
            outcome = cmd.outcome
            step_facts.append(f"report_completion: {cmd.outcome}")
            print(f"  tool='report_completion' completed_steps_laconic={cmd.completed_steps_laconic!r} "
                  f"message='{cmd.message[:100]}' grounding_refs={cmd.grounding_refs!r} outcome='{outcome}'")
            try:
                dispatch(vm, cmd)
            except Exception as e:
                print(f"{CLI_RED}[loop] report_completion dispatch error: {e}{CLI_CLR}")
            print(f"{CLI_GREEN}[evaluator] APPROVED{CLI_CLR}")
            print(f"OUT: {{}}")
            print(f"agent {outcome}. Summary:")
            for s in cmd.completed_steps_laconic:
                print(f"- {s}")
            print(f"\nAGENT SUMMARY: {cmd.message}")
            for ref in cmd.grounding_refs:
                print(f"- {ref}")
            break

        # Execute tool
        step_facts.append(f"{action_name}: {getattr(cmd, 'path', getattr(cmd, 'pattern', ''))}")
        print(f"  tool='{cmd.tool}' " + " ".join(f"{k}={repr(v)}" for k, v in _tool_args.items()))

        try:
            result = dispatch(vm, cmd)
        except Exception as e:
            result_txt = f"ERROR: {e}"
            print(f"{CLI_RED}[loop] dispatch error: {e}{CLI_CLR}")
            log.append({"role": "user", "content": result_txt})
            continue

        if isinstance(cmd, Req_Write):
            done_ops.append(f"WRITTEN: {cmd.path}")
        elif isinstance(cmd, Req_Delete):
            done_ops.append(f"DELETED: {cmd.path}")

        result_txt = _format_result(result)
        _raw_limit = None if _LOG_LEVEL == "DEBUG" else 2000
        print(f"OUT: {result_txt[:200]}")

        log.append({"role": "user", "content": f"Result of {action_name}: {result_txt[:_raw_limit] if _raw_limit else result_txt}"})

    return {
        "outcome": outcome,
        "step_facts": step_facts,
        "done_ops": done_ops,
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": total_elapsed_ms,
    }
