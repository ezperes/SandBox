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
- Decisão: `ToolDescriptor` permaneceu inicialmente como tipo interno do Core, sem entrar ainda no bundle de contratos Pydantic, para não alterar os contratos canônicos durante este incremento sem a migração/versionamento correspondente. A formalização no bundle será tratada em etapa específica de contratos.

## Incremento 6
- Objetivo: materializar `ModelPort` tipado, contratos neutros de modelo, roteamento substituível e primeiro adapter real sem acoplar o Core ao provider.
- Criados `ModelRequest`, `ModelSelection` e `ModelResponse` como contratos Pydantic neutros a provider.
- `ModelPort` passou de `dict → dict` para `ModelRequest → ModelResponse`.
- Criado `ModelRouter`, que seleciona por capacidade, preferência explícita e prioridade; seleção gera `ModelSelection` auditável.
- Criado `FakeModelAdapter` para testes e `OpenAIResponsesAdapter` como adapter real fino para Responses API, recebendo cliente injetado; o Core não importa o SDK OpenAI.
- O adapter valida boundary por `model_request_id`, `run_id`, provider e modelo selecionados antes de aceitar o retorno.
- Testes provam troca de provider/modelo sem alteração de `AgentIdentity` e tradução do Responses Adapter por stub de cliente.
- Tentativa que falhou: o primeiro teste comparava duas novas instâncias de `AgentIdentity` inteiras e falhou por diferença em `resolved_at`.
- Causa: timestamp de resolução é naturalmente distinto entre instâncias e não representa mudança de identidade institucional.
- Solução correta: congelar os campos estáveis de `AgentIdentity` antes do roteamento e verificar que permanecem inalterados; `resolved_at` fica fora da comparação semântica.
- Validação CI após correção: pytest, exportação de schemas e verificação de drift concluíram com sucesso.

## Incremento 7
- Objetivo: implementar `LangGraphAdapter` atrás de `RuntimePort`, preservando o runtime como mecanismo substituível e não como fonte institucional.
- Criado `LangGraphAdapter` sobre uma superfície mínima `CompiledGraphPort` (`invoke(input, config)`), evitando import obrigatório de LangGraph no Core.
- `run_id` é projetado para `configurable.thread_id`, permitindo checkpoint/interrupt/resume nativos do runtime sem promover o checkpoint técnico a verdade canônica.
- `execute` traduz o estado nativo retornado pelo grafo para `RunState`; `resume` invoca o thread existente com `input=None` e combina apenas campos técnicos com o `RunState` canônico prévio.
- O adapter não injeta `agent_id`, `authority_context_ref`, identidade ou autoridade no estado do grafo; essas semânticas continuam fora do runtime.
- Resume rejeita `RunState` estrangeiro antes de chamar o grafo.
- Idempotência de side effects permanece exclusivamente em `StatePort`/`ToolGateway`; o LangGraphAdapter não recebe prerrogativa para reexecutar side effects por conta própria.
- Testes adicionados para tradução de estado, uso de `thread_id`, resume e rejeição de estado canônico pertencente a outro Run.
- Decisão: não adicionar dependência obrigatória de `langgraph` ao `pyproject.toml` neste incremento. Causa evitada: transformar o framework em dependência semântica do pacote-base e quebrar o critério de remoção do LangGraph sem mudança dos contratos/Core. Solução: adapter estrutural por protocolo mínimo; integração com uma instância real de LangGraph pode ser adicionada como dependência opcional/extra sem alterar `RuntimePort`.
