from __future__ import annotations

from uuid import uuid4

from harness.contracts import Checkpoint, HarnessErrorCode, HarnessRun, RunState
from harness.core.identity import HarnessResolutionError
from harness.ports import RuntimePort, StatePort


class StateManager:
    """Own canonical RunState/Checkpoint persistence and guarded resume semantics."""

    def __init__(self, state_port: StatePort):
        self.state_port = state_port

    def persist(self, state: RunState) -> RunState:
        self.state_port.save_run_state(state)
        return state

    def checkpoint(
        self,
        state: RunState,
        *,
        validated_step: str,
        resume_instruction: str,
        artifact_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            checkpoint_id=f"CP-{uuid4()}",
            run_id=state.run_id,
            run_state_ref=state.run_state_id,
            validated_step=validated_step,
            resume_instruction=resume_instruction,
            artifact_refs=list(artifact_refs or []),
            evidence_refs=list(evidence_refs or []),
        )
        state.checkpoint_ref = checkpoint.checkpoint_id
        self.state_port.save_checkpoint(checkpoint)
        self.state_port.save_run_state(state)
        return checkpoint

    def resume(self, run: HarnessRun, runtime: RuntimePort, checkpoint_id: str) -> RunState:
        try:
            checkpoint = self.state_port.load_checkpoint(checkpoint_id)
            state = self.state_port.load_run_state(checkpoint.run_state_ref)
        except KeyError as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"checkpoint or run state not found: {exc}",
                checkpoint_id,
            ) from exc

        if checkpoint.run_id != run.run_id or state.run_id != run.run_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                "checkpoint/run mismatch",
                checkpoint_id,
            )
        if state.checkpoint_ref != checkpoint_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                "run state does not point to requested checkpoint",
                checkpoint_id,
            )

        resumed = runtime.resume(run, state)
        self.state_port.save_run_state(resumed)
        return resumed

    def claim_side_effect(self, run_id: str, operation: str, business_key: str) -> str:
        key = f"{run_id}:{operation}:{business_key}"
        if not self.state_port.claim_idempotency(key):
            raise HarnessResolutionError(
                HarnessErrorCode.RETRY_BLOCKED,
                "side effect already claimed; duplicate execution blocked",
                key,
            )
        return key
