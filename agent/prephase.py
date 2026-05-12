import csv
import io
import os
from dataclasses import dataclass, field

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ReadRequest, ExecRequest
from google.protobuf.json_format import MessageToDict

from .agents_md_parser import parse_agents_md
from .llm import CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_YELLOW

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_SCHEMA_TABLES = ["products", "product_properties", "inventory", "kinds"]


@dataclass
class PrephaseResult:
    log: list
    preserve_prefix: list
    agents_md_content: str = ""
    agents_md_path: str = ""
    db_schema: str = ""
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)


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
    system_prompt_text: str,
) -> PrephaseResult:
    print(f"\n{CLI_BLUE}[prephase] Starting pre-phase exploration{CLI_CLR}")

    log: list = [{"role": "system", "content": system_prompt_text}]

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

    prephase_parts = [f"TASK: {task_text}"]
    if agents_md_content:
        if _LOG_LEVEL == "DEBUG":
            print(f"{CLI_BLUE}[prephase] AGENTS.MD content:\n{agents_md_content}{CLI_CLR}")
        prephase_parts.append(
            f"\n{agents_md_path} CONTENT (source of truth for vault semantics):\n{agents_md_content}"
        )
    prephase_parts.append(
        "\nNOTE: Use AGENTS.MD above to identify actual folder paths. "
        "Verify paths with list/find before acting. Do not assume paths."
    )

    log.append({"role": "user", "content": "\n".join(prephase_parts)})
    preserve_prefix = list(log)

    agents_md_index: dict = parse_agents_md(agents_md_content) if agents_md_content else {}

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
        log=log,
        preserve_prefix=preserve_prefix,
        agents_md_content=agents_md_content,
        agents_md_path=agents_md_path,
        db_schema=db_schema,
        agents_md_index=agents_md_index,
        schema_digest=schema_digest,
    )
