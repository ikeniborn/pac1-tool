"""Schema-aware SQL validator: unknown columns, unverified literals, double-key JOINs."""
from __future__ import annotations

import re


def check_schema_compliance(
    queries: list[str],
    schema_digest: dict,
    confirmed_values: dict,
    task_text: str,
) -> str | None:
    """Check queries against schema. Returns first error string or None if all pass."""
    known_cols: set[str] = set()
    for table_info in schema_digest.get("tables", {}).values():
        for col in table_info.get("columns", []):
            known_cols.add(col["name"])

    all_confirmed: set[str] = set()
    for vals in confirmed_values.values():
        if isinstance(vals, list):
            all_confirmed.update(str(v) for v in vals)
        else:
            all_confirmed.add(str(vals))

    for q in queries:
        # Check 1: Unknown table.col references
        if known_cols:
            for match in re.finditer(r'\b\w+\.(\w+)\b', q):
                col = match.group(1)
                if col not in known_cols:
                    return f"unknown column: {col} (not in schema)"

        # Check 2: Unverified string literal copied from task_text
        for match in re.finditer(r"'([^']+)'", q):
            val = match.group(1)
            if val in task_text and val not in all_confirmed:
                return f"unverified literal: '{val}' — run discovery first"

        # Check 3: Double-key JOIN on product_properties
        if re.search(
            r'JOIN\s+product_properties\s+\w+.*?WHERE.*?\w+\.key\s*=.*?AND.*?\w+\.key\s*=',
            q, re.IGNORECASE | re.DOTALL,
        ):
            return "double-key JOIN on product_properties — use separate EXISTS subqueries"

    return None
