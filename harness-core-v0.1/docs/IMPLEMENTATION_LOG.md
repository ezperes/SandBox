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
- Side effect passa por `claim_side_effect(run_id, operation, business_key)`; segunda tentativa com a mesma chave retorna `RETRY_BLOCKED` antes de nova execução externa.
- O checkpoint canônico permanece independente do mecanismo de checkpoint de qualquer Runtime Adapter.
- Testes adicionados para persistência por valor, checkpoint+resume, rejeição de checkpoint cruzado e idempotência de side effects.
- Decisão: idempotência foi mantida no `StatePort`, e não no Runtime, para que a proteção sobreviva à troca de LangGraph/n8n/outro executor.

## Incremento 5
- Objetivo: implementar Tool Registry/Gateway + Policy/Risk/Approval Gate antes de qualquer boundary externo.
- Criado `ToolDescriptor` com `tool_id`, escopo de ação, risco, side effect, competência requerida, aprovação, evidência e exigência de idempotência.
- `ToolRegistry` exige registro explícito e rejeita duplicidade; tool não registrada falha fechado com `TOOL_UNAVAILABLE`.
- `ToolGateway` consulta `AuthorityResolver.decide` antes de chamar `ToolPort`.
- Ordem de gate implementada: ferramenta registrada → autoridade/escopo → competência → aprovação → business key/idempotência → execução → evidência requerida.
- Proibição explícita termina em `ACTION_FORBIDDEN`; competência insuficiente em `COMPETENCE_INSUFFICIENT`; aprovação pendente em `APPROVAL_REQUIRED`; side effect sem business key em `SIDE_EFFECT_UNKNOWN`.
- Side effect só chama o adapter após claim de idempotência; repetição da mesma operação/business key é bloqueada por `RETRY_BLOCKED` antes de nova chamada externa.
- `FakeToolAdapter` registra chamadas para provar em teste que DENY/ESCALATE/REQUIRE_APPROVAL/erros de idempotência não atravessam o boundary.
- Evidência obrigatória ausente após execução retorna `VERIFICATION_FAILED`, preservando a distinção entre resultado produzido e resultado aceitável.
- Testes adicionados para side effect sem chave, duplicidade, proibição, competência, aprovação humana, evidência e tool ausente.
- Decisão: `ToolDescriptor` permaneceu inicialmente como tipo interno do Core, sem entrar ainda no bundle de contratos Pydantic, para não alterar os contratos canônicos durante este incremento sem a migração/versionamento correspondente.

## Incremento 6
- Objetivo: materializar `ModelPort` tipado, contratos neutros de modelo, roteamento substituível e primeiro adapter de provider sem acoplar o Core ao provider.
- Criados `ModelRequest`, `ModelSelection` e `ModelResponse` como contratos Pydantic neutros a provider.
- `ModelPort` passou de `dict → dict` para `ModelRequest → ModelResponse`.
- Criado `ModelRouter`, que seleciona por capacidade, preferência explícita e prioridade; seleção gera `ModelSelection` auditável.
- Criado `FakeModelAdapter` para testes e `OpenAIResponsesAdapter` como adapter fino para Responses API, recebendo cliente injetado; o Core não importa o SDK OpenAI.
- O adapter valida boundary por `model_request_id`, `run_id`, provider e modelo selecionados antes de aceitar o retorno.
- Testes provam troca de provider/modelo sem alteração de `AgentIdentity` e tradução do Responses Adapter por stub de cliente.
- Tentativa que falhou: o primeiro teste comparava duas novas instâncias de `AgentIdentity` inteiras e falhou por diferença em `resolved_at`.
- Causa: timestamp de resolução é naturalmente distinto entre instâncias e não representa mudança de identidade institucional.
- Solução correta: congelar os campos estáveis de `AgentIdentity` antes do roteamento e verificar que permanecem inalterados.
- Retificação pós-auditoria: a implementação comprova adapter e tradução por cliente compatível/stub; chamada live ao provider ainda não foi comprovada.

## Incremento 7
- Objetivo: implementar `LangGraphAdapter` atrás de `RuntimePort`, preservando o runtime como mecanismo substituível e não como fonte institucional.
- Criado `LangGraphAdapter` sobre uma superfície mínima `CompiledGraphPort` (`invoke(input, config)`), evitando import obrigatório de LangGraph no Core.
- `run_id` é projetado para `configurable.thread_id`, permitindo checkpoint/interrupt/resume nativos do runtime sem promover o checkpoint técnico a verdade canônica.
- `execute` traduz o estado nativo retornado pelo grafo para `RunState`; `resume` invoca o thread existente com `input=None` e combina apenas campos técnicos com o `RunState` canônico prévio.
- O adapter não injeta `agent_id`, `authority_context_ref`, identidade ou autoridade no estado do grafo.
- Resume rejeita `RunState` estrangeiro antes de chamar o grafo.
- Idempotência de side effects permanece exclusivamente em `StatePort`/`ToolGateway`.
- Retificação pós-auditoria: refs de decisão/checkpoint agora só são preservados do estado canônico anterior/Core; valores homônimos do runtime são ignorados.

## Auditoria transversal pós-Incrementos 1–7 — estado pré-GT
- Documento: `docs/POST_INCREMENT_AUDIT_1_7.md`.
- A1 concluído: interseção de allow-lists aplicáveis.
- A2 concluído posteriormente: ledger idempotente com estados e reconciliação.
- A5 concluído posteriormente: supporting refs `POINTER_ONLY`.
- A3 permanecia pendente antes do GT: integração física LangGraph real.
- A4 permanece separado: chamada live ou declaração explícita de FakeModelAdapter.

## GT paralelo — integração e auditoria — 2026-08-29

### Estado recebido
Quatro branches nasceram do mesmo `BASE_SHA 59d3eb987136ec628bcaba4b45949fb81b2616a2`:
- `worker/b1-core-errors` → HEAD `10c01bba5378c7341af22b186844707830bcf9c8`;
- `worker/a3-langgraph-real` → HEAD `66d8c0a62646d8818d4ea805e976350b9e59ea85`;
- `worker/ci-schema-drift` → HEAD `3c2561a628656d86f9ed0a17dbafbfe24d21a971`;
- `worker/arch-t01-t12-audit` → HEAD `88fc69566838b33153521df9d5714e8fd7396f95`.

### Review dos workers
- B1 `ACCEPT`: move `HarnessResolutionError` para `harness.core.errors`, mantendo re-export legado do mesmo objeto e sem alterar payload/códigos/raises.
- A3 `ACCEPT`: prova física LangGraph `1.2.11` com `StateGraph`, `MemorySaver`, interrupt estático e resume, sem promover runtime a autoridade institucional.
- CI-01 `ACCEPT_WITH_FIXES`: detector correto para tracked/untracked/ignored; BASE_SHA não possuía schemas rastreados e exigia baseline.
- ARCH-01 `ACCEPT`: auditoria documental independente sem mudanças de produção.

### Ordem executada em staging
`B1 → A3 → CI-01 → materializar schemas → ARCH-01 → CI conjunta → auditoria final`.

### CI-01 — tentativa que falhou → causa → solução correta
- Situação antiga: `git diff --exit-code -- harness/schemas` retornava 0 diante de arquivo novo/untracked.
- Causa: `git diff` não enumera arquivos que nunca entraram no índice.
- Solução: `check_schema_drift.py` usa `git status --porcelain=v1 --untracked-files=all --ignored=matching -- harness/schemas`.
- Problema revelado pelo fix: BASE_SHA não tinha `harness/schemas/**` rastreado; o hardening correto tornaria a CI vermelha imediatamente.
- Solução do Integrador: workflow temporário de staging executou o exportador canônico em Python 3.11 e versionou 17 schemas + `all.schemas.json`; workflow temporário foi removido depois.

### A3 — tentativa que falhou → causa → solução correta
- Tentativa local de clone/execução não resolveu `github.com`/pacote.
- Solução: GitHub Actions executou a integração física com versão fixada.
- Resultado: runtime físico comprovado, mas isso não altera o fato de que T10 institucional exige revalidação Core-owned antes do resume técnico.

### B1 — tentativa que falhou → causa → solução correta
- Validação local ficou limitada pelo ambiente; integração GitHub + Actions confirmou semântica e compatibilidade.
- O único risco residual identificado é `__module__` diferente para introspecção/pickle; nenhum contrato atual o considera parte da API pública.

### Evento concorrente de integração
- Durante o staging, `harness-core-v0.1` avançou de `59d3eb...` para `29f6d72...`.
- Causa: outro fluxo integrou B1 diretamente.
- Ação: nenhum overwrite/rebase silencioso. O novo commit foi auditado e confirmado como merge do mesmo B1 já aceito.
- Solução: PR de integração final foi recalculada contra a nova base e a CI testou o merge resultante.

### Validação conjunta
GitHub Actions `Harness Core CI` sobre o merge testado:
- CPython `3.11.16`;
- Pydantic `2.13.5`;
- pytest `8.4.2`;
- LangGraph `1.2.11`;
- `50 passed in 0.69s`;
- `17 schemas` exportados;
- `schema export matches the Git-tracked state`.

### Auditoria T01–T12 pós-integração
`PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`.

- PARTIAL: T01, T02, T04, T05, T06, T07, T12.
- NOT_PROVEN: T03, T08, T09.
- CONTRADICTED/P0: T10, T11.

T10 permanece contradito porque `StateManager.resume()` chama `RuntimePort.resume()` sem revalidar revisões/autoridade/contexto.
T11 permanece contradito porque `ToolGateway.execute()` aceita `AuthorityContext` pronto sem freshness gate antes de side effect.

### Estado final da auditoria
- A1: sem regressão.
- A2: sem regressão.
- A3: concluído fisicamente.
- A5: sem regressão; supporting refs continuam `POINTER_ONLY`.
- CI schema drift: corrigido e comprovado no merge conjunto.
- `HarnessResolutionError`: propriedade neutra consolidada sem mudança semântica pública observável.
- Arquitetura Core/Ports/Adapters: preservada.
- E2E institucional: bloqueado por T10/T11.

### Próximo passo único
Implementar freshness/revision gate Core-owned antes de side effects no `ToolGateway`, fechando T11 com fail-closed quando as revisões atuais não corresponderem ao `AuthorityContext`. Projetar o primitivo para reutilização posterior no resume de T10.
