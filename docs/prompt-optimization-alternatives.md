# Open-source альтернативы DSPy для оптимизации промтов

**Дата**: 2026-04-21
**Контекст проекта**: PAC1-tool использует DSPy + COPRO для оптимизации трёх компонентов — `prompt_builder` (генерация 3–6 bullet points контекстной инструкции), `evaluator` (yes/no проверка качества завершения) и `classifier` (10 типов задач: think, distill, email, lookup, inbox, queue, capture, crm, temporal, preject).

Документ — справочный обзор альтернативных фреймворков автоматической оптимизации промтов, актуальный на 2025–2026 гг.

---

## Оглавление

1. [TextGrad](#1-textgrad) — текстовые градиенты (Stanford)
2. [AdalFlow](#2-adalflow) — PyTorch-подобный unified framework
3. [GEPA](#3-gepa) — рефлексивный генетический оптимизатор (команда DSPy)
4. [PromptWizard](#4-promptwizard) — self-evolving critique (Microsoft)
5. [Promptbreeder](#5-promptbreeder) — self-referential evolution (DeepMind)
6. [EvoPrompt](#6-evoprompt) — генетика + differential evolution (Microsoft)
7. [OPRO](#7-opro) — LLM-as-optimizer (Google DeepMind)
8. [SAMMO](#8-sammo) — structure-aware metaprompt search (Microsoft)
9. [APE](#9-ape) — automatic prompt engineer (classic)
10. [AutoPrompt](#10-autoprompt) — gradient-based token search
11. [OpenPrompt](#11-openprompt) — unified prompt-learning
12. [Trace](#12-trace) — end-to-end generative optimization (Microsoft + Stanford)
13. [ProTeGi](#13-protegi) — natural-language gradients (Microsoft)
14. [Новые фреймворки 2025](#14-новые-фреймворки-2025)
15. [Комплементарные инструменты (evaluation)](#15-комплементарные-инструменты-evaluation)
16. [Сводная таблица](#сводная-сравнительная-таблица)
17. [Рекомендации для PAC1-tool](#рекомендации-для-pac1-tool)

---

## 1. TextGrad

- **GitHub**: https://github.com/zou-group/textgrad
- **Paper**: arXiv:2406.07496; опубликован в Nature (2025)
- **Автор / лаборатория**: Stanford / CZ Biohub (Zou Lab)

**Подход**: Textual Gradient Descent (TGD) — LLM-судья генерирует feedback на естественном языке, который играет роль градиента и распространяется по графу вычислений в обратном направлении (аналог backpropagation).

**Что оптимизирует**: Любые текстовые переменные — промты, код, молекулярные структуры, решения задач. Не ограничен только промтами.

**API**: PyTorch-подобный (`Variable`, `Loss`, `Optimizer`). Новый движок на litellm позволяет подключать произвольные модели (Anthropic, Bedrock, Together, Gemini, локальный Ollama).

**Лицензия**: MIT.

**Сильные стороны vs DSPy**:
- Гибче — оптимизирует произвольные текстовые артефакты, а не только структуру промта.
- Естественный API для тех, кто знает PyTorch.

**Слабые стороны vs DSPy**:
- Медленнее (по данным AdalFlow, ~80 с на backprop против ~12 с у AdalFlow).
- Меньше готовых модулей/рецептов.

**Применимо для PAC1-tool**: Частично. Для `evaluator` с free-form feedback — разумный кандидат, но скорость уступает GEPA.

---

## 2. AdalFlow

- **GitHub**: https://github.com/SylphAI-Inc/AdalFlow
- **Документация**: https://adalflow.sylph.ai/
- **Автор**: SylphAI-Inc в коллаборации с VITA Group (UT Austin)

**Подход**: Собственный LLM-AutoDiff + Few-Shot Bootstrap (как в DSPy) + текстовые градиенты (как в TextGrad). Унифицированный фреймворк, объединяющий лучшие идеи трёх школ.

**Что оптимизирует**: Одновременно три составляющие промта:
1. Инструкции
2. Few-shot примеры
3. Шаблон промта

Параметры помечаются как `PROMPT` или `DEMOS`.

**Архитектура**: `Component` (аналог `nn.Module`), `Generator`, `AdalComponent`, `Trainer`. Model-agnostic через `ModelClient`.

**Лицензия**: MIT.

**Сильные стороны vs DSPy**:
- По заявлениям авторов — 94% на QA с одним bootstrap-shot.
- Быстрее TextGrad в ~6 раз.
- Единый API для оптимизации инструкций + few-shot одновременно.

**Слабые стороны vs DSPy**:
- Меньше сообщества и рецептов.
- Миграция с DSPy требует переписывания компонентов.

**Применимо для PAC1-tool**: Сильный кандидат, если готов полный рефакторинг `prompt_builder.py` и `evaluator.py`. Особенно полезен, если нужно автогенерировать few-shot примеры для каждого task_type.

---

## 3. GEPA

- **GitHub**: https://github.com/gepa-ai/gepa
- **Интеграция с DSPy**: https://dspy.ai/api/optimizers/GEPA/overview/
- **Paper**: arXiv:2507.19457 (UC Berkeley, Stanford, Databricks и др.); принята на ICLR 2026 (Oral)
- **Авторы**: Команда DSPy (17 авторов во главе с Lakshya A. Agrawal; Koushik Sen, Dan Klein, Ion Stoica, Matei Zaharia, Christopher Potts, Omar Khattab и др.)

**Подход**: **Genetic-Pareto Reflective Prompt Evolution**. LLM читает полные execution traces (ошибки, логи рассуждений, промежуточные состояния) и генерирует целевые исправления. Генетическая мутация + Pareto-aware selection.

**Ключевая новация**: Actionable Side Information (ASI) — текстовый feedback как аналог градиента. Pareto frontier вместо единого "лучшего" кандидата сохраняет комплементарные стратегии.

**Что оптимизирует**:
- Инструкции и структуру промта
- Целые DSPy-программы (включая signatures, modules, control flow) через адаптеры:
  - **DSPy Full Program Adapter**
  - **Generic RAG Adapter** (ChromaDB / Weaviate / Qdrant)
  - **MCP Adapter**
  - **ConfidenceAdapter** — для классификации с использованием logprobs (идеально для задач типа `classifier` в PAC1-tool)

**Лицензия**: MIT.

**Сильные стороны vs DSPy-COPRO/MIPROv2**:
- Превосходит MIPROv2 на +13% в среднем.
- До +20% vs GRPO при 35× меньшем числе rollouts.
- 93% на MATH vs 67% у ChainOfThought.
- Использует полные execution traces вместо скалярных наград.

**Слабые стороны**:
- Метрика должна возвращать `dspy.Prediction(score=..., feedback=...)`.
- Нужен качественный LLM-рефлексор.

**Зрелость**: Широкое принятие индустрией — интеграции в MLflow, Pydantic AI, OpenAI Cookbook, Google ADK; активное сообщество.

**Применимо для PAC1-tool**: **Сильнейший прагматичный кандидат.** Прямая замена COPRO без смены стека DSPy. Особенно подходит для `classifier` через `ConfidenceAdapter` (10 типов задач — точный кейс) и `evaluator` (feedback информативнее yes/no-скаляра).

---

## 4. PromptWizard

- **GitHub**: https://github.com/microsoft/PromptWizard
- **Paper**: arXiv:2405.18369
- **Автор**: Microsoft Research

**Подход**: Task-Aware Agent-driven self-evolving framework. LLM сам генерирует, критикует и улучшает промты и примеры в итеративном цикле с синтезом новых примеров.

**Что оптимизирует**: Одновременно инструкции и in-context examples (positive, negative, synthetic) с self-generated Chain-of-Thought шагами.

**Три режима**:
1. `use_examples` — если есть training
2. `generate_synthetic_examples` — нет training-данных
3. `run_without_train_examples` — чистый zero-shot

**Лицензия**: MIT.

**Сильные стороны vs DSPy**:
- Превосходит DSPy, APO, PromptAgent по точности и числу API-вызовов.
- Устойчив при малом количестве примеров за счёт синтетики.
- Интеграция с Azure Content Safety.

**Слабые стороны**:
- Research-oriented: предупреждение "not for downstream applications without additional analysis".
- Требует YAML-конфигурации.

**Применимо для PAC1-tool**: Рекомендуется, когда данных мало — например, для редких task_type (`preject`, `temporal`) в `classifier`. Синтетические примеры закроют пробелы в датасете.

---

## 5. Promptbreeder

- **Paper**: arXiv:2309.16797 (DeepMind, 2023–2024)
- **GitHub (community форки — официального кода нет)**:
  - https://github.com/vaughanlove/PromptBreeder (LangChain, Cohere)
  - https://github.com/suvalaki/prompt_breeder (LangChain)

**Подход**: Self-referential механизм. Эволюционируют **одновременно** task-prompts и mutation-prompts (мета-уровень). 5 классов операторов мутации. Bitournament selection.

**Сильные стороны**:
- Превосходит Chain-of-Thought и Plan-and-Solve на арифметике и common sense.
- Находит неинтуитивные эффективные формулировки (например, обнаружил, что "SOLUTION:" работает лучше "Let's think step by step").

**Слабые стороны**:
- Нет официальной реализации от DeepMind.
- Дорого: ~60 USD и ~6.7 часов за полный прогон 50 units × 20 генераций.
- Качество community-форков среднее.

**Применимо для PAC1-tool**: Исследовательский интерес; для продакшена проигрывает GEPA.

---

## 6. EvoPrompt

- **GitHub (официальный, от автора)**: https://github.com/beeevita/EvoPrompt
- **GitHub (Microsoft-mirror)**: https://github.com/microsoft/EvoPrompt
- **Paper**: ICLR 2024
- **Автор**: Qingyan Guo (Microsoft)

**Подход**: Объединение LLM с классическими эволюционными алгоритмами — Genetic Algorithm (GA) и Differential Evolution (DE) — без градиентов. LLM применяет эволюционные операторы (mutation, crossover) через шаблонные промты.

**Сильные стороны**:
- До +25% на BBH vs ручные промты.
- Работает и с closed-source (GPT-3.5), и с open-source (Alpaca) моделями.
- Протестирован на 31 датасете.

**Слабые стороны**:
- Узкоспециализирован под discrete prompt optimization (не модульные пайплайны).
- Требует ручной подготовки данных в специфическом формате.

**Лицензия**: MIT.

**Применимо для PAC1-tool**: Для одиночных промтов (например, отдельно `prompt_builder` как standalone-компонент), где хочется выжать максимум из эволюционного поиска.

---

## 7. OPRO (Optimization by PROmpting)

- **GitHub**: https://github.com/google-deepmind/opro
- **Paper**: arXiv:2309.03409; "Large Language Models as Optimizers", ICLR 2024
- **Автор**: Google DeepMind

**Подход**: Meta-prompt с историей кандидатов и их оценок → LLM генерирует новых кандидатов, стремясь улучшить score. Работает по принципу "LLM как оптимизатор".

**Сильные стороны**:
- До +8% на GSM8K и +50% на BBH vs ручные промты.
- Концептуально простой и понятный.

**Слабые стороны**:
- Context window лимитирует масштаб истории.
- Плохо работает на маленьких LLM (показано в follow-up paper "Revisiting OPRO").
- Мало инфраструктуры вокруг.

**Лицензия**: Apache 2.0.

**Применимо для PAC1-tool**: Baseline для сравнений; в продакшене уступает GEPA.

---

## 8. SAMMO

- **GitHub**: https://github.com/microsoft/sammo
- **Paper**: EMNLP 2024
- **Автор**: Microsoft Research

**Подход**: **Structure-aware Multi-objective Metaprompt Optimization.** Работает с промтами как со структурированными программами. Genetic search по мутационным операторам, вдохновлённый neural architecture search. CSS-подобные селекторы для модификации частей промта.

**Что оптимизирует**:
- Структура metaprompt: task description, guidelines, examples, format.
- Prompt compression (сокращение промта без потери качества).

**SAMMO Express (2024)**: Превращает Markdown в программы промтов; поддерживает structured outputs.

**Лицензия**: MIT.

**Сильные стороны**:
- +10–100% при instruction tuning.
- +26–133% при RAG tuning.
- +40% при prompt compression.
- Efficient minibatching.

**Слабые стороны**:
- Избыточен для простых случаев.
- Более высокая кривая обучения.

**Применимо для PAC1-tool**: Рекомендуется для оптимизации системного промта в `prompt.py` как структурированной программы (секции: codegen rules, security gates, discovery patterns, task-type guidance) и для компрессии — полезно в рамках token budget.

---

## 9. APE (Automatic Prompt Engineer)

- **GitHub**: https://github.com/keirp/automatic_prompt_engineer
- **Авторы paper**: Yongchao Zhou, Andrei I. Muresanu, Ziwen Han, Keiran Paster, Silviu Pitis, Harris Chan, Jimmy Ba (University of Toronto / Vector Institute); репозиторий ведёт Keiran Paster (keirp)

**Подход**: Один из самых ранних фреймворков. LLM генерирует кандидатов инструкций → eval-функция оценивает → возвращает лучший (Monte Carlo + UCB bandit).

**Сильные стороны**:
- Историческое значение: открыл известное "Let's work this out in a step by step way to be sure we have the right answer" (лучше чем ручное "Let's think step by step").
- Максимальная простота.

**Слабые стороны**:
- Только инструкции (нет few-shot, пайплайнов, workflow-абстракций).

**Лицензия**: MIT.

**Применимо для PAC1-tool**: Образовательный/baseline-инструмент.

---

## 10. AutoPrompt

### 10a. AutoPrompt (UCINLP, Shin et al. 2020)

- **GitHub**: https://github.com/ucinlp/autoprompt

**Подход**: Gradient-guided search по токенам-триггерам (HotFlip-style) для Masked LM (BERT/RoBERTa). **Настоящие** градиенты, не текстовые.

**Применимо для PAC1-tool**: Нет — работает только с open-weight MLM, не с API-based LLM.

### 10b. Eladlev/AutoPrompt

- **GitHub**: https://github.com/Eladlev/AutoPrompt

**Подход**: Production-oriented фреймворк с Intent-based Prompt Calibration; prompt squeezing для объединения правил; миграция промтов между моделями.

**Применимо для PAC1-tool**: Интересен для `evaluator` (бинарная классификация с критериями) и при миграции между моделями (Sonnet ↔ Ollama ↔ OpenRouter).

---

## 11. OpenPrompt

- **GitHub**: https://github.com/thunlp/OpenPrompt
- **Награда**: ACL 2022 Best Demo Paper Award

**Подход**: Унифицированный интерфейс для методов prompt-learning с PLM — template + verbalizer + модель. Поддерживает manual/soft/prefix prompts, WARP, P-tuning.

**Лицензия**: Apache 2.0.

**Применимо для PAC1-tool**: Нет — другая парадигма (работа с open-weight моделями и soft prompts). Не подходит для проекта, работающего через API (Anthropic / OpenRouter).

---

## 12. Trace

- **GitHub**: https://github.com/microsoft/Trace
- **Paper**: arXiv:2406.16218
- **Авторы**: Microsoft Research + Stanford

**Подход**: End-to-end generative optimization для AI-агентов. **OPTO** (Optimization with Trace Oracle) — обобщение AutoDiff для нематематических workflow. Оптимизатор `OptoPrime` использует execution traces + feedback.

**Архитектура**: Декларирование через `node` и `@bundle` декораторы. Автоматически захватывает execution graph.

**Что оптимизирует**: **Heterogeneous parameters** — промты, гиперпараметры, код одновременно.

**Лицензия**: MIT.

**Сильные стороны vs DSPy**:
- +10% точности на BigBenchHard при оптимизации DSPy-программы vs собственный оптимизатор DSPy.
- Joint optimization промтов + гиперпараметров + кода.
- Подходит для non-differentiable workflow (включая роботов).

**Слабые стороны**:
- Потенциальные проблемы с графами >100 операций (context-length).

**Применимо для PAC1-tool**: Сильнейший кандидат для оптимизации **всего агентного loop'а** — `dispatch.py`, `loop.py`, stall-detection и security gates совместно. Позволит превратить поведенческий код + промты в единый оптимизируемый граф.

---

## 13. ProTeGi

- **GitHub**: https://github.com/microsoft/LMOps/tree/main/prompt_optimization
- **Paper**: EMNLP 2023
- **Автор**: Microsoft

**Подход**: Прообраз и идейный источник TextGrad. Natural language "gradients" критикуют текущий промт → редактируют в противоположном семантическом направлении. Beam search + bandit selection.

**Сильные стороны**:
- +31 п.п. F1 на задачах типа jailbreak detection и hate speech.
- Первая рабочая реализация "текстовых градиентов".

**Слабые стороны**:
- Менее развит, чем TextGrad.
- Нет PyTorch-style API.

**Лицензия**: MIT.

**Применимо для PAC1-tool**: Baseline или для задач модерации/безопасности (security gates).

---

## 14. Новые фреймворки 2025

### 14a. Promptomatix

- **Paper**: arXiv:2507.14241

**Подход**: Zero-config. Автоматически генерирует промты из описания задачи на естественном языке. Комбинация lightweight meta-prompt optimizer и DSPy-powered compiler. Анализирует intent, генерирует synthetic data, выбирает prompting strategy.

**Применимо для PAC1-tool**: Быстрое получение baseline-промтов для новых task_type без ручной настройки.

### 14b. promptolution

- **Paper**: arXiv:2512.02840

**Подход**: Модульный унифицирующий фреймворк. Включает CAPO, EvoPromptGA, OPRO. Бенчмаркается с AdalFlow (LLM-AutoDiff) и DSPy (GEPA).

**Применимо для PAC1-tool**: Платформа для A/B-тестирования разных оптимизаторов без ручной интеграции каждого.

### 14c. AutoPDL

- **Paper**: arXiv:2504.04365

**Подход**: AutoML для промтов — структурированный поиск в комбинаторном пространстве агентных паттернов (ReAct / CoT / Plan-and-Solve) + демонстраций, с successive halving.

**Ключевое отличие от DSPy**: Автоматически выбирает prompting pattern (DSPy требует ручного выбора между `Predict` / `ChainOfThought` / `ReAct`).

**Применимо для PAC1-tool**: Интересен для главного agent loop — пусть оптимизатор сам решит, нужен ли ReAct или хватит CoT для каждого task_type.

### 14d. Opik Agent Optimizer (Comet ML)

- **GitHub**: https://github.com/comet-ml/opik
- **Лицензия**: Apache-2.0

**Подход**: Продакшн-oriented LLM observability + evaluation + agent optimizer в одном стеке. Предоставляет SDK с набором оптимизаторов для промтов и агентов, LLM-as-a-judge метрики, продакшн-мониторинг.

**Применимо для PAC1-tool**: Связка tracing + optimization; может заменить собственную реализацию `OptimizeLogger` в `optimize_prompts.py`.

### 14e. Eladlev/AutoPrompt

См. раздел [10b](#10b-eladlevautoprompt).

---

## 15. Комплементарные инструменты (evaluation)

Не заменяют DSPy, но хорошо с ним сочетаются.

| Инструмент | GitHub | Роль |
|---|---|---|
| **Promptfoo** | https://github.com/promptfoo/promptfoo | Prompt testing + red-teaming в CI/CD; YAML-декларации; MIT |
| **Opik** (Comet) | https://github.com/comet-ml/opik | Observability + evaluation + agent optimizer SDK; Apache-2.0 |
| **Langfuse** | https://github.com/langfuse/langfuse | Observability + prompt management + evals; удобный UI; легко self-hosted |
| **Phoenix** (Arize) | https://github.com/Arize-ai/phoenix | Observability + evals; медленнее Opik в ~7 раз |

**Рекомендуемый продакшн-стек**: DSPy + GEPA (оптимизация) + Opik/Langfuse (eval + tracing) + Promptfoo (regression tests в CI).

---

## Сводная сравнительная таблица

| № | Фреймворк | Подход | Что оптимизирует | Зрелость | Лицензия | vs DSPy |
|---|---|---|---|---|---|---|
| 1 | **TextGrad** | Textual gradients (feedback) | Любые текстовые переменные | Высокая (Nature 2025) | MIT | Гибче, но медленнее |
| 2 | **AdalFlow** | LLM-AutoDiff + Bootstrap | Instructions + demos + template | Высокая | MIT | Быстрее, unified API |
| 3 | **GEPA** | Reflective genetic + Pareto | Инструкции, целые DSPy-программы | Очень высокая (ICLR 2026) | MIT | **+13% vs MIPROv2** |
| 4 | **PromptWizard** | Self-evolving critique + synth | Instructions + few-shot | Высокая | MIT | Превосходит DSPy на малых данных |
| 5 | **Promptbreeder** | Self-referential evolution | Task + mutation prompts | Низкая (только community) | MIT / Apache (форки) | Экспериментальный |
| 6 | **EvoPrompt** | Genetic Algorithm + DE | Discrete prompts | Средняя (ICLR 2024) | MIT | Узкоспециализирован |
| 7 | **OPRO** | LLM as optimizer (meta-prompt) | Instructions | Средняя | Apache 2.0 | Проще, но слабее |
| 8 | **SAMMO** | Structure-aware genetic search | Structured metaprompts | Высокая (EMNLP 2024) | MIT | Лучше для RAG/compression |
| 9 | **APE** | Candidate generation + UCB | Single instructions | Низкая (старый) | MIT | Значительно слабее |
| 10a | **AutoPrompt (UCI)** | Gradient-guided token search | Trigger tokens для MLM | Низкая (2020) | Apache 2.0 | Только для MLM |
| 10b | **AutoPrompt (Eladlev)** | Intent-based Calibration | Prompts (production) | Средняя | Open-source | Продакшн-фокус |
| 11 | **OpenPrompt** | Unified prompt-learning API | Soft prompts, verbalizers | Средняя | Apache 2.0 | Другая парадигма |
| 12 | **Trace** | OPTO (graph + LLM optimizer) | Prompts + code + hyperparams | Высокая | MIT | **+10% vs DSPy-оптимизаторы** |
| 13 | **ProTeGi** | Natural language gradients | Prompts | Средняя (EMNLP 2023) | MIT | Предшественник TextGrad |
| 14a | **Promptomatix** | Zero-config meta-prompt | Full pipeline | Новая (2025) | Open-source | Wrapper над DSPy |
| 14b | **promptolution** | Модульный (CAPO/EvoGA/OPRO) | Prompts | Новая (2025) | Open-source | Для сравнения |
| 14c | **AutoPDL** | AutoML over patterns + demos | Patterns + few-shot | Новая (2025) | Open-source | Выбирает паттерн сам |

---

## Рекомендации для PAC1-tool

С учётом текущей архитектуры (три DSPy-компонента + COPRO; 10 task_type; ограниченный бюджет API-вызовов) приоритет кандидатов:

### Приоритет 1 — минимум инвестиций, максимум выигрыша

**GEPA.** Прямая замена COPRO, совместимая с DSPy. Ключевые выигрыши:
- `ConfidenceAdapter` идеально подходит для `classifier` (10 task_type — logprob-aware optimization).
- `DSPy Full Program Adapter` позволяет оптимизировать всю программу сразу, включая control flow.
- Метрика возвращает `feedback` (не только скаляр) — информативнее для `evaluator`.
- Требует только переписать метрики в `optimize_prompts.py` (возвращать `dspy.Prediction(score, feedback)`) и заменить `COPRO(...)` на `GEPA(...)`.

### Приоритет 2 — если данных мало для отдельных task_type

**PromptWizard.** Текущий `COPRO_MIN_PER_TYPE=3` даёт много "skipped" типов — PromptWizard синтезирует недостающие примеры и оптимизирует без минимального порога. Применять к редким типам: `preject`, `temporal`, `capture`.

### Приоритет 3 — амбициозный рефакторинг

**Trace.** Если захочется оптимизировать не только три компонента, а **весь agent loop**: `dispatch.py` (retry-логика), `loop.py` (шаги), `stall.py` (пороги), `security.py` (нормализация). OPTO-граф + `OptoPrime` превратят поведенческие константы + промты в единый оптимизируемый объект.

### Приоритет 4 — узкий кейс

**SAMMO.** Для оптимизации структурированного системного промта в `prompt.py` (секции codegen, security, discovery) и prompt compression — полезно в рамках token budget.

### Чего стоит избегать

- **AutoPrompt (UCI), OpenPrompt** — ориентированы на open-weight MLM, не применимы к API-based стеку проекта.
- **Promptbreeder** — нет официальной реализации; community-форки среднего качества.
- **APE, OPRO** — baseline-уровень; уступают современным подходам.

### Первый шаг миграции (конкретно)

```bash
# Установить GEPA (интегрирован в DSPy)
uv add dspy-ai[gepa]

# В optimize_prompts.py заменить:
#   from dspy.teleprompt import COPRO
# на:
#   from dspy.teleprompt import GEPA

# Адаптировать метрики — возвращать feedback:
def _builder_metric(example, prediction, _trace=None) -> dspy.Prediction:
    ...
    return dspy.Prediction(score=result, feedback="Addendum is missing bullet structure" if result < 1.0 else "")
```

Миграция должна занять ~1–2 дня без риска для остальных компонентов — DSPy-signatures `PromptAddendum`, `EvaluateCompletion`, `ClassifyTask` не меняются.

---

## Источники

- [TextGrad GitHub](https://github.com/zou-group/textgrad)
- [TextGrad paper (arXiv)](https://arxiv.org/abs/2406.07496)
- [AdalFlow GitHub](https://github.com/SylphAI-Inc/AdalFlow)
- [AdalFlow docs](https://adalflow.sylph.ai/)
- [GEPA GitHub](https://github.com/gepa-ai/gepa)
- [GEPA DSPy integration](https://dspy.ai/api/optimizers/GEPA/overview/)
- [GEPA paper (arXiv)](https://arxiv.org/abs/2507.19457)
- [PromptWizard GitHub](https://github.com/microsoft/PromptWizard)
- [Promptbreeder paper (arXiv)](https://arxiv.org/abs/2309.16797)
- [Promptbreeder community impl (vaughanlove)](https://github.com/vaughanlove/PromptBreeder)
- [Promptbreeder community impl (suvalaki)](https://github.com/suvalaki/prompt_breeder)
- [EvoPrompt GitHub (beeevita)](https://github.com/beeevita/EvoPrompt)
- [EvoPrompt GitHub (microsoft)](https://github.com/microsoft/EvoPrompt)
- [OPRO GitHub (google-deepmind)](https://github.com/google-deepmind/opro)
- [OPRO paper](https://arxiv.org/abs/2309.03409)
- [APE GitHub](https://github.com/keirp/automatic_prompt_engineer)
- [AutoPrompt GitHub (ucinlp)](https://github.com/ucinlp/autoprompt)
- [AutoPrompt GitHub (Eladlev)](https://github.com/Eladlev/AutoPrompt)
- [OpenPrompt GitHub](https://github.com/thunlp/OpenPrompt)
- [Trace GitHub](https://github.com/microsoft/Trace)
- [Trace paper](https://arxiv.org/abs/2406.16218)
- [SAMMO GitHub](https://github.com/microsoft/sammo)
- [ProTeGi (Microsoft LMOps)](https://github.com/microsoft/LMOps)
- [DSPy docs — Optimizers](https://dspy.ai/learn/optimization/optimizers/)
- [Promptomatix paper](https://arxiv.org/html/2507.14241v3)
- [AutoPDL paper](https://arxiv.org/abs/2504.04365)
- [promptolution paper](https://arxiv.org/html/2512.02840v2)
- [Awesome-LLM-Prompt-Optimization](https://github.com/jxzhangjhu/Awesome-LLM-Prompt-Optimization)
- [Opik (Comet ML) GitHub](https://github.com/comet-ml/opik)
