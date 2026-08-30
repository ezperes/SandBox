# Implementation Log — Harness Core V0.1

## Incremento 1
- Objetivo: materializar contratos canônicos e RuntimePort fake sem LangGraph.
- Decisão: Pydantic V2 como fonte dos schemas; JSON Schema gerado, não mantido manualmente.
- Decisão: Protocols Python para Ports, evitando dependência de framework de DI.
- Risco evitado: não importar LangGraph/OpenAI/n8n no Core.
- Tentativa que falhou: `python scripts/export_schemas.py` falhou com `ModuleNotFoundError: harness`.
- Causa: execução direta do script não adicionava a raiz do repositório ao `sys.path` antes de instalação editable.
- Solução correta: resolver a raiz do repositório no próprio script e adicioná-la ao `sys.path` antes do import.
- Validação local final: 6 testes verdes; 14 schemas exportados.

## Incremento 2
- Objetivo: implementar `IdentityResolver` + `AuthorityResolver` sobre `SourcePort`.
- `IdentityResolver` valida `AgentIdentity`, conserva `source_ref` e captura `source_revision_ref`; fonte ausente/inválida falha fechada com `IDENTITY_UNRESOLVED`.
- `AuthorityResolver` resolve cadeias TACTICAL, TECHNICAL e NORMATIVE; suporta `MESMA_CADEIA_TATICA` e `NAO_APLICAVEL_JUSTIFICADO` explicitamente.
- `AuthoritySnapshot` captura revisões das fontes para auditoria histórica.
- Decisão determinística implementada: proibição explícita → `DENY`; cadeia/escopo/competência não resolvidos → `ESCALATE`; gate humano → `REQUIRE_APPROVAL`; caso válido → `ALLOW`.
- Autoridade ≠ competência: competência requerida ausente nunca vira autorização implícita.
- Criado `InMemorySourceAdapter` para testes sem acoplamento ao Google Drive/Livro da Vida físico.
- Criado CI GitHub Actions para `pytest`, exportação de schemas e verificação de drift.

## Incremento 3
- Objetivo: implementar `BootstrapResolver` + `ContextBuilder`.
- Bootstrap resolve uma única entrada em até três rotas segmentadas: TACTICAL, TECHNICAL e NORMATIVE; não materializa conteúdo.
- ContextBuilder lê apenas referências candidatas, prioriza contexto obrigatório/alta prioridade, aplica orçamento de tokens e deduplica referências.
- Cada bloco carregado preserva proveniência de cadeia em `ContextBuildResult.provenance`.
- `TaskContext` recebe referências separadas por cadeia e `bootstrap_trace_ref` único.
- Re-Bootstrap parcial preserva cadeias não afetadas e relê apenas a cadeia alterada mais a própria Tarefa de Trabalho.
- Fail closed: contexto marcado `required` que não cabe no orçamento encerra com erro em vez de truncamento silencioso.
- Testes adicionados para três rotas, contexto mínimo, proveniência, budget obrigatório e Re-Bootstrap parcial.
- Tentativa descartada durante implementação: reconstruir o contexto inteiro e restaurar depois as cadeias não alteradas. Causa: apesar do resultado final correto, releria fontes desnecessariamente e violaria economia de tokens/I/O. Solução correta: preservar refs e token usage das cadeias intactas e materializar somente `changed_chains`.

## Incremento 4
- Objetivo: implementar `RunState` + `Checkpoint` + persistência substituível e proteção contra repetição de side effects.
- Criado `StatePort` com operações de persistência/recuperação de `RunState`, `Checkpoint` e claim de idempotência.
- Criado `InMemoryStateAdapter` para desenvolvimento/testes, com cópia defensiva dos objetos persistidos e claim atômico de chave de idempotência.
- Criado `StateManager` como camada do Core responsável por persistir estado, criar checkpoint canônico, validar vínculo checkpoint↔Run e retomar via `RuntimePort`.
- Resume falha fechado com `CHECKPOINT_INVALID` quando checkpoint/estado não existe, pertence a outro Run ou não coincide com `checkpoint_ref` do estado.
- Side effect passa por ledger Core-owned; repetição da mesma operação/business key é bloqueada antes de nova execução externa.
- O checkpoint canônico permanece independente do mecanismo de checkpoint de qualquer Runtime Adapter.

## Incremento 5
- Objetivo: implementar Tool Registry/Gateway + Policy/Risk/Approval Gate antes de qualquer boundary externo.
- Criado `ToolDescriptor` com `tool_id`, escopo de ação, risco, side effect, competência requerida, aprovação, evidência e exigência de idempotência.
- `ToolRegistry` exige registro explícito e rejeita duplicidade; tool não registrada falha fechado.
- Ordem de gate implementada: ferramenta registrada → autoridade/escopo → competência → aprovação → business key/idempotência → execução → evidência requerida.
- Side effect só chama o adapter após gate Core-owned.

## Incremento 6
- Objetivo: materializar `ModelPort` tipado, contratos neutros de modelo, roteamento substituível e primeiro adapter de provider sem acoplar o Core ao provider.
- Criados `ModelRequest`, `ModelSelection` e `ModelResponse` como contratos Pydantic neutros a provider.
- Criado `ModelRouter`, `FakeModelAdapter` e `OpenAIResponsesAdapter` por cliente injetado.
- Provider/modelo não altera identidade institucional.

## Incremento 7
- Objetivo: implementar `LangGraphAdapter` atrás de `RuntimePort`, preservando o runtime como mecanismo substituível e não como fonte institucional.
- `run_id` é projetado em `thread_id`; estado nativo é traduzido para `RunState`.
- Runtime não injeta refs canônicos de decisão/checkpoint.
- A3 posteriormente comprovou LangGraph real `1.2.11` com `StateGraph`, `MemorySaver`, interrupt e resume.

## GT paralelo — integração e auditoria — 2026-08-29
- BASE comum: `59d3eb987136ec628bcaba4b45949fb81b2616a2`.
- A3: ACCEPT.
- B1: ACCEPT.
- CI-01: ACCEPT_WITH_FIXES; baseline de schemas materializado.
- ARCH-01: ACCEPT.
- Estado integrado final anterior ao freshness gate: T10/T11 `CONTRADICTED`; E2E bloqueado.

## CORE-FRESHNESS-GATE — branch candidata — 2026-08-29

### Objetivo
Eliminar a causa estrutural comum de T11/T10 com uma família Core-owned de freshness/revalidation, sem criar um segundo sistema de autoridade e sem transferir semântica institucional a Tool/Runtime adapters.

### T11 — side effect freshness
- Criado `AuthorityFreshnessGate`.
- Cada cadeia aplicável compara `source_revision_refs` capturados no `AuthorityContext` com `revision_ref` atual lido via `SourcePort`.
- Ausência de autoridade/ref de revisão, fonte ilegível, revisão atual ausente ou mismatch falha fechado com `AUTHORITY_UNRESOLVED` na V0.1.
- `ToolGateway` aplica freshness em side effects **antes** de autorização final, reserva idempotente e chamada ao adapter.
- Prova: `rev-A → fonte rev-B → contexto rev-A reutilizado → mismatch antes do ToolPort → adapter não chamado`.

### T10 — resume freshness
- Criado `ResumeFreshnessGate`.
- Antes do resume: re-resolve `AgentIdentity`, re-resolve `AuthorityContext`, compara revisions, deriva `changed_chains` e executa `ContextBuilder.rebuild_partial()` somente nas cadeias afetadas.
- `StateManager.resume()` passou a exigir freshness Core-owned; sem gate, falha fechado antes do runtime.
- Se a autoridade alterada não resolver, `RuntimePort.resume()` não é chamado.
- Run é reatrelado ao novo `authority_context_ref` e `task_context_ref` antes do boundary do runtime.

### Persistência auditável da revalidação
- Criado `RevalidationAuditRecord` (`RV-*`).
- Registro contém: boundary sensível, previous/current authority refs, previous/current TaskContext refs, `AuthoritySnapshot` atual, Bootstrap trace, cadeias alteradas, flag de mudança de identidade e contexto que liberou a operação.
- `StateManager.resume()` persiste `RV-*` e adiciona o ponteiro em `RunState.decision_refs` **antes** de chamar `RuntimePort.resume()`.
- A implementação preserva o estado histórico em vez de sobrescrever silenciosamente a decisão anterior.

### Tentativa que falhou → causa → solução correta
1. Clone/teste local → container sem DNS para `github.com` → usar GitHub Actions da PR como evidência executável.
2. Criação inicial de PR sem commit entre base/head → GitHub rejeitou corretamente → criar primeiro commit do work contract e só então abrir PR.
3. Teste T10 esperava lista exata de contexto apenas com excerpt → Bootstrap também inclui route ref da autoridade → corrigir o teste para a invariante semântica (`CTX-T1` substituído por `CTX-T2`, cadeia não afetada preservada), sem alterar produção.
4. Após adicionar persistência `RV-*`, test double antigo não fornecia `authority_snapshot`/trace necessários → contrato do teste ficou abaixo da nova exigência auditável → atualizar o double para representar uma preparação válida; não enfraquecer a persistência.

### Validação
- PR draft #17, branch `worker/core-freshness-gate`.
- HEAD de implementação/documentação desta etapa evolui na própria PR; consultar PR para SHA corrente antes de integração.
- CI após persistência auditável: **57 passed**, **17 schemas exportados**, **schema drift clean**, job `SUCCESS`.
- Nenhum contrato canônico/schema precisou ser alterado para acomodar freshness.

### Estado formal
- A implementação é **candidata**, ainda não canônica: PR #17 permanece draft e sem merge.
- Evidência executável remove os caminhos contraditórios conhecidos de T10/T11 na branch candidata, mas a classificação canônica T01–T12 só deve mudar após reauditoria T07/T10/T11/T12 e integração pós-CI.

### Próximo passo único
`reauditar T07/T10/T11/T12 na PR #17 → emitir ACCEPT/REWORK → se ACCEPT, integrar PR #17 → CI pós-merge → atualizar auditoria canônica → só então decidir A4/E2E`.
