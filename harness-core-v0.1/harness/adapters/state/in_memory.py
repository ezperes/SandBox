from __future__ import annotations

from copy import deepcopy
from threading import Lock
from typing import Any

from harness.contracts import Checkpoint, RunState


class InMemoryStateAdapter:
    """Development StatePort with process-local linearizable record claims and CAS."""

    def __init__(self):
        self._states: dict[str, RunState] = {}
        self._checkpoints: dict[str, Checkpoint] = {}
        self._revalidation_records: dict[str, dict[str, Any]] = {}
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

    def save_revalidation_record(self, revalidation_id: str, record: dict[str, Any]) -> None:
        if not revalidation_id.strip():
            raise ValueError("revalidation_id must be explicit")
        with self._lock:
            self._revalidation_records[revalidation_id] = deepcopy(record)

    def load_revalidation_record(self, revalidation_id: str) -> dict[str, Any]:
        with self._lock:
            if revalidation_id not in self._revalidation_records:
                raise KeyError(revalidation_id)
            return deepcopy(self._revalidation_records[revalidation_id])

    def list_revalidation_records(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            records = [deepcopy(record) for record in self._revalidation_records.values() if record.get("run_id") == run_id]
        return sorted(records, key=lambda record: (record.get("created_at") or "", record.get("revalidation_id") or ""))

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

    def compare_and_swap_idempotency_record(
        self,
        key: str,
        expected: dict[str, Any],
        replacement: dict[str, Any],
    ) -> bool:
        """Atomically replace one record iff its entire persisted value is unchanged."""
        if not key.strip():
            raise ValueError("idempotency key must be explicit")
        with self._lock:
            current = self._idempotency_records.get(key)
            if current is None or current != expected:
                return False
            self._idempotency_records[key] = deepcopy(replacement)
            return True
