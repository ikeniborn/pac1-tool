#!/usr/bin/env python3
"""
run5_collect.py — 5 runs of t42,t43,t40,t41,t13 with state capture.
Writes progressive report to docs/run_analysis_{date}_v3.md
"""
import json, os, subprocess, sys, glob, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
TASKS = ["t42", "t43", "t40", "t41", "t13"]
REPORT_PATH = ROOT / f"docs/run_analysis_{datetime.now().strftime('%Y-%m-%d')}_v3.md"

os.chdir(ROOT)


def capture_state() -> dict:
    state = {}

    # Graph
    try:
        with open("data/wiki/graph.json") as f:
            g = json.load(f)
        nodes = g.get("nodes", {})
        edges = g.get("edges", {})
        types: dict = {}
        for n in nodes.values():
            t = n.get("type", "?")
            types[t] = types.get(t, 0) + 1
        state["graph_nodes"] = len(nodes)
        state["graph_edges"] = len(edges)
        state["graph_types"] = types
    except Exception:
        state["graph_nodes"] = 0
        state["graph_edges"] = 0
        state["graph_types"] = {}

    # Wiki pages
    pages = glob.glob("data/wiki/pages/**/*.md", recursive=True)
    state["wiki_pages"] = len(pages)
    state["wiki_page_names"] = [p.replace("data/wiki/pages/", "") for p in pages]

    # Fragment counts from wiki pages
    total_frags = 0
    for p in pages:
        try:
            content = Path(p).read_text()
            m = re.search(r"fragment_count:\s*(\d+)", content)
            if m:
                total_frags += int(m.group(1))
        except Exception:
            pass
    state["wiki_fragments"] = total_frags

    # DSPy examples
    try:
        with open("data/dspy_examples.jsonl") as f:
            state["dspy_examples"] = sum(1 for _ in f)
    except Exception:
        state["dspy_examples"] = 0

    # DSPy programs
    progs = glob.glob("data/*program*.json")
    state["dspy_programs"] = [os.path.basename(p) for p in progs]

    return state


def get_latest_log_dir() -> Path | None:
    dirs = sorted(Path("logs").glob("*/"), key=lambda p: p.name)
    return dirs[-1] if dirs else None


def extract_scores(log_dir: Path) -> dict[str, dict]:
    scores = {}
    main_log = log_dir / "main.log"
    if not main_log.exists():
        return scores
    with open(main_log) as f:
        for line in f:
            m = re.match(r"^\s*(t\d+)\s+([0-9.]+)\s+([0-9.]+)s\s+.*$", line)
            if m:
                task_id = m.group(1)
                score = float(m.group(2))
                time_s = float(m.group(3))
                # Extract detail (last field after lots of whitespace)
                detail = line.strip().split()[-1] if line.strip() else ""
                # Get full end of line for error detail
                parts = line.rstrip().split("  ")
                detail_full = parts[-1].strip() if len(parts) > 1 else ""
                scores[task_id] = {
                    "score": score,
                    "time_s": time_s,
                    "detail": detail_full,
                }
    return scores


def format_state_table(states: list[dict], labels: list[str]) -> str:
    lines = []
    lines.append("| После прогона | Узлы | Рёбра | insight | rule | antipattern | pattern | wiki pages | wiki frags | DSPy примеры |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for label, s in zip(labels, states):
        types = s.get("graph_types", {})
        lines.append(
            f"| {label} | {s['graph_nodes']} | {s['graph_edges']} "
            f"| {types.get('insight',0)} | {types.get('rule',0)} "
            f"| {types.get('antipattern',0)} | {types.get('pattern',0)} "
            f"| {s['wiki_pages']} | {s['wiki_fragments']} "
            f"| {s['dspy_examples']} |"
        )
    return "\n".join(lines)


def main():
    report_lines = []

    def emit(line: str = ""):
        report_lines.append(line)
        print(line, flush=True)
        # Write progressively
        REPORT_PATH.write_text("\n".join(report_lines) + "\n")

    emit(f"# 5-run Analysis: t42,t43,t40,t41,t13 — {datetime.now().strftime('%Y-%m-%d')} (v3)")
    emit()
    emit(f"Запуск: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    emit()

    # Baseline state
    baseline = capture_state()
    emit(f"**Стартовое состояние (до прогона 1):** граф {baseline['graph_nodes']} узлов, {baseline['graph_edges']} рёбер. "
         f"Wiki: {baseline['wiki_pages']} страниц, {baseline['wiki_fragments']} фрагментов. "
         f"DSPy: {baseline['dspy_examples']} примеров, программы: {baseline['dspy_programs']}")
    emit()

    all_states = [baseline]
    all_labels = ["0 (старт)"]
    all_scores: list[dict[str, dict]] = []

    for run_num in range(1, 6):
        emit(f"## Прогон {run_num} / 5")
        emit()
        start_t = datetime.now(timezone.utc)
        emit(f"Старт: {start_t.strftime('%H:%M:%SZ')}")
        emit()

        # Run the benchmark
        cmd = ["uv", "run", "python", "main.py"] + TASKS
        emit(f"Команда: `{' '.join(cmd)}`")
        emit()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=7200,  # 2 hours max per run
            )
            end_t = datetime.now(timezone.utc)
            elapsed = (end_t - start_t).total_seconds()
            emit(f"Завершён за {elapsed:.0f}с (exit {result.returncode})")
            if result.returncode != 0:
                emit(f"**STDERR:**")
                emit("```")
                emit(result.stderr[-2000:] if result.stderr else "(пусто)")
                emit("```")
        except subprocess.TimeoutExpired:
            emit("**TIMEOUT** — прогон превысил 2 часа")
            all_states.append(capture_state())
            all_labels.append(f"{run_num} (timeout)")
            all_scores.append({})
            continue
        except Exception as e:
            emit(f"**ERROR:** {e}")
            all_states.append(capture_state())
            all_labels.append(f"{run_num} (error)")
            all_scores.append({})
            continue

        # Get scores from latest log
        log_dir = get_latest_log_dir()
        scores = {}
        if log_dir:
            scores = extract_scores(log_dir)
            emit(f"Лог: `{log_dir.name}`")
            emit()
            emit("**Результаты задач:**")
            emit()
            emit("| Task | Score | Time | Detail |")
            emit("|------|-------|------|--------|")
            total = 0.0
            for task in TASKS:
                info = scores.get(task, {})
                s = info.get("score", "?")
                t = info.get("time_s", "?")
                d = info.get("detail", "—")[:80]
                emit(f"| {task} | {s} | {t}s | {d} |")
                if isinstance(s, float):
                    total += s
            emit()
            emit(f"**Итого прогона {run_num}:** {total:.2f} / {len(TASKS)} ({total/len(TASKS)*100:.0f}%)")
        emit()

        # State after run
        state = capture_state()
        all_states.append(state)
        all_labels.append(str(run_num))
        all_scores.append(scores)

        prev = all_states[-2]
        emit(f"**Состояние после прогона {run_num}:**")
        emit(f"- Граф: {state['graph_nodes']} узлов (+{state['graph_nodes']-prev['graph_nodes']}), "
             f"{state['graph_edges']} рёбер (+{state['graph_edges']-prev['graph_edges']})")
        emit(f"- Wiki: {state['wiki_pages']} страниц, {state['wiki_fragments']} фрагментов (+{state['wiki_fragments']-prev['wiki_fragments']})")
        emit(f"- DSPy примеры: {state['dspy_examples']} (+{state['dspy_examples']-prev['dspy_examples']})")
        emit()

    # Summary tables
    emit("---")
    emit()
    emit("## Сводная таблица результатов")
    emit()
    emit("| Прогон | " + " | ".join(TASKS) + " | ИТОГО |")
    emit("|--------|" + "|".join(["-"*7]*len(TASKS)) + "|-------|")
    for i, (scores, label) in enumerate(zip(all_scores, range(1, 6))):
        cells = []
        total = 0.0
        for task in TASKS:
            info = scores.get(task, {})
            s = info.get("score", "?")
            if isinstance(s, float):
                total += s
                mark = "✓" if s == 1.0 else "✗"
                cells.append(f"**{s:.2f}** {mark}")
            else:
                cells.append("?")
        pct = f"{total/len(TASKS)*100:.0f}%"
        emit(f"| {label} | " + " | ".join(cells) + f" | {pct} |")
    emit()

    emit("## Динамика накопления знаний")
    emit()
    emit(format_state_table(all_states, all_labels))
    emit()

    # Growth analysis
    final = all_states[-1]
    node_growth = final["graph_nodes"] - baseline["graph_nodes"]
    edge_growth = final["graph_edges"] - baseline["graph_edges"]
    frag_growth = final["wiki_fragments"] - baseline["wiki_fragments"]
    ex_growth = final["dspy_examples"] - baseline["dspy_examples"]

    emit(f"**Рост графа:** +{node_growth} узлов, +{edge_growth} рёбер за 5 прогонов.")
    emit(f"**Рост wiki:** +{frag_growth} фрагментов.")
    emit(f"**Рост DSPy:** +{ex_growth} примеров.")
    emit()

    emit(f"---")
    emit(f"Завершено: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    emit(f"Отчёт: `{REPORT_PATH}`")

    print(f"\n✓ Report written to {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
