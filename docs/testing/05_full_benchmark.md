# 05 — Full benchmark

## Команда

```bash
make run
```

## Exit criteria

- Total score ≥ 80% (≥34/43 верных).
- Длительность 6-8 часов (зависит от tier'а — `claude-code/*` медленнее).

## Pre-flight checklist

- [ ] Шаги 1-4 прошли green.
- [ ] `.env` содержит правильную модель в `MODEL_DEFAULT`.
- [ ] `.secrets` содержит активный `ANTHROPIC_API_KEY` (или `OPENROUTER_API_KEY`).
- [ ] Disk space: `df -h` — хотя бы 2 GB на `logs/`.
- [ ] `data/wiki/pages/` свежий (Successful patterns + Verified refusals от
      прошлого researcher-run'а если есть).

## Что делать если score < 80%

1. Сверь summary table с baseline `20260425_095904`:
   ```bash
   diff <(grep -E '^t[0-9]+' logs/20260425_095904/summary.txt) \
        <(grep -E '^t[0-9]+' logs/<current>/summary.txt)
   ```
2. **Регрессия** = task которая раньше была 1.0 а стала 0.0. Это блокер —
   реверти последние коммиты по одному пока не зеленеет.
3. **Не-регрессия** (раньше 0.0, сейчас 0.0) = task которая никогда не
   решалась. Не блокер, материал для следующего research-цикла.

## Promotion после успеха

Если score ≥ 80% И есть researcher_pending_promotion'ы — `main.py` уже
автоматом записал паттерны в `data/wiki/pages/<task_type>.md`. Закоммить:

```bash
git add data/wiki/pages/ data/wiki/graph.json
git commit -m "wiki: promote patterns from <RUN_ID>"
```
