# Rules Loader (YAML)

> 15 nodes · cohesion 0.22

## Key Concepts

- **RulesLoader** (11 connections) — `agent/rules_loader.py`
- **_make_rules_dir()** (6 connections) — `tests/test_rules_loader.py`
- **test_rules_loader.py** (6 connections) — `tests/test_rules_loader.py`
- **rules_loader.py** (3 connections) — `agent/rules_loader.py`
- **._load()** (3 connections) — `agent/rules_loader.py`
- **test_append_rule_creates_new_file()** (3 connections) — `tests/test_rules_loader.py`
- **test_append_rule_unique_id()** (3 connections) — `tests/test_rules_loader.py`
- **test_load_all_rules()** (3 connections) — `tests/test_rules_loader.py`
- **test_load_verified_rules_only()** (3 connections) — `tests/test_rules_loader.py`
- **.__init__()** (2 connections) — `agent/rules_loader.py`
- **test_empty_directory_returns_empty()** (2 connections) — `tests/test_rules_loader.py`
- **Load and append SQL planning rules from data/rules/ (one YAML file per rule).** (1 connections) — `agent/rules_loader.py`
- **.append_rule()** (1 connections) — `agent/rules_loader.py`
- **.get_rules_markdown()** (1 connections) — `agent/rules_loader.py`
- **Create a rules directory with two individual rule files.** (1 connections) — `tests/test_rules_loader.py`

## Relationships

- [[SQL Pipeline State Machine]] (2 shared connections)
- [[LLM Dispatch & Routing]] (1 shared connections)

## Source Files

- `agent/rules_loader.py`
- `tests/test_rules_loader.py`

## Audit Trail

- EXTRACTED: 38 (78%)
- INFERRED: 11 (22%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*