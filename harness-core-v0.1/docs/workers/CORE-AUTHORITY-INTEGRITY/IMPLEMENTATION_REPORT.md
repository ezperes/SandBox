# GT P1-B — CORE-AUTHORITY-INTEGRITY — Implementation Report

## Scope

- Work base: `530386c35e21066b11ffb5491a52418faae67269`
- Branch: `worker/p1-authority-integrity`
- Parent branch: `worker/core-freshness-gate` (left unchanged)
- Historical audit SHA `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff` used only as evidence.
- No merge and no E2E release.

## Implemented invariant

Before freshness, authority decision, idempotency reservation, or ToolPort invocation, ToolGateway now requires a Core-owned `HarnessRun` and verifies:

1. provided `HarnessRun.run_id == run_id`;
2. `AuthorityContext.run_id == run_id`;
3. `AuthorityContext.agent_id == HarnessRun.agent_id`.

Binding failures are persisted as `BLOCKED` with institutional `ESCALATE` semantics and identifiable outcomes (`RUN_BINDING_UNRESOLVED`, `RUN_BINDING_MISMATCH`, `AUTHORITY_RUN_MISMATCH`, `AUTHORITY_AGENT_MISMATCH`). No ledger reservation or ToolPort call occurs on these paths.

## Identity freshness

No canonical contract/port extension was required. `AgentIdentity` already carries `source_ref` and `source_revision_ref`.

`AuthorityFreshnessGate` now receives the resolved `AgentIdentity` baseline and validates, fail-closed, the canonical identity `revision_ref` and agent identity before checking tactical, technical, and normative authority revisions. Identity drift is persisted through the existing `FRESHNESS_REJECTED` audit path.

## Preserved authority semantics

The authority resolver was not changed. Existing semantics remain:

- tactical ∩ technical ∩ normative allow-list intersection;
- absent `allowed_scopes` differs from explicit `allowed_scopes=[]`;
- explicit empty allow-list authorizes nothing;
- forbidden scope takes precedence;
- valid authority does not imply sufficient competence.

## Failed attempt → cause → correct solution

### Attempt 1 — CI #193

Result: `5 failed, 69 passed`.

Two causes were exposed:

1. Identity drift test changed the canonical top-level `revision_ref`, but the first gate implementation relied on `IdentityResolver.source_revision_ref`. The resolver intentionally preserves an already materialized `identity.source_revision_ref`, so a stale embedded value could mask the new top-level canonical revision.
2. Four existing audit tests still used the old ToolGateway/freshness constructor interface.

### Correct solution

1. The identity freshness gate now reads the canonical source record directly and compares its top-level `revision_ref` with the captured `AgentIdentity.source_revision_ref`; `IdentityResolver` remains responsible for validating identity payload/source ownership and agent identity.
2. Existing audit call sites were migrated to provide the Core-owned `HarnessRun` and identity baseline.

### Validation after correction — CI #197

- `74 passed`;
- `17 schemas` exported;
- schema drift clean.

## Contracts and protected set

No Pydantic institutional contract was changed. No StatePort/ToolPort protocol was expanded. `StateManager.resume`, TOCTOU mechanisms, LangGraph, ModelPort, A4/E2E were not changed.

The only API delta is the Core ToolGateway call boundary requiring the already-existing `HarnessRun` object, plus `AuthorityFreshnessGate` requiring the already-existing resolved `AgentIdentity` baseline.

## Integration status

This GT closes the cross-run/cross-agent authority-integrity blocker and adds identity revision checking at the side-effect boundary. It does not claim T11/T12 proven and does not address the separate TOCTOU gate.
