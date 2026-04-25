# AICODE-NOTE: Keep these wrappers aligned with the README commands so the sample
# stays trivial to run from a fresh checkout without inventing parallel workflows.

.PHONY: sync run task graph-health

sync:
	uv sync

# FIX-388: graph health gate. Set GRAPH_HEALTH=0 to skip (e.g. CI rebuilding from scratch).
graph-health:
	uv run python scripts/check_graph_health.py

run:
	@if [ "$(GRAPH_HEALTH)" != "0" ]; then \
		uv run python scripts/check_graph_health.py --quiet || \
		{ echo "[make] graph health FAIL — purge then re-run, or GRAPH_HEALTH=0 make run to override"; exit 1; }; \
	fi
	uv run python main.py

task:
	@if [ -z "$(TASKS)" ]; then echo "usage: make task TASKS='t01 t03'"; exit 1; fi
	@if [ "$(GRAPH_HEALTH)" != "0" ]; then \
		uv run python scripts/check_graph_health.py --quiet || \
		{ echo "[make] graph health FAIL — purge then re-run, or GRAPH_HEALTH=0 make task to override"; exit 1; }; \
	fi
	uv run python main.py $(TASKS)
