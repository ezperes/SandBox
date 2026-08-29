# RECOMMENDATIONS — CORE-FRESHNESS-GATE

1. Use one Core-owned freshness/revalidation primitive for both T11 and later T10.
2. Close T11 first at the side-effect boundary.
3. Preserve historical revision/snapshot evidence while checking current source revisions.
4. Rebuild only affected chains/context when safe; otherwise `ESCALATE`/fail closed.
5. Keep LangGraph, providers, tool adapters and native checkpoints outside institutional authority.
6. After T11/T10, rerun T07/T10/T11/T12 before releasing E2E.
7. Keep A4/provider-live separate from institutional freshness.

## Next executable step

TDD scenario:

`authority rev-A → canonical source changes to rev-B and revokes permission → stale AuthorityContext is presented for a side effect → mismatch detected before adapter invocation → Core re-resolves or ESCALATE/fails closed → ToolPort is not called under stale authority`.

Status: REGISTERED. Production implementation remains isolated on this worker branch until tests and integration review pass.
