"""Security gate evaluation — gates loaded from data/security/*.yaml."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_SECURITY_DIR = Path(__file__).parent.parent / "data" / "security"


def load_security_gates(directory: Path = _SECURITY_DIR) -> list[dict]:
    """Load all gate definitions from *.yaml files in directory, sorted by filename."""
    gates = []
    for f in sorted(directory.glob("*.yaml")):
        try:
            gate = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(gate, dict) and gate.get("verified", True):
                gates.append(gate)
        except Exception:
            pass
    return gates


def check_sql_queries(queries: list[str], security_gates: list[dict]) -> str | None:
    """Apply security gates to SQL queries. Returns error message or None if all pass."""
    for query in queries:
        for gate in security_gates:
            if "pattern" in gate:
                if re.search(gate["pattern"], query, re.IGNORECASE):
                    return f"[{gate['id']}] {gate['message']}: {query[:80]}"
            elif gate.get("check") == "no_where_clause":
                if _is_select(query) and not _has_where_clause(query):
                    return f"[{gate['id']}] {gate['message']}: {query[:80]}"
    return None


def check_path_access(path: str, security_gates: list[dict]) -> str | None:
    """Check if a file path access is blocked by path_prefix gates."""
    for gate in security_gates:
        if "path_prefix" in gate and path.startswith(gate["path_prefix"]):
            return f"[{gate['id']}] {gate['message']}: {path}"
    return None


def _is_select(sql: str) -> bool:
    return sql.strip().upper().startswith("SELECT")


def _has_where_clause(sql: str) -> bool:
    # Strip string literals to avoid matching WHERE inside quoted values
    stripped = re.sub(r"'[^']*'", "", sql).upper()
    return "WHERE" in stripped.split()
