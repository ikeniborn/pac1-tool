"""System prompt builder — loads blocks from data/prompts/*.md."""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent / "data" / "prompts"

_BLOCKS: dict[str, str] = {}
_warned_missing_blocks: set[str] = set()


def _load_all() -> None:
    if not _PROMPTS_DIR.exists():
        return
    for f in _PROMPTS_DIR.glob("*.md"):
        _BLOCKS[f.stem] = f.read_text(encoding="utf-8")


_load_all()


def load_prompt(name: str) -> str:
    """Return prompt block by file stem name. Returns '' if not found."""
    return _BLOCKS.get(name, "")


_TASK_BLOCKS: dict[str, list[str]] = {
    "lookup":   ["core", "lookup", "catalogue"],
    "temporal": ["core", "lookup"],
    "capture":  ["core"],
    "crm":      ["core", "lookup"],
    "distill":  ["core", "lookup"],
    "preject":  ["core"],
    "default":  ["core", "lookup", "catalogue"],
}


def build_system_prompt(task_type: str) -> str:
    """Assemble system prompt from file-based blocks for the given task type."""
    if task_type not in _TASK_BLOCKS and task_type not in _warned_missing_blocks:
        _warned_missing_blocks.add(task_type)
        print(f"[PROMPT] task_type={task_type!r} has no _TASK_BLOCKS entry — using 'default'")
    block_names = _TASK_BLOCKS.get(task_type, _TASK_BLOCKS["default"])
    return "\n".join(load_prompt(name) for name in block_names)


# Backward-compatibility aliases
system_prompt = build_system_prompt("default")
SYSTEM_PROMPT = build_system_prompt("default")
