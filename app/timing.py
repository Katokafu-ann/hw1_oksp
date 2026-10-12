from __future__ import annotations
import threading
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine


_lock = threading.Lock()
_enabled = False
_db_time_ms = 0.0
_db_query_count = 0
_query_starts: dict[int, float] = {}


def reset_timing() -> None:
    global _enabled, _db_time_ms, _db_query_count, _query_starts
    with _lock:
        _enabled = True
        _db_time_ms = 0.0
        _db_query_count = 0
        _query_starts = {}


def disable_timing() -> None:
    global _enabled
    with _lock:
        _enabled = False


def snapshot() -> tuple[float, int]:
    with _lock:
        return _db_time_ms, _db_query_count


def bind_stats(_stats=None) -> None:
    """Совместимость с db.py. Счётчики сбрасывает только middleware."""
    global _enabled
    with _lock:
        _enabled = True


def unbind_stats(_stats=None) -> None:
    """Совместимость с db.py. Не отключает учёт — это делает middleware."""
    pass


def register_timing_listeners(engine: Engine) -> None:
    if getattr(engine, "_anna_timing_registered", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, _cursor, _statement, _parameters, _context, _executemany):
        with _lock:
            if _enabled:
                _query_starts[id(conn)] = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, _cursor, _statement, _parameters, _context, _executemany):
        global _db_time_ms, _db_query_count
        with _lock:
            if not _enabled:
                return
            started = _query_starts.pop(id(conn), None)
            if started is None:
                return
            _db_time_ms += (time.perf_counter() - started) * 1000
            _db_query_count += 1

    engine._anna_timing_registered = True  # type: ignore[attr-defined]