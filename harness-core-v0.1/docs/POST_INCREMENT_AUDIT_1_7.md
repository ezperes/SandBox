# Auditoria Pós-Incrementos 1–7 — Harness Core V0.1

Data: 2026-08-29  
Status: **ATIVA — BLOQUEADOR ARQUITETURAL ANTES DO E2E**

## Objetivo

Revisar conjuntamente contratos, implementação, adapters, CI e testes arquiteturais antes da primeira prova end-to-end. Esta versão incorpora o GT paralelo A3/B1/CI-01/ARCH-01.

## Retificações concluídas

### R1 — `NAO_APLICAVEL_JUSTIFICADO`

Forma sem justificativa real não é aceita. Ausência de justificativa falha fechado com `AUTHORITY_UNRESOLVED`.

### R2 — refs canônicos vindos do runtime

`decision_refs` e `checkpoint_ref` canônicos só podem ser preservados do estado canônico/Core; valores homônimos do runtime são ignorados.

## Gates anteriores

### A1 — Autoridade por interseção — `CLOSED`

`allowed_scopes` efetivo é a interseção das allow-lists declaradas pelas cadeias aplicáveis. Cadeia sem allow-list não acrescenta whitelist; ausência total é `*`; interseção vazia autoriza nada; proibição explícita prevalece.

Regra preservada: `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`.

### A2 — Ledger idempotente — `CLOSED`

Ledger com `PENDING | COMPLETED | FAILED | UNKNOWN`, resultado/evidência, erro e reconciliação. Retry cego é bloqueado quando operação está pendente, concluída ou com outcome desconhecido.

### A3 — LangGraph físico real — `CLOSED`

Comprovado contra `langgraph==1.2.11` real:
- `StateGraph` real e compilado;
- `MemorySaver` real;
- static interrupt/breakpoint;
- resume do mesmo thread;
- `run_id → configurable.thread_id`;
- checkpoint técnico distinto do checkpoint canônico;
- runtime sem autoridade/identidade institucional.

A3 comprova o **mecanismo físico do adapter**, não a segurança semântica do resume canônico. T10 permanece aberto/contradito.

### A4 — Provider live — `OPEN`

OpenAIResponsesAdapter continua comprovado por superfície compatível/stub, não chamada live. Um E2E futuro deve declarar explicitamente FakeModelAdapter ou executar provider real. A4 não é o bloqueador prioritário atual porque T10/T11 impedem avanço seguro antes dele.

### A5 — Supporting refs — `CLOSED`

`procedural_refs`, `knowledge_refs`, `risk_refs`, `memory_refs` são `POINTER_ONLY` na V0.1:
- não consomem budget apenas por existirem;
- não são lidos automaticamente pelo ContextBuilder;
- não entram em provenance/token_usage enquanto ponteiros;
- materialização futura deve passar por pipeline explícito com budget, revisão, deduplicação e proveniência.

## Melhorias B do audit anterior

### B1 — erro compartilhado — `CLOSED`

`HarnessResolutionError` agora vive em `core.errors`, com re-export compatível por `core.identity`. Teste dedicado preserva classe/payload/string.

### B2 — ToolDescriptor interno — `OPEN / NON-BLOCKING`

Formalizar como contrato canônico somente se passar a cruzar boundary externo, persistência ou configuração declarativa.

### B3 — estado técnico ≠ conclusão institucional — `OPEN / ARCHITECTURAL RULE`

`harness_status=COMPLETED` do runtime não pode encerrar institucionalmente uma Tarefa sem Evidence + VerificationResult + gates finais. Deve ser testado na futura composição E2E.

### B4 — resume instruction — `OPEN`

`Checkpoint.resume_instruction` é persistido, mas seu papel no futuro coordenador/revalidation gate precisa ser formalizado. Não deve virar fonte autônoma de autoridade do runtime.

### B5 — schema drift untracked — `CLOSED`

Schemas canônicos foram materializados/versionados: 17 arquivos + `all.schemas.json`.

CI agora executa:

`pytest → export_schemas.py → check_schema_drift.py`

`check_schema_drift.py` detecta mudanças tracked, arquivos `??` e arquivos `!!` em `harness/schemas`.

## Nova auditoria arquitetural T01–T12

| T | Estado pós-GT | Observação |
|---|---|---|
| T01 | `PARTIAL` | mecanismos unitários existem; cenário completo não provado |
| T02 | `PARTIAL` | cadeias/proveniência separadas; sem prova completa objetivo/método |
| T03 | `NOT_PROVEN` | contrato CrossDomainEvent existe; ciclo multidomínio não executável |
| T04 | `PARTIAL` | DENY/fail-closed antes de tool existe; cenário completo não provado |
| T05 | `PARTIAL` | conflito por interseção pode ESCALATE; alternativa técnica não materializada |
| T06 | `PARTIAL` | competência bloqueia execução; falta Delegation Gate |
| T07 | `PARTIAL` | rebuild seletivo existe; falta detector de revision drift |
| T08 | `NOT_PROVEN` | falta mudança Fração/GT/domínio governada |
| T09 | `NOT_PROVEN` | falta delegação cross-provider + Instruction Adapters |
| T10 | `CONTRADICTED` | resume entra no runtime sem revalidar/reconstruir contexto |
| T11 | `CONTRADICTED` | ToolGateway pode usar AuthorityContext stale |
| T12 | `PARTIAL` | ESCALATE existe; trace completo/persistido de conflito não |

Totais: `PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`.

## Bloqueadores críticos atuais

### T10 — Resume canônico

Fluxo atual de `StateManager.resume()`:

`load checkpoint → load RunState → validar vínculo → runtime.resume(run, state) → persistir resultado`

Não há passo obrigatório de:

`freshness das fontes → re-resolver autoridade → detectar cadeias alteradas → re-bootstrap/rebuild Active Context`

Portanto um runtime físico correto pode retomar sob contexto institucional obsoleto.

### T11 — Fonte canônica muda durante Run

`AuthoritySnapshot` captura revisions durante resolução, mas `ToolGateway.execute()` recebe um `AuthorityContext` pronto e decide apenas sobre ele. Não existe gate que compare as revisões desse snapshot com a fonte atual antes de novo side effect.

Consequência: revogação/mudança pós-resolução pode não ser percebida antes de ação externa subsequente.

## Invariantes preservadas pelo GT

- contratos continuam mais estáveis que frameworks;
- Core não depende semanticamente de LangGraph/OpenAI/n8n;
- LangGraph permanece extra opcional;
- runtime/provider não ganham autoridade institucional;
- checkpoint técnico não vira fonte canônica;
- provider/modelo não altera identidade;
- side effects continuam atrás de gates + ledger;
- `POINTER_ONLY` não regrediu;
- B1 não alterou códigos/decisões;
- CI endurecida não mascara drift.

## Novos débitos e oportunidades

1. Implementar Core-owned freshness/revalidation gate para T10/T11.
2. Criar Delegation Gate/Port + contrato operacional antes de T06/T08/T09.
3. Implementar roteamento/reconciliação de obrigações CrossDomainEvent e gate de conclusão global para T03.
4. Persistir `DecisionTrace`/conflito para T12.
5. Avaliar pin/lock da versão de Pydantic usada para gerar schemas; o checker é fail-closed, mas faixa ampla reduz determinismo bit-a-bit entre ambientes.
6. Definir evolução contratual se dynamic LangGraph `interrupt()` com `Command(resume=...)` for necessário.
7. Checkpointer durável é decisão futura de deployment, não requisito para prova semântica A3.

## Gate de saída

O Harness **não** está autorizado a seguir diretamente para E2E.

`HARNESS STATUS = ARCHITECTURAL_BLOCKER`

### Próximo passo único

`RUN-REVALIDATION-GATE`

Especificar por testes e implementar no Core um boundary obrigatório antes de resume e side effect relevante:

`revision/freshness → detectar delta → preservar snapshot histórico → re-resolver autoridade → rebuild seletivo de contexto → ESCALATE se não seguro → executar boundary`

Nenhum runtime/provider pode executar essa função como fonte institucional.
