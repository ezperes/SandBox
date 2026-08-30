# P0-2-INDEPENDENT-RED-TEAM — Fase 1 Addendum

Status: `PHASE1_ONLY`

Baseline: `worker/core-freshness-gate@530386c35e21066b11ffb5491a52418faae67269`

This addendum records cross-front findings that must become adversarial requirements for the future frozen integration SHA. It is not an integration audit and contains no production correction.

## RT-12 — Revision-proof infrastructure split

Threat: a TOCTOU fix may close one local race while creating a second, competing revision-proof subsystem.

Known rejected pattern:

```text
existing canonical revision machinery
    VersionedReadSet + strong Revision Guard

parallel runtime-only family
    RevisionLeasePort + RuntimeResumeFence
```

The second family was classified `REWORK` by the Integrator. The red-team requirement is convergence, not coexistence.

### Required future proof

On the Integrator-provided frozen SHA, both sensitive releases must be attacked dynamically:

```text
Tool:
version/revision proof
→ adversarial source mutation
→ ToolPort.invoke()

Runtime resume:
version/revision proof
→ adversarial source mutation
→ RuntimePort.resume()
```

A future candidate is not proven merely because it introduces a lease/fence object. The proof must show that both boundaries consume the same canonical revision semantics rooted in `VersionedReadSet + strong Revision Guard`, with no parallel institutional source of truth.

### Prepared structural tripwire

`tests/test_p0_2_red_team_revision_guard_convergence.py`

It fails if production code introduces the known duplicate-family symbols:

- `RevisionLeasePort`
- `RuntimeResumeFence`

This tripwire is necessary but not sufficient. Renaming a parallel subsystem does not make the architecture acceptable; Phase 2 must inspect ownership/dataflow and rerun the active TOCTOU probes.

## SourcePort.read() is not a fence

The current baseline exposes freshness through source reads and revision comparison. The active Tool TOCTOU probe already demonstrates the security distinction:

```text
read/check rev-A
≠
guarantee that the side effect executes while rev-A is still authoritative
```

Therefore a future implementation that merely adds another `SourcePort.read()` immediately before the call is still subject to CHECK→USE races unless the canonical strong Revision Guard supplies an execution-bound proof/fence semantics.

The same standard applies to resume: revalidation ordered before `RuntimePort.resume()` is necessary but does not prove atomicity or effective fencing.

## Updated Phase 1 threat inventory

| ID | Threat | Prepared evidence/probe |
|---|---|---|
| RT-01 | cross-run/cross-agent AuthorityContext laundering | execution-binding adversarial test |
| RT-02 | idempotency reset across runs | same business effect replayed under new run |
| RT-03 | Tool TOCTOU | physical revision flip before ToolPort |
| RT-04 | RunState task mismatch | foreign task in same-run state/checkpoint |
| RT-05 | Run↔RunState identity mismatch | foreign state ref through checkpoint |
| RT-06 | stale/foreign ResumeFreshnessGate lineage | prior context from another run |
| RT-07 | Runtime mutation of Core-owned HarnessRun | hostile runtime mutates institutional fields |
| RT-08 | Runtime state firewall | hostile runtime returns foreign RunState |
| RT-09 | Runtime resume TOCTOU | physical revision flip before RuntimePort.resume |
| RT-10 | repeated resume | same checkpoint re-enters runtime |
| RT-11 | temporal trace attribution | who/run/task/authority+revision/boundary/time/outcome |
| RT-12 | competing revision-proof families | structural tripwire + future ownership/dataflow audit |

## Phase 2 non-negotiable rule

No Phase 2 work occurs until the Integrator supplies an explicit frozen SHA. When supplied, classifications are recomputed from zero for that exact SHA. No verdict from the baseline, other workers, CI, or this addendum is inherited.

Current state:

`WAITING_FROZEN_SHA`
