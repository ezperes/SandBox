# Auditoria Pós-Incrementos 1–7 — Harness Core V0.1

Data: 2026-08-29
Status: ATIVA — GATE ANTES DA PRIMEIRA PROVA END-TO-END

## Objetivo
Revisar conjuntamente os Incrementos 1–7 antes da primeira prova end-to-end, procurando divergências entre contratos canônicos, decisões arquiteturais, implementação e afirmações de validação.

## Retificações já executadas

### R1 — `NAO_APLICAVEL_JUSTIFICADO` sem justificativa real
**Problema:** o AuthorityResolver aceitava `NAO_APLICAVEL_JUSTIFICADO` sem texto justificativo e criava a justificativa genérica `explicitly justified`.

**Risco:** transformar ausência de autoridade técnica em exceção válida sem fundamento auditável.

**Correção:** agora a forma exige `NAO_APLICAVEL_JUSTIFICADO:<justificativa não vazia>`; ausência de justificativa falha fechado com `AUTHORITY_UNRESOLVED`.

### R2 — Runtime podia injetar referências canônicas
**Problema:** o LangGraphAdapter aceitava do estado nativo `decision_refs` e `canonical_checkpoint_ref`.

**Risco:** permitir que runtime externo promovesse seus próprios valores a decisão/checkpoint canônicos do Harness.

**Correção:** `decision_refs` e `checkpoint_ref` passam a vir exclusivamente do estado canônico anterior/Core. Valores homônimos produzidos pelo runtime são ignorados.

## Itens obrigatórios antes do E2E

### A1 — Autoridade deve obedecer interseção entre cadeias — CONCLUÍDO EM 2026-08-29
**Problema anterior:** `allowed_scopes` era agregado por união dos documentos tático/técnico/normativo, podendo autorizar uma ação aceita por apenas uma das cadeias.

**Correção implementada:** `AuthorityResolver` agora calcula os allow-lists efetivos pela interseção de todas as cadeias aplicáveis que declaram `allowed_scopes`. Cadeias que não declaram allow-list não adicionam restrição positiva; quando nenhuma cadeia declara allow-list, o contexto usa `*` para representar ausência explícita de whitelist, mantendo proibições como regra prevalente. Quando allow-lists declarados têm interseção vazia, nenhuma ação é autorizada automaticamente e a decisão termina em `ESCALATE`.

**Regressões cobertas:**
- ação comum às cadeias → `ALLOW`;
- ação permitida apenas pela cadeia tática → `ESCALATE`;
- interseção vazia → nenhuma das ações exclusivas é autorizada;
- ausência total de allow-list → `*`, ainda subordinado a `forbidden_scopes`;
- `MESMA_CADEIA_TATICA` preserva o mesmo conjunto efetivo da cadeia tática.

**Nota:** `competence_refs` permanece agregada separadamente porque competência não é autoridade. Qualquer evolução da semântica de competência por cadeia deve ser tratada em item próprio, sem reintroduzir união de autoridade.

### A2 — Idempotência precisa de ledger de execução, não apenas claim permanente
**Estado atual:** `StatePort.claim_idempotency()` grava uma chave em set antes da chamada externa e não possui estados intermediários/finais.

**Risco:** se a chamada externa falhar antes de produzir o efeito, a chave fica permanentemente ocupada e impede retry legítimo; se houver timeout após efeito externo, o Harness também não consegue distinguir `não executado`, `executado` e `resultado desconhecido`.

**Correção necessária:** substituir claim binário por registro idempotente com ao menos `PENDING | COMPLETED | UNKNOWN/FAILED`, resultado/evidence refs quando conhecidos e estratégia explícita de reconciliação/retry.

### A3 — LangGraph ainda não foi validado contra a biblioteca real
**Estado atual:** existe `LangGraphAdapter` atrás de uma superfície mínima (`CompiledGraphPort`) e os testes usam StubGraph.

**Retificação de linguagem:** o Incremento 7 prova o boundary e a tradução LangGraph-compatível, mas ainda não prova integração real com pacote LangGraph, checkpointer ou interrupt/resume nativos.

**Ação:** adicionar teste de integração com versão fixada do LangGraph antes de declarar o runtime real comprovado.

### A4 — OpenAIResponsesAdapter ainda não teve chamada live
**Estado atual:** o adapter traduz uma superfície Responses compatível por cliente injetado; testes usam stub.

**Retificação de linguagem:** adapter de provider implementado, mas integração live com credencial/provider real ainda não comprovada.

**Ação:** na prova E2E, executar ao menos uma chamada real ou registrar explicitamente que a prova usa FakeModelAdapter e que o teste live é gate separado.

### A5 — Proveniência e budget dos refs de tarefa precisam de semântica explícita
**Estado atual:** `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` são copiados do registro da Tarefa de Trabalho para `TaskContext`; não entram no `token_usage` do ContextBuilder e não recebem proveniência por bloco.

**Risco:** se esses refs representarem conteúdo já materializado no Active Context, a implementação subconta budget e não cumpre proveniência/revisão por bloco. Se forem somente apontadores, o comportamento atual é aceitável.

**Correção necessária:** formalizar no contrato que são `refs-only` até materialização posterior, ou submetê-los ao mesmo pipeline de materialização/budget/proveniência.

## Melhorias recomendadas, não bloqueantes isoladamente

### B1 — Erro compartilhado
`HarnessResolutionError` nasceu no pacote `core.identity` e passou a ser reutilizado por autoridade, estado e tools. Mover para `core.errors` reduz acoplamento semântico indevido.

### B2 — ToolDescriptor ainda é contrato interno
A decisão do Incremento 5 foi deliberada, mas antes de interfaces externas estáveis convém versionar/formalizar `ToolDescriptor` em contrato Pydantic se ele for atravessar boundaries, persistência ou configuração declarativa.

### B3 — Estado técnico ≠ conclusão institucional
O LangGraphAdapter traduz `harness_status=COMPLETED` em `RunStatus.COMPLETED`. Na composição E2E, conclusão institucional só deve ser encerrada após Evidence + VerificationResult + gates finais. A prova E2E deve demonstrar essa distinção explicitamente.

### B4 — Resume instruction
`Checkpoint.resume_instruction` é persistido, mas o `StateManager.resume()` ainda não o entrega explicitamente ao RuntimePort. Definir se ele é orientação auditável apenas para o Core/coordenador ou parte obrigatória do payload de retomada.

## Gate de saída desta auditoria
Antes da primeira prova E2E completa:
1. ~~corrigir A1 (interseção de autoridade);~~ CONCLUÍDO;
2. corrigir A2 (ledger idempotente com estado);
3. decidir e documentar A5;
4. executar teste real de LangGraph (A3) ou manter a prova explicitamente como compatibilidade de boundary;
5. declarar claramente se o E2E usa modelo real ou fake e, se necessário, separar teste live do provider (A4).

As retificações R1 e R2 já foram aplicadas e devem permanecer cobertas por testes de regressão.
