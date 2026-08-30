# ARCH-02 — Reauditoria independente T07/T10/T11/T12

Data: 2026-08-29
PR: #17 — `worker/core-freshness-gate`
SHA auditado: `61cd47670909469d0c684396d73b4572a1e4463a`
Parecer: **REWORK**

## Classificação independente

| Requisito | Classificação |
|---|---|
| T07 | `PARTIAL` |
| T10 | `CONTRADICTED` |
| T11 | `CONTRADICTED` |
| T12 | `CONTRADICTED` |

## Achados P0 incorporados ao gate de integração

### G01 — T10: freshness Core-owned pode ser contornada
`StateManager.resume(..., freshness_gate=...)` valida apenas presença de um objeto com `.prepare()`. A suíte contém `PassFreshnessGate`, que não usa SourcePort, não verifica revisions e ainda assim permite alcançar `RuntimePort.resume()`.

Correção mínima: tornar impossível `resume → fake/no-op gate → runtime`. O Core deve possuir/validar estruturalmente a revalidação aplicável, não aceitar um objeto arbitrário duck-typed como substituto institucional.

### G02 — T11: freshness opcional no ToolGateway
`ToolGateway(..., freshness_gate=None)` continua permitindo side effect. Existe teste verde no SHA auditado que executa side effect sem freshness e confirma chamada ao adapter.

Correção mínima: para `descriptor.side_effect=True`, ausência de freshness deve falhar fechado antes de authority decision, ledger e ToolPort.

### G03 — revogação explícita pode virar wildcard
`AuthorityResolver._effective_allowed_scopes()` considera allow-list somente quando `raw.get("allowed_scopes")` é truthy. Assim, `allowed_scopes=[]` é tratado como ausência da lista; se nenhuma cadeia declarar allow-list não vazia, o resultado pode ser `['*']`.

Consequência: uma revogação explícita pode virar autorização ampla após re-resolução.

Correção mínima: distinguir campo ausente de campo presente e vazio. Lista explicitamente vazia deve participar da interseção como conjunto vazio.

### G04 — T12: bloqueios não deixam trilha persistente suficiente
DENY/ESCALATE/freshness failure lançam erro sem decision/revalidation trace persistido suficiente. Isso converge com TRACE-01: caminho fail-closed não é reconstruível apenas pelos registros persistidos.

Correção mínima: persistir antes de retornar/lançar, com decisão/outcome, fundamento, source refs, revisions esperada/observada, authority/context refs, run/correlation id e boundary.

## Achados P1

- falta cenário executável T07 de mudança somente técnica;
- snapshot/revisions anteriores não são preservados integralmente no RV;
- não existe baseline persistido da revisão anterior de AgentIdentity no resume;
- `identity_changed` pode falhar em detectar mudança sem alteração dos authority refs.

## Incongruências documentais/testes

- documentação diz que snapshot stale não atravessa adapter, mas `ToolGateway` sem freshness permite;
- teste verde comprova side effect sem freshness;
- teste T11 usa `allowed_scopes=[]` como revogação, mas o resolver atual pode convertê-lo em wildcard após re-resolução;
- Code Map menciona `tests/test_revalidation_audit.py`, ausente no SHA auditado; a prova equivalente está em `tests/test_resume_freshness_gate.py`.

## Decisão do Integrador após ARCH-02 + TRACE-01

A classificação conservadora para o SHA auditado passa a ser:

- T07 = `PARTIAL`
- T10 = `CONTRADICTED`
- T11 = `CONTRADICTED`
- T12 = `CONTRADICTED`

A PR #17 permanece **REWORK — NÃO INTEGRAR**.

## Ordem mínima de correção

1. fechar bypass T10: freshness/revalidation não pode ser substituída por gate arbitrário;
2. fechar bypass T11: freshness obrigatória/fail-closed para side effects;
3. corrigir semântica `allowed_scopes=[]` para conjunto vazio, nunca wildcard;
4. persistir RV/decision trace também no caminho BLOCKED/FAILED/ESCALATED;
5. preservar snapshot/revisions anteriores e contexto histórico suficiente;
6. blindar `decision_refs` contra injeção do runtime;
7. adicionar T07 technical-only;
8. adicionar regressões para todos os P0;
9. CI completa;
10. reauditoria T07/T10/T11/T12 + TRACE-01 + adversarial review.

`HARNESS STATUS = ARCHITECTURAL_BLOCKER`.
