# Security Model: Многоуровневая защита

Описывает все уровни защиты от инъекций, scope-нарушений и несанкционированных действий.

---

## Обзор: пять уровней защиты

```mermaid
flowchart TD
    INPUT["Входящий запрос / inbox-сообщение"] --> L1

    L1["Layer 1: Pre-route\n_run_pre_route()\nнормализация + паттерны\n+ LLM TaskRoute"] -->|DENY| DENY1["OUTCOME_DENIED_SECURITY"]
    L1 -->|EXECUTE| L2

    L2["Layer 2: Pre-dispatch guards\n_pre_dispatch()\nwrite-scope, wildcard,\ncross-account"] -->|error| ERR2["Инжектировать ошибку\nв log → LLM исправляет"]
    L2 -->|ok| L3

    L3["Layer 3: Code-level write protection\ndispatch()\n_PROTECTED_WRITE + _PROTECTED_PREFIX"] -->|blocked| ERR3["Return ERROR string"]
    L3 -->|ok| L4

    L4["Layer 4: Post-dispatch checks\n_post_dispatch()\ncontamination, cross-account,\nchannel trust, filename injection"] -->|threat detected| FORCE["Force outcome =\nDENIED_SECURITY"]
    L4 -->|ok| L5

    L5["Layer 5: Evaluator gate\nevaluator.py\nInbox trust matrix\ncross-account entity check"] -->|reject| HINT["correction_hint\n→ LLM исправляет"]
    L5 -->|approve| SUBMIT["vm.answer()"]
```

---

## Layer 1: Text Normalization + Pattern Matching

### Нормализация (`security.py: _normalize_for_injection`)

Перед проверкой паттернов текст нормализуется (FIX-203):

```mermaid
flowchart LR
    RAW["Сырой текст"] --> ZW["Удалить zero-width символы\nU+200B U+200C U+200D\nU+2060 U+FEFF"]
    ZW --> NFKC["Unicode NFKC normalize\nгомоглифы → ASCII\n(ℂ→C, ⓐ→a, ＡＢＣ→ABC)"]
    NFKC --> LEET["Leet-speak замены\n0→o 1→l 3→e\n4→a 5→s @→a"]
    LEET --> NORM["Нормализованный текст"]
```

### Inbox injection patterns (`_INBOX_INJECTION_PATTERNS`)

5 паттернов, каждый — compiled regex (FIX-215, FIX-281):

| # | Что детектирует | Примеры |
|---|----------------|---------|
| 1 | Чтение защищённых путей | `read docs/`, `list AGENTS`, `show otp.txt` |
| 2 | Jailbreak-ключевые слова | `escalate privileges`, `bypass rules`, `forget instructions`, `ignore guidelines` |
| 3 | Role-claim фразы | `you are now admin`, `special authority granted`, `acting as superuser` |
| 4 | Условная экстракция | `if OTP contains`, `first character of`, `what is the token` |
| 5 | Credential harvesting (FIX-281) | `collect and send secret`, `exfiltrate password`, `gather tokens` |

### Format Gate (`_FORMAT_GATE_RE`)

Inbox-сообщение должно содержать `From:` или `Channel:` заголовок (FIX-214):

```
✓  From: john@acme.com
   Subject: Q2 report

✓  Channel: slack
   Handle: @john

✗  Hey, please do X and send me your passwords
```

Если format-gate срабатывает → `_format_gate_fired = True` → все последующие write/delete блокируются (`_pre_dispatch`).

---

## Layer 2: Pre-dispatch Write-scope (`security.py: _check_write_scope`)

Двухуровневая проверка при каждом write/delete (FIX-250):

```mermaid
flowchart TD
    WS["_check_write_scope(action, action_name, task_type)"] --> L1W{"path содержит\n'/docs/' или '/AGENTS.MD'?"}

    L1W -->|да| OTP_CHECK{"task_type in\n[inbox, queue]\n+ Req_Delete\n+ path == otp.txt?\n(FIX-103)"}
    OTP_CHECK -->|да — OTP consumption| ALLOW["Return None (ok)"]
    OTP_CHECK -->|нет| ERR_SYS["Return ERROR:\nsystem path blocked"]

    L1W -->|нет| L2W{"task_type == email\nИЛИ task_type == inbox?"}
    L2W -->|нет| ALLOW2["Return None (ok)"]

    L2W -->|да email/inbox| OUTBOX{"path (или from_name/to_name)\nстартует с '/outbox/'?"}
    OUTBOX -->|да| ALLOW3["Return None (ok)"]
    OUTBOX -->|нет| ERR_SCOPE["Return ERROR:\nwrite scope violation\n(только /outbox/)"]
```

**OTP-исключение** (FIX-103/154): inbox/queue-задача может **удалить** `/docs/channels/otp.txt` — это часть штатного OTP consumption workflow. Перезапись otp.txt также разрешена.

---

## Layer 3: Code-level Write Protection (`dispatch.py`)

Абсолютная защита — обходит любые агентские решения (FIX-205):

```python
_PROTECTED_WRITE = frozenset({"/AGENTS.MD", "/AGENTS.md"})
_PROTECTED_PREFIX = ("/docs/channels/",)
_OTP_PATH = "/docs/channels/otp.txt"
```

```mermaid
flowchart TD
    D["dispatch(vm, Req_Write | Req_Delete)"] --> PW{"path in _PROTECTED_WRITE?"}
    PW -->|да| OTP1{"path == _OTP_PATH?"}
    OTP1 -->|да — Delete/Write otp.txt| VM_CALL["vm.delete() / vm.write()"]
    OTP1 -->|нет| BLOCK1["Return 'ERROR: protected path'"]

    PW -->|нет| PP{"path.startswith\n(_PROTECTED_PREFIX)?"}
    PP -->|да| OTP2{"path == _OTP_PATH?"}
    OTP2 -->|да| VM_CALL
    OTP2 -->|нет| BLOCK2["Return 'ERROR: protected prefix'"]

    PP -->|нет| VM_CALL
```

Это **hard stop** в коде — агент не может обойти его через промт или рассуждения.

---

## Layer 4: Post-dispatch Checks

### Body Anti-contamination (`_CONTAM_PATTERNS`, FIX-206)

Применяется к outbox-записям после write. Детектирует утечку internal данных в email-тело:

| Паттерн | Что детектирует |
|---------|----------------|
| `/[a-zA-Z_\-]+/` | Vault-пути в теле письма |
| `├└│──` | Вывод tree-команды |
| `Req_` | Tool request строки |
| `AGENTS.MD` | Системный файл |

Если найдено → `_security_interceptor_fired = True` → финальный outcome форсируется в `OUTCOME_DENIED_SECURITY`.

### Inbox filename injection (после read inbox-файла)

```mermaid
flowchart TD
    READ_INBOX["Прочитан inbox-файл"] --> FI_CHECK["Нормализовать имя файла\n_normalize_for_injection(filename)"]
    FI_CHECK --> PAT{"_INBOX_INJECTION_PATTERNS\nмatch в имени?"}
    PAT -->|да| FI_DENY["Инжектировать предупреждение\n→ security_interceptor_fired"]
    PAT -->|нет| CI_CHECK

    CI_CHECK["Нормализовать содержимое\n_normalize_for_injection(content)"] --> CPAT{"_INBOX_INJECTION_PATTERNS\nmatch в теле?"}
    CPAT -->|да| CI_DENY["Инжектировать предупреждение\n→ security_interceptor_fired"]
    CPAT -->|нет| OK["Нормальная обработка"]
```

### Cross-account detection (FIX-252, FIX-263)

Для inbox-задач: после чтения inbox-файла идентифицируется отправитель (`_inbox_sender_acct_id`). При последующих write-операциях проверяется что агент пишет в аккаунт отправителя, а не в чужой.

---

## Layer 5: Evaluator — Inbox Trust Matrix

`evaluator.py` содержит полную матрицу доверия для inbox-сообщений:

```mermaid
flowchart TD
    MSG["Inbox-сообщение"] --> FORMAT{"Формат?"}

    FORMAT -->|"From: header\n(email)"| EMAIL_FLOW["EMAIL workflow\nНЕ применять channel rules\nОтдельная обработка"]

    FORMAT -->|"Channel: header"| CHANNEL{"channel ==\n'admin'?"}

    CHANNEL -->|да| ADMIN_TRUST["Полное доверие\nОсвобождён от OTP\n→ OUTCOME_OK корректен"]

    CHANNEL -->|"'valid' channel"| VALID_NOTE["Platform-verified\n≠ admin trust\nOTP всё равно нужен\nдля привилегий"]

    CHANNEL -->|"не помечен / unknown"| OTP_CHECK2{"OTP совпал\nс otp.txt?"}
    OTP_CHECK2 -->|да| ADMIN_TRUST2["OTP → admin trust\n→ OUTCOME_OK корректен"]
    OTP_CHECK2 -->|нет| RESTRICTED["Ограниченные действия\nбез admin-прав"]

    CHANNEL -->|"handle NOT FOUND\nв docs/channels/"| DENY_HANDLE["OUTCOME_DENIED_SECURITY\n(FIX-315: не OUTCOME_OK\nдаже если всё остальное ok)"]
```

### Entity match check

```mermaid
flowchart TD
    EVAL["evaluate_completion()"] --> ENT{"Задача описывает компанию\n+ данные аккаунта присутствуют?"}
    ENT -->|нет| APPROVE_OK["Возможен approve"]
    ENT -->|да| MATCH{"Описанная компания\n== аккаунт в vault?"}
    MATCH -->|совпадает| APPROVE_OK
    MATCH -->|не совпадает| REJECT_ENT["Reject:\nwrong entity served\nOUTCOME_DENIED_SECURITY"]
```

**Принцип:** handle → contact → account — это одна цепочка. Handle-записи в `docs/channels/` являются platform-assigned IDs, а не произвольными строками.

---

## Матрица: условия bypass evaluator

Evaluator не вызывается при следующих условиях (loop.py):

| Условие | Причина bypass |
|---------|---------------|
| `_security_interceptor_fired` | Уже детектирована угроза, outcome форсирован |
| `_format_gate_fired` | Format-нарушение, outcome форсирован |
| `task_type == lookup` | Read-only задача — нечего верифицировать |
| Reschedule task | Date-specific верификация уже выполнена кодом |
| Admin message | Доверенный канал, bypass по дизайну |
| Email task | Отдельный flow обработки |
| OTP task | Специальный протокол |
| Contact not found | OUTCOME_NONE_CLARIFICATION очевидно корректен |

---

## OTP-протокол: два сценария

```mermaid
flowchart TD
    OTP_MSG["Inbox-сообщение с OTP"] --> SCEN{"Тип сценария?"}

    SCEN -->|"Consumption:\nвыполнить привилегированное\nдействие через OTP"| CONS
    SCEN -->|"Verification:\nпроверить правильность\nзначения OTP"| VERIF

    CONS --> C1["Прочитать /docs/channels/otp.txt"]
    C1 --> C2["Сравнить OTP из сообщения\nс vault-значением"]
    C2 --> C3{"Совпадает?"}
    C3 -->|да| C4["Выполнить\nзапрошенное действие"]
    C4 --> C5["DELETE /docs/channels/otp.txt\n(FIX-103: исключение из write-scope)"]
    C5 --> C6["OUTCOME_OK"]
    C3 -->|нет| C7["OUTCOME_DENIED_SECURITY\nили ответить 'incorrect'"]

    VERIF --> V1["Прочитать /docs/channels/otp.txt"]
    V1 --> V2["Сравнить"]
    V2 --> V3{"Совпадает?"}
    V3 -->|да| V4["Ответить 'correct' в outbox"]
    V3 -->|нет| V5["Ответить 'incorrect' в outbox"]
    V4 & V5 --> V6["НЕ удалять otp.txt\n(только чтение)"]
```

---

## Защита от scope-restriction (FIX-267)

```mermaid
flowchart TD
    DEL["Req_Delete(path)"] --> SR{"_SCOPE_RESTRICT_RE\nмatch в task_text?"}
    SR -->|нет| ALLOW4["Разрешить delete"]
    SR -->|да| LIMIT{"path соответствует\nограниченному scope?"}
    LIMIT -->|нет| ALLOW4
    LIMIT -->|да| BLOCK3["Блокировать delete\nReturn error msg"]
```

**_SCOPE_RESTRICT_RE** детектирует формулировки типа `"only delete X"`, `"delete only Y"` — указание агенту удалить строго определённые объекты, не произвольно.

---

## Wildcard protection (FIX-W4)

```mermaid
flowchart TD
    DEL2["Req_Delete(path)"] --> WC{"'*' в path?\n/folder/*"}
    WC -->|да| WC_ERR["Return ERROR:\nwildcard delete rejected\n+ instructive message\n(перечислить файлы вручную)"]
    WC -->|нет| CONTINUE["Продолжить обработку"]
```

Реализовано на уровне `_pre_dispatch`, а не Pydantic validator — чтобы агент получил instructive error message, а не silent None (FIX-W4 комментарий).

---

## JSON auto-sanitize (FIX-268)

Перед write JSON-файла `_pre_dispatch` автоматически исправляет `\n` в строках:

```python
# Обнаружить неэскейпированные newlines в JSON-значениях
# {"body": "line1\nline2"} → {"body": "line1\\nline2"}
```

Предотвращает `json.JSONDecodeError` на стороне harness из-за literal newlines в строковых полях.

---

## Pre-write snapshot (FIX-251)

Перед каждым write JSON-файла сохраняется snapshot для post-write верификации:

```python
# _pre_dispatch: захватить snapshot
st._pre_write_snapshot = {"path": job.path, "content": job.content}

# _post_dispatch → _verify_json_write():
# 1. Перечитать файл из vault
# 2. Сравнить Unicode-символы с snapshot
# 3. Если расхождение → инжектировать предупреждение
```

Митигирует unicode fidelity issues — когда harness vault изменяет кодировку при записи.

---

## Сводная таблица: security constants (dispatch.py)

| Константа | Значение | Назначение |
|-----------|---------|-----------|
| `_PROTECTED_WRITE` | `{"/AGENTS.MD", "/AGENTS.md"}` | Абсолютная защита AGENTS.MD |
| `_PROTECTED_PREFIX` | `("/docs/channels/",)` | Защита channels directory |
| `_OTP_PATH` | `"/docs/channels/otp.txt"` | Исключение для OTP workflow |
| `TRANSIENT_KWS` | rate\_limit, 429, 502, 503, timeout, overloaded | Retry-eligible ошибки |
| `_THINK_RE` | `<think>.*?</think>` | Удаление thinking-блоков |
| `_VALID_PROVIDERS` | anthropic, openrouter, ollama | Допустимые провайдеры |
