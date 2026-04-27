"""Aggregate and promote soft task-type candidates (FIX-325, step 3).

Usage
-----
    uv run python scripts/analyze_task_types.py              # summary only
    uv run python scripts/analyze_task_types.py --promote    # interactive promote
    uv run python scripts/analyze_task_types.py --min-count 3  # change threshold

Reads  : data/task_type_candidates.jsonl  (written by classifier._log_soft_candidate)
Mutates: data/task_types.json             (only in --promote mode, with confirm)

Each candidate record:
    {ts, task_text, classified_as, llm_suggested, vault_hint_present}

Records are grouped by a normalized form of `llm_suggested`:
  - lowercase
  - non-alphanumeric → "_"
  - collapsed underscores, stripped

After promotion, prints a reminder to run:
    uv run python scripts/optimize_prompts.py --target classifier
so the COPRO-compiled DSPy classifier learns the new type.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parent.parent
_CANDIDATES_PATH = _ROOT / "data" / "task_type_candidates.jsonl"
_REGISTRY_PATH = _ROOT / "data" / "task_types.json"
_WIKI_FRAGMENTS_DIR = _ROOT / "data" / "wiki" / "fragments"


def _normalize_label(raw: str) -> str:
    s = raw.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _load_candidates(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _load_registry_raw(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_registry_raw(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _group(candidates: Iterable[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for rec in candidates:
        sug = str(rec.get("llm_suggested", "")).strip()
        if not sug:
            continue
        key = _normalize_label(sug)
        if not key:
            continue
        buckets[key].append(rec)
    return buckets


def _print_summary(buckets: dict[str, list[dict]], min_count: int) -> None:
    if not buckets:
        print("no candidates found in", _CANDIDATES_PATH)
        return
    rows = sorted(buckets.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    total = sum(len(v) for v in buckets.values())
    print(f"Soft-label candidates: {total} records across {len(buckets)} labels "
          f"(promote threshold: ≥{min_count})\n")
    print(f"{'label':<24} {'count':>6}  sample task_text")
    print("-" * 78)
    for key, recs in rows:
        marker = "✓" if len(recs) >= min_count else " "
        sample = recs[0].get("task_text", "")[:44]
        variants = Counter(r.get("llm_suggested") for r in recs)
        variants_note = ""
        if len(variants) > 1:
            top_two = ", ".join(f"{v}({c})" for v, c in variants.most_common(2))
            variants_note = f"  [variants: {top_two}]"
        print(f"{marker} {key:<22} {len(recs):>6}  {sample}{variants_note}")
    print()
    eligible = [k for k, v in buckets.items() if len(v) >= min_count]
    if eligible:
        print(f"Eligible for promotion (count ≥ {min_count}): {', '.join(eligible)}")
        print("Run with --promote to start the interactive flow.")
    else:
        print(f"No labels reached the promotion threshold of {min_count}.")


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    resp = input(f"{msg}{suffix}: ").strip()
    return resp or default


def _prompt_yn(msg: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    resp = input(f"{msg} [{hint}]: ").strip().lower()
    if not resp:
        return default
    return resp in ("y", "yes", "да", "д")


def _promote(buckets: dict[str, list[dict]], min_count: int) -> None:
    registry = _load_registry_raw(_REGISTRY_PATH)
    existing = set(registry.get("types", {}).keys())
    eligible = [
        (key, recs) for key, recs in sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        if len(recs) >= min_count and key not in existing
    ]
    if not eligible:
        print(f"Nothing to promote: no labels with count ≥ {min_count} outside the registry.")
        return

    print(f"Promoting {len(eligible)} candidate label(s). Ctrl-C or EOF to stop; accepted entries are saved.\n")
    promoted: list[str] = []
    try:
        for key, recs in eligible:
            variants = Counter(r.get("llm_suggested") for r in recs)
            top_label = variants.most_common(1)[0][0]
            print(f"─ candidate '{key}' ({len(recs)} records, top variant: {top_label!r})")
            for r in recs[:3]:
                print(f"    · {r.get('task_text', '')[:80]}")

            if not _prompt_yn(f"Add type '{key}' to registry?", default=False):
                print("  skipped.\n")
                continue

            name = _prompt("  type name", default=key)
            if name in existing:
                print(f"  '{name}' already exists — skipping.\n")
                continue
            description = _prompt("  description", default=f"tasks similar to: {top_label}")
            model_env = _prompt("  MODEL_ env var", default=f"MODEL_{name.upper()}")
            fallback_raw = _prompt("  fallback_chain (comma-separated)", default="default")
            fallback = [s.strip() for s in fallback_raw.split(",") if s.strip()]
            wiki_folder = _prompt("  wiki_folder", default=name)

            entry = {
                "description": description,
                "model_env": model_env,
                "fallback_chain": fallback,
                "wiki_folder": wiki_folder,
                "fast_path": None,
                "needs_builder": True,
                "status": "soft",
            }
            registry["types"][name] = entry
            existing.add(name)
            promoted.append(name)
            # Ensure wiki folder exists so future fragments have a home.
            (_WIKI_FRAGMENTS_DIR / wiki_folder).mkdir(parents=True, exist_ok=True)
            print(f"  ✓ added '{name}' with status='soft'\n")
    except (EOFError, KeyboardInterrupt):
        print("\n(interrupted — saving accepted entries)")

    if promoted:
        _save_registry_raw(_REGISTRY_PATH, registry)
        print(f"Wrote {len(promoted)} entries to {_REGISTRY_PATH}: {', '.join(promoted)}")
        print()
        print("NEXT STEPS:")
        print("  1. Set MODEL_<UPPER> in .env for any new type that needs a specific model.")
        print("  2. Recompile the DSPy classifier so it learns to predict the new types:")
        print("       uv run python scripts/optimize_prompts.py --target classifier")
        print("  3. (Optional) Add a bespoke _TASK_BLOCKS entry in agent/prompt.py —")
        print("     until you do, new types reuse the 'default' system-prompt block.")
    else:
        print("No types promoted.")


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--promote", action="store_true",
                        help="Interactively promote eligible candidates into data/task_types.json.")
    parser.add_argument("--min-count", type=int,
                        default=int(os.environ.get("PROMOTE_MIN_COUNT", "5")),
                        help="Minimum candidate count to consider a label for promotion (default 5, env PROMOTE_MIN_COUNT).")
    parser.add_argument("--candidates", type=Path, default=_CANDIDATES_PATH,
                        help="Path to candidates JSONL (default: data/task_type_candidates.jsonl).")
    args = parser.parse_args()

    candidates = _load_candidates(args.candidates)
    if not candidates:
        print(f"No candidates found in {args.candidates}.")
        print("Run the agent with LLM classification enabled — candidates accumulate when")
        print("the LLM proposes a type outside the current registry.")
        return 0

    buckets = _group(candidates)
    _print_summary(buckets, args.min_count)

    if args.promote:
        print()
        _promote(buckets, args.min_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
