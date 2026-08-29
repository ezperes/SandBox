# Plano de Implementação — Harness Core V0.1

Data de atualização: 2026-08-29

## Estado dos gates

| Gate | Estado | Evidência principal |
|---|---|---|
| A1 — autoridade por interseção | `DONE` | testes de `AuthorityResolver`; suíte conjunta verde |
| A2 — ledger idempotente com estado | `DONE` | `PENDING|COMPLETED|FAILED|UNKNOWN`; ToolGateway/StatePort |
| A3 — LangGraph físico | `DONE` | LangGraph 1.2.11 + StateGraph + MemorySaver + interrupt/resume real |
| A5 — supporting refs | `DONE` | `POINTER_ONLY` no contrato/schema e testes |
| CI-01 — schema drift | `DONE` | tracked + untracked + ignored; baseline versionado |
| B1 — Core errors | `DONE` | propriedade em `core.errors` + alias legado |
| A4 — provider live | `OPEN` | não é o bloqueio imediato |
| T10 — resume com Active Context revalidado | `BLOCKER_P0` | `CONTRADICTED` |
| T11 — freshness de autoridade antes de side effect | `BLOCKER_P0` | `CONTRADICTED` |

## Sequência prioritária

### 1. CORE-FRESHNESS-GATE — PRIORIDADE ÚNICA ATUAL

Objetivo: impedir que autoridade/contexto stale chegue a novo side effect ou resume.

Critério de saída:

`revision snapshot anterior → leitura das revisões atuais → detectar mudanças por cadeia → re-resolver Identity/Authority quando aplicável → rebuild/re-bootstrap somente do contexto afetado → persistir novo snapshot/trace → só então liberar RuntimePort.resume ou side effect`

TDD obrigatório:

1. T11 vermelho: resolver autoridade em rev-A → alterar fonte para rev-B removendo permissão → reutilizar contexto rev-A → provar que novo side effect é bloqueado/revalidado antes do adapter.
2. T10 vermelho: checkpoint em rev-A → alterar fonte técnica/normativa para rev-B → resume → provar que runtime não é chamado antes da revalidação/reconstrução.
3. Implementar primitivo Core-owned de freshness/revalidation sem colocar SourcePort/Authority no Runtime Adapter.
4. Reusar o mesmo primitivo no caminho de resume.
5. Persistir transição old snapshot → new snapshot + decision trace.
6. Reclassificar T10/T11.

### 2. Somente depois de T10/T11

- compor Run Coordinator/Agent Loop para elevar T01/T02/T04 de provas unitárias a cenários arquiteturais completos;
- implementar Delegation Gate/Port para T06 e base de T09;
- implementar detector de revisão/transição para fechar T07;
- implementar mudança Fração/GT/domínio para T08;
- implementar Instruction Compatibility Layer cross-provider para T09;
- materializar conflito/decision trace completo para T12;
- implementar dispatcher/reconciler multidomínio e conclusão global para T03;
- decidir durable checkpointer para runtime de produção;
- tratar A4 provider live conforme o desenho do primeiro E2E.

## Gate para E2E

Não iniciar E2E institucional enquanto existir `CONTRADICTED` em T10 ou T11.

Condição mínima para reconsiderar E2E:

`T10 != CONTRADICTED ∩ T11 != CONTRADICTED ∩ CI verde ∩ schemas sem drift ∩ A1/A2/A3/A5 sem regressão`.
