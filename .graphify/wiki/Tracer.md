# Tracer

> 20 nodes · cohesion 0.12

## Key Concepts

- **tracer.py** (7 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **RunTracer** (6 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **TaskTracer** (5 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **close_tracer()** (3 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **get_task_tracer()** (3 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **init_tracer()** (3 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **.close()** (2 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **.emit()** (2 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **set_task_id()** (2 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Replay tracer for the agent loop (П3).  Writes JSONL event stream to logs/{ts}_{** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Store task_id in thread-local so loop.py can access it without signature changes** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Return a TaskTracer bound to task_id (falls back to thread-local if not given).** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Flush and close the run-level tracer. Call at process exit.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Append-only JSONL writer. Fail-open: errors in emit() never propagate.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Append one event line. Fail-open on any error.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Per-task facade over RunTracer. Binds task_id for all emit calls.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **Initialise the run-level JSONL tracer. No-op if TRACE_ENABLED != 1.** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **.__init__()** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **.emit()** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`
- **.__init__()** (1 connections) — `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`

## Relationships

- No strong cross-community connections detected

## Source Files

- `/home/UF.RT.RU/i.y.tischenko/Документы/Git/ecom1-agent/agent/tracer.py`

## Audit Trail

- EXTRACTED: 44 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*