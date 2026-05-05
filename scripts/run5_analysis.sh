#!/usr/bin/env bash
# run5_analysis.sh — 5 прогонов t42,t43,t40,t41,t13 с захватом состояния
set -euo pipefail

TASKS="t42 t43 t40 t41 t13"
OUTDIR="docs"
REPORT="$OUTDIR/run_analysis_$(date +%Y-%m-%d)_v3.md"
cd /home/ikeniborn/Documents/Project/pac1-tool

capture_state() {
    local label="$1"
    echo "=== STATE: $label @ $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    python3 -c "
import json, os, glob

# graph
try:
    with open('data/wiki/graph.json') as f:
        g = json.load(f)
    nodes = g.get('nodes', {})
    edges = g.get('edges', {})
    types = {}
    for n in nodes.values():
        t = n.get('type','?')
        types[t] = types.get(t,0)+1
    print(f'graph: nodes={len(nodes)}, edges={len(edges)}, types={types}')
except:
    print('graph: missing')

# wiki pages
pages = glob.glob('data/wiki/pages/**/*.md', recursive=True)
print(f'wiki_pages: {len(pages)} - {[p.replace(\"data/wiki/pages/\",\"\") for p in pages]}')

# wiki fragments
try:
    total_frags = 0
    for p in pages:
        with open(p) as f:
            content = f.read()
        import re
        m = re.search(r'fragment_count:\s*(\d+)', content)
        if m:
            total_frags += int(m.group(1))
    print(f'wiki_fragments_total: {total_frags}')
except Exception as e:
    print(f'wiki_fragments: error {e}')

# dspy examples
try:
    with open('data/dspy_examples.jsonl') as f:
        n = sum(1 for _ in f)
    print(f'dspy_examples: {n}')
except:
    print('dspy_examples: 0')

# dspy programs
progs = glob.glob('data/*program*.json')
print(f'dspy_programs: {len(progs)} - {[os.path.basename(p) for p in progs]}')
"
}

get_scores() {
    local logdir="$1"
    echo "=== SCORES from $logdir ==="
    if [ -f "$logdir/main.log" ]; then
        grep -E "^\s*t[0-9]+" "$logdir/main.log" | awk '{printf "  %s: score=%s time=%s detail=%s\n", $1, $2, $3, $NF}' || true
    else
        echo "  no main.log"
    fi
}

# State before all runs
{
echo "# 5-run Analysis: t42,t43,t40,t41,t13 — $(date +%Y-%m-%d)"
echo ""
capture_state "BASELINE"
echo ""
} | tee "$REPORT"

TOTAL_SCORE=0
TOTAL_TASKS=0

for RUN in 1 2 3 4 5; do
    echo "" | tee -a "$REPORT"
    echo "## RUN $RUN / 5 — start $(date -u +%H:%M:%SZ)" | tee -a "$REPORT"
    echo "" | tee -a "$REPORT"

    # Run benchmark
    if uv run python main.py $TASKS 2>&1 | tee -a "$REPORT.run${RUN}.tmp"; then
        echo "run $RUN: OK" | tee -a "$REPORT"
    else
        echo "run $RUN: FAILED (exit $?)" | tee -a "$REPORT"
    fi

    # Get latest log dir
    LATEST_LOG=$(ls -1d logs/*/ | sort | tail -1)

    echo "" | tee -a "$REPORT"
    get_scores "$LATEST_LOG" | tee -a "$REPORT"
    echo "" | tee -a "$REPORT"
    capture_state "AFTER_RUN_$RUN" | tee -a "$REPORT"
    echo "" | tee -a "$REPORT"

    # Extract scores for summary
    if [ -f "${LATEST_LOG}main.log" ]; then
        run_scores=$(grep -E "^\s*t[0-9]+" "${LATEST_LOG}main.log" | awk '{print $2}' | tr '\n' ' ')
        echo "Run $RUN scores: $run_scores" | tee -a "$REPORT"
    fi

    echo "--- run $RUN complete at $(date -u +%H:%M:%SZ)" | tee -a "$REPORT"
done

echo "" | tee -a "$REPORT"
echo "## DONE: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$REPORT"
echo "Report saved to: $REPORT"
