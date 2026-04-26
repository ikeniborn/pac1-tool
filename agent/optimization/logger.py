"""Append-only JSONL logger for optimization runs."""
from __future__ import annotations

import json
import threading
import traceback as _traceback
from datetime import datetime, timezone
from pathlib import Path


class OptimizeLogger:
    """Append-only JSONL logger for optimization runs. Fail-open.

    Writes two streams:
      - `path`        — all events (run_start, lm_call, metric_eval, run_end)
      - `error_path`  — structured errors only (one JSON per exception)
    """

    def __init__(self, path: Path, error_path: Path | None = None) -> None:
        self._path = path
        self._error_path = error_path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._fh = path.open("a", encoding="utf-8", buffering=1)
        except OSError:
            self._fh = None
        self._err_fh = None
        if error_path is not None:
            try:
                self._err_fh = error_path.open("a", encoding="utf-8", buffering=1)
            except OSError:
                self._err_fh = None

    def emit(self, event: str, data: dict) -> None:
        if self._fh is None:
            return
        record = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **data,
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with self._lock:
                self._fh.write(line)
        except Exception:
            pass

    def emit_error(self, target: str, exc: BaseException, extra: dict | None = None) -> None:
        """Write a structured error record to the dedicated error log.

        Captures type, message, and traceback — safe to call from except-blocks.
        Also mirrors a compact `error` event into the main run log.
        """
        record = {
            "event": "error",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target": target,
            "exc_type": type(exc).__name__,
            "exc_message": str(exc)[:2000],
            "traceback": _traceback.format_exc()[:8000],
            **(extra or {}),
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        try:
            with self._lock:
                if self._err_fh is not None:
                    self._err_fh.write(line)
                if self._fh is not None:
                    compact = {
                        "event": "error",
                        "timestamp": record["timestamp"],
                        "target": target,
                        "exc_type": record["exc_type"],
                        "exc_message": record["exc_message"][:500],
                    }
                    self._fh.write(json.dumps(compact, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def close(self) -> None:
        for fh in (self._fh, self._err_fh):
            try:
                if fh:
                    fh.close()
            except Exception:
                pass
