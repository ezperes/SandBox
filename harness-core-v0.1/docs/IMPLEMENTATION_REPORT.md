# Implementation Report — Harness Core V0.1

Data de consolidação: 2026-08-29  
Relatório detalhado do GT: `docs/GT_INTEGRATION_AUDIT_2026-08-29.md`

## Resultado implementado — Incrementos 1–7

1. **Contratos/Core inicial:** contratos Pydantic V0.1, Ports e FakeRuntimeAdapter independentes de LangGraph.
2. **Identity + Authority:** identidade por `SourcePort`; três cadeias tática/técnica/normativa; snapshots de revisão; decisões `ALLOW | DENY | REQUIRE_APPROVAL | ESCALATE`; autorização positiva por interseção.
3. **Bootstrap + Context:** um Bootstrap, até três rotas segmentadas, contexto mínimo por budget/proveniência e `rebuild_partial()` seletivo.
4. **State + Checkpoint:** `StatePort`, `RunState`, `Checkpoint`, resume técnico e ledger idempotente com `PENDING | COMPLETED | FAILED | UNKNOWN`.
5. **Tool Gateway:** gates de autoridade, competência, aprovação, idempotência e evidência antes/depois do boundary externo.
6. **Model routing:** contratos neutros, `ModelRouter`, FakeModelAdapter e OpenAIResponsesAdapter; provider/modelo não alteram `AgentIdentity`.
7. **Runtime LangGraph:** adapter isolado atrás de `RuntimePort`; runtime não se torna fonte institucional.

## Consolidação do GT paralelo

### A3 — LangGraph real — CONCLUÍDO

A integração física foi comprovada contra `langgraph==1.2.11` real com `StateGraph`, compilação, `MemorySaver`, static interrupt/breakpoint e resume no mesmo `thread_id`. LangGraph continua extra opcional/dev; não integra as dependências obrigatórias do Core.

A3 fecha o gate físico do runtime, mas **não** resolve o requisito canônico de freshness/re-bootstrap antes de resume (T10).

### B1 — erro compartilhado — CONCLUÍDO

`HarnessResolutionError` foi movido para `harness.core.errors`. O antigo caminho via `harness.core.identity` é re-export compatível. Payload, códigos e string observável permanecem preservados por teste de regressão.

### CI-01 — schema drift — CONCLUÍDO COM CORREÇÃO DO INTEGRADOR

O checker antigo baseado somente em `git diff` não via schemas novos/untracked. O novo `scripts/check_schema_drift.py` usa Git porcelain e detecta tracked, untracked e ignored.

O Integrador materializou o baseline faltante: 17 schemas canônicos + `all.schemas.json`, gerados pelo próprio GitHub Actions e versionados sem alterar contratos.

CI atual:

`pytest → python scripts/export_schemas.py → python scripts/check_schema_drift.py`

### ARCH-01 — auditoria independente — INCORPORADA

O Gap Map do BASE_SHA foi preservado como evidência histórica. Nova auditoria pós-integração manteve:

`PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`

T10 e T11 continuam críticos.

## Gates e invariantes

### Fechados

- A1 — interseção de autoridade.
- A2 — ledger idempotente com estados/reconciliação.
- A3 — prova física LangGraph real.
- A5 — supporting refs `POINTER_ONLY`.
- B1 — `HarnessResolutionError` compartilhado.
- B5/CI — detecção de schema novo/untracked/ignored.
- R1 — `NAO_APLICAVEL_JUSTIFICADO` exige justificativa real.
- R2 — runtime não injeta refs canônicos de decisão/checkpoint.

### Abertos

- **T10 / CRITICAL:** `StateManager.resume()` ainda entra no runtime sem revalidar fontes/autoridade nem reconstruir o Active Context.
- **T11 / CRITICAL:** `ToolGateway` pode receber um `AuthorityContext` stale; não há freshness/revision gate antes de novo side effect.
- A4 — provider live ainda não foi comprovado; eventual E2E deve declarar FakeModelAdapter ou executar provider real.
- T03/T06/T08/T09/T12 — faltam componentes de interdomínio/delegação/instruction compatibility/decision trace completo.

## Regras arquiteturais preservadas

- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`.
- identidade/autoridade não pertencem ao runtime/provider.
- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA` continua sendo condição de autorização positiva.
- autoridade ≠ competência.
- conflito/lacuna não resolvidos falham fechado/ESCALATE.
- checkpoint técnico não substitui checkpoint canônico.
- side effects passam por gates do Core + ledger.
- `procedural_refs`, `knowledge_refs`, `risk_refs`, `memory_refs` permanecem `POINTER_ONLY` até materialização explícita.
- estado pequeno + artefatos fora + apontadores estáveis permanece a regra.

## Testes/CI

A integração foi sequencial, com CI entre workers. Foram observados passos verdes de `pytest`, exportação de schemas e verificação de drift após B1, A3, baseline, CI-01 e ARCH-01.

A execução de CI-01 antes do baseline falhou exatamente no novo checker após testes/exportação passarem; após o baseline, o mesmo checker passou. Isso foi tratado como evidência do blind spot e da correção, não como regressão.

## Tentativa que falhou → causa → solução correta

- **CI-01 sem baseline:** checker estrito deixou a CI vermelha → schemas gerados não estavam versionados no BASE_SHA → Integrador gerou os schemas no GitHub Actions, versionou somente a saída canônica e então reintegrou CI-01.
- **Busca ARCH por CrossDomainEvent:** code search incompleto sugeriu ausência → busca não era prova negativa → leitura direta do bundle encontrou `CrossDomainEvent`/`InstructionProfile`; auditoria foi corrigida antes do relatório.
- **A3 dynamic interrupt como possível interpretação:** `Command(resume=<payload>)` exigiria contrato de resume não existente → não expandir RuntimePort silenciosamente → usar static interrupt real compatível com V0.1 e registrar dynamic HITL como evolução contratual futura.

Demais tentativas/causas/soluções dos Incrementos 1–7 permanecem registradas em `docs/IMPLEMENTATION_LOG.md` e nos relatórios de workers.

## Riscos e débitos principais

- freshness/revalidation Core-owned antes de resume e side effect;
- Delegation Gate/Port e Instruction Compatibility Layer;
- conclusão global de CrossDomainEvent/obrigações;
- DecisionTrace persistido para conflitos;
- provider live A4;
- eventual lock da toolchain Pydantic para reprodutibilidade bit-a-bit dos schemas;
- checkpointer durável somente quando deployment exigir.

## Code map

`docs/CODE_MAP.md`

## Estado

`HARNESS STATUS = ARCHITECTURAL_BLOCKER`

## Próximo passo único

Executar `RUN-REVALIDATION-GATE`: implementar no Core, por testes arquiteturais, freshness/revalidação obrigatória antes de resume e antes de side effect relevante, preservando snapshot histórico e reconstruindo apenas cadeias/contexto afetados antes de atravessar Runtime/Tool boundaries.
