import csv
import io
import os
from dataclasses import dataclass, field

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ExecRequest, ReadRequest
from google.protobuf.json_format import MessageToDict

from .agents_md_parser import parse_agents_md
from .llm import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_SCHEMA_TABLES = ["products", "product_properties", "inventory", "kinds", "carts", "cart_items"]


@dataclass
class PrephaseResult:
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)
    agent_id: str = ""
    current_date: str = ""


def _exec_sql_text(vm: EcomRuntimeClientSync, query: str) -> str:
    try:
        result = vm.exec(ExecRequest(path="/bin/sql", args=[query]))
        try:
            d = MessageToDict(result)
            txt = d.get("stdout", "") or d.get("output", "") or ""
            if txt:
                return txt
        except Exception:
            pass
        return getattr(result, "stdout", "") or getattr(result, "output", "") or ""
    except Exception:
        return ""


def _parse_csv_rows(text: str) -> list[dict]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        reader = csv.DictReader(io.StringIO(stripped))
        return list(reader)
    except Exception:
        return []


def _build_schema_digest(vm: EcomRuntimeClientSync) -> dict:
    tables: dict = {}
    for table in _SCHEMA_TABLES:
        cols_txt = _exec_sql_text(vm, f"PRAGMA table_info({table})")
        cols = [
            {"name": r["name"], "type": r["type"], "notnull": r.get("notnull", "0")}
            for r in _parse_csv_rows(cols_txt) if "name" in r
        ]
        fk_txt = _exec_sql_text(vm, f"PRAGMA foreign_key_list({table})")
        fk = [
            {"from": r["from"], "to": f"{r['table']}.{r['to']}"}
            for r in _parse_csv_rows(fk_txt) if "from" in r
        ]
        entry: dict = {"columns": cols}
        if fk:
            entry["fk"] = fk
        tables[table] = entry

    keys_txt = _exec_sql_text(vm, (
        "SELECT key, COUNT(*) AS cnt, "
        "SUM(CASE WHEN value_text IS NOT NULL THEN 1 ELSE 0 END) AS text_cnt, "
        "SUM(CASE WHEN value_number IS NOT NULL THEN 1 ELSE 0 END) AS num_cnt "
        "FROM product_properties GROUP BY key ORDER BY cnt DESC LIMIT 20"
    ))
    rows = _parse_csv_rows(keys_txt)
    top_keys = [r["key"] for r in rows if "key" in r]
    value_type_map: dict = {}
    for r in rows:
        if "key" not in r:
            continue
        try:
            text_cnt = int(r.get("text_cnt") or 0)
            num_cnt = int(r.get("num_cnt") or 0)
            value_type_map[r["key"]] = "text" if text_cnt >= num_cnt else "number"
        except (ValueError, TypeError):
            value_type_map[r["key"]] = "text"

    return {"tables": tables, "value_type_map": value_type_map, "top_keys": top_keys}


def run_prephase(
    vm: EcomRuntimeClientSync,
    task_text: str,
) -> PrephaseResult:
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    agents_md_content = ""
    agents_md_path = ""
    for candidate in ("/AGENTS.MD", "/AGENTS.md"):
        try:
            r = vm.read(ReadRequest(path=candidate))
            if r.content:
                agents_md_content = r.content
                agents_md_path = candidate
                print(f"{CLI_BLUE}[prephase] read {candidate}:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
                break
        except Exception:
            pass

    if agents_md_content and _LOG_LEVEL == "DEBUG":
        print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")

    agents_md_index: dict = parse_agents_md(agents_md_content) if agents_md_content else {}

    # /bin/date — best-effort
    current_date = ""
    try:
        date_result = vm.exec(ExecRequest(path="/bin/date"))
        current_date = getattr(date_result, "stdout", "").strip()
        print(f"{CLI_BLUE}[prephase] /bin/date:{CLI_CLR} {CLI_GREEN}{current_date!r}{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/date failed: {e}{CLI_CLR}")

    # /bin/id — best-effort
    agent_id = ""
    try:
        id_result = vm.exec(ExecRequest(path="/bin/id"))
        agent_id = getattr(id_result, "stdout", "").strip()
        print(f"{CLI_BLUE}[prephase] /bin/id:{CLI_CLR} {CLI_GREEN}{agent_id!r}{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/id failed: {e}{CLI_CLR}")

    db_schema = ""
    schema_digest: dict = {}
    try:
        schema_result = vm.exec(ExecRequest(path="/bin/sql", args=[".schema"]))
        try:
            d = MessageToDict(schema_result)
            db_schema = d.get("stdout", "") or d.get("output", "")
        except Exception:
            db_schema = ""
        if not db_schema:
            db_schema = getattr(schema_result, "stdout", "") or getattr(schema_result, "output", "") or ""
        print(f"{CLI_BLUE}[prephase] /bin/sql .schema:{CLI_CLR} {CLI_GREEN}ok{CLI_CLR}")
        schema_digest = _build_schema_digest(vm)
        print(f"{CLI_BLUE}[prephase] schema_digest: {len(schema_digest.get('tables', {}))} tables{CLI_CLR}")
    except Exception as e:
        print(f"{CLI_YELLOW}[prephase] /bin/sql .schema: {e}{CLI_CLR}")

    print(f"{CLI_BLUE}[prephase] done{CLI_CLR}")

    return PrephaseResult(
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        db_schema=db_schema,
        agents_md_index=agents_md_index,
        schema_digest=schema_digest,
        agent_id=agent_id,
        current_date=current_date,
    )
