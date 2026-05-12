"""Load and append SQL planning rules from data/rules/ (one YAML file per rule)."""
from __future__ import annotations

from datetime import date
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

    def append_rule(self, content: str, task_id: str) -> None:
        existing_nums = []
        for r in self._rules:
            rid = r.get("id", "")
            if rid.startswith("sql-") and rid[4:].isdigit():
                existing_nums.append(int(rid[4:]))
        next_num = max(existing_nums, default=0) + 1
        rule_id = f"sql-{next_num:03d}"
        new_rule = {
            "id": rule_id,
            "phase": "sql_plan",
            "verified": False,
            "source": "auto",
            "content": content,
            "created": date.today().isoformat(),
            "task_id": task_id,
        }
        self._rules.append(new_rule)
        self._dir.mkdir(parents=True, exist_ok=True)
        dest = self._dir / f"{rule_id}-auto.yaml"
        with open(dest, "w", encoding="utf-8") as f:
            yaml.dump(new_rule, f, allow_unicode=True, default_flow_style=False)
