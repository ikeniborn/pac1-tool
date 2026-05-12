#!/usr/bin/env python3
"""Synthesize eval_log optimization entries into candidate files."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

_ROOT = Path(__file__).parent.parent
_EVAL_LOG = _ROOT / "data" / "eval_log.jsonl"
_RULES_DIR = _ROOT / "data" / "rules"
_SECURITY_DIR = _ROOT / "data" / "security"
_PROMPTS_OPTIMIZED_DIR = _ROOT / "data" / "prompts" / "optimized"
_PROCESSED_FILE = _ROOT / "data" / ".eval_optimizations_processed"
_MODELS_JSON = _ROOT / "models.json"


def _load_model_cfg(model: str) -> dict:
    raw = json.loads(_MODELS_JSON.read_text())
    profiles = raw.get("_profiles", {})
    cfg = dict(raw.get(model, {}))
    for fname in ("ollama_options", "ollama_options_evaluator"):
        if isinstance(cfg.get(fname), str):
            cfg[fname] = profiles.get(cfg[fname], {})
    return cfg


def _load_processed() -> set[str]:
    if _PROCESSED_FILE.exists():
        return set(line for line in _PROCESSED_FILE.read_text().splitlines() if line)
    return set()


def _save_processed(hashes: set[str]) -> None:
    _PROCESSED_FILE.write_text("\n".join(sorted(hashes)) + "\n")


def _entry_hash(task_text: str, channel: str, rec: str) -> str:
    return hashlib.sha256(f"{channel}|{task_text}|{rec}".encode()).hexdigest()[:16]


def _existing_rules_text() -> str:
    parts = []
    for f in sorted(_RULES_DIR.glob("*.yaml")):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(r, dict) and "content" in r:
                parts.append(f"- {r['content'].strip()}")
        except Exception:
            pass
    return "\n".join(parts)


def _next_num(directory: Path, prefix: str) -> int:
    existing = []
    for f in directory.glob("*.yaml"):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            rid = r.get("id", "")
            if rid.startswith(prefix):
                num_part = rid[len(prefix):].split("-")[0]
                if num_part.isdigit():
                    existing.append(int(num_part))
        except Exception:
            pass
    return max(existing, default=0) + 1


def _synthesize_rule(raw_rec: str, existing_rules_md: str, model: str, cfg: dict) -> str | None:
    from agent.llm import call_llm_raw

    system = (
        "Convert the raw recommendation into a concise, actionable SQL planning rule. "
        "Start with 'Never', 'Always', or 'Use'. One self-contained paragraph. "
        "Include a concrete SQL example if helpful. "
        "If the recommendation is already fully covered by an existing rule, respond with exactly: null\n\n"
        f"Existing rules:\n{existing_rules_md}"
    )
    result = call_llm_raw(system, f"Raw recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=512, plain_text=True)
    if not result:
        return None
    result = result.strip()
    return None if result.lower() == "null" else result


def _synthesize_security_gate(raw_rec: str, model: str, cfg: dict) -> dict | None:
    from agent.llm import call_llm_raw
    from agent.json_extract import _extract_json_from_text

    system = (
        "Convert the security recommendation into a gate spec. "
        "Return JSON: {\"pattern\": \"<regex or null>\", \"check\": \"<name or null>\", \"message\": \"<block reason>\"}. "
        "Exactly one of pattern or check must be non-null. "
        "If not blockable as a regex/check, return exactly: null"
    )
    result = call_llm_raw(system, f"Security recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=256)
    if not result:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    parsed = _extract_json_from_text(result)
    if not isinstance(parsed, dict) or not parsed.get("message"):
        return None
    if not parsed.get("pattern") and not parsed.get("check"):
        return None
    return parsed


def _synthesize_prompt_patch(raw_rec: str, model: str, cfg: dict) -> dict | None:
    from agent.llm import call_llm_raw
    from agent.json_extract import _extract_json_from_text

    system = (
        "Convert the prompt optimization recommendation into a markdown rule block. "
        "Return JSON: {\"target_file\": \"<basename e.g. answer.md>\", \"content\": \"<markdown section starting with ## heading>\"}. "
        "If too vague to produce a concrete rule, return exactly: null"
    )
    result = call_llm_raw(system, f"Prompt recommendation:\n{raw_rec}",
                          model, cfg, max_tokens=512)
    if not result:
        return None
    result = result.strip()
    if result.lower() == "null":
        return None
    parsed = _extract_json_from_text(result)
    if not isinstance(parsed, dict):
        return None
    if not parsed.get("target_file") or not parsed.get("content"):
        return None
    return parsed


def _write_rule(num: int, content: str, entry: dict, raw_rec: str) -> Path:
    rule_id = f"sql-{num:03d}"
    dest = _RULES_DIR / f"{rule_id}.yaml"
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump({
            "id": rule_id, "phase": "sql_plan", "verified": False, "source": "eval",
            "content": content, "created": date.today().isoformat(),
            "eval_score": entry.get("score"),
            "raw_recommendation": raw_rec,
        }, f, allow_unicode=True, default_flow_style=False)
    return dest


def _write_security(num: int, gate_spec: dict, entry: dict, raw_rec: str) -> Path:
    gate_id = f"sec-{num:03d}"
    dest = _SECURITY_DIR / f"{gate_id}.yaml"
    record: dict = {
        "id": gate_id, "action": "block", "message": gate_spec["message"],
        "verified": False, "source": "eval", "created": date.today().isoformat(),
        "task_text": entry["task_text"][:120],
        "eval_score": entry.get("score"),
        "raw_recommendation": raw_rec,
    }
    if gate_spec.get("pattern"):
        record["pattern"] = gate_spec["pattern"]
    if gate_spec.get("check"):
        record["check"] = gate_spec["check"]
    with open(dest, "w", encoding="utf-8") as f:
        yaml.dump(record, f, allow_unicode=True, default_flow_style=False)
    return dest


def _write_prompt(patch_result: dict, entry: dict, raw_rec: str) -> Path:
    _PROMPTS_OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    n = len(list(_PROMPTS_OPTIMIZED_DIR.glob(f"{today}-*.md"))) + 1
    dest = _PROMPTS_OPTIMIZED_DIR / f"{today}-{n:02d}-{patch_result['target_file']}"
    header = (
        f"<!-- target: {patch_result['target_file']} | "
        f"score: {entry.get('score', '?')} | created: {today} -->\n"
        f"<!-- raw: {raw_rec[:120]} -->\n\n"
    )
    dest.write_text(header + patch_result["content"] + "\n", encoding="utf-8")
    return dest


def main(dry_run: bool = False) -> None:
    load_dotenv()
    model = os.environ.get("MODEL_EVALUATOR", "")
    if not model:
        print("ERROR: MODEL_EVALUATOR not set", file=sys.stderr)
        sys.exit(1)
    cfg = _load_model_cfg(model)

    if not _EVAL_LOG.exists():
        print(f"No eval log at {_EVAL_LOG}")
        return

    entries = [json.loads(l) for l in _EVAL_LOG.read_text().splitlines() if l.strip()]
    processed = _load_processed()
    rules_md = _existing_rules_text()
    new_processed = set(processed)
    written = 0

    for entry in entries:
        for raw_rec in entry.get("rule_optimization", []):
            h = _entry_hash(entry["task_text"], "rule", raw_rec)
            if h in processed:
                continue
            print(f"[rule] {raw_rec[:80]}...")
            content = _synthesize_rule(raw_rec, rules_md, model, cfg)
            if content is None:
                new_processed.add(h)
                print("  → skip (null/duplicate)")
                continue
            num = _next_num(_RULES_DIR, "sql-")
            if dry_run:
                print(f"  → [DRY RUN] sql-{num:03d}.yaml: {content[:100]}")
            else:
                dest = _write_rule(num, content, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.add(h)
                written += 1

        for raw_rec in entry.get("security_optimization", []):
            h = _entry_hash(entry["task_text"], "security", raw_rec)
            if h in processed:
                continue
            print(f"[security] {raw_rec[:80]}...")
            gate_spec = _synthesize_security_gate(raw_rec, model, cfg)
            if gate_spec is None:
                new_processed.add(h)
                print("  → skip (null/not-applicable)")
                continue
            num = _next_num(_SECURITY_DIR, "sec-")
            if dry_run:
                print(f"  → [DRY RUN] sec-{num:03d}.yaml: {gate_spec.get('message', '')}")
            else:
                dest = _write_security(num, gate_spec, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.add(h)
                written += 1

        for raw_rec in entry.get("prompt_optimization", []):
            h = _entry_hash(entry["task_text"], "prompt", raw_rec)
            if h in processed:
                continue
            print(f"[prompt] {raw_rec[:80]}...")
            patch_result = _synthesize_prompt_patch(raw_rec, model, cfg)
            if patch_result is None:
                new_processed.add(h)
                print("  → skip (null/vague)")
                continue
            if dry_run:
                print(f"  → [DRY RUN] {patch_result['target_file']}: {patch_result['content'][:80]}")
            else:
                dest = _write_prompt(patch_result, entry, raw_rec)
                print(f"  → {dest.name}")
                new_processed.add(h)
                written += 1

    if not dry_run:
        _save_processed(new_processed)
        print(f"\nDone. {written} candidate(s) written.")
    else:
        total = sum(
            1 for e in entries
            for ch, key in [("rule", "rule_optimization"),
                            ("security", "security_optimization"),
                            ("prompt", "prompt_optimization")]
            for r in e.get(key, [])
            if _entry_hash(e["task_text"], ch, r) not in processed
        )
        print(f"\n[DRY RUN] {total} entry(ies) would be processed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
