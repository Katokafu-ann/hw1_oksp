"""Учёт времени SQL для раздела 2.6 отчёта ДЗ1 (не оптимизация)."""

from __future__ import annotations

import time
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.engine import Engine


timing_enabled: ContextVar[bool] = ContextVar("timing_enabled", default=False)
db_time_ms: ContextVar[float] = ContextVar("db_time_ms", default=0.0)
db_query_count: ContextVar[int] = ContextVar("db_query_count", default=0)


def reset_timing() -> None:
    timing_enabled.set(True)
    db_time_ms.set(0.0)
    db_query_count.set(0)


def disable_timing() -> None:
    timing_enabled.set(False)


def snapshot() -> tuple[float, int]:
    return db_time_ms.get(), db_query_count.get()


def register_timing_listeners(engine: Engine) -> None:
    if getattr(engine, "_anna_timing_registered", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, _cursor, _statement, _parameters, _context, _executemany):
        if timing_enabled.get():
            conn.info["anna_query_start"] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, _cursor, _statement, _parameters, _context, _executemany):
        if not timing_enabled.get():
            return
        started = conn.info.pop("anna_query_start", None)
        if started is None:
            return
        elapsed = (time.perf_counter() - started) * 1000
        db_time_ms.set(db_time_ms.get() + elapsed)
        db_query_count.set(db_query_count.get() + 1)

    engine._anna_timing_registered = True  # type: ignore[attr-defined]
