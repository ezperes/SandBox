# CORE-FRESHNESS-GATE — P0 correction plan

Historical re-audit base: `61cd47670909469d0c684396d73b4572a1e4463a`.
Last production/test correction commit: `865255b37c683f3fd1f13a8e06ba56936d2ea95d`.
Frozen branch HEAD for independent re-audit: `9a8fac4237bf0b70ff3946bef35d341df3f5022b`.

## Implemented correction cycle

1. T10: `StateManager.resume()` rejects missing and duck-typed freshness; only the concrete Core `ResumeFreshnessGate` may release `RuntimePort.resume()`.
2. T11: every side effect requires the concrete Core `AuthorityFreshnessGate`; absence/fake/stale freshness fails closed before authority, idempotency or ToolPort.
3. Authority semantics: omitted `allowed_scopes` remains unconstrained-by-whitelist, while explicit `allowed_scopes=[]` is a real empty constraint and authorizes nothing.
4. T12/TRACE: boundary audit is persisted before verification and finalized as `RELEASED`, `BLOCKED` or `FAILED`; DENY/ESCALATE/freshness/idempotency/tool failures are traceable.
5. Previous authority context, task context, bootstrap refs, authority revision lineage and previous identity revision metadata are persisted for reconstruction.
6. `RuntimePort.resume()` cannot mint institutional decision refs: returned `decision_refs` are replaced by the Core-owned pre-boundary list.
7. T07: technical-only revision drift has an executable selective-rebuild regression; identity revision drift is detected even when authority refs remain unchanged.
8. `StatePort` exposes run-scoped revalidation trace retrieval and `tests/test_revalidation_audit.py` exists with blocked/released reconstruction regressions.
9. Side-effect `ESCALATE` and ToolPort failure paths have explicit regressions; ToolPort failure leaves idempotency state `UNKNOWN` requiring reconciliation.

## Validation on frozen HEAD

GitHub Actions `Harness Core CI` run #179 on PR merge tree for HEAD `9a8fac4237bf0b70ff3946bef35d341df3f5022b`:
- CPython 3.11.16;
- Pydantic 2.13.5;
- LangGraph 1.2.11;
- `68 passed`;
- `17 schemas` exported;
- schema drift clean.

## Integration gate

Corrections implemented does not mean architectural promotion. PR #17 remains draft and must not be merged until independent defensive verification and re-audit of T07/T10/T11/T12 + TRACE-01 are executed against exactly `9a8fac4237bf0b70ff3946bef35d341df3f5022b` and no blocking contradiction remains.

Residual question explicitly delegated to independent verification: TOCTOU windows where canonical sources change after freshness/re-resolution but before `ToolPort.invoke()` or `RuntimePort.resume()`.
