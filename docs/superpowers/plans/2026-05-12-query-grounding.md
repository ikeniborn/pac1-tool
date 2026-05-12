# Query Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden query formation by adding programmatic AGENTS.MD indexing, schema digest, resolve phase, and schema-aware gate to the pipeline.

**Architecture:** New `resolve` phase runs one LLM call before the cycle loop to discover and confirm real DB values; a new `schema_gate` checks every plan for unknown columns, unverified literals, and double-key JOINs; AGENTS.MD is parsed into named sections and only task-relevant sections are injected per cycle; confirmed values accumulate across cycles and are passed as `# CONFIRMED VALUES` block.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, MagicMock, SQLite PRAGMA queries via existing `/bin/sql` exec path.

---

## File Structure

**New files:**
- `agent/agents_md_parser.py` — parse AGENTS.MD markdown into `{section: [lines]}`
- `agent/resolve.py` — resolve phase: LLM → discovery queries → confirmed_values
- `agent/schema_gate.py` — schema-aware SQL validator (unknown col, unverified literal, double-key JOIN)
- `data/prompts/resolve.md` — LLM prompt for resolve phase
- `tests/test_agents_md_parser.py`
- `tests/test_resolve.py`
- `tests/test_schema_gate.py`
- `tests/test_eval_metrics.py`

**Modified files:**
- `agent/models.py` — add `agents_md_refs`, `agents_md_anchor`, new metrics fields, `ResolveCandidate`, `ResolveOutput`
- `agent/prephase.py` — add `agents_md_index` + `schema_digest` to `PrephaseResult`; build them in `run_prephase()`
- `agent/pipeline.py` — update `_build_system()`, `run_pipeline()`, `_run_learn()`, add `_extract_discovery_results()`
- `agent/evaluator.py` — add `_compute_eval_metrics()`, extend `EvalInput`
- `data/prompts/sql_plan.md` — add `agents_md_refs` field to output format
- `data/prompts/learn.md` — add `agents_md_anchor` field to output format

---

## Task 1: Extend Pydantic Models

**Files:**
- Modify: `agent/models.py`
- Test: `tests/test_pipeline_models.py` (already exists — extend it)

- [ ] **Step 1: Write failing tests for new model fields**

```python
# Add to tests/test_pipeline_models.py

from agent.models import (
    SqlPlanOutput, LearnOutput, PipelineEvalOutput,
    ResolveCandidate, ResolveOutput,
)


def test_sql_plan_output_agents_md_refs_defaults_empty():
    obj = SqlPlanOutput(reasoning="r", queries=["SELECT 1 WHERE 1=1"])
    assert obj.agents_md_refs == []


def test_sql_plan_output_agents_md_refs_set():
    obj = SqlPlanOutput(reasoning="r", queries=["SELECT 1 WHERE 1=1"], agents_md_refs=["brand_aliases"])
    assert obj.agents_md_refs == ["brand_aliases"]


def test_learn_output_agents_md_anchor_defaults_none():
    obj = LearnOutput(reasoning="r", conclusion="c", rule_content="Always use X")
    assert obj.agents_md_anchor is None


def test_learn_output_agents_md_anchor_set():
    obj = LearnOutput(reasoning="r", conclusion="c", rule_content="r", agents_md_anchor="brand_aliases > Heco")
    assert obj.agents_md_anchor == "brand_aliases > Heco"


def test_pipeline_eval_output_new_metrics_default():
    obj = PipelineEvalOutput(
        reasoning="r", score=0.8, comment="c",
        prompt_optimization=[], rule_optimization=[],
    )
    assert obj.agents_md_coverage == 0.0
    assert obj.schema_grounding == 0.0


def test_pipeline_eval_output_new_metrics_set():
    obj = PipelineEvalOutput(
        reasoning="r", score=0.8, comment="c",
        prompt_optimization=[], rule_optimization=[],
        agents_md_coverage=0.75, schema_grounding=1.0,
    )
    assert obj.agents_md_coverage == 0.75
    assert obj.schema_grounding == 1.0


def test_resolve_candidate_minimal():
    c = ResolveCandidate(
        term="Heco",
        field="brand",
        discovery_query="SELECT DISTINCT brand FROM products WHERE brand ILIKE '%Heco%' LIMIT 10",
    )
    assert c.confirmed_value is None


def test_resolve_candidate_with_value():
    c = ResolveCandidate(
        term="heco", field="brand",
        discovery_query="SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10",
        confirmed_value="Heco",
    )
    assert c.confirmed_value == "Heco"


def test_resolve_output_validate():
    obj = ResolveOutput(
        reasoning="found brand",
        candidates=[
            ResolveCandidate(
                term="heco", field="brand",
                discovery_query="SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10",
            )
        ],
    )
    assert len(obj.candidates) == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_pipeline_models.py -v -k "agents_md_refs or agents_md_anchor or new_metrics or resolve"
```

Expected: ImportError or AttributeError — models don't have these fields yet.

- [ ] **Step 3: Implement new model fields**

Replace `agent/models.py` with:

```python
from typing import Literal

from pydantic import BaseModel


class SqlPlanOutput(BaseModel):
    reasoning: str
    queries: list[str]
    agents_md_refs: list[str] = []


class LearnOutput(BaseModel):
    reasoning: str
    conclusion: str
    rule_content: str
    agents_md_anchor: str | None = None


class AnswerOutput(BaseModel):
    reasoning: str
    message: str
    outcome: Literal[
        "OUTCOME_OK",
        "OUTCOME_NONE_CLARIFICATION",
        "OUTCOME_NONE_UNSUPPORTED",
        "OUTCOME_DENIED_SECURITY",
    ]
    grounding_refs: list[str]
    completed_steps: list[str]


class PipelineEvalOutput(BaseModel):
    reasoning: str
    score: float
    comment: str
    prompt_optimization: list[str]
    rule_optimization: list[str]
    security_optimization: list[str] = []
    agents_md_coverage: float = 0.0
    schema_grounding: float = 0.0


class ResolveCandidate(BaseModel):
    term: str
    field: str
    discovery_query: str
    confirmed_value: str | None = None


class ResolveOutput(BaseModel):
    reasoning: str
    candidates: list[ResolveCandidate]
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run pytest tests/test_pipeline_models.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/models.py tests/test_pipeline_models.py
git commit -m "feat: extend models with agents_md_refs, agents_md_anchor, eval metrics, ResolveCandidate/Output"
```

---

## Task 2: AGENTS.MD Parser

**Files:**
- Create: `agent/agents_md_parser.py`
- Create: `tests/test_agents_md_parser.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agents_md_parser.py

import pytest
from agent.agents_md_parser import parse_agents_md


def test_empty_string_returns_empty_dict():
    assert parse_agents_md("") == {}


def test_no_sections_returns_empty_dict():
    assert parse_agents_md("just some intro text\nno headers") == {}


def test_single_section():
    content = "## Brand Aliases\nheco = Heco\nmaker = Maker GmbH"
    result = parse_agents_md(content)
    assert "brand_aliases" in result
    assert result["brand_aliases"] == ["heco = Heco", "maker = Maker GmbH"]


def test_multiple_sections():
    content = "## Brand Aliases\nheco = Heco\n## Kind Synonyms\nscrew = bolt\nfastener = bolt"
    result = parse_agents_md(content)
    assert set(result.keys()) == {"brand_aliases", "kind_synonyms"}
    assert result["brand_aliases"] == ["heco = Heco"]
    assert result["kind_synonyms"] == ["screw = bolt", "fastener = bolt"]


def test_section_name_lowercased_and_underscored():
    content = "## Folder Roles\nsome/path = archive"
    result = parse_agents_md(content)
    assert "folder_roles" in result


def test_leading_content_before_first_section_ignored():
    content = "# Top-level heading\nIntro text\n## Brand Aliases\nheco = Heco"
    result = parse_agents_md(content)
    assert list(result.keys()) == ["brand_aliases"]


def test_empty_section_has_empty_lines():
    content = "## Brand Aliases\n## Kind Synonyms\nscrew = bolt"
    result = parse_agents_md(content)
    assert result["brand_aliases"] == []
    assert result["kind_synonyms"] == ["screw = bolt"]


def test_h1_heading_not_treated_as_section():
    content = "# Main Title\n## Brand Aliases\nheco = Heco"
    result = parse_agents_md(content)
    assert "main_title" not in result
    assert "brand_aliases" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_agents_md_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'agent.agents_md_parser'`

- [ ] **Step 3: Implement agents_md_parser**

Create `agent/agents_md_parser.py`:

```python
def parse_agents_md(content: str) -> dict[str, list[str]]:
    """Parse AGENTS.MD into {section_name: [lines]} for each ## section."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in content.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower().replace(" ", "_")
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_agents_md_parser.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/agents_md_parser.py tests/test_agents_md_parser.py
git commit -m "feat: add agents_md_parser to index AGENTS.MD sections"
```

---

## Task 3: Extend Prephase

**Files:**
- Modify: `agent/prephase.py`
- Modify: `tests/test_prephase.py` (update existing field check + add new tests)

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_prephase.py


def _make_vm_with_schema(agents_md="## Brand Aliases\nheco = Heco", schema="CREATE TABLE products"):
    """VM mock that handles read (AGENTS.MD) and exec (.schema + PRAGMA + SELECT)."""
    vm = MagicMock()
    agents_r = MagicMock()
    agents_r.content = agents_md

    def _read(req):
        if req.path in ("/AGENTS.MD", "/AGENTS.md"):
            return agents_r
        raise Exception(f"unexpected read: {req.path}")

    def _exec(req):
        r = MagicMock()
        r.stdout = ""
        if req.args and req.args[0] == ".schema":
            r.stdout = schema
        elif req.args and "PRAGMA" in req.args[0]:
            r.stdout = "cid,name,type,notnull,dflt_value,pk\n0,sku,TEXT,1,,1\n1,brand,TEXT,0,,0"
        elif req.args and "product_properties" in req.args[0] and "COUNT" in req.args[0]:
            r.stdout = "key,cnt,text_cnt,num_cnt\ndiameter_mm,100,0,100\nscrew_type,80,80,0"
        elif req.args and "foreign_key_list" in req.args[0]:
            r.stdout = ""
        return r

    vm.read.side_effect = _read
    vm.exec.side_effect = _exec
    return vm


def test_prephase_result_fields_updated():
    """PrephaseResult has agents_md_index and schema_digest fields."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert "agents_md_index" in fields
    assert "schema_digest" in fields


def test_agents_md_index_populated():
    """agents_md_index has parsed sections from AGENTS.MD."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "find Heco screws", "sys")
    assert "brand_aliases" in result.agents_md_index
    assert result.agents_md_index["brand_aliases"] == ["heco = Heco"]


def test_agents_md_index_empty_when_no_agents_md():
    """agents_md_index is empty dict if AGENTS.MD not found."""
    vm = MagicMock()
    vm.read.side_effect = Exception("not found")
    exec_r = MagicMock(); exec_r.stdout = ""
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "task", "sys")
    assert result.agents_md_index == {}


def test_schema_digest_has_tables():
    """schema_digest['tables'] has product-related tables."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "task", "sys")
    assert "tables" in result.schema_digest
    assert "products" in result.schema_digest["tables"]


def test_schema_digest_has_top_keys():
    """schema_digest['top_keys'] lists top property keys."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "task", "sys")
    assert "top_keys" in result.schema_digest
    assert "diameter_mm" in result.schema_digest["top_keys"]


def test_schema_digest_value_type_map():
    """schema_digest['value_type_map'] maps key to text/number."""
    vm = _make_vm_with_schema()
    result = run_prephase(vm, "task", "sys")
    vt = result.schema_digest.get("value_type_map", {})
    assert vt.get("diameter_mm") == "number"
    assert vt.get("screw_type") == "text"


def test_schema_digest_empty_on_exec_failure():
    """schema_digest is empty dict if all exec calls fail."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "## Brand Aliases\nheco = Heco"
    vm.read.return_value = agents_r
    vm.exec.side_effect = Exception("exec failed")
    result = run_prephase(vm, "task", "sys")
    assert result.schema_digest == {}
```

Also update the existing `test_prephase_result_fields` test since the field set now includes `agents_md_index` and `schema_digest`:

```python
def test_prephase_result_fields():
    """PrephaseResult has exactly the expected fields."""
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PrephaseResult)}
    assert fields == {
        "log", "preserve_prefix", "agents_md_content", "agents_md_path",
        "db_schema", "agents_md_index", "schema_digest",
    }
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_prephase.py -v
```

Expected: `test_prephase_result_fields` fails (missing new fields), `test_agents_md_index_*` and `test_schema_digest_*` fail.

- [ ] **Step 3: Implement prephase extension**

Replace `agent/prephase.py` with:

```python
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
            return d.get("stdout", "") or d.get("output", "") or ""
        except Exception:
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
```

- [ ] **Step 4: Fix the existing test that expects exactly 1 exec call**

In `tests/test_prephase.py`, update `test_normal_mode_reads_schema`:

```python
def test_normal_mode_reads_schema():
    """Normal mode calls vm.exec for schema and digest queries."""
    vm = MagicMock()
    agents_r = MagicMock(); agents_r.content = "AGENTS CONTENT"
    exec_r = MagicMock(); exec_r.stdout = "CREATE TABLE products ..."
    vm.read.return_value = agents_r
    vm.exec.return_value = exec_r
    result = run_prephase(vm, "find products", "sys prompt")
    # Called for .schema + PRAGMA table_info (4 tables) + PRAGMA foreign_key_list (4) + SELECT key
    assert vm.exec.call_count >= 1
    assert result.db_schema == "CREATE TABLE products ..."
```

- [ ] **Step 5: Run tests**

```
uv run pytest tests/test_prephase.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/prephase.py tests/test_prephase.py
git commit -m "feat: add agents_md_index and schema_digest to PrephaseResult"
```

---

## Task 4: Write Prompt Files

**Files:**
- Create: `data/prompts/resolve.md`
- Modify: `data/prompts/sql_plan.md`
- Modify: `data/prompts/learn.md`

No unit tests — verified by end-to-end runs. Commit each file separately.

- [ ] **Step 1: Create resolve.md**

Create `data/prompts/resolve.md`:

```markdown
# Resolve Phase

You are a value-resolution agent. Your job is to identify concrete identifiers in the task and generate discovery SQL queries to confirm their exact stored values in the database.

/no_think

## Task

Given a task description, an AGENTS.MD section index, and top property keys, extract unique identifiers (brands, models, kinds, attribute values with units) and generate one ILIKE discovery query per identifier.

## Rules

- Output PURE JSON only. The very first character must be `{`.
- `reasoning` field: briefly explain which terms you identified and why.
- `candidates` field: list of objects with `term`, `field`, and `discovery_query`.
- `field` must be one of: `brand`, `model`, `kind`, `attr_key`, `attr_value`.
- `discovery_query` MUST be a SELECT DISTINCT query with ILIKE or DISTINCT.
- Only discovery queries — no filter queries, no JOIN, no subqueries.
- If no identifiable terms exist, return empty candidates list.

## Discovery query patterns

Brand: `SELECT DISTINCT brand FROM products WHERE brand ILIKE '%<term>%' LIMIT 10`
Model: `SELECT DISTINCT model FROM products WHERE model ILIKE '%<term>%' LIMIT 10`
Kind: `SELECT DISTINCT name FROM kinds WHERE name ILIKE '%<term>%' LIMIT 10`
Attr key: `SELECT DISTINCT key FROM product_properties WHERE key ILIKE '%<term>%' LIMIT 10`
Attr value (text): `SELECT DISTINCT value_text FROM product_properties WHERE key = '<known_key>' AND value_text ILIKE '%<term>%' LIMIT 10`

## Output format (JSON only)

{"reasoning": "<which terms found and why>", "candidates": [{"term": "<raw term from task>", "field": "<brand|model|kind|attr_key|attr_value>", "discovery_query": "SELECT DISTINCT ..."}]}
```

- [ ] **Step 2: Commit resolve.md**

```bash
git add data/prompts/resolve.md
git commit -m "feat: add resolve phase prompt"
```

- [ ] **Step 3: Update sql_plan.md output format to require agents_md_refs**

In `data/prompts/sql_plan.md`, replace the output format line:

```
{"reasoning": "<chain-of-thought: why these queries answer the task>", "queries": ["SELECT ...", "SELECT ..."]}
```

with:

```
{"reasoning": "<chain-of-thought: why these queries answer the task>", "queries": ["SELECT ...", "SELECT ..."], "agents_md_refs": ["<section_key>", ...]}
```

Also add after the `## Rules` section, insert a new bullet after the existing bullets:

```
- `agents_md_refs` field MUST list every AGENTS.MD section key you consulted (e.g. `["brand_aliases", "kind_synonyms"]`). If you used no AGENTS.MD sections, return `[]`.
```

And add after `## Rules`, before `## Multi-attribute filtering`:

```
## CONFIRMED VALUES

When a `# CONFIRMED VALUES` block is present in your context, you MUST use those values as literals in WHERE clauses — do not re-invent them. Example: if `brand → confirmed: "Heco"`, use `WHERE brand = 'Heco'` not `WHERE brand ILIKE '%Heco%'`.
```

- [ ] **Step 4: Commit sql_plan.md**

```bash
git add data/prompts/sql_plan.md
git commit -m "feat: require agents_md_refs in sql_plan output; add CONFIRMED VALUES instruction"
```

- [ ] **Step 5: Update learn.md output format to require agents_md_anchor**

In `data/prompts/learn.md`, replace the output format line:

```
{"reasoning": "<diagnosis of what went wrong>", "conclusion": "<one-sentence summary>", "rule_content": "<markdown rule text>"}
```

with:

```
{"reasoning": "<diagnosis of what went wrong>", "conclusion": "<one-sentence summary>", "rule_content": "<markdown rule text>", "agents_md_anchor": "<section_key > entry, or null>"}
```

Also add to the `## Rules` section (after existing bullets):

```
- `agents_md_anchor` field: if the failure was caused by ignoring an AGENTS.MD section (e.g. wrong brand alias, wrong kind synonym), set this to `"<section_key> > <specific_entry>"` (e.g. `"brand_aliases > Heco"`). Set to `null` if failure is unrelated to AGENTS.MD.
```

- [ ] **Step 6: Commit learn.md**

```bash
git add data/prompts/learn.md
git commit -m "feat: require agents_md_anchor in learn output"
```

---

## Task 5: Resolve Phase

**Files:**
- Create: `agent/resolve.py`
- Create: `tests/test_resolve.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_resolve.py

import pytest
from unittest.mock import MagicMock, patch
from agent.resolve import _security_check, _first_value, run_resolve
from agent.prephase import PrephaseResult


def test_security_check_allows_ilike():
    assert _security_check("SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10") is None


def test_security_check_allows_distinct():
    assert _security_check("SELECT DISTINCT name FROM kinds WHERE name ILIKE '%screw%' LIMIT 10") is None


def test_security_check_blocks_drop():
    err = _security_check("DROP TABLE products")
    assert err is not None
    assert "DDL" in err or "not allowed" in err


def test_security_check_blocks_insert():
    err = _security_check("INSERT INTO products VALUES (1)")
    assert err is not None


def test_security_check_blocks_query_without_ilike_or_distinct():
    err = _security_check("SELECT brand FROM products WHERE brand = 'Heco'")
    assert err is not None
    assert "ILIKE" in err or "DISTINCT" in err


def test_first_value_returns_first_data_cell():
    csv_text = "brand\nHeco\nMaker"
    assert _first_value(csv_text) == "Heco"


def test_first_value_returns_none_for_header_only():
    assert _first_value("brand\n") is None


def test_first_value_returns_none_for_empty():
    assert _first_value("") is None


def test_first_value_strips_quotes():
    csv_text = 'brand\n"Heco GmbH"'
    assert _first_value(csv_text) == "Heco GmbH"


def _make_pre(agents_md_index=None, schema_digest=None):
    return PrephaseResult(
        log=[], preserve_prefix=[],
        agents_md_index=agents_md_index or {"brand_aliases": ["heco = Heco"]},
        schema_digest=schema_digest or {"top_keys": ["diameter_mm", "screw_type"]},
    )


def test_run_resolve_returns_confirmed_values():
    vm = MagicMock()
    exec_r = MagicMock(); exec_r.stdout = "brand\nHeco"
    vm.exec.return_value = exec_r

    raw_response = '{"reasoning": "found brand", "candidates": [{"term": "heco", "field": "brand", "discovery_query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE \'%heco%\' LIMIT 10"}]}'

    with patch("agent.resolve.call_llm_raw", return_value=raw_response):
        result = run_resolve(vm, "test-model", "find Heco products", _make_pre(), {})

    assert "brand" in result
    assert "Heco" in result["brand"]


def test_run_resolve_blocks_unsafe_query():
    vm = MagicMock()

    raw_response = '{"reasoning": "x", "candidates": [{"term": "heco", "field": "brand", "discovery_query": "DROP TABLE products"}]}'

    with patch("agent.resolve.call_llm_raw", return_value=raw_response):
        result = run_resolve(vm, "test-model", "task", _make_pre(), {})

    # vm.exec never called — unsafe query was blocked
    vm.exec.assert_not_called()
    assert result == {}


def test_run_resolve_returns_empty_on_llm_failure():
    with patch("agent.resolve.call_llm_raw", return_value=None):
        result = run_resolve(MagicMock(), "model", "task", _make_pre(), {})
    assert result == {}


def test_run_resolve_returns_empty_on_exception():
    with patch("agent.resolve.call_llm_raw", side_effect=Exception("network error")):
        result = run_resolve(MagicMock(), "model", "task", _make_pre(), {})
    assert result == {}


def test_run_resolve_accumulates_multiple_fields():
    vm = MagicMock()
    def _exec(req):
        r = MagicMock()
        if "brand" in req.args[0]:
            r.stdout = "brand\nHeco"
        else:
            r.stdout = "name\nwood screw"
        return r
    vm.exec.side_effect = _exec

    raw_response = '{"reasoning": "found two", "candidates": [{"term": "heco", "field": "brand", "discovery_query": "SELECT DISTINCT brand FROM products WHERE brand ILIKE \'%heco%\' LIMIT 10"}, {"term": "screw", "field": "kind", "discovery_query": "SELECT DISTINCT name FROM kinds WHERE name ILIKE \'%screw%\' LIMIT 10"}]}'

    with patch("agent.resolve.call_llm_raw", return_value=raw_response):
        result = run_resolve(vm, "model", "find Heco screws", _make_pre(), {})

    assert result.get("brand") == ["Heco"]
    assert result.get("kind") == ["wood screw"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_resolve.py -v
```

Expected: `ModuleNotFoundError: No module named 'agent.resolve'`

- [ ] **Step 3: Implement resolve.py**

Create `agent/resolve.py`:

```python
"""Resolve phase: confirm task identifiers against DB before pipeline cycles."""
from __future__ import annotations

import re

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import ExecRequest
from google.protobuf.json_format import MessageToDict

from .json_extract import _extract_json_from_text
from .llm import call_llm_raw
from .models import ResolveOutput
from .prephase import PrephaseResult
from .prompt import load_prompt

_DDL_RE = re.compile(r"^\s*(DROP|INSERT|UPDATE|DELETE|ALTER|CREATE|REPLACE)\b", re.IGNORECASE)
_DISCOVERY_RE = re.compile(r"\b(ILIKE|DISTINCT)\b", re.IGNORECASE)


def _security_check(query: str) -> str | None:
    if _DDL_RE.match(query):
        return f"DDL/DML not allowed in resolve: {query[:60]}"
    if not _DISCOVERY_RE.search(query):
        return f"resolve query must contain ILIKE or DISTINCT: {query[:60]}"
    return None


def _exec_sql(vm: EcomRuntimeClientSync, query: str) -> str:
    result = vm.exec(ExecRequest(path="/bin/sql", args=[query]))
    try:
        d = MessageToDict(result)
        return d.get("stdout", "") or d.get("output", "") or ""
    except Exception:
        return getattr(result, "stdout", "") or getattr(result, "output", "") or ""


def _first_value(csv_text: str) -> str | None:
    lines = [ln.strip() for ln in csv_text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    parts = lines[1].split(",")
    return parts[0].strip().strip('"') if parts else None


def _build_resolve_system(pre: PrephaseResult) -> str:
    parts: list[str] = []
    if pre.agents_md_index:
        index_lines = "\n".join(f"- {k}" for k in pre.agents_md_index)
        parts.append(f"# AGENTS.MD INDEX\n{index_lines}")
    top_keys = pre.schema_digest.get("top_keys", [])
    if top_keys:
        parts.append("# TOP PROPERTY KEYS\n" + "\n".join(f"- {k}" for k in top_keys))
    guide = load_prompt("resolve")
    if guide:
        parts.append(guide)
    return "\n\n".join(parts)


def run_resolve(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    """Resolve identifiers in task_text against DB. Returns confirmed_values or {} on failure."""
    try:
        return _run(vm, model, task_text, pre, cfg)
    except Exception as e:
        print(f"[resolve] non-fatal error: {e}")
        return {}


def _run(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    system = _build_resolve_system(pre)
    raw = call_llm_raw(system, f"TASK: {task_text}", model, cfg, max_tokens=1024)
    if not raw:
        return {}

    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return {}

    try:
        resolve_out = ResolveOutput.model_validate(parsed)
    except Exception:
        return {}

    confirmed_values: dict[str, list[str]] = {}

    for candidate in resolve_out.candidates:
        err = _security_check(candidate.discovery_query)
        if err:
            print(f"[resolve] security blocked: {err}")
            continue

        result_txt = _exec_sql(vm, candidate.discovery_query)
        value = _first_value(result_txt)
        if value:
            field = candidate.field
            if field not in confirmed_values:
                confirmed_values[field] = []
            if value not in confirmed_values[field]:
                confirmed_values[field].append(value)

    return confirmed_values
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_resolve.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/resolve.py tests/test_resolve.py
git commit -m "feat: add resolve phase to confirm task identifiers against DB"
```

---

## Task 6: Schema Gate

**Files:**
- Create: `agent/schema_gate.py`
- Create: `tests/test_schema_gate.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schema_gate.py

import pytest
from agent.schema_gate import check_schema_compliance

_DIGEST = {
    "tables": {
        "products": {
            "columns": [
                {"name": "sku", "type": "TEXT", "notnull": "1"},
                {"name": "brand", "type": "TEXT", "notnull": "0"},
                {"name": "model", "type": "TEXT", "notnull": "0"},
                {"name": "name", "type": "TEXT", "notnull": "0"},
            ]
        },
        "product_properties": {
            "columns": [
                {"name": "sku", "type": "TEXT", "notnull": "1"},
                {"name": "key", "type": "TEXT", "notnull": "1"},
                {"name": "value_text", "type": "TEXT", "notnull": "0"},
                {"name": "value_number", "type": "REAL", "notnull": "0"},
            ]
        },
        "inventory": {
            "columns": [
                {"name": "sku", "type": "TEXT", "notnull": "1"},
                {"name": "store_id", "type": "TEXT", "notnull": "1"},
                {"name": "available_today", "type": "INTEGER", "notnull": "0"},
            ]
        },
        "kinds": {
            "columns": [
                {"name": "id", "type": "INTEGER", "notnull": "1"},
                {"name": "name", "type": "TEXT", "notnull": "1"},
            ]
        },
    }
}


def test_valid_query_passes():
    q = "SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "find Heco products") is None


def test_unknown_column_detected():
    q = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    err = check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "find Heco products")
    assert err is not None
    assert "unknown column" in err
    assert "color" in err


def test_known_columns_pass():
    q = "SELECT p.sku, p.brand, p.model FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "Heco model") is None


def test_unverified_literal_detected():
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    # 'Heco' appears in task_text but is NOT in confirmed_values
    err = check_schema_compliance([q], _DIGEST, {}, "find Heco products")
    assert err is not None
    assert "unverified literal" in err
    assert "Heco" in err


def test_confirmed_literal_passes():
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    # 'Heco' is in confirmed_values
    assert check_schema_compliance([q], _DIGEST, {"brand": ["Heco"]}, "find Heco products") is None


def test_literal_not_in_task_passes():
    # 'Heco' is in the query but NOT in task_text — not a user-supplied copy
    q = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    assert check_schema_compliance([q], _DIGEST, {}, "find screws") is None


def test_double_key_join_detected():
    q = (
        "SELECT p.sku FROM products p "
        "JOIN product_properties pp ON pp.sku = p.sku "
        "WHERE pp.key = 'diameter_mm' AND pp.key = 'screw_type'"
    )
    err = check_schema_compliance([q], _DIGEST, {}, "find screws")
    assert err is not None
    assert "double-key JOIN" in err


def test_separate_exists_passes():
    q = (
        "SELECT p.sku FROM products p "
        "WHERE EXISTS (SELECT 1 FROM product_properties pp WHERE pp.sku = p.sku AND pp.key = 'diameter_mm' AND pp.value_number = 3) "
        "AND EXISTS (SELECT 1 FROM product_properties pp2 WHERE pp2.sku = p.sku AND pp2.key = 'screw_type' AND pp2.value_text = 'wood screw')"
    )
    assert check_schema_compliance([q], _DIGEST, {"diameter_mm": ["3"], "screw_type": ["wood screw"]}, "find 3mm wood screws") is None


def test_empty_queries_passes():
    assert check_schema_compliance([], _DIGEST, {}, "task") is None


def test_empty_digest_skips_column_check():
    q = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    # No tables in digest — unknown column check skipped
    assert check_schema_compliance([q], {}, {"brand": ["Heco"]}, "Heco") is None


def test_multiple_queries_first_error_returned():
    q_ok = "SELECT p.sku FROM products p WHERE p.brand = 'Heco'"
    q_bad = "SELECT p.sku, p.color FROM products p WHERE p.brand = 'Heco'"
    err = check_schema_compliance([q_ok, q_bad], _DIGEST, {"brand": ["Heco"]}, "Heco")
    assert err is not None
    assert "color" in err
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_schema_gate.py -v
```

Expected: `ModuleNotFoundError: No module named 'agent.schema_gate'`

- [ ] **Step 3: Implement schema_gate.py**

Create `agent/schema_gate.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_schema_gate.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/schema_gate.py tests/test_schema_gate.py
git commit -m "feat: add schema_gate for unknown column, unverified literal, double-key JOIN checks"
```

---

## Task 7: Wire Pipeline

**Files:**
- Modify: `agent/pipeline.py`
- Modify: `tests/test_pipeline.py` (extend existing tests)

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/test_pipeline.py

from agent.pipeline import _extract_discovery_results, _format_confirmed_values, _format_schema_digest


def test_extract_discovery_results_basic():
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10"]
    results = ["brand\nHeco\nMaker"]
    cv: dict = {}
    _extract_discovery_results(queries, results, cv)
    assert cv.get("brand") == ["Heco", "Maker"]


def test_extract_discovery_results_skips_non_distinct():
    queries = ["SELECT sku FROM products WHERE brand = 'Heco'"]
    results = ["sku\nABC-001"]
    cv: dict = {}
    _extract_discovery_results(queries, results, cv)
    assert cv == {}


def test_extract_discovery_results_accumulates():
    cv = {"brand": ["Heco"]}
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%maker%' LIMIT 10"]
    results = ["brand\nMaker"]
    _extract_discovery_results(queries, results, cv)
    assert cv["brand"] == ["Heco", "Maker"]


def test_extract_discovery_results_no_duplicates():
    cv = {"brand": ["Heco"]}
    queries = ["SELECT DISTINCT brand FROM products WHERE brand ILIKE '%heco%' LIMIT 10"]
    results = ["brand\nHeco"]
    _extract_discovery_results(queries, results, cv)
    assert cv["brand"] == ["Heco"]


def test_format_confirmed_values_single():
    cv = {"brand": ["Heco"]}
    text = _format_confirmed_values(cv)
    assert 'brand → confirmed: "Heco"' in text


def test_format_confirmed_values_multiple():
    cv = {"kind": ["wood screw", "self-tapping screw"]}
    text = _format_confirmed_values(cv)
    assert "wood screw" in text
    assert "self-tapping screw" in text


def test_format_schema_digest_lists_tables():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku", "type": "TEXT"}, {"name": "brand", "type": "TEXT"}]}
        },
        "top_keys": ["diameter_mm"],
    }
    text = _format_schema_digest(digest)
    assert "products" in text
    assert "sku" in text
    assert "diameter_mm" in text
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_pipeline.py -v -k "extract_discovery or format_confirmed or format_schema"
```

Expected: `ImportError` — those functions don't exist yet.

- [ ] **Step 3: Rewrite pipeline.py with all wiring**

Replace `agent/pipeline.py` with the full updated version:

```python
"""Phase-based SQL pipeline for lookup tasks — replaces run_loop() for task_type='lookup'."""
from __future__ import annotations

import json
import os
import re
import traceback
from pathlib import Path

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message

from bitgn.vm.ecom.ecom_connect import EcomRuntimeClientSync
from bitgn.vm.ecom.ecom_pb2 import AnswerRequest, ExecRequest

from .llm import (
    call_llm_raw, OUTCOME_BY_NAME,
    CLI_BLUE, CLI_CLR, CLI_GREEN, CLI_RED, CLI_YELLOW,
)
from .json_extract import _extract_json_from_text
from .models import SqlPlanOutput, LearnOutput, AnswerOutput
from .prephase import PrephaseResult
from .prompt import load_prompt
from .resolve import run_resolve
from .rules_loader import RulesLoader, _RULES_DIR
from .schema_gate import check_schema_compliance
from .sql_security import check_sql_queries, load_security_gates

_MAX_CYCLES = 3
_EVAL_ENABLED = os.environ.get("EVAL_ENABLED", "0") == "1"
_MODEL_EVALUATOR = os.environ.get("MODEL_EVALUATOR", "")
_EVAL_LOG = Path(__file__).parent.parent / "data" / "eval_log.jsonl"


def _exec_result_text(result) -> str:
    if isinstance(result, Message):
        try:
            d = MessageToDict(result)
            return d.get("stdout", "") or d.get("output", "") or ""
        except Exception:
            pass
    return getattr(result, "stdout", "") or getattr(result, "output", "") or ""


def _csv_has_data(result_txt: str) -> bool:
    stripped = result_txt.strip()
    if not stripped:
        return False
    if stripped.startswith("["):
        return stripped not in ("[]",)
    if stripped.startswith("{"):
        return stripped not in ("{}",)
    lines = [l for l in stripped.splitlines() if l.strip()]
    return len(lines) > 1


def _call_llm_phase(
    system: str,
    user_msg: str,
    model: str,
    cfg: dict,
    output_cls,
    max_tokens: int = 4096,
) -> tuple[object | None, dict]:
    tok_info: dict = {}
    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=max_tokens, token_out=tok_info)
    phase_name = output_cls.__name__
    sgr_entry: dict = {
        "phase": phase_name,
        "guide_prompt": system[:300],
        "reasoning": "",
        "output": raw or "",
    }
    if not raw:
        return None, sgr_entry
    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None, sgr_entry
    try:
        obj = output_cls.model_validate(parsed)
        sgr_entry["reasoning"] = obj.reasoning
        sgr_entry["output"] = parsed
        return obj, sgr_entry
    except Exception:
        return None, sgr_entry


def _gates_summary(gates: list[dict]) -> str:
    return "\n".join(f"- [{g['id']}] {g.get('message', '')}" for g in gates)


def _format_confirmed_values(cv: dict) -> str:
    lines = []
    for field, values in cv.items():
        if isinstance(values, list):
            if len(values) == 1:
                lines.append(f'{field} → confirmed: "{values[0]}"')
            else:
                joined = ", ".join(f'"{v}"' for v in values)
                lines.append(f'{field} → confirmed db values: [{joined}]')
        else:
            lines.append(f'{field} → confirmed: "{values}"')
    return "\n".join(lines)


def _format_schema_digest(sd: dict) -> str:
    lines = []
    for table, info in sd.get("tables", {}).items():
        cols = ", ".join(f"{c['name']}({c['type']})" for c in info.get("columns", []))
        lines.append(f"{table}: {cols}")
        for fk in info.get("fk", []):
            lines.append(f"  FK: {fk['from']} → {fk['to']}")
    top_keys = sd.get("top_keys", [])
    if top_keys:
        lines.append("Top property keys: " + ", ".join(top_keys[:10]))
    return "\n".join(lines)


def _relevant_agents_sections(agents_md_index: dict, task_text: str) -> dict[str, list[str]]:
    task_words = {w.lower() for w in task_text.split() if len(w) > 3}
    relevant = {}
    for section, lines in agents_md_index.items():
        section_text = (" ".join(lines) + " " + section).lower()
        if any(w in section_text for w in task_words):
            relevant[section] = lines
    return relevant


def _build_system(
    phase: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    rules_loader: RulesLoader,
    session_rules: list[str],
    security_gates: list[dict],
    confirmed_values: dict | None = None,
    highlighted_vault_rules: list[str] | None = None,
    task_text: str = "",
) -> str:
    parts: list[str] = []

    if phase in ("sql_plan", "learn", "answer", "pipeline_evaluator"):
        if agents_md_index and task_text and phase in ("sql_plan", "learn"):
            relevant = _relevant_agents_sections(agents_md_index, task_text)
            index_line = "Section index: " + ", ".join(agents_md_index.keys())
            if relevant:
                section_blocks = "\n\n".join(
                    f"### {k}\n" + "\n".join(lines) for k, lines in relevant.items()
                )
                parts.append(f"# VAULT RULES\n{index_line}\n\n{section_blocks}")
            elif agents_md:
                parts.append(f"# VAULT RULES\n{agents_md}")
        elif agents_md:
            parts.append(f"# VAULT RULES\n{agents_md}")

    if phase in ("sql_plan", "learn"):
        rules_md = rules_loader.get_rules_markdown(phase="sql_plan", verified_only=True)
        if rules_md:
            parts.append(f"# PIPELINE RULES\n{rules_md}")

    if phase == "sql_plan" and security_gates:
        parts.append(f"# SECURITY GATES\n{_gates_summary(security_gates)}")

    if schema_digest and phase in ("sql_plan", "learn"):
        parts.append(f"# SCHEMA DIGEST\n{_format_schema_digest(schema_digest)}")

    if db_schema:
        parts.append(f"# DATABASE SCHEMA\n{db_schema}")

    if phase in ("sql_plan", "learn"):
        for r in session_rules:
            parts.append(f"# IN-SESSION RULE\n{r}")

    if highlighted_vault_rules:
        for rule in highlighted_vault_rules:
            parts.append(f"# HIGHLIGHTED VAULT RULE\n{rule}")

    if confirmed_values and phase in ("sql_plan", "learn"):
        parts.append(f"# CONFIRMED VALUES\n{_format_confirmed_values(confirmed_values)}")

    guide = load_prompt(phase)
    if guide:
        parts.append(guide)

    return "\n\n".join(parts)


def _extract_discovery_results(
    queries: list[str],
    results: list[str],
    confirmed_values: dict,
) -> None:
    """Update confirmed_values in-place from DISTINCT query results."""
    for q, result_txt in zip(queries, results):
        m = re.search(r'SELECT\s+DISTINCT\s+(\w+)', q, re.IGNORECASE)
        if not m:
            continue
        col = m.group(1).lower()
        lines = [ln.strip() for ln in result_txt.strip().splitlines() if ln.strip()]
        for line in lines[1:]:
            val = line.split(",")[0].strip().strip('"')
            if val:
                if col not in confirmed_values:
                    confirmed_values[col] = []
                if val not in confirmed_values[col]:
                    confirmed_values[col].append(val)


def run_pipeline(
    vm: EcomRuntimeClientSync,
    model: str,
    task_text: str,
    pre: PrephaseResult,
    cfg: dict,
) -> dict:
    """Phase-based SQL pipeline. Returns stats dict compatible with run_loop()."""
    rules_loader = RulesLoader(_RULES_DIR)
    security_gates = load_security_gates()
    session_rules: list[str] = []
    highlighted_vault_rules: list[str] = []
    sgr_trace: list[dict] = []
    total_in_tok = 0
    total_out_tok = 0

    last_error = ""
    sql_results: list[str] = []
    executed_queries: list[str] = []
    sql_plan_outputs: list[SqlPlanOutput] = []
    success = False
    cycles_used = 0

    # ── RESOLVE ───────────────────────────────────────────────────────────────
    confirmed_values: dict = run_resolve(vm, model, task_text, pre, cfg)
    if confirmed_values:
        print(f"{CLI_BLUE}[pipeline] RESOLVE: {list(confirmed_values.keys())}{CLI_CLR}")

    for cycle in range(_MAX_CYCLES):
        cycles_used = cycle + 1
        print(f"\n{CLI_BLUE}[pipeline] cycle={cycle + 1}/{_MAX_CYCLES}{CLI_CLR}")

        # ── SQL_PLAN ──────────────────────────────────────────────────────────
        system = _build_system(
            "sql_plan", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
            pre.schema_digest, rules_loader, session_rules, security_gates,
            confirmed_values=confirmed_values,
            highlighted_vault_rules=highlighted_vault_rules,
            task_text=task_text,
        )
        user_msg = f"TASK: {task_text}"
        if last_error:
            user_msg += f"\n\nPREVIOUS ERROR: {last_error}"

        sql_plan_out, sgr_entry = _call_llm_phase(system, user_msg, model, cfg, SqlPlanOutput)
        sgr_trace.append(sgr_entry)

        if not sql_plan_out:
            print(f"{CLI_RED}[pipeline] SQL_PLAN LLM call failed{CLI_CLR}")
            last_error = "SQL_PLAN phase LLM call failed"
            _run_learn(pre, model, cfg, task_text, [], last_error,
                       rules_loader, session_rules, sgr_trace, security_gates,
                       confirmed_values, highlighted_vault_rules)
            continue

        sql_plan_outputs.append(sql_plan_out)
        queries = sql_plan_out.queries
        print(f"{CLI_BLUE}[pipeline] SQL_PLAN: {len(queries)} queries{CLI_CLR}")

        # ── AGENTS.MD REFS CHECK ───────────────────────────────────────────────
        if not sql_plan_out.agents_md_refs and pre.agents_md_index:
            task_lower = task_text.lower()
            index_terms_in_task = [
                k for k in pre.agents_md_index
                if any(part in task_lower for part in k.split("_"))
            ]
            if index_terms_in_task:
                last_error = "agents_md_refs empty despite known vocabulary terms in task"
                print(f"{CLI_YELLOW}[pipeline] AGENTS.MD refs check failed: {last_error}{CLI_CLR}")
                _run_learn(pre, model, cfg, task_text, queries, last_error,
                           rules_loader, session_rules, sgr_trace, security_gates,
                           confirmed_values, highlighted_vault_rules)
                continue

        # ── SECURITY CHECK ────────────────────────────────────────────────────
        gate_err = check_sql_queries(queries, security_gates)
        if gate_err:
            print(f"{CLI_YELLOW}[pipeline] SECURITY gate blocked: {gate_err}{CLI_CLR}")
            last_error = gate_err
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates,
                       confirmed_values, highlighted_vault_rules)
            continue

        # ── SCHEMA GATE ───────────────────────────────────────────────────────
        schema_err = check_schema_compliance(queries, pre.schema_digest, confirmed_values, task_text)
        if schema_err:
            print(f"{CLI_YELLOW}[pipeline] SCHEMA gate blocked: {schema_err}{CLI_CLR}")
            last_error = schema_err
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates,
                       confirmed_values, highlighted_vault_rules)
            continue

        # ── VALIDATE ──────────────────────────────────────────────────────────
        validate_error = None
        for q in queries:
            try:
                result = vm.exec(ExecRequest(path="/bin/sql", args=[f"EXPLAIN {q}"]))
                result_txt = _exec_result_text(result)
                if "error" in result_txt.lower():
                    validate_error = f"EXPLAIN error: {result_txt[:200]}"
                    break
            except Exception as e:
                validate_error = f"EXPLAIN exception: {e}"
                break

        if validate_error:
            print(f"{CLI_YELLOW}[pipeline] VALIDATE failed: {validate_error}{CLI_CLR}")
            last_error = validate_error
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates,
                       confirmed_values, highlighted_vault_rules)
            continue

        # ── EXECUTE ───────────────────────────────────────────────────────────
        execute_error = None
        sql_results = []
        for q in queries:
            try:
                result = vm.exec(ExecRequest(path="/bin/sql", args=[q]))
                result_txt = _exec_result_text(result)
                sql_results.append(result_txt)
                print(f"{CLI_BLUE}[pipeline] EXECUTE: {q[:60]!r} → {result_txt[:80]}{CLI_CLR}")
            except Exception as e:
                execute_error = f"Execute exception: {e}"
                break

        last_empty = not sql_results or not _csv_has_data(sql_results[-1])
        if execute_error or last_empty:
            err = execute_error or f"Empty result set: {(sql_results[-1] if sql_results else '').strip()[:120]}"
            print(f"{CLI_YELLOW}[pipeline] EXECUTE failed: {err}{CLI_CLR}")
            last_error = err
            _run_learn(pre, model, cfg, task_text, queries, last_error,
                       rules_loader, session_rules, sgr_trace, security_gates,
                       confirmed_values, highlighted_vault_rules)
            continue

        # ── CARRYOVER: update confirmed_values from DISTINCT results ──────────
        executed_queries.extend(queries)
        _extract_discovery_results(queries, sql_results, confirmed_values)

        success = True
        break

    if not success:
        print(f"{CLI_RED}[pipeline] All {_MAX_CYCLES} cycles exhausted — clarification{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message="Could not retrieve data after multiple attempts.",
                outcome=OUTCOME_BY_NAME["OUTCOME_NONE_CLARIFICATION"],
                refs=[],
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")
        return {
            "outcome": "OUTCOME_NONE_CLARIFICATION",
            "step_facts": [f"cycles={_MAX_CYCLES}"],
            "done_ops": [],
            "input_tokens": total_in_tok,
            "output_tokens": total_out_tok,
            "total_elapsed_ms": 0,
        }

    # ── ANSWER ────────────────────────────────────────────────────────────────
    answer_system = _build_system(
        "answer", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, session_rules, security_gates,
    )
    answer_user = f"TASK: {task_text}\n\nSQL RESULTS:\n" + "\n---\n".join(sql_results)
    answer_out, sgr_answer = _call_llm_phase(answer_system, answer_user, model, cfg, AnswerOutput)
    sgr_trace.append(sgr_answer)

    outcome = "OUTCOME_NONE_CLARIFICATION"
    if answer_out:
        outcome = answer_out.outcome
        print(f"{CLI_GREEN}[pipeline] ANSWER: {outcome} — {answer_out.message[:100]}{CLI_CLR}")
        try:
            vm.answer(AnswerRequest(
                message=answer_out.message,
                outcome=OUTCOME_BY_NAME[outcome],
                refs=answer_out.grounding_refs,
            ))
        except Exception as e:
            print(f"{CLI_RED}[pipeline] vm.answer error: {e}{CLI_CLR}")

    # ── EVALUATE ──────────────────────────────────────────────────────────────
    if _EVAL_ENABLED and _MODEL_EVALUATOR:
        _run_evaluator_safe(
            task_text=task_text,
            agents_md=pre.agents_md_content,
            agents_md_index=pre.agents_md_index,
            db_schema=pre.db_schema,
            schema_digest=pre.schema_digest,
            sgr_trace=sgr_trace,
            cycles=cycles_used,
            final_outcome=outcome,
            sql_plan_outputs=sql_plan_outputs,
            executed_queries=executed_queries,
            model=_MODEL_EVALUATOR,
            cfg=cfg,
        )

    return {
        "outcome": outcome,
        "step_facts": [f"pipeline cycles={cycles_used}"],
        "done_ops": [],
        "input_tokens": total_in_tok,
        "output_tokens": total_out_tok,
        "total_elapsed_ms": 0,
    }


def _run_learn(
    pre: PrephaseResult,
    model: str,
    cfg: dict,
    task_text: str,
    queries: list[str],
    error: str,
    rules_loader: RulesLoader,
    session_rules: list[str],
    sgr_trace: list[dict],
    security_gates: list[dict],
    confirmed_values: dict,
    highlighted_vault_rules: list[str],
) -> None:
    learn_system = _build_system(
        "learn", pre.agents_md_content, pre.agents_md_index, pre.db_schema,
        pre.schema_digest, rules_loader, session_rules, security_gates,
        confirmed_values=confirmed_values,
        highlighted_vault_rules=highlighted_vault_rules,
        task_text=task_text,
    )
    learn_user = (
        f"TASK: {task_text}\n"
        f"FAILED QUERIES: {json.dumps(queries)}\n"
        f"ERROR: {error}"
    )
    learn_out, sgr_learn = _call_llm_phase(learn_system, learn_user, model, cfg, LearnOutput, max_tokens=2048)
    sgr_trace.append(sgr_learn)
    if learn_out:
        anchor = learn_out.agents_md_anchor
        if anchor:
            anchor_section = anchor.split(">")[0].strip()
            if anchor_section in pre.agents_md_index:
                anchor_lines = pre.agents_md_index[anchor_section]
                highlighted_vault_rules.append(f"[{anchor_section}]\n" + "\n".join(anchor_lines))
                print(f"{CLI_BLUE}[pipeline] LEARN: anchor={anchor!r}, elevating vault rule{CLI_CLR}")
                return
        session_rules.append(learn_out.rule_content)
        print(f"{CLI_BLUE}[pipeline] LEARN: rule added to session, retrying{CLI_CLR}")


def _run_evaluator_safe(
    task_text: str,
    agents_md: str,
    agents_md_index: dict,
    db_schema: str,
    schema_digest: dict,
    sgr_trace: list[dict],
    cycles: int,
    final_outcome: str,
    sql_plan_outputs: list,
    executed_queries: list[str],
    model: str,
    cfg: dict,
) -> None:
    try:
        from .evaluator import run_evaluator, EvalInput
        run_evaluator(
            EvalInput(
                task_text=task_text,
                agents_md=agents_md,
                agents_md_index=agents_md_index,
                db_schema=db_schema,
                schema_digest=schema_digest,
                sgr_trace=sgr_trace,
                cycles=cycles,
                final_outcome=final_outcome,
                sql_plan_outputs=sql_plan_outputs,
                executed_queries=executed_queries,
            ),
            model=model,
            cfg=cfg,
        )
    except Exception as e:
        print(f"{CLI_YELLOW}[pipeline] evaluator error (non-fatal): {e}{CLI_CLR}")
```

- [ ] **Step 4: Run all pipeline tests**

```
uv run pytest tests/test_pipeline.py tests/test_orchestrator_pipeline.py -v
```

Expected: All tests PASS. If existing tests break due to `_build_system` or `_run_learn` signature change, update their mocks accordingly (add `agents_md_index={}`, `schema_digest={}` etc. to any direct calls).

- [ ] **Step 5: Run full test suite**

```
uv run python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py tests/test_pipeline.py
git commit -m "feat: wire resolve, schema gate, confirmed_values carryover, agents_md_refs check into pipeline"
```

---

## Task 8: Evaluator Metrics

**Files:**
- Modify: `agent/evaluator.py`
- Create: `tests/test_eval_metrics.py`

- [ ] **Step 1: Write failing tests**

Note: `index_terms_in_task` matches section keys whose CONTENT (lines joined) or key name contains any word (>3 chars) from task_text. Same logic as `_relevant_agents_sections` in pipeline.

```python
# tests/test_eval_metrics.py

import pytest
from agent.evaluator import _compute_eval_metrics
from agent.models import SqlPlanOutput


def test_agents_md_coverage_full():
    # "heco" matches "heco = Heco" content; "screw" matches "screw = bolt" content
    index = {"brand_aliases": ["heco = Heco"], "kind_synonyms": ["screw = bolt"]}
    plans = [
        SqlPlanOutput(reasoning="r", queries=["SELECT 1 WHERE 1=1"], agents_md_refs=["brand_aliases", "kind_synonyms"])
    ]
    metrics = _compute_eval_metrics("find heco screw products", index, [], {}, plans)
    assert metrics["agents_md_coverage"] == 1.0


def test_agents_md_coverage_zero():
    # "heco" matches "heco = Heco" content, plan refs nothing
    index = {"brand_aliases": ["heco = Heco"]}
    plans = [SqlPlanOutput(reasoning="r", queries=["SELECT 1 WHERE 1=1"], agents_md_refs=[])]
    metrics = _compute_eval_metrics("find heco products", index, [], {}, plans)
    assert metrics["agents_md_coverage"] == 0.0


def test_agents_md_coverage_no_relevant_terms():
    index = {"brand_aliases": ["heco = Heco"]}
    plans = [SqlPlanOutput(reasoning="r", queries=["SELECT 1 WHERE 1=1"], agents_md_refs=[])]
    # "show", "shelf", "count" — none appear in "heco = heco brand_aliases"
    metrics = _compute_eval_metrics("show shelf count", index, [], {}, plans)
    assert metrics["agents_md_coverage"] == 1.0  # 0/0 → 1.0 (no relevant terms)


def test_schema_grounding_full():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku"}, {"name": "brand"}]},
        }
    }
    queries = ["SELECT p.sku, p.brand FROM products p WHERE p.brand = 'Heco'"]
    metrics = _compute_eval_metrics("task", {}, queries, digest, [])
    assert metrics["schema_grounding"] == 1.0


def test_schema_grounding_partial():
    digest = {
        "tables": {
            "products": {"columns": [{"name": "sku"}]},
        }
    }
    # p.sku is known, p.color is not
    queries = ["SELECT p.sku, p.color FROM products p WHERE p.sku = 'x'"]
    metrics = _compute_eval_metrics("task", {}, queries, digest, [])
    assert 0.0 < metrics["schema_grounding"] < 1.0


def test_schema_grounding_no_table_col_refs():
    digest = {"tables": {"products": {"columns": [{"name": "sku"}]}}}
    queries = ["SELECT COUNT(*) FROM products WHERE brand = 'x'"]
    metrics = _compute_eval_metrics("task", {}, queries, digest, [])
    # No table.col refs → grounding defaults to 1.0
    assert metrics["schema_grounding"] == 1.0


def test_schema_grounding_empty_digest():
    metrics = _compute_eval_metrics("task", {}, ["SELECT p.sku FROM products p WHERE p.sku = 'x'"], {}, [])
    assert metrics["schema_grounding"] == 1.0
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run pytest tests/test_eval_metrics.py -v
```

Expected: `ImportError: cannot import name '_compute_eval_metrics' from 'agent.evaluator'`

- [ ] **Step 3: Implement evaluator changes**

Replace `agent/evaluator.py` with:

```python
"""Post-execution pipeline evaluator. Fail-open: any exception returns None."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .llm import call_llm_raw
from .json_extract import _extract_json_from_text
from .models import PipelineEvalOutput, SqlPlanOutput
from .prompt import load_prompt

_EVAL_LOG = Path(__file__).parent.parent / "data" / "eval_log.jsonl"


@dataclass
class EvalInput:
    task_text: str
    agents_md: str
    db_schema: str
    sgr_trace: list[dict]
    cycles: int
    final_outcome: str
    agents_md_index: dict = field(default_factory=dict)
    schema_digest: dict = field(default_factory=dict)
    sql_plan_outputs: list = field(default_factory=list)
    executed_queries: list[str] = field(default_factory=list)


def _compute_eval_metrics(
    task_text: str,
    agents_md_index: dict,
    executed_queries: list[str],
    schema_digest: dict,
    sql_plan_outputs: list,
) -> dict:
    """Compute agents_md_coverage and schema_grounding. Returns dict with both floats."""
    # agents_md_coverage — match sections whose content OR key contains a task word (>3 chars)
    task_words = {w.lower() for w in task_text.split() if len(w) > 3}
    index_terms_in_task = {
        k for k, lines in agents_md_index.items()
        if any(w in (" ".join(lines) + " " + k).lower() for w in task_words)
    }
    refs_used: set[str] = set()
    for plan in sql_plan_outputs:
        if hasattr(plan, "agents_md_refs"):
            refs_used.update(plan.agents_md_refs)
    if index_terms_in_task:
        coverage = len(index_terms_in_task & refs_used) / len(index_terms_in_task)
    else:
        coverage = 1.0

    # schema_grounding
    known_cols: set[str] = set()
    for table_info in schema_digest.get("tables", {}).values():
        for col in table_info.get("columns", []):
            known_cols.add(col.get("name", ""))
    known_cols.discard("")

    table_col_refs = []
    for q in executed_queries:
        table_col_refs.extend(re.findall(r'\b\w+\.(\w+)\b', q))

    if table_col_refs and known_cols:
        grounding = sum(1 for c in table_col_refs if c in known_cols) / len(table_col_refs)
    else:
        grounding = 1.0

    return {"agents_md_coverage": coverage, "schema_grounding": grounding}


def run_evaluator(
    eval_input: EvalInput,
    model: str,
    cfg: dict,
) -> PipelineEvalOutput | None:
    """Evaluate pipeline trace. Returns PipelineEvalOutput or None on any failure."""
    try:
        return _run(eval_input, model, cfg)
    except Exception as e:
        print(f"[evaluator] non-fatal error: {e}")
        return None


def _run(eval_input: EvalInput, model: str, cfg: dict) -> PipelineEvalOutput | None:
    metrics = _compute_eval_metrics(
        eval_input.task_text,
        eval_input.agents_md_index,
        eval_input.executed_queries,
        eval_input.schema_digest,
        eval_input.sql_plan_outputs,
    )

    system = _build_eval_system(eval_input.agents_md)
    user_msg = json.dumps({
        "task_text": eval_input.task_text,
        "db_schema": eval_input.db_schema,
        "sgr_trace": eval_input.sgr_trace,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
        "agents_md_coverage": metrics["agents_md_coverage"],
        "schema_grounding": metrics["schema_grounding"],
    }, ensure_ascii=False)

    raw = call_llm_raw(system, user_msg, model, cfg, max_tokens=2048)
    if not raw:
        return None

    parsed = _extract_json_from_text(raw)
    if not isinstance(parsed, dict):
        return None

    try:
        parsed.setdefault("agents_md_coverage", metrics["agents_md_coverage"])
        parsed.setdefault("schema_grounding", metrics["schema_grounding"])
        result = PipelineEvalOutput.model_validate(parsed)
    except Exception:
        return None

    _append_log(eval_input, result, metrics)
    return result


def _build_eval_system(agents_md: str) -> str:
    parts: list[str] = []
    if agents_md:
        parts.append(f"# VAULT RULES\n{agents_md}")
    guide = load_prompt("pipeline_evaluator")
    if guide:
        parts.append(guide)
    return "\n\n".join(parts)


def _append_log(eval_input: EvalInput, result: PipelineEvalOutput, metrics: dict) -> None:
    entry = {
        "task_text": eval_input.task_text,
        "cycles": eval_input.cycles,
        "final_outcome": eval_input.final_outcome,
        "score": result.score,
        "comment": result.comment,
        "prompt_optimization": result.prompt_optimization,
        "rule_optimization": result.rule_optimization,
        "security_optimization": result.security_optimization,
        "agents_md_coverage": metrics["agents_md_coverage"],
        "schema_grounding": metrics["schema_grounding"],
        "reasoning": result.reasoning,
    }
    _EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Run evaluator tests**

```
uv run pytest tests/test_eval_metrics.py tests/test_evaluator.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full test suite**

```
uv run python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/evaluator.py tests/test_eval_metrics.py
git commit -m "feat: add _compute_eval_metrics and extend EvalInput for agents_md_coverage/schema_grounding"
```

---

## Final Verification

- [ ] **Run full test suite**

```
uv run python -m pytest tests/ -v
```

Expected: All tests PASS with no errors.

- [ ] **Run pipeline smoke test (dry run)**

```
uv run python scripts/propose_optimizations.py --dry-run
```

Expected: No import errors.

- [ ] **Verify imports**

```bash
uv run python -c "
from agent.agents_md_parser import parse_agents_md
from agent.resolve import run_resolve
from agent.schema_gate import check_schema_compliance
from agent.pipeline import run_pipeline, _build_system, _extract_discovery_results
from agent.evaluator import _compute_eval_metrics
print('All imports OK')
"
```

Expected: `All imports OK`
