from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any

from harness.contracts import Checkpoint, RunState


class InMemoryStateAdapter:
    """Development StatePort with atomic idempotency ledger records."""

    def __init__(self):
        self._states: dict[str, RunState] = {}
        self._checkpoints: dict[str, Checkpoint] = {}
        self._idempotency_records: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def save_run_state(self, state: RunState) -> None:
        with self._lock:
            self._states[state.run_state_id] = state.model_copy(deep=True)

    def load_run_state(self, run_state_id: str) -> RunState:
        with self._lock:
            if run_state_id not in self._states:
                raise KeyError(run_state_id)
            return self._states[run_state_id].model_copy(deep=True)

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        with self._lock:
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint.model_copy(deep=True)

    def load_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        with self._lock:
            if checkpoint_id not in self._checkpoints:
                raise KeyError(checkpoint_id)
            return self._checkpoints[checkpoint_id].model_copy(deep=True)

    def create_idempotency_record(self, key: str, record: dict[str, Any]) -> bool:
        if not key.strip():
            raise ValueError("idempotency key must be explicit")
        with self._lock:
            if key in self._idempotency_records:
                return False
            self._idempotency_records[key] = deepcopy(record)
            return True

    def load_idempotency_record(self, key: str) -> dict[str, Any]:
        with self._lock:
            if key not in self._idempotency_records:
                raise KeyError(key)
            return deepcopy(self._idempotency_records[key])

    def update_idempotency_record(self, key: str, record: dict[str, Any]) -> None:
        with self._lock:
            if key not in self._idempotency_records:
                raise KeyError(key)
            self._idempotency_records[key] = deepcopy(record)
