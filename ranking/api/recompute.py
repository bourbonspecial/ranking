"""Debounced background recompute: many comparisons in quick succession
trigger one fit, `debounce` seconds after the last write."""
from __future__ import annotations

import threading

from sqlalchemy.orm import sessionmaker

from .. import repo


class Recomputer:
    def __init__(self, session_factory: sessionmaker, debounce: float):
        self.session_factory = session_factory
        self.debounce = debounce
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def schedule(self) -> None:
        if self.debounce <= 0:
            self.run_now()
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self.run_now)
            self._timer.daemon = True
            self._timer.start()

    def run_now(self) -> None:
        with self._lock:
            self._timer = None
        with self.session_factory() as s:
            repo.recompute_all(s)

    def shutdown(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
