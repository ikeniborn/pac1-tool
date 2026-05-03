import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agent.maintenance.health import HealthResult
from agent.maintenance.purge import PurgeResult
from agent.maintenance.distill import DistillResult
from agent.maintenance.candidates import CandidatesReport


def _health_ok() -> HealthResult:
    return HealthResult(exit_code=0, report=["OK: 0 nodes, 0 edges"])


def _health_warn() -> HealthResult:
    return HealthResult(exit_code=1, report=["WARN: 1 orphan edge"], orphan_count=1)


def _health_fail() -> HealthResult:
    return HealthResult(exit_code=2, report=["FAIL: 1/1 contaminated"], contaminated_ids=["bad"])


def _purge_ok() -> PurgeResult:
    return PurgeResult(removed_node_ids=["bad"], applied=True)


class TestPreflight:
    def test_clean_graph_passes(self):
        with patch("agent.preflight.run_health_check", return_value=_health_ok()), \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            pf.run_preflight()  # must not raise

    def test_warn_health_passes_without_purge(self):
        with patch("agent.preflight.run_health_check", return_value=_health_warn()) as mock_health, \
             patch("agent.preflight.run_purge") as mock_purge, \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            pf.run_preflight()
        mock_purge.assert_not_called()

    def test_fail_graph_triggers_auto_purge(self):
        health_seq = [_health_fail(), _health_ok()]
        with patch("agent.preflight.run_health_check", side_effect=health_seq) as mock_health, \
             patch("agent.preflight.run_purge", return_value=_purge_ok()) as mock_purge, \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            pf.run_preflight()  # must not raise

        mock_purge.assert_called_once()
        assert mock_health.call_count == 2

    def test_fail_still_after_purge_exits(self):
        with patch("agent.preflight.run_health_check", return_value=_health_fail()), \
             patch("agent.preflight.run_purge", return_value=_purge_ok()), \
             patch("agent.preflight._check_wiki_pages"), \
             patch("agent.preflight._check_graph_loadable"):
            import agent.preflight as pf
            with pytest.raises(SystemExit) as exc:
                pf.run_preflight()
            assert exc.value.code == 1

    def test_empty_wiki_page_exits(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "email.md").write_text("", encoding="utf-8")

        import agent.preflight as pf
        with pytest.raises(SystemExit) as exc:
            pf._check_wiki_pages(pages_dir=pages)
        assert exc.value.code == 1

    def test_valid_wiki_pages_pass(self, tmp_path):
        pages = tmp_path / "pages"
        pages.mkdir()
        (pages / "email.md").write_text("## Pattern\nsome content", encoding="utf-8")

        import agent.preflight as pf
        pf._check_wiki_pages(pages_dir=pages)  # must not raise

    def test_invalid_graph_json_exits(self, tmp_path):
        gp = tmp_path / "graph.json"
        gp.write_text("{bad json}", encoding="utf-8")

        import agent.preflight as pf
        with pytest.raises(SystemExit) as exc:
            pf._check_graph_loadable(graph_path=gp)
        assert exc.value.code == 1

    def test_missing_graph_is_ok(self, tmp_path):
        import agent.preflight as pf
        pf._check_graph_loadable(graph_path=tmp_path / "missing.json")  # must not raise


class TestPostrun:
    def test_all_steps_run_in_order(self, monkeypatch):
        call_log: list[str] = []
        monkeypatch.delenv("POSTRUN_OPTIMIZE", raising=False)

        with patch("agent.postrun.run_purge", side_effect=lambda **kw: call_log.append("purge") or PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint", side_effect=lambda **kw: call_log.append("wiki_lint")), \
             patch("agent.postrun.run_distill", side_effect=lambda **kw: call_log.append("distill") or DistillResult()), \
             patch("agent.postrun.log_candidates", side_effect=lambda **kw: call_log.append("candidates") or CandidatesReport()), \
             patch("agent.postrun._count_contract_examples", return_value=100), \
             patch("subprocess.run") as mock_sub:
            import agent.postrun as pr
            pr.run_postrun()

        assert "purge" in call_log
        assert "wiki_lint" in call_log
        mock_sub.assert_not_called()  # POSTRUN_OPTIMIZE not set

    def test_optimize_subprocess_called_when_enabled(self, monkeypatch):
        monkeypatch.setenv("POSTRUN_OPTIMIZE", "1")

        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint"), \
             patch("agent.postrun.run_distill"), \
             patch("agent.postrun.log_candidates"), \
             patch("agent.postrun._count_contract_examples", return_value=0), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
            import agent.postrun as pr
            pr.run_postrun()

        mock_run.assert_called_once_with(
            ["python", "scripts/optimize_prompts.py", "--target", "all"],
            check=True, capture_output=True, text=True,
        )

    def test_optimize_not_called_by_default(self, monkeypatch):
        monkeypatch.delenv("POSTRUN_OPTIMIZE", raising=False)
        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint"), \
             patch("agent.postrun.run_distill"), \
             patch("agent.postrun.log_candidates"), \
             patch("agent.postrun._count_contract_examples", return_value=0), \
             patch("subprocess.run") as mock_run:
            import agent.postrun as pr
            pr.run_postrun()
        mock_run.assert_not_called()

    def test_purge_failure_exits(self):
        with patch("agent.postrun.run_purge", side_effect=RuntimeError("disk full")):
            import agent.postrun as pr
            with pytest.raises(SystemExit) as exc:
                pr.run_postrun()
            assert exc.value.code == 1

    def test_wiki_lint_failure_exits(self):
        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint", side_effect=RuntimeError("LLM error")):
            import agent.postrun as pr
            with pytest.raises(SystemExit) as exc:
                pr.run_postrun()
            assert exc.value.code == 1

    def test_candidates_failure_does_not_exit(self, monkeypatch):
        monkeypatch.delenv("POSTRUN_OPTIMIZE", raising=False)
        with patch("agent.postrun.run_purge", return_value=PurgeResult(applied=True)), \
             patch("agent.postrun.run_wiki_lint"), \
             patch("agent.postrun.run_distill"), \
             patch("agent.postrun.log_candidates", side_effect=RuntimeError("oops")), \
             patch("agent.postrun._count_contract_examples", return_value=0):
            import agent.postrun as pr
            pr.run_postrun()  # must NOT raise — candidates failure is non-critical
