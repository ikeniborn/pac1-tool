---
wiki_title: "Contract Phase CC-tier + Wiki Graph Fixes"
wiki_status: stub
wiki_sources:
  - "docs/superpowers/plans/2026-04-27-contract-graph-fixes.md"
wiki_updated: "2026-05-06"
tags: [fix, contract, graph, race-condition, CC-tier, markdown-fence]
---

# Contract Phase CC-tier + Wiki Graph Fixes

**Источник:** `docs/superpowers/plans/2026-04-27-contract-graph-fixes.md`

## Цель

Исправить два дефекта: (A) контракт-фаза всегда падает на CC-tier из-за markdown-фенсов в JSON-ответе и отсутствия schema enforcement; (B) параллельный граф-фидбэк теряет reinforcements из-за race condition при конкурентных записях.

## Дефект A: CC-tier markdown fences в contract JSON

**Проблема:** CC tier возвращает `\`\`\`json ... \`\`\`` вместо чистого JSON → parse fail в `negotiate_contract`.  
**Фикс:**
1. Strip markdown fences перед json.loads
2. Schema enforcement через `response_format={"type": "json_object"}` где API поддерживает
3. Fallback: `_extract_json_from_text()` для случаев без schema enforcement

## Дефект B: Graph race condition

**Проблема:** При `PARALLEL_TASKS>1` — несколько воркеров одновременно читают/пишут `graph.json` → потеря reinforcements.  
**Фикс:** Файловая блокировка через `fcntl.flock` в `save_graph()`:

```python
def save_graph(graph, path):
    with open(path, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(graph, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

**Ключевые файлы:** `agent/contract_phase.py`, `agent/wiki_graph.py`
