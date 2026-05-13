# Cycle Control & Logging Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `MAX_STEPS` env var to `_MAX_CYCLES` in the pipeline, and replace the stdout Tee so `main.log` only stores the final statistics table.

**Architecture:**
- `agent/pipeline.py` reads `MAX_STEPS` from env at module load (same pattern as `EVAL_ENABLED`).
- `main.py` keeps `sys.stdout` wrapped only for the terminal `[task_id]` prefix (no file writes). A global `_stats_fh` file handle receives explicit writes from the three stats-printing functions.
- No other files touched.

**Tech Stack:** Python 3.11+, `os.environ`, `threading.local`, `re` (ANSI strip), `pytest`/`monkeypatch`

---

## File Map

| File | Change |
|------|--------|
| `agent/pipeline.py` | Line 36: read `MAX_STEPS` from env instead of hardcode |
| `agent/CLAUDE.md` | Remove "unused" note for `MAX_STEPS` |
| `main.py` | Refactor `_setup_log_tee` → new design; add `_stats_fh` global + `_log_stats()` helper; update three stats functions |
| `tests/test_pipeline.py` | Add test for `MAX_STEPS` env var |
| `tests/test_trace_main.py` | Extend to verify `main.log` contains only stats |

---

## Task 1: Wire MAX_STEPS → _MAX_CYCLES

**Files:**
- Modify: `agent/pipeline.py:36`
- Modify: `agent/CLAUDE.md`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_pipeline.py`:

```python
def test_max_cycles_reads_env(monkeypatch):
    monkeypatch.setenv("MAX_STEPS", "7")
    import importlib
    import agent.pipeline as pipeline_mod
    importlib.reload(pipeline_mod)
    assert pipeline_mod._MAX_CYCLES == 7
    monkeypatch.delenv("MAX_STEPS")
    importlib.reload(pipeline_mod)
    assert pipeline_mod._MAX_CYCLES == 3  # default
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_pipeline.py::test_max_cycles_reads_env -v
```

Expected: `FAILED` — `assert 3 == 7`

- [ ] **Step 3: Change agent/pipeline.py line 36**

Replace:
```python
_MAX_CYCLES = 3
```
With:
```python
_MAX_CYCLES = int(os.environ.get("MAX_STEPS", "3"))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_pipeline.py::test_max_cycles_reads_env -v
```

Expected: `PASSED`

- [ ] **Step 5: Update agent/CLAUDE.md**

Find the line:
```
- `MAX_STEPS` — unused in current pipeline (pipeline uses `_MAX_CYCLES=3`)
```
Replace with:
```
- `MAX_STEPS` — max pipeline retry cycles (default: 3). Controls `_MAX_CYCLES` in `pipeline.py`.
```

- [ ] **Step 6: Commit**

```bash
git add agent/pipeline.py agent/CLAUDE.md tests/test_pipeline.py
git commit -m "feat(pipeline): wire MAX_STEPS env var to _MAX_CYCLES"
```

---

## Task 2: Explicit stats writer for main.log

**Files:**
- Modify: `main.py`
- Test: `tests/test_trace_main.py`

### Design

Current `_setup_log_tee()` wraps `sys.stdout` with a `_Tee` that writes everything to `main.log`. 

New design:
1. `_setup_logging()` (rename of `_setup_log_tee`):
   - Same run_path/`_run_dir` setup as before.
   - Opens `main.log` → global `_stats_fh`.
   - Writes `[LOG]` header directly to `_stats_fh`.
   - Wraps `sys.stdout` with `_PrefixWriter` — adds `[task_id]` prefix to terminal output only; no file writes.
2. Module-level `_stats_fh: "IO[str] | None" = None` global.
3. `_log_stats(text)` helper: strips ANSI, writes `text + "\n"` to `_stats_fh`.
4. `_print_table_header()`, `_print_table_row()`, `_write_summary()`: each builds the line string explicitly, calls `print()` for terminal AND `_log_stats()` for file.

- [ ] **Step 1: Write failing test**

Add to `tests/test_trace_main.py`:

```python
def test_main_log_contains_only_stats(tmp_path, monkeypatch):
    """main.log must contain stats rows but NOT pipeline cycle lines."""
    import main as m
    import io

    stats_buf = io.StringIO()
    monkeypatch.setattr(m, "_run_dir", tmp_path)
    monkeypatch.setattr(m, "_stats_fh", stats_buf)

    # Simulate a table header + one row + summary
    m._print_table_header()
    m._print_table_row("t01", 1.0, [], 12.5, {
        "input_tokens": 100, "output_tokens": 50,
        "task_type": "lookup", "model_used": "anthropic/claude-sonnet-4-6",
    })
    m._write_summary([("t01", 1.0, [], 12.5, {"input_tokens": 100, "output_tokens": 50})], 0.0)

    contents = stats_buf.getvalue()
    assert "ИТОГОВАЯ СТАТИСТИКА" in contents
    assert "t01" in contents
    assert "ИТОГО" in contents
    # Must NOT contain pipeline noise
    assert "[pipeline]" not in contents
    assert "cycle=" not in contents
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_trace_main.py::test_main_log_contains_only_stats -v
```

Expected: `FAILED` — `_stats_fh` attribute doesn't exist yet (or `_print_table_header` doesn't write to it).

- [ ] **Step 3: Add _stats_fh global and _log_stats helper to main.py**

After line 14 (`_run_dir: "Path | None" = None`), add:

```python
_stats_fh: "object | None" = None  # IO[str] opened by _setup_logging()
_ansi_re = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")


def _log_stats(text: str) -> None:
    if _stats_fh is not None:
        _stats_fh.write(_ansi_re.sub("", text) + "\n")
        _stats_fh.flush()
```

- [ ] **Step 4: Refactor _setup_log_tee → _setup_logging**

Replace the entire `_setup_log_tee` function (find it by name — `def _setup_log_tee`) and its module-level call `_setup_log_tee()` with:

```python
def _setup_logging() -> None:
    """Create run dir, open main.log for stats, wrap stdout for [task_id] terminal prefix."""
    _env_path = Path(__file__).parent / ".env"
    _dotenv: dict[str, str] = {}
    try:
        for _line in _env_path.read_text().splitlines():
            _s = _line.strip()
            if _s and not _s.startswith("#") and "=" in _s:
                _k, _, _v = _s.partition("=")
                _dotenv[_k.strip()] = _v.strip()
    except Exception:
        pass

    model = os.getenv("MODEL") or _dotenv.get("MODEL") or "unknown"
    log_level = (os.getenv("LOG_LEVEL") or _dotenv.get("LOG_LEVEL") or "INFO").upper()

    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    _tz_name = os.environ.get("TZ", "")
    try:
        _tz = zoneinfo.ZoneInfo(_tz_name) if _tz_name else None
    except Exception:
        _tz = None
    _now = datetime.datetime.now(tz=_tz) if _tz else datetime.datetime.now()
    _safe = model.replace("/", "-").replace(":", "-")
    run_name = f"{_now.strftime('%Y%m%d_%H%M%S')}_{_safe}"
    run_path = logs_dir / run_name
    run_path.mkdir(exist_ok=True)

    global _run_dir, _stats_fh
    _run_dir = run_path
    _stats_fh = open(run_path / "main.log", "w", buffering=1, encoding="utf-8")
    _stats_fh.write(f"[LOG] {run_path}/  (LOG_LEVEL={log_level})\n")
    _stats_fh.flush()

    _orig = sys.stdout

    class _PrefixWriter:
        def write(self, data: str) -> None:
            prefix = getattr(_task_local, "task_id", None)
            if prefix and data and data != "\n":
                _orig.write(f"[{prefix}] {data}")
            else:
                _orig.write(data)

        def flush(self) -> None:
            _orig.flush()

        def isatty(self) -> bool:
            return _orig.isatty()

        @property
        def encoding(self) -> str:
            return _orig.encoding

    sys.stdout = _PrefixWriter()
    print(f"[LOG] {run_path}/  (LOG_LEVEL={log_level})")


_setup_logging()
```

- [ ] **Step 5: Update _print_table_header to write to stats**

Replace:
```python
def _print_table_header() -> None:
    print(f"\n{'=' * 80}")
    print(f"{'ИТОГОВАЯ СТАТИСТИКА':^80}")
    print('=' * 80)
    print(f"{'Задание':<10} {'Оценка':>7} {'Время':>8}  {'Вход(tok)':>10} {'Выход(tok)':>10}  {'Тип':<11} {'Модель':<30}  Проблемы")
    print("-" * 80)
```
With:
```python
def _print_table_header() -> None:
    lines = [
        f"\n{'=' * 80}",
        f"{'ИТОГОВАЯ СТАТИСТИКА':^80}",
        '=' * 80,
        f"{'Задание':<10} {'Оценка':>7} {'Время':>8}  {'Вход(tok)':>10} {'Выход(tok)':>10}  {'Тип':<11} {'Модель':<30}  Проблемы",
        "-" * 80,
    ]
    for line in lines:
        print(line)
        _log_stats(line)
```

- [ ] **Step 6: Update _print_table_row to write to stats**

Replace:
```python
def _print_table_row(task_id: str, score: float, detail: list, elapsed: float, ts: dict) -> None:
    issues = "; ".join(detail) if score < 1.0 else "—"
    in_t = ts.get("input_tokens", 0)
    out_t = ts.get("output_tokens", 0)
    m = ts.get("model_used", "—")
    m_short = m.split("/")[-1] if "/" in m else m
    t_type = ts.get("task_type", "—")
    print(f"{task_id:<10} {score:>7.2f} {elapsed:>7.1f}s  {in_t:>10,} {out_t:>10,}  {t_type:<11} {m_short:<30}  {issues}")
```
With:
```python
def _print_table_row(task_id: str, score: float, detail: list, elapsed: float, ts: dict) -> None:
    issues = "; ".join(detail) if score < 1.0 else "—"
    in_t = ts.get("input_tokens", 0)
    out_t = ts.get("output_tokens", 0)
    m = ts.get("model_used", "—")
    m_short = m.split("/")[-1] if "/" in m else m
    t_type = ts.get("task_type", "—")
    line = f"{task_id:<10} {score:>7.2f} {elapsed:>7.1f}s  {in_t:>10,} {out_t:>10,}  {t_type:<11} {m_short:<30}  {issues}"
    print(line)
    _log_stats(line)
```

- [ ] **Step 7: Update _write_summary to write to stats**

Replace:
```python
def _write_summary(scores: list, run_start: float) -> None:
    n = len(scores)
    total = sum(s for _, s, *_ in scores) / n * 100.0
    total_elapsed = time.time() - run_start
    total_in = sum(ts.get("input_tokens", 0) for *_, ts in scores)
    total_out = sum(ts.get("output_tokens", 0) for *_, ts in scores)
    print('=' * 80)
    print(f"{'ИТОГО':<10} {total:>6.2f}% {total_elapsed:>7.1f}s  {total_in:>10,} {total_out:>10,}")
    print('=' * 80)
```
With:
```python
def _write_summary(scores: list, run_start: float) -> None:
    n = len(scores)
    total = sum(s for _, s, *_ in scores) / n * 100.0
    total_elapsed = time.time() - run_start
    total_in = sum(ts.get("input_tokens", 0) for *_, ts in scores)
    total_out = sum(ts.get("output_tokens", 0) for *_, ts in scores)
    lines = [
        '=' * 80,
        f"{'ИТОГО':<10} {total:>6.2f}% {total_elapsed:>7.1f}s  {total_in:>10,} {total_out:>10,}",
        '=' * 80,
    ]
    for line in lines:
        print(line)
        _log_stats(line)
```

- [ ] **Step 8: Run new test**

```bash
uv run pytest tests/test_trace_main.py::test_main_log_contains_only_stats -v
```

Expected: `PASSED`

- [ ] **Step 9: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (zero regressions).

- [ ] **Step 10: Commit**

```bash
git add main.py tests/test_trace_main.py
git commit -m "feat(logging): main.log writes only final stats table"
```
