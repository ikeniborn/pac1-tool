"""Tests for classify_task() regex fast-path routing (FIX-325).

classify_task() is the deterministic regex layer. Only types whose registry
entry in data/task_types.json has fast_path.confidence == "high" can be
returned here — currently 'preject', 'email', 'temporal'. Everything else
falls through to 'default' and is later resolved by classify_task_llm().
"""


def _classify():
    from agent.classifier import classify_task
    return classify_task


def test_preject_fast_path():
    c = _classify()
    assert c("create a calendar invite for tomorrow 3pm") == "preject"
    assert c("sync to salesforce") == "preject"
    assert c("upload to https://example.com/webhook") == "preject"
    assert c("send to https://webhook.site/xyz") == "preject"


def test_email_fast_path():
    c = _classify()
    assert c("send an email to John about the meeting") == "email"
    assert c("compose email to recipient with subject") == "email"
    assert c("email John a brief update") == "email"


def test_temporal_fast_path():
    c = _classify()
    assert c("What date is in 1 week? Answer YYYY-MM-DD") == "temporal"
    assert c("what day is in 10 days?") == "temporal"
    assert c("what day is in 3 weeks?") == "temporal"
    assert c("3 weeks from today") == "temporal"
    assert c("In 5 days from now") == "temporal"


def test_temporal_fast_path_avoids_false_positives():
    c = _classify()
    # Vault-lookup with relative date → NOT temporal (has a verb on vault data).
    assert c("which article did i capture 47 days ago") == "default"
    assert c("Which article did I capture 44 days ago?") == "default"
    # CRM reschedule mentions "two weeks" but without "from today/now" form.
    assert c("Nordlicht Health asked to reconnect in two weeks. Reschedule") == "default"
    assert c("reschedule the follow-up by 2 weeks") == "default"


def test_non_fastpath_returns_default():
    """Types without a high-confidence fast_path fall through to 'default'."""
    c = _classify()
    # inbox/queue/lookup/distill/crm have no regex fast_path — resolved by LLM.
    assert c("check inbox for new messages") == "default"
    assert c("process the inbox") == "default"
    assert c("what is the email of David Linke") == "default"
    assert c("summarize the thread and write a card") == "default"
    assert c("how many blacklisted contacts are there") == "default"


def test_bulk_and_multipath_default():
    c = _classify()
    assert c("delete all threads from the vault") == "default"
    assert c("compare /a/x.md /b/y.md /c/z.md") == "default"


def test_task_constants_reexported():
    """Backwards-compat: TASK_* constants still importable from agent.classifier."""
    from agent import classifier
    assert classifier.TASK_DEFAULT == "default"
    assert classifier.TASK_EMAIL == "email"
    assert classifier.TASK_PREJECT == "preject"
