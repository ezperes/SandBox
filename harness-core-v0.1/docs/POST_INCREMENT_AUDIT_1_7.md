# Auditoria Pós-Incrementos 1–7 — Harness Core V0.1

Data: 2026-08-29
Status: ATIVA — GATE ANTES DA PRIMEIRA PROVA END-TO-END

## Objetivo
Revisar conjuntamente os Incrementos 1–7 antes da primeira prova end-to-end, procurando divergências entre contratos canônicos, decisões arquiteturais, implementação e afirmações de validação.

## Retificações já executadas

### R1 — `NAO_APLICAVEL_JUSTIFICADO` sem justificativa real
**Problema:** o AuthorityResolver aceitava `NAO_APLICAVEL_JUSTIFICADO` sem texto justificativo e criava a justificativa genérica `explicitly justified`.

**Correção:** agora a forma exige `NAO_APLICAVEL_JUSTIFICADO:<justificativa não vazia>`; ausência de justificativa falha fechado com `AUTHORITY_UNRESOLVED`.

### R2 — Runtime podia injetar referências canônicas
**Problema:** o LangGraphAdapter aceitava do estado nativo `decision_refs` e `canonical_checkpoint_ref`.

**Correção:** `decision_refs` e `checkpoint_ref` passam a vir exclusivamente do estado canônico anterior/Core. Valores homônimos produzidos pelo runtime são ignorados.

## Itens obrigatórios antes do E2E

### A1 — Autoridade por interseção — CONCLUÍDO EM 2026-08-29
`AuthorityResolver` calcula allow-lists efetivos pela interseção das cadeias aplicáveis que declaram `allowed_scopes`. Cadeias sem allow-list não acrescentam restrição positiva; ausência total de whitelist é representada por `*`; interseção vazia não autoriza nenhuma ação automaticamente. Proibição explícita continua prevalecendo.

Regressões cobertas: ação comum → `ALLOW`; ação exclusiva de uma cadeia → `ESCALATE`; interseção vazia → nenhuma autorização comum; ausência de whitelist → `*`; `MESMA_CADEIA_TATICA` preserva o conjunto tático.

### A2 — Ledger idempotente — CONCLUÍDO EM 2026-08-29
O claim binário foi substituído por ledger de execução com estados `PENDING | COMPLETED | FAILED | UNKNOWN`, preservando resultado, `evidence_refs`, erro e necessidade de reconciliação.

Semântica aplicada:
- `PENDING`: efeito em andamento/indeterminado; retry automático bloqueado;
- `COMPLETED`: efeito comprovadamente concluído; repetição bloqueada;
- `FAILED`: falha conhecida; retry exige decisão explícita;
- `UNKNOWN`: não é possível determinar se o efeito externo ocorreu; retry automático bloqueado até reconciliação.

`ToolGateway` integra o ledger ao boundary de side effects. Timeout/exceção após atravessar o boundary não é tratado como simples falha segura: o registro pode ir para `UNKNOWN` para evitar duplicação externa.

Documentação específica: `docs/A2_IDEMPOTENCY_LEDGER_IMPLEMENTATION_LOG.md` e `docs/A2_IDEMPOTENCY_LEDGER_IMPLEMENTATION_REPORT.md`.

### A3 — LangGraph ainda não foi validado contra a biblioteca real
Existe `LangGraphAdapter` atrás de superfície mínima (`CompiledGraphPort`) e os testes atuais usam StubGraph. O Incremento 7 prova boundary/tradução compatível, não integração física com pacote/checkpointer/interrupt reais.

**Ação:** adicionar teste de integração com versão fixada do LangGraph antes de declarar runtime físico comprovado.

### A4 — OpenAIResponsesAdapter ainda não teve chamada live
O adapter traduz uma superfície Responses compatível por cliente injetado; testes usam stub.

**Ação:** na prova E2E executar chamada real ou declarar explicitamente que o E2E usa `FakeModelAdapter`, mantendo teste live como gate separado.

### A5 — Semântica de refs de tarefa — CONCLUÍDO EM 2026-08-29
Decisão canônica V0.1: `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` são **apontadores (`POINTER_ONLY`)**, não conteúdo já materializado no Active Context.

Consequências obrigatórias:
- esses quatro campos não consomem `max_context_tokens` apenas por existirem no `TaskContext`;
- o `ContextBuilder` não lê suas fontes automaticamente;
- eles não entram em `token_usage`/proveniência enquanto permanecem apenas apontadores;
- para virarem conteúdo ativo, devem passar por uma etapa explícita de materialização, que então deve aplicar budget, proveniência, revisão e deduplicação;
- conteúdo materializado não pode ser disfarçado nesses campos para escapar do budget.

O contrato ganhou `ReferenceSemantics` e `TaskContext.supporting_ref_semantics`, fixado em `POINTER_ONLY` na V0.1. Marcar esses refs como `MATERIALIZED_CONTEXT` dentro de `TaskContext` falha fechado. Testes provam que as fontes desses refs não são lidas e que não alteram o budget ativo.

## Melhorias recomendadas, não bloqueantes isoladamente

### B1 — Erro compartilhado
`HarnessResolutionError` nasceu no pacote `core.identity` e passou a ser reutilizado por autoridade, estado e tools. Mover para `core.errors` reduz acoplamento semântico indevido.

### B2 — ToolDescriptor ainda é contrato interno
Antes de interfaces externas estáveis convém versionar/formalizar `ToolDescriptor` em contrato Pydantic se ele atravessar boundaries, persistência ou configuração declarativa.

### B3 — Estado técnico ≠ conclusão institucional
O LangGraphAdapter traduz `harness_status=COMPLETED` em `RunStatus.COMPLETED`. Na composição E2E, conclusão institucional só deve ocorrer após Evidence + VerificationResult + gates finais.

### B4 — Resume instruction
`Checkpoint.resume_instruction` é persistido, mas o `StateManager.resume()` ainda não o entrega explicitamente ao RuntimePort. Definir se é orientação auditável apenas para Core/coordenador ou parte obrigatória do payload de retomada.

### B5 — Verificação de schemas gerados
A CI executa `git diff --exit-code -- harness/schemas`, mas arquivos novos não rastreados podem escapar desse check. Endurecer a CI para também verificar `git status --porcelain -- harness/schemas` antes de considerar o bundle de schemas integralmente protegido contra drift.

## Gate de saída desta auditoria
Antes da primeira prova E2E completa:
1. ~~A1 — interseção de autoridade~~ CONCLUÍDO;
2. ~~A2 — ledger idempotente com estado~~ CONCLUÍDO;
3. ~~A5 — semântica/budget/proveniência dos refs~~ CONCLUÍDO;
4. A3 — integração física com LangGraph real;
5. A4 — declarar FakeModelAdapter ou executar provider live.

As retificações R1 e R2 permanecem cobertas por testes de regressão.
