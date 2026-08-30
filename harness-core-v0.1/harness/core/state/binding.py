from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import Checkpoint, HarnessErrorCode, HarnessRun, RunState
from harness.core.errors import HarnessResolutionError


@dataclass(frozen=True, slots=True)
class RunStateBinding:
    """Immutable proof that run, state and checkpoint name one execution."""

    run_id: str
    tarefa_trabalho_id: str
    agent_id: str
    run_state_id: str
    checkpoint_id: str


class RunStateBindingGuard:
    """Core-owned fail-closed validation for resume ownership.

    This guard performs no persistence and mutates none of its inputs. It can be
    called by StateManager/ResumeFreshnessGate before any resume boundary is
    released.
    """

    @staticmethod
    def _required(value: str | None, field_name: str, source_ref: str | None = None) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"required binding reference is missing: {field_name}",
                source_ref,
            )
        return normalized

    @classmethod
    def ensure_bound(
        cls,
        run: HarnessRun,
        state: RunState,
        checkpoint: Checkpoint,
    ) -> RunStateBinding:
        run_id = cls._required(run.run_id, "HarnessRun.run_id")
        task_id = cls._required(
            run.tarefa_trabalho_id,
            "HarnessRun.tarefa_trabalho_id",
            run_id,
        )
        agent_id = cls._required(run.agent_id, "HarnessRun.agent_id", run_id)
        run_state_ref = cls._required(
            run.run_state_ref,
            "HarnessRun.run_state_ref",
            run_id,
        )

        state_id = cls._required(
            state.run_state_id,
            "RunState.run_state_id",
            run_state_ref,
        )
        state_run_id = cls._required(
            state.run_id,
            "RunState.run_id",
            state_id,
        )
        state_task_id = cls._required(
            state.tarefa_trabalho_id,
            "RunState.tarefa_trabalho_id",
            state_id,
        )
        state_checkpoint_ref = cls._required(
            state.checkpoint_ref,
            "RunState.checkpoint_ref",
            state_id,
        )

        checkpoint_id = cls._required(
            checkpoint.checkpoint_id,
            "Checkpoint.checkpoint_id",
            state_checkpoint_ref,
        )
        checkpoint_run_id = cls._required(
            checkpoint.run_id,
            "Checkpoint.run_id",
            checkpoint_id,
        )
        checkpoint_state_ref = cls._required(
            checkpoint.run_state_ref,
            "Checkpoint.run_state_ref",
            checkpoint_id,
        )

        if state_run_id != run_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"RunState.run_id {state_run_id!r} does not match HarnessRun.run_id {run_id!r}",
                state_id,
            )
        if checkpoint_run_id != run_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"Checkpoint.run_id {checkpoint_run_id!r} does not match HarnessRun.run_id {run_id!r}",
                checkpoint_id,
            )
        if state_task_id != task_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                (
                    f"RunState.tarefa_trabalho_id {state_task_id!r} does not match "
                    f"HarnessRun.tarefa_trabalho_id {task_id!r}"
                ),
                state_id,
            )
        if state_id != run_state_ref:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"RunState.run_state_id {state_id!r} does not match HarnessRun.run_state_ref {run_state_ref!r}",
                state_id,
            )
        if checkpoint_state_ref != state_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                (
                    f"Checkpoint.run_state_ref {checkpoint_state_ref!r} does not match "
                    f"RunState.run_state_id {state_id!r}"
                ),
                checkpoint_id,
            )
        if state_checkpoint_ref != checkpoint_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                (
                    f"RunState.checkpoint_ref {state_checkpoint_ref!r} does not match "
                    f"Checkpoint.checkpoint_id {checkpoint_id!r}"
                ),
                checkpoint_id,
            )

        return RunStateBinding(
            run_id=run_id,
            tarefa_trabalho_id=task_id,
            agent_id=agent_id,
            run_state_id=state_id,
            checkpoint_id=checkpoint_id,
        )


__all__ = ["RunStateBinding", "RunStateBindingGuard"]
