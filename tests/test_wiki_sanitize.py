"""FIX-328: verify negative-boilerplate sanitizer on synthesized wiki pages."""
from agent.wiki import _sanitize_synthesized_page


def test_strips_halt_and_request_clarification():
    src = (
        "## Lookup\n\n"
        "Step 1: find the contact.\n"
        "- Solution: Halt and request clarification before proceeding.\n"
        "Step 2: read the file.\n"
    )
    out = _sanitize_synthesized_page(src)
    assert "Halt and request clarification" not in out
    assert "Step 1: find the contact." in out
    assert "Step 2: read the file." in out


def test_strips_no_outcome_ok_signal():
    src = (
        "Observed sequences (candidate only):\n"
        "- **No `OUTCOME_OK` signal yet**: Treat as unverified.\n"
        "- Valid pattern: search → read.\n"
    )
    out = _sanitize_synthesized_page(src)
    assert "No `OUTCOME_OK` signal yet" not in out
    assert "Valid pattern" in out


def test_strips_no_outcome_ok_recorded():
    src = "- **No OUTCOME_OK recorded** — data unverified.\nUseful content stays.\n"
    out = _sanitize_synthesized_page(src)
    assert "No OUTCOME_OK" not in out
    assert "Useful content stays." in out


def test_strips_stop_for_clarification_instead_of_guessing():
    src = "If multiple contacts could match, stop for clarification instead of guessing.\nKeep this line.\n"
    out = _sanitize_synthesized_page(src)
    assert "stop for clarification instead of guessing" not in out
    assert "Keep this line." in out


def test_strips_candidate_patterns_until():
    src = "Treat all step sequences as *candidate patterns* until a successful end-to-end run.\nGood line.\n"
    out = _sanitize_synthesized_page(src)
    assert "candidate patterns" not in out
    assert "Good line." in out


def test_no_op_on_clean_content():
    src = "## Lookup\n\nStep 1: search.\nStep 2: read.\n"
    out = _sanitize_synthesized_page(src)
    # content preserved (may have trailing newline normalization)
    assert "Step 1: search." in out
    assert "Step 2: read." in out


def test_empty_input():
    assert _sanitize_synthesized_page("") == ""
    assert _sanitize_synthesized_page(None) is None  # type: ignore[arg-type]


def test_collapses_excess_blank_lines():
    src = "A\n\n\n\n\nB\n"
    out = _sanitize_synthesized_page(src)
    assert "\n\n\n" not in out
    assert "A" in out and "B" in out
