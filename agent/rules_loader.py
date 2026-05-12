"""Load SQL planning rules from data/rules/ (one YAML file per rule)."""
from __future__ import annotations

from pathlib import Path

import yaml

_RULES_DIR = Path(__file__).parent.parent / "data" / "rules"


class RulesLoader:
    def __init__(self, directory: Path = _RULES_DIR):
        self._dir = directory
        self._rules: list[dict] = self._load()

    def _load(self) -> list[dict]:
        rules = []
        for f in sorted(self._dir.glob("*.yaml")):
            try:
                rule = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(rule, dict):
                    rules.append(rule)
            except Exception:
                pass
        return rules

    def get_rules_markdown(self, phase: str, verified_only: bool = True) -> str:
        filtered = [
            r for r in self._rules
            if r.get("phase") == phase and (not verified_only or r.get("verified", False))
        ]
        return "\n\n".join(f"- {r['content'].strip()}" for r in filtered)

