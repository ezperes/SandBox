# Auditoria Pós-Incrementos 1–7 — Harness Core V0.1

Data: 2026-08-29
Status: **ATIVA — BLOQUEIO ARQUITETURAL ANTES DO E2E INSTITUCIONAL**

## Objetivo
Revisar conjuntamente os Incrementos 1–7 e os quatro trabalhos paralelos do GT, exigindo a interseção:

`FUNCIONAL ∩ CONTRATUAL ∩ ARQUITETURAL ∩ AUTORIZADO ∩ TESTADO ∩ RASTREÁVEL`

Resultado funcionando, isoladamente, não é critério de saída.

## Retificações e gates concluídos

### R1 — `NAO_APLICAVEL_JUSTIFICADO`
Justificativa textual real é obrigatória; ausência falha fechado com `AUTHORITY_UNRESOLVED`.

### R2 — Runtime não injeta referências canônicas
`decision_refs` e `checkpoint_ref` vêm exclusivamente do estado canônico anterior/Core. Estado nativo do runtime não pode criá-los ou substituí-los.

### A1 — Autoridade por interseção — CONCLUÍDO
`AuthorityResolver` calcula autorização positiva pela interseção das allow-lists declaradas pelas cadeias aplicáveis; interseção vazia não autoriza e proibição explícita prevalece.

### A2 — Ledger idempotente — CONCLUÍDO
Estados `PENDING | COMPLETED | FAILED | UNKNOWN`, com resultado/evidência/erro/reconciliação. Retry cego de resultado incerto é bloqueado.

### A3 — LangGraph físico — CONCLUÍDO
Prova física com LangGraph `1.2.11`: `StateGraph`, `MemorySaver`, `interrupt_before`, checkpoint técnico e resume no mesmo `thread_id`. O checkpoint técnico não substitui `Checkpoint` canônico e o Core/FakeRuntime continua executável sem importar LangGraph.

### A5 — Supporting refs — CONCLUÍDO
`procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` permanecem `POINTER_ONLY` na V0.1. Materialização exige caminho explícito sujeito a budget, provenance, revisão e deduplicação.

### CI-01 — Schema drift — CONCLUÍDO
A CI deixou de depender apenas de `git diff`. `scripts/check_schema_drift.py` usa Git porcelain e detecta alterações rastreadas, schemas novos/untracked (`??`) e schemas ignorados (`!!`). O baseline de 17 schemas + `all.schemas.json` foi materializado pelo exportador em Python 3.11 e a CI conjunta confirmou `schema export matches the Git-tracked state`.

### B1 — Erro compartilhado — CONCLUÍDO
`HarnessResolutionError` tem propriedade neutra em `harness.core.errors`; `harness.core.identity` reexporta o mesmo objeto de classe. Códigos, payload, string e pontos de raise permanecem semanticamente equivalentes.

## Gate ainda separado

### A4 — Provider live — ABERTO, mas não é o blocker imediato
`OpenAIResponsesAdapter` continua comprovado por cliente injetado/stub. Um E2E futuro deve declarar explicitamente FakeModelAdapter ou executar chamada live. Não antecipar esse gate enquanto T10/T11 estiverem contraditos.

## Auditoria arquitetural T01–T12 pós-integração

Classificação canônica:
- `PROVEN`: cenário completo demonstrado executavelmente.
- `PARTIAL`: componentes relevantes existem, mas o cenário institucional completo não está demonstrado.
- `NOT_PROVEN`: contratos/documentação existem sem fluxo executável suficiente.
- `CONTRADICTED`: há caminho executável que viola diretamente o requisito.

| Teste | Status | Evidência pós-integração |
|---|---|---|
| T01 | `PARTIAL` | Same-as-tactical, normativa, contexto mínimo e ALLOW existem/testam separadamente; falta composição integral identidade→autoridade→contexto→execução→evidência/trace. |
| T02 | `PARTIAL` | Cadeias tática/técnica permanecem segregadas; falta prova E2E de objetivo Comercial versus método TI sem mistura semântica. |
| T03 | `NOT_PROVEN` | `CrossDomainEvent`/`DomainObligation` são contratos; não há dispatcher/reconciler nem gate de conclusão global. |
| T04 | `PARTIAL` | Proibição normativa impede tool call; falta cenário completo com origem normativa, estado, evidência e decision trace integrado. |
| T05 | `PARTIAL` | Interseção rejeita método não comum, mas não há representação explícita objetivo+método nem seleção de alternativa técnica válida. |
| T06 | `PARTIAL` | Competência insuficiente bloqueia execução; não existe Delegation Gate/Port para Elemento competente. |
| T07 | `PARTIAL` | `rebuild_partial()` preserva cadeias não alteradas; não há detector de revisão que derive `changed_chains` e persista transição. |
| T08 | `NOT_PROVEN` | Mudança de Fração/GT/domínio não dispara nova Identity/Authority/Bootstrap/InstructionProfile. |
| T09 | `NOT_PROVEN` | Não há Delegation Gate nem Instruction Adapters Claude/Codex; ModelRouter não prova delegação cross-provider. |
| T10 | `CONTRADICTED` | `StateManager.resume()` valida checkpoint/RunState e chama imediatamente `runtime.resume(run,state)` sem re-resolver fontes/autoridade ou reconstruir Active Context. A3 prova o runtime físico, não corrige essa ordem institucional. |
| T11 | `CONTRADICTED` | `ToolGateway.execute()` aceita `AuthorityContext` pronto e decide sem comparar revisões atuais das fontes; um contexto antigo pode alcançar novo side effect após revogação. |
| T12 | `PARTIAL` | Fail-closed/ESCALATE existe para várias lacunas; falta conflito explícito e decision trace persistido com fundamentos/fontes/revisões. |

Contagem pós-integração:

`PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`

A integração de A3, B1 e CI-01 melhora evidência física, acoplamento e CI, mas não muda as classificações funcionais T01–T12 produzidas pela auditoria ARCH-01 porque nenhum desses workers implementou coordenação/freshness/delegação.

## Verificações arquiteturais transversais

- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`: preservada no `AuthorityResolver`; nenhum worker afrouxou a interseção.
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`: preservado. LangGraph permanece sob adapter e dependência opcional/dev.
- Identidade institucional continua em Core/fontes canônicas; provider/runtime não altera `AgentIdentity`.
- Autoridade continua em Core/fontes canônicas; LangGraph não recebe `authority_context_ref` como estado nativo canônico.
- Checkpoint nativo LangGraph permanece técnico; `Checkpoint` canônico continua Core-owned.
- Supporting refs continuam `POINTER_ONLY`.
- Side effects continuam atravessando `ToolGateway` + ledger; porém T11 exige freshness antes desse gate ser considerado suficiente contra revogação posterior.
- A1/A2/A5 não sofreram regressão observável: suíte conjunta inteira passou após B1/A3/CI-01.

## CI conjunta pós-integração

GitHub Actions `Harness Core CI`, PR de integração:
- Ubuntu 24.04;
- CPython `3.11.16`;
- Pydantic `2.13.5`;
- pytest `8.4.2`;
- LangGraph `1.2.11`;
- `pytest`: **50 passed in 0.69s**;
- exportador: **17 schemas**;
- hardening CI: **schema export matches the Git-tracked state**.

## Incongruence check

1. **Corrigido:** documentação antiga dizia que A3/LangGraph real estava pendente; agora há prova física.
2. **Corrigido:** documentação antiga marcava A2/A5 como próximos; ambos já estavam implementados.
3. **Corrigido:** B5 dizia que untracked schemas poderiam escapar; CI-01 fechou o blind spot e o baseline foi versionado.
4. **Retificado:** relatórios A3/B1 anteriores registraram schema check verde usando `git diff`; isso não era prova suficiente porque o BASE_SHA não possuía schemas rastreados. A evidência válida de sincronismo é a CI conjunta endurecida após materialização do baseline.
5. **Mantido:** A3 prova checkpoint/interrupt/resume técnico real, mas não deve ser citado como prova de T10 institucional.
6. **Mantido:** `RunStatus.COMPLETED` produzido por runtime técnico não equivale automaticamente a conclusão institucional; Evidence/Verification/gates finais continuam necessários.

## Riscos e débitos técnicos

### P0 — T11: autoridade stale antes de side effect
Risco: autorização revogada após resolução pode continuar válida dentro de `AuthorityContext` antigo. Necessário freshness/revision gate Core-owned antes de side effects relevantes.

### P0 — T10: resume com contexto stale
Risco: retomada pode executar runtime antes de reconstruir Active Context e revalidar autoridade. Ledger reduz duplicação, mas não resolve autorização/contexto obsoleto.

### P1 — T03/T06/T08/T09
Coordenação interdomínio, delegação por competência, transição organizacional e Instruction Compatibility Layer permanecem não materializadas.

### P1 — T07/T12
Detector de mudança por revisão e decision trace persistido permanecem incompletos.

### P2 — dependências de schema
Pydantic usa intervalo `>=2.10,<3`; schemas foram gerados/validados com 2.13.5. A CI protege drift, mas não há lockfile do ambiente Python. Mudança futura de Pydantic pode produzir drift legítimo que exigirá revisão explícita.

## Gate de saída

O Harness **não está autorizado a avançar para E2E institucional** enquanto T10/T11 permanecerem `CONTRADICTED`.

O próximo trabalho deve priorizar um freshness gate Core-owned antes de novo side effect, com comparação de revision refs e fail-closed em mismatch. O mesmo primitivo poderá depois ser reutilizado no fluxo de resume para fechar T10.
