# CORE-FRESHNESS-GATE — P0 correction plan

Base inspected: `7fc0665e367ed16e798d279eed09edd06650ac7c`.

Scope for this correction cycle:

1. T10: reject any non-canonical/duck-typed resume freshness gate.
2. T11: make authority freshness mandatory/fail-closed for every side effect.
3. Authority semantics: distinguish omitted `allowed_scopes` from explicit `allowed_scopes=[]`; explicit empty means authorize nothing.
4. T12/TRACE: persist revalidation attempts before verification and finalize them as `RELEASED`, `BLOCKED`, or `FAILED`, including blocked paths.
5. Preserve sufficient previous authority/context revision evidence in the revalidation record.
6. Sanitize `RunState.decision_refs` after `RuntimePort.resume()` so runtime adapters cannot inject Core/institutional refs.
7. Add regression tests, including technical-only T07 evidence where practical.

Rule: no merge to canonical branch until CI and re-audit pass.
