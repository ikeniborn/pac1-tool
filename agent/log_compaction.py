"""Log compaction, step facts accumulation, and state digest for the agent loop.

Extracted from loop.py to reduce God Object size.
Public API used by loop.py:
  _StepFact       — dataclass for one key step fact
  _extract_fact() — extract fact from a completed step result
  build_digest()  — build compact state digest from accumulated facts
  _compact_log()  — sliding-window log compaction with digest injection
  _compact_tool_result() — compact individual tool result for log history
  _history_action_repr() — compact assistant message for log history
"""
import json
from dataclasses import dataclass, field as dc_field


def _estimate_tokens(log: list) -> int:
    """Estimate token count for a message log (3 chars/token, conservative for mixed languages)."""
    return sum(len(str(m.get("content", ""))) for m in log) // 3


# ---------------------------------------------------------------------------
# Tool result compaction for log history
# ---------------------------------------------------------------------------

def _compact_tool_result(action_name: str, txt: str) -> str:
    """Compact tool result before storing in log history.
    Read results are preserved in full — file content may contain the answer.
    List and search results are normalized to a compact format."""
    if txt.startswith("WRITTEN:") or txt.startswith("DELETED:") or \
            txt.startswith("CREATED DIR:") or txt.startswith("MOVED:") or \
            txt.startswith("ERROR") or txt.startswith("VAULT STRUCTURE:"):
        return txt  # already compact or important verbatim

    if action_name == "Req_Read":
        return txt  # full file content preserved in log history

    if action_name == "Req_List":
        try:
            d = json.loads(txt)
            names = [e["name"] for e in d.get("entries", [])]
            return f"entries: {', '.join(names)}" if names else "entries: (empty)"
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    if action_name == "Req_Search":
        try:
            d = json.loads(txt)
            hits = [f"{m['path']}:{m.get('line', '')}" for m in d.get("matches", [])]
            if hits:
                return f"matches: {', '.join(hits)}"
            return "matches: (none)"
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    return txt  # fallback: unchanged


# ---------------------------------------------------------------------------
# Assistant message schema strip for log history
# ---------------------------------------------------------------------------

def _history_action_repr(action_name: str, action) -> str:
    """Compact function call representation for log history.
    Drops None/False/0/'' defaults (e.g. number=false, start_line=0) that waste tokens
    without carrying information. Full args still used for actual dispatch."""
    try:
        d = action.model_dump(exclude_none=True)
        d = {k: v for k, v in d.items() if v not in (False, 0, "")}
        args_str = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
        return f"Action: {action_name}({args_str})"
    except Exception:
        return f"Action: {action_name}({action.model_dump_json()})"


# ---------------------------------------------------------------------------
# Step facts accumulation for rolling state digest
# ---------------------------------------------------------------------------

@dataclass
class _StepFact:
    """One key fact extracted from a completed step for rolling digest."""
    kind: str    # "list", "read", "search", "write", "delete", "move", "mkdir", "stall"
    path: str
    summary: str  # compact 1-line description
    error: str = dc_field(default="")  # FIX-199: preserve error details through compaction


def _extract_fact(action_name: str, action, result_txt: str) -> "_StepFact | None":
    """Extract key fact from a completed step — used to build state digest."""
    path = getattr(action, "path", getattr(action, "from_name", ""))

    if action_name == "Req_Read":
        try:
            d = json.loads(result_txt)
            content = d.get("content", "").replace("\n", " ").strip()
            return _StepFact("read", path, content)
        except (json.JSONDecodeError, ValueError):
            pass
        return _StepFact("read", path, result_txt.replace("\n", " "))

    if action_name == "Req_List":
        try:
            d = json.loads(result_txt)
            names = [e["name"] for e in d.get("entries", [])]
            return _StepFact("list", path, ", ".join(names[:20]))
        except (json.JSONDecodeError, ValueError, KeyError):
            return _StepFact("list", path, result_txt[:200])

    if action_name == "Req_Search":
        try:
            d = json.loads(result_txt)
            hits = [f"{m['path']}:{m.get('line', '')}" for m in d.get("matches", [])]
            summary = ", ".join(hits) if hits else "(no matches)"
            return _StepFact("search", path, summary)
        except (json.JSONDecodeError, ValueError, KeyError):
            return _StepFact("search", path, result_txt[:200])

    # For mutating operations, check result_txt for errors before reporting success
    _is_err = result_txt.startswith("ERROR")
    _err_detail = result_txt[:300] if _is_err else ""  # FIX-199: capture error for digest
    if action_name == "Req_Write":
        summary = result_txt[:300] if _is_err else f"WRITTEN: {path}"
        return _StepFact("write", path, summary, error=_err_detail)
    if action_name == "Req_Delete":
        summary = result_txt[:300] if _is_err else f"DELETED: {path}"
        return _StepFact("delete", path, summary, error=_err_detail)
    if action_name == "Req_Move":
        to = getattr(action, "to_name", "?")
        summary = result_txt[:300] if _is_err else f"MOVED: {path} → {to}"
        return _StepFact("move", path, summary, error=_err_detail)
    if action_name == "Req_MkDir":
        summary = result_txt[:300] if _is_err else f"CREATED DIR: {path}"
        return _StepFact("mkdir", path, summary, error=_err_detail)

    return None


def build_digest(facts: "list[_StepFact]") -> str:
    """Build compact state digest from accumulated step facts.

    Read facts are deduplicated by path (latest wins) and emitted as metadata
    only — no content. This keeps the digest compact regardless of file sizes.
    Agent re-reads if it needs the content again.
    """
    # FIX-409: Deduplicate reads: last read of each path wins
    latest_reads: dict[str, "_StepFact"] = {}
    for f in facts:
        if f.kind == "read":
            latest_reads[f.path] = f

    sections: dict[str, list[str]] = {
        "LISTED": [], "READ": [], "FOUND": [],
        "DONE": [],
        "ERRORS": [],   # FIX-199: preserve error details through compaction
        "STALLS": [],   # FIX-200: preserve stall events through compaction
    }
    for f in facts:
        if f.kind == "list":
            sections["LISTED"].append(f"  {f.path}: {f.summary}")
        elif f.kind == "read":
            if latest_reads.get(f.path) is f:  # FIX-409: emit only the latest read per path
                char_count = len(f.summary)
                sections["READ"].append(f"  {f.path}: (read, {char_count} chars)")
        elif f.kind == "search":
            sections["FOUND"].append(f"  {f.summary}")
        elif f.kind in ("write", "delete", "move", "mkdir"):
            sections["DONE"].append(f"  {f.summary}")
        elif f.kind == "stall":  # FIX-200
            sections["STALLS"].append(f"  {f.summary}")
        if f.error:  # FIX-199: errors on any kind propagate to ERRORS section
            sections["ERRORS"].append(f"  {f.kind}({f.path}): {f.error}")
    parts = [
        f"{label}:\n" + "\n".join(lines)
        for label, lines in sections.items()
        if lines
    ]
    return "State digest:\n" + ("\n".join(parts) if parts else "(no facts)")


# ---------------------------------------------------------------------------
# Log compaction (sliding window)
# ---------------------------------------------------------------------------

def _compact_log(log: list, max_tool_pairs: int = 7, preserve_prefix: list | None = None,
                 step_facts: "list[_StepFact] | None" = None) -> list:
    """Keep preserved prefix + last N assistant/tool message pairs.
    Older pairs are replaced with a single summary message.
    If step_facts provided, uses build_digest() instead of 'Actions taken:'."""
    prefix_len = len(preserve_prefix) if preserve_prefix else 0
    tail = log[prefix_len:]
    max_msgs = max_tool_pairs * 2

    if len(tail) <= max_msgs:
        return log

    old = tail[:-max_msgs]
    kept = tail[-max_msgs:]

    # Extract confirmed operations from compacted pairs (safety net for done_ops)
    confirmed_ops = []
    for msg in old:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user" and content:
            for line in content.splitlines():
                if line.startswith(("WRITTEN:", "DELETED:", "MOVED:", "CREATED DIR:")):
                    confirmed_ops.append(line)

    parts: list[str] = []
    if confirmed_ops:
        parts.append("Confirmed ops (already done, do NOT redo):\n" + "\n".join(f"  {op}" for op in confirmed_ops))

    # Use ALL accumulated step facts as the complete state digest.
    # Always use the full step_facts list — never slice by old_step_count, because:
    # 1. Extra injected messages (auto-lists, stall hints, JSON retries) shift len(old)//2
    # 2. After a previous compaction the old summary message itself lands in `old`, skewing the count
    # 3. step_facts is the authoritative ground truth regardless of how many compactions occurred
    if step_facts:
        parts.append(build_digest(step_facts))
        print(f"\x1B[33m[compact] Compacted {len(old)} msgs into digest ({len(step_facts)} facts)\x1B[0m")
    else:
        # Fallback: plain text summary from assistant messages (legacy behaviour)
        summary_parts = []
        for msg in old:
            if msg.get("role") == "assistant" and msg.get("content"):
                summary_parts.append(f"- {msg['content'][:120]}")
        if summary_parts:
            parts.append("Actions taken:\n" + "\n".join(summary_parts[-5:]))

    summary = "Previous steps summary:\n" + ("\n".join(parts) if parts else "(none)")

    base = preserve_prefix if preserve_prefix is not None else log[:prefix_len]
    return list(base) + [{"role": "user", "content": summary}] + kept
