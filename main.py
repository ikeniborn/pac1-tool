import datetime
import json
import os
import sys
import re
import textwrap
import threading
import time
import zoneinfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_task_local = threading.local()
_run_dir: "Path | None" = None


def _setup_log_tee() -> None:
    """Tee stdout to logs/{ts}_{model}.log. ANSI codes are stripped in file."""
    _env_path = Path(__file__).parent / ".env"
    _dotenv: dict[str, str] = {}
    try:
        for _line in _env_path.read_text().splitlines():
            _s = _line.strip()
            if _s and not _s.startswith("#") and "=" in _s:
                _k, _, _v = _s.partition("=")
                _dotenv[_k.strip()] = _v.strip()
    except Exception:
        pass

    model = os.getenv("MODEL") or _dotenv.get("MODEL") or "unknown"
    log_level = (os.getenv("LOG_LEVEL") or _dotenv.get("LOG_LEVEL") or "INFO").upper()

    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    _tz_name = os.environ.get("TZ", "")
    try:
        _tz = zoneinfo.ZoneInfo(_tz_name) if _tz_name else None
    except Exception:
        _tz = None
    _now = datetime.datetime.now(tz=_tz) if _tz else datetime.datetime.now()
    _safe = model.replace("/", "-").replace(":", "-")
    run_name = f"{_now.strftime('%Y%m%d_%H%M%S')}_{_safe}"
    run_path = logs_dir / run_name
    run_path.mkdir(exist_ok=True)
    global _run_dir
    _run_dir = run_path

    _fh = open(run_path / "main.log", "w", buffering=1, encoding="utf-8")
    _ansi = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")
    _orig = sys.stdout

    class _Tee:
        def write(self, data: str) -> None:
            prefix = getattr(_task_local, "task_id", None)
            task_fh = getattr(_task_local, "log_fh", None)
            clean = _ansi.sub("", data)
            if prefix and data and data != "\n":
                _orig.write(f"[{prefix}] {data}")
            else:
                _orig.write(data)
            if task_fh is not None:
                task_fh.write(clean)
            else:
                _fh.write(clean)

        def flush(self) -> None:
            _orig.flush()
            _fh.flush()
            task_fh = getattr(_task_local, "log_fh", None)
            if task_fh is not None:
                task_fh.flush()

        def isatty(self) -> bool:
            return _orig.isatty()

        @property
        def encoding(self) -> str:
            return _orig.encoding

    sys.stdout = _Tee()
    print(f"[LOG] {run_path}/  (LOG_LEVEL={log_level})")


_setup_log_tee()

from agent.tracer import init_tracer as _init_tracer, set_task_id as _set_task_id
if _run_dir is not None:
    _init_tracer(str(_run_dir))

from bitgn.harness_connect import HarnessServiceClientSync
from bitgn.harness_pb2 import (
    EndTrialRequest, EvalPolicy, GetBenchmarkRequest,
    StartRunRequest, StartTrialRequest,
    StatusRequest, SubmitRunRequest,
)
from connectrpc.errors import ConnectError

from agent import run_agent

BITGN_URL = os.getenv("BENCHMARK_HOST") or "https://api.bitgn.com"
BENCHMARK_ID = os.getenv("BENCHMARK_ID") or "bitgn/pac1-dev"
BITGN_API_KEY = os.getenv("BITGN_API_KEY") or ""
_base_run_name = os.getenv("BITGN_RUN_NAME") or ""
BITGN_RUN_NAME = f"{_base_run_name}-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}" if _base_run_name else ""
PARALLEL_TASKS = max(1, int(os.getenv("PARALLEL_TASKS", "1")))

_MODELS_JSON = Path(__file__).parent / "models.json"
_raw = json.loads(_MODELS_JSON.read_text())
_profiles: dict[str, dict] = _raw.get("_profiles", {})
MODEL_CONFIGS: dict[str, dict] = {k: v for k, v in _raw.items() if not k.startswith("_")}
for _cfg in MODEL_CONFIGS.values():
    for _fname in ("ollama_options", "ollama_options_classifier", "ollama_options_evaluator"):
        if isinstance(_cfg.get(_fname), str):
            _cfg[_fname] = _profiles.get(_cfg[_fname], {})

def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise ValueError(f"Env var {name} is required but not set.")
    return v

_model_default = _require_env("MODEL")
print(f"[MODEL] default={_model_default}")

CLI_RED = "\x1B[31m"
CLI_GREEN = "\x1B[32m"
CLI_CLR = "\x1B[0m"
CLI_BLUE = "\x1B[34m"


def _run_single_task(trial_id: str, task_filter: list) -> tuple:
    """Execute one benchmark trial."""
    client = HarnessServiceClientSync(BITGN_URL)
    trial = client.start_trial(StartTrialRequest(trial_id=trial_id))
    task_id = trial.task_id

    if task_filter and task_id not in task_filter:
        return (task_id, -1, [], 0.0, {})

    _task_local.task_id = task_id
    _set_task_id(task_id)
    assert _run_dir is not None
    _task_local.log_fh = open(_run_dir / f"{task_id}.log", "w", buffering=1, encoding="utf-8")
    try:
        task_start = time.time()
        print(f"\n{'=' * 30} Starting task: {task_id} {'=' * 30}")
        print(f"{CLI_BLUE}{trial.instruction}{CLI_CLR}\n{'-' * 80}")
        token_stats: dict = {"input_tokens": 0, "output_tokens": 0}
        try:
            token_stats = run_agent({}, trial.harness_url, trial.instruction, task_id=task_id)
        except Exception as exc:
            print(exc)
        task_elapsed = time.time() - task_start
        result = client.end_trial(EndTrialRequest(trial_id=trial.trial_id))
        score = result.score
        detail = list(result.score_detail)
        _score_f = float(score)
        in_t = token_stats.get("input_tokens", 0)
        out_t = token_stats.get("output_tokens", 0)
        t_type = token_stats.get("task_type", "—")
        m_short = (token_stats.get("model_used") or "—").split("/")[-1]
        style = CLI_GREEN if score == 1 else CLI_RED
        detail_str = "\n" + textwrap.indent("\n".join(detail), "  ") if detail else ""
        print(
            f"{style}[{task_id}] Score: {score:0.2f}"
            f" | {task_elapsed:.1f}s"
            f" | in {in_t:,} / out {out_t:,} tok"
            f" | {t_type} | {m_short}"
            f"{detail_str}{CLI_CLR}"
        )
        return (task_id, _score_f, detail, task_elapsed, token_stats)
    finally:
        fh = _task_local.log_fh
        _task_local.log_fh = None
        if fh:
            fh.flush()
            fh.close()


def _print_table_header() -> None:
    print(f"\n{'=' * 80}")
    print(f"{'ИТОГОВАЯ СТАТИСТИКА':^80}")
    print('=' * 80)
    print(f"{'Задание':<10} {'Оценка':>7} {'Время':>8}  {'Вход(tok)':>10} {'Выход(tok)':>10}  {'Тип':<11} {'Модель':<30}  Проблемы")
    print("-" * 80)


def _print_table_row(task_id: str, score: float, detail: list, elapsed: float, ts: dict) -> None:
    issues = "; ".join(detail) if score < 1.0 else "—"
    in_t = ts.get("input_tokens", 0)
    out_t = ts.get("output_tokens", 0)
    m = ts.get("model_used", "—")
    m_short = m.split("/")[-1] if "/" in m else m
    t_type = ts.get("task_type", "—")
    print(f"{task_id:<10} {score:>7.2f} {elapsed:>7.1f}s  {in_t:>10,} {out_t:>10,}  {t_type:<11} {m_short:<30}  {issues}")


def _write_summary(scores: list, run_start: float) -> None:
    n = len(scores)
    total = sum(s for _, s, *_ in scores) / n * 100.0
    total_elapsed = time.time() - run_start
    total_in = sum(ts.get("input_tokens", 0) for *_, ts in scores)
    total_out = sum(ts.get("output_tokens", 0) for *_, ts in scores)
    print('=' * 80)
    print(f"{'ИТОГО':<10} {total:>6.2f}% {total_elapsed:>7.1f}s  {total_in:>10,} {total_out:>10,}")
    print('=' * 80)


def main() -> None:
    task_filter = [t for arg in sys.argv[1:] for t in arg.split(",") if t]

    scores = []
    scores_lock = threading.Lock()
    run_start = time.time()
    try:
        client = HarnessServiceClientSync(BITGN_URL)
        print("Connecting to BitGN", client.status(StatusRequest()))
        res = client.get_benchmark(GetBenchmarkRequest(benchmark_id=BENCHMARK_ID))
        print(
            f"{EvalPolicy.Name(res.policy)} benchmark: {res.benchmark_id} "
            f"with {len(res.tasks)} tasks.\n{CLI_GREEN}{res.description}{CLI_CLR}"
        )

        run = client.start_run(StartRunRequest(
            name=BITGN_RUN_NAME,
            benchmark_id=BENCHMARK_ID,
            api_key=BITGN_API_KEY,
        ))
        print(f"Run started: {run.run_id} ({len(run.trial_ids)} trials)")

        try:
            _print_table_header()
            with ThreadPoolExecutor(max_workers=PARALLEL_TASKS) as pool:
                futures = {
                    pool.submit(_run_single_task, tid, task_filter): tid
                    for tid in run.trial_ids
                }
                for fut in as_completed(futures):
                    try:
                        task_id, score, detail, task_elapsed, token_stats = fut.result()
                    except Exception as exc:
                        failed_tid = futures[fut]
                        print(f"{CLI_RED}[{failed_tid}] Task error: {exc}{CLI_CLR}")
                        continue
                    if score >= 0:
                        with scores_lock:
                            scores.append((task_id, score, detail, task_elapsed, token_stats))
                        _print_table_row(task_id, score, detail, task_elapsed, token_stats)
        finally:
            if scores:
                _write_summary(scores, run_start)
            client.submit_run(SubmitRunRequest(run_id=run.run_id, force=True))
            print(f"Run submitted: {run.run_id}")

    except ConnectError as exc:
        print(f"{exc.code}: {exc.message}")
    except KeyboardInterrupt:
        print(f"{CLI_RED}Interrupted{CLI_CLR}")


if __name__ == "__main__":
    try:
        main()
    finally:
        from agent.tracer import close_tracer as _close_tracer
        _close_tracer()
