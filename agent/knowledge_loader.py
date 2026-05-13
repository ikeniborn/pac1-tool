"""Shared loaders for existing rules/security/prompts content."""
from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent
_RULES_DIR = _ROOT / "data" / "rules"
_SECURITY_DIR = _ROOT / "data" / "security"
_PROMPTS_DIR = _ROOT / "data" / "prompts"
_PROMPTS_OPTIMIZED_DIR = _PROMPTS_DIR / "optimized"


def existing_rules_text() -> str:
    parts = []
    for f in sorted(_RULES_DIR.glob("*.yaml")):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(r, dict) and r.get("id") and r.get("content"):
                parts.append(f"- {r['id']}: {r['content'].strip()}")
        except Exception:
            pass
    return "\n".join(parts)


def existing_security_text() -> str:
    parts = []
    for f in sorted(_SECURITY_DIR.glob("*.yaml")):
        try:
            r = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(r, dict) and r.get("id") and r.get("message"):
                parts.append(f"- {r['id']}: {r['message']}")
        except Exception:
            pass
    return "\n".join(parts)


def existing_prompts_text() -> str:
    parts = []
    for f in sorted(_PROMPTS_DIR.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            parts.append(f"=== {f.name} ===\n{content}")
        except Exception:
            pass
    for f in sorted(_PROMPTS_OPTIMIZED_DIR.glob("*.md")):
        try:
            content = f.read_text(encoding="utf-8")
            parts.append(f"=== optimized/{f.name} ===\n{content}")
        except Exception:
            pass
    return "\n".join(parts)
