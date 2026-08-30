# Implementation Report — Harness Core V0.1

## Estado consolidado

Os Incrementos 1–7 e o GT paralelo estão consolidados no estado canônico anterior. O trabalho `CORE-FRESHNESS-GATE` permanece isolado na branch `worker/core-freshness-gate`, PR draft #17, ainda **não integrada** à branch canônica.

Estado canônico anterior: T10/T11 `CONTRADICTED`, Harness em `ARCHITECTURAL_BLOCKER`.

Estado candidato atual: ciclo corretivo P0 implementado e CI verde, porém a promoção arquitetural depende de reauditoria independente. O SHA funcional de correção é `865255b37c683f3fd1f13a8e06ba56936d2ea95d`. O artefato congelado entregue aos auditores independentes é `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff`.

## Incrementos 1–7

- Incremento 1: contratos/ports/runtime fake.
- Incremento 2: IdentityResolver + AuthorityResolver e interseção das cadeias aplicáveis.
- Incremento 3: Bootstrap + ContextBuilder + rebuild parcial.
- Incremento 4: RunState, Checkpoint, StatePort e ledger idempotente.
- Incremento 5: Tool Registry/Gateway e gates antes de side effect.
- Incremento 6: contratos/model routing/provider adapters neutros à identidade.
- Incremento 7: LangGraphAdapter atrás de RuntimePort; A3 físico comprovado com LangGraph `1.2.11`.

## CORE-FRESHNESS-GATE — ciclo corretivo P0

### G01 — Resume freshness obrigatório

`StateManager.resume()` rejeita ausência de freshness e objetos duck-typed/no-op. Somente o `ResumeFreshnessGate` Core-owned concreto pode liberar `RuntimePort.resume()`.

Fluxo candidato:

`Checkpoint/RunState → RV-* PENDING → ResumeFreshnessGate → re-resolução de identidade/autoridade → changed_chains → rebuild aplicável → persistência do resultado → RuntimePort.resume()`.

### G02 — Freshness obrigatório em side effects

Todo `ToolDescriptor.side_effect=True` exige `AuthorityFreshnessGate` Core-owned concreto antes de decisão de autoridade, reserva idempotente e `ToolPort.invoke()`.

Ausência, gate incompatível, source stale, unreadable source ou revision ausente falham fechado antes do ToolPort.

### G03 — Semântica de `allowed_scopes=[]`

Campo ausente e lista vazia não são equivalentes:

- ausência de `allowed_scopes`: a cadeia não adiciona whitelist;
- `allowed_scopes=[...]`: restrição positiva;
- `allowed_scopes=[]`: conjunto vazio / revogação total naquela interseção.

A transição `['finance:pay'] → []` não pode resultar em `['*']`.

### G04 — Trilha persistente de boundary

O ciclo de auditoria é persistido como:

`PENDING → RELEASED | BLOCKED | FAILED`.

O registro `RV-*` preserva, quando aplicável:

- run/correlation/boundary;
- refs anteriores de autoridade e TaskContext;
- revisões anteriores de identidade e cadeias;
- AuthoritySnapshot atual;
- AuthorityContext/TaskContext atuais;
- Bootstrap trace;
- changed_chains;
- identity_changed;
- decision/outcome/error/source_ref;
- sequência temporal da tentativa.

BLOCKED/FAILED são registrados para freshness inválida/rejeitada, DENY, ESCALATE, REQUIRE_APPROVAL, idempotency block, ToolPort failure e Runtime resume failure.

### Proteção contra autoridade institucional do runtime

`decision_refs` devolvidos pelo RuntimePort são descartados; o Core restaura a lista Core-owned válida antes de persistir estado institucional.

### T07 técnico-only e stale identity

Há regressão específica para mudança apenas da cadeia técnica: `changed_chains == {TECHNICAL}`, rebuild somente técnico e preservação das cadeias não afetadas.

A revisão anterior de AgentIdentity também é capturada e comparada; mudança de identidade é detectada mesmo sem alteração dos authority refs.

### Idempotência após falha externa incerta

Se ToolPort é chamado e lança exceção após cruzar o boundary, o registro fica `FAILED/TOOLPORT_ERROR` e o ledger fica `UNKNOWN` com `reconciliation_required=true`, impedindo retry cego.

## Arquitetura preservada

- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`.
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`.
- SourcePort permanece boundary para fontes canônicas.
- Tool/Runtime adapters não decidem identidade, autoridade ou freshness institucional.
- LangGraph permanece substituível.
- Supporting refs permanecem `POINTER_ONLY`.
- Nenhum contrato canônico/schema foi alterado apenas para acomodar a correção.

## Validação executável

No SHA congelado `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff`:

- GitHub Actions Harness Core CI #180: SUCCESS;
- CPython 3.11;
- LangGraph 1.2.11;
- **68 testes passed**;
- **17 schemas exportados**;
- schema drift clean.

CI verde não promove automaticamente T07/T10/T11/T12/TRACE.

## Tentativa que falhou → causa → solução correta

1. Teste local via clone não executou → ambiente sem resolução DNS para GitHub → usar GitHub Actions sobre a PR.
2. Primeiro teste T10 exigiu lista exata de refs → Bootstrap inclui route ref legítimo → corrigir expectativa para a invariante arquitetural, sem mudar produção.
3. Test double antigo não possuía snapshot/trace suficientes → double não representava preparação válida → atualizar o double, sem enfraquecer persistência.
4. Reauditoria encontrou fake/no-op freshness, side effect sem gate, `allowed_scopes=[]` permissivo e bloqueios sem trilha → implementar gates concretos, semântica de conjunto vazio e boundary audit persistente.

## Estado de auditoria

O SHA histórico `61cd47670909469d0c684396d73b4572a1e4463a` permanece classificado como:

- T07 `PARTIAL`;
- T10 `CONTRADICTED`;
- T11 `CONTRADICTED`;
- T12 `CONTRADICTED`;
- TRACE `TRACE_PARTIAL`.

O SHA novo não herda automaticamente nem reprovação nem aprovação. Seu estado é:

`CORRECTIONS_IMPLEMENTED → CI_GREEN → READY_FOR_DEFENSIVE_REAUDIT → DO_NOT_MERGE`.

## Risco residual principal

TOCTOU entre freshness/re-resolution e uso externo ainda requer verificação independente:

`freshness/check → fonte muda → ToolPort.invoke()`

ou

`prepare/re-resolve → fonte muda → RuntimePort.resume()`.

A implementação atual não deve ser declarada atomicamente segura sem essa prova.

## Higiene pré-integração

Após congelar o SHA de auditoria, artefatos worker claramente temporários/obsoletos foram removidos da branch de trabalho. Permanecem apenas o `WORK_CONTRACT` e o `IMPLEMENTATION_LOG` worker como histórico operacional, além da documentação consolidada em `docs/`.

Essa higiene documental não altera o código funcional entregue aos auditores no SHA `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff`.

## Próximo passo

`ARCH-03 + VERIFY-SEC-01 + TRACE-02 → consolidação do Integrador → ACCEPT | ACCEPT_WITH_FIXES | REWORK`.

Somente após decisão positiva: congelar HEAD final de integração, CI final, merge, CI pós-merge e atualização canônica. A4/E2E permanece fora de escopo até esse gate ser vencido.
