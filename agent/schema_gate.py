"""Schema-aware SQL validator: unknown columns, unverified literals, double-key JOINs."""
from __future__ import annotations

import sqlglot
import sqlglot.expressions as exp

SYSTEM_TABLES = {"sqlite_schema", "sqlite_master"}


def _build_alias_map(parsed: exp.Expression) -> dict[str, str]:
    """Return {alias_lower: table_name_lower} from FROM and JOIN clauses."""
    alias_map: dict[str, str] = {}
    for node in parsed.walk():
        if isinstance(node, exp.Table):
            table_name = node.name.lower() if node.name else ""
            alias = node.alias.lower() if node.alias else ""
            if table_name:
                alias_map[table_name] = table_name  # table refs itself
                if alias:
                    alias_map[alias] = table_name
    return alias_map


def _known_cols_by_table(schema_digest: dict) -> dict[str, set[str]]:
    """Return {table_name_lower: {col_name_lower, ...}}."""
    result: dict[str, set[str]] = {}
    for table, info in schema_digest.get("tables", {}).items():
        cols = {c["name"].lower() for c in info.get("columns", [])}
        result[table.lower()] = cols
    return result


def _check_query(
    q: str,
    schema_digest: dict,
    all_confirmed: set[str],
    task_text: str,
) -> str | None:
    try:
        parsed = sqlglot.parse_one(q, dialect="sqlite")
    except Exception:
        return None  # parse failure → let DB catch syntax errors

    alias_map = _build_alias_map(parsed)

    # Check 0: unknown table (requires non-empty digest)
    known_tables = set(schema_digest.get("tables", {}).keys())
    if known_tables:
        known_lower = {t.lower() for t in known_tables} | SYSTEM_TABLES
        for node in parsed.walk():
            if isinstance(node, exp.Table):
                name = (node.name or "").lower()
                if not name:
                    continue
                if name in known_lower:
                    continue
                if name.startswith("pragma_"):
                    continue
                return f"unknown table: '{name}' (not in schema digest)"

    cols_by_table = _known_cols_by_table(schema_digest)

    # Check 1: unknown qualified column references
    if cols_by_table:
        for node in parsed.walk():
            if isinstance(node, exp.Column):
                table_ref = node.table.lower() if node.table else ""
                col_name = node.name.lower() if node.name else ""
                if not table_ref:
                    continue  # unqualified column — skip
                real_table = alias_map.get(table_ref, "")
                if not real_table:
                    continue  # unknown alias — skip (DB will catch)
                known = cols_by_table.get(real_table, set())
                if known and col_name not in known:
                    return f"unknown column: {table_ref}.{col_name} (not in schema)"

    # System-table exemption: literals in sqlite_schema/sqlite_master/pragma_* queries
    # are table-name identifiers (DDL discovery), not data values.
    # pragma_table_info('x') parses as Table(Anonymous(name='pragma_table_info'))
    # so we check both node.name and inner Anonymous node names.
    referenced_tables: set[str] = set()
    for node in parsed.walk():
        if isinstance(node, exp.Table):
            referenced_tables.add((node.name or "").lower())
            if isinstance(node.this, exp.Anonymous):
                referenced_tables.add((node.this.name or "").lower())
    if any(t in SYSTEM_TABLES or t.startswith("pragma_") for t in referenced_tables):
        return None  # skip remaining literal/JOIN checks for system-table queries

    # Check 2: unverified literal — context-aware LIKE exemption
    for node in parsed.walk():
        if isinstance(node, exp.Literal) and node.is_string:
            val = node.this
            if val not in task_text:
                continue
            if val in all_confirmed:
                continue
            # Skip if parent is LIKE/ILike — discovery query
            parent = node.parent
            if isinstance(parent, (exp.Like, exp.ILike)):
                continue
            return f"unverified literal: '{val}' — use LIKE '%{val}%' for discovery first"

    # Check 3: double-key JOIN on product_properties
    for node in parsed.walk():
        if not isinstance(node, exp.Join):
            continue
        join_table_node = node.find(exp.Table)
        if not join_table_node:
            continue
        join_alias = join_table_node.alias.lower() if join_table_node.alias else ""
        join_table = alias_map.get(join_alias, alias_map.get(join_table_node.name.lower() if join_table_node.name else "", ""))
        if join_table != "product_properties":
            continue
        # Count key= conditions in WHERE scope
        key_eqs = [
            n for n in parsed.walk()
            if isinstance(n, exp.EQ)
            and isinstance(n.left, exp.Column)
            and n.left.name.lower() == "key"
        ]
        if len(key_eqs) > 1:
            return "double-key JOIN on product_properties — use separate EXISTS subqueries"

    return None


def check_schema_compliance(
    queries: list[str],
    schema_digest: dict,
    confirmed_values: dict,
    task_text: str,
) -> str | None:
    """Check queries against schema. Returns first error string or None if all pass."""
    all_confirmed: set[str] = set()
    for vals in confirmed_values.values():
        if isinstance(vals, list):
            all_confirmed.update(str(v) for v in vals)
        else:
            all_confirmed.add(str(vals))

    for q in queries:
        err = _check_query(q, schema_digest, all_confirmed, task_text)
        if err:
            return err
    return None
