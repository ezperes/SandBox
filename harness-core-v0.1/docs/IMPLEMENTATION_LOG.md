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
- Objetivo: materializar `ModelPort` tipado, contratos neutros de modelo, roteamento substituível e primeiro adapter de provider sem acoplar o Core ao provider.
- Criados `ModelRequest`, `ModelSelection` e `ModelResponse` como contratos Pydantic neutros a provider.
- `ModelPort` passou de `dict → dict` para `ModelRequest → ModelResponse`.
- Criado `ModelRouter`, que seleciona por capacidade, preferência explícita e prioridade; seleção gera `ModelSelection` auditável.
- Criado `FakeModelAdapter` para testes e `OpenAIResponsesAdapter` como adapter fino para Responses API, recebendo cliente injetado; o Core não importa o SDK OpenAI.
- O adapter valida boundary por `model_request_id`, `run_id`, provider e modelo selecionados antes de aceitar o retorno.
- Testes provam troca de provider/modelo sem alteração de `AgentIdentity` e tradução do Responses Adapter por stub de cliente.
- Tentativa que falhou: o primeiro teste comparava duas novas instâncias de `AgentIdentity` inteiras e falhou por diferença em `resolved_at`.
- Causa: timestamp de resolução é naturalmente distinto entre instâncias e não representa mudança de identidade institucional.
- Solução correta: congelar os campos estáveis de `AgentIdentity` antes do roteamento e verificar que permanecem inalterados; `resolved_at` fica fora da comparação semântica.
- Validação CI após correção: pytest, exportação de schemas e verificação de drift concluíram com sucesso.
- Retificação pós-auditoria: a implementação comprova adapter e tradução por cliente compatível/stub; chamada live ao provider ainda não foi comprovada.

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
- Retificação pós-auditoria: o estado nativo podia fornecer `decision_refs`/`canonical_checkpoint_ref`; isso daria ao runtime capacidade de injetar refs canônicos. Correção aplicada: refs de decisão/checkpoint agora só são preservados do estado canônico anterior/Core; valores homônimos do runtime são ignorados.
- Retificação de linguagem: a prova inicial usava `StubGraph`; o GT posterior adicionou a prova física real descrita abaixo.

## Auditoria transversal pós-Incrementos 1–7 — estado anterior ao GT
- Documento: `docs/POST_INCREMENT_AUDIT_1_7.md`.
- Correção aplicada: `NAO_APLICAVEL_JUSTIFICADO` sem justificativa real deixou de ser aceito; agora falha fechado.
- Correção aplicada: runtime não pode mais injetar `decision_refs`/`checkpoint_ref` canônicos.
- A1 CONCLUÍDO: `allowed_scopes` efetivo é interseção das allow-lists declaradas pelas cadeias aplicáveis.
- A2 foi posteriormente concluído com ledger idempotente com estado.
- A5 foi posteriormente concluído com `POINTER_ONLY` formalizado.

## GT paralelo A3 + B1 + CI-01 + ARCH-01 — Integração 2026-08-29

### Estado de nascimento
- BASE_SHA comum: `59d3eb987136ec628bcaba4b45949fb81b2616a2`.
- Todos os workers mantiveram branches isoladas e não escreveram diretamente na integração.
- Branch temporária do Integrador: `integration/gt-harness-core-v0.1`.

### B1 — erro compartilhado
- Resultado: `ACCEPT`.
- `HarnessResolutionError` movido de `core.identity` para `core.errors`.
- Re-export legado preservado.
- Testes provam mesma classe/payload/string observável.
- Merge de integração: `627ae2305eccd3c3df5ae60a69b0869934da2e3a`.

### A3 — LangGraph real
- Resultado: `ACCEPT`.
- `langgraph==1.2.11` adicionado apenas aos extras `dev`/`langgraph`.
- Teste real usa `StateGraph`, compiled graph, `MemorySaver`, static interrupt e resume no mesmo thread.
- Runtime continua sem autoridade/identidade institucional.
- Merge de integração: `1032e020d71963f7fbd4df7fb845cc9635f9958d`.
- Decisão de interpretação: não introduzir dynamic `Command(resume=<payload>)` porque `RuntimePort` V0.1 não possui resume payload; static interrupt é a prova física compatível com o contrato atual.

### CI-01 — tentativa que falhou → causa → solução correta
- Worker implementou checker correto de tracked/untracked/ignored.
- Primeira CI remota do worker: `pytest` PASS → export schemas PASS → `check_schema_drift.py` FAIL.
- Causa: no BASE_SHA nenhum `harness/schemas/**` estava versionado; o novo checker revelou todos como `??`.
- Isso confirmou o `SCOPE_EXPANSION_REQUEST` do worker e o comportamento fail-closed.
- Solução correta do Integrador: gerar os schemas no próprio GitHub Actions, versionar 17 schemas + `all.schemas.json`, remover o workflow temporário e validar o baseline por `pytest + export + git diff`.
- Baseline merge: `58aea84585e7c35dc7039be98ed3fde9319e98d4`.
- Em seguida CI-01 foi revalidado sobre esse baseline: `pytest` PASS → export PASS → checker estrito PASS.
- CI-01 merge: `85658371f9db06a3cbcb68cd7649bc54a4005a3c`.

### ARCH-01 — tentativa de busca corrigida
- Resultado: `ACCEPT` como auditoria do BASE_SHA.
- Uma busca de código incompleta inicialmente sugeriu ausência de `CrossDomainEvent`.
- Causa: resultado de code search tinha cobertura incompleta e não podia sustentar prova negativa.
- Solução correta: leitura direta do bundle de contratos, que confirmou `CrossDomainEvent` e `InstructionProfile`; conclusão corrigida antes do Gap Map final.
- Merge de integração: `799278f94d5f0bd59a631148117d8566e58a2197`.

### Nova auditoria após os quatro merges
- A3 fecha a prova física LangGraph, mas não altera o fluxo Core de resume.
- B1 altera localização de erro, não semântica de autoridade/gates.
- CI-01 altera CI, não coordenação do Core.
- Portanto T10 e T11 permanecem `CONTRADICTED`.
- Classificação pós-GT: `PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`.
- Detalhamento: `docs/GT_INTEGRATION_AUDIT_2026-08-29.md`.

### Gates consolidados
- A1 `CLOSED`.
- A2 `CLOSED`.
- A3 `CLOSED`.
- A5 `CLOSED`.
- B1 `CLOSED`.
- blind spot CI de schemas `CLOSED`.
- A4 provider live `OPEN`.
- T10/T11 `ARCHITECTURAL_BLOCKER`.

### Próximo passo único
`RUN-REVALIDATION-GATE`: freshness/revalidação Core-owned obrigatória antes de resume e side effect relevante, com preservação de snapshot histórico, re-resolução de autoridade, rebuild seletivo de contexto e ESCALATE quando a mudança não puder ser resolvida com segurança.
