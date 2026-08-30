# P0-2-RUNTIME-TERMINAL-TRACE

BASE_SHA: `5a18ce034987b14617442fc48194bd9dec2f87f2`
BRANCH: `worker/p0-2-runtime-terminal-trace`

## Scope

Localized Core-owned trace primitive only. This worker does **not** edit `StateManager.resume()`, Tool trace, RevisionGuard, authority/binding architecture, PR #17, or the `harness-core-v0.1` branch ref.

## API

```python
from harness.core.freshness.audit import finalize_runtime_resume_success

completed_audit = finalize_runtime_resume_success(released_audit)
```

Accepted predecessor:

```text
boundary = RuntimePort.resume
status   = RELEASED
outcome  = REVALIDATED_AND_GUARDED
```

Produced terminal state:

```text
status   = RELEASED
outcome  = COMPLETED
```

Historical events are appended, not replaced:

```text
PENDING
→ RELEASED / REVALIDATED_AND_GUARDED
→ RELEASED / COMPLETED
```

The helper is pure and performs no persistence. It is fail-closed for wrong boundary, wrong predecessor, FAILED/BLOCKED history, and inconsistent pre-existing COMPLETED state. Repeated terminalization of an already valid COMPLETED record is idempotent and appends no duplicate event.

## Exact integration wiring point

Current frozen `StateManager.resume()` success tail ends conceptually as:

```python
released["metadata"]["revision_guard_final"] = guard_final
self.state_port.save_revalidation_record(audit["revalidation_id"], released)
self.state_port.save_run_state(resumed)
return resumed
```

The Integrator should wire **after canonical RunState persistence succeeds**, and before return:

```python
released["metadata"]["revision_guard_final"] = guard_final
self.state_port.save_revalidation_record(audit["revalidation_id"], released)
self.state_port.save_run_state(resumed)
completed_audit = finalize_runtime_resume_success(released)
self.state_port.save_revalidation_record(audit["revalidation_id"], completed_audit)
return resumed
```

This ordering is intentional:

1. `RuntimePort.resume()` has returned.
2. Core firewall/validation has accepted the runtime result.
3. canonical `RunState` persistence has succeeded.
4. only then is the terminal `COMPLETED` trace constructed and persisted.

If runtime execution, firewall/validation, or canonical persistence raises before that point, this API is not called and no false `COMPLETED` event is produced.

## Integration regression to activate with wiring

The existing independent Red Team probe should remain unchanged and become green after the Integrator wiring. Add/activate an integration assertion equivalent to:

```python
resumed = manager.resume(run, SuccessfulRuntime(), cp.checkpoint_id, freshness_gate=gate)
record = port.load_revalidation_record(next(ref for ref in resumed.decision_refs if ref.startswith("RV-")))
assert record["outcome"] == "COMPLETED"
assert [event.get("outcome") for event in record["events"]] == [
    None,
    "REVALIDATED_AND_GUARDED",
    "COMPLETED",
]
```

Do not xfail, skip, weaken, or rewrite the Red Team assertion.

## Failed attempt → cause → correct solution

- failed attempt: re-export the helper from `harness.core.freshness.__init__`.
- cause: connector safety layer blocked that write; no repository change occurred from the blocked call.
- correct solution: keep the public integration import explicit from `harness.core.freshness.audit`, which is already the owning module and requires no additional production surface.
