# Code Map — Harness Core V0.1

## Contratos

- `harness/contracts/`: contratos canônicos Pydantic e enums/códigos de erro.
- `harness/contracts/model.py`: `ModelRequest`, `ModelSelection` e `ModelResponse` neutros a provider.
- `harness/schemas/`: 17 JSON Schemas gerados e versionados mais `all.schemas.json`; a fonte continua sendo os contratos Pydantic, não edição manual dos schemas.

## Core

- `harness/core/errors.py`: `HarnessResolutionError` compartilhado pelo Core; `harness.core.identity` mantém re-export compatível.
- `harness/core/identity/`: resolução de `AgentIdentity` exclusivamente por `SourcePort`, com falha fechada e revisão da fonte.
- `harness/core/authority/`: resolução das cadeias tática/técnica/normativa, `AuthoritySnapshot` e decisão determinística `ALLOW/DENY/REQUIRE_APPROVAL/ESCALATE`; `allowed_scopes` positivo usa interseção das allow-lists declaradas.
- `harness/core/context/bootstrap.py`: resolve até três rotas segmentadas sem materializar conteúdo; produz `BootstrapResolution` e `trace_id`.
- `harness/core/context/builder.py`: materializa contexto mínimo, aplica budget/deduplicação/proveniência e possui `rebuild_partial()` para cadeias explicitamente informadas como alteradas.
- `harness/core/state/manager.py`: persistência canônica de `RunState`, criação/validação de `Checkpoint`, resume via `RuntimePort` e ledger idempotente `PENDING | COMPLETED | FAILED | UNKNOWN`.
- `harness/core/tools/registry.py`: `ToolDescriptor`, registro explícito e resolução de tools.
- `harness/core/tools/gateway.py`: boundary antes de tools; aplica autoridade, competência, aprovação, business key/idempotência e evidência.
- `harness/core/routing/model_router.py`: seleção de modelo/provider por capacidade/preferência/prioridade sem alterar `AgentIdentity`.

### Lacuna arquitetural ativa do Core

- `StateManager.resume()` ainda chama `RuntimePort.resume()` após validar checkpoint/RunState, sem gate obrigatório de freshness/re-resolução/rebuild do Active Context. Relacionado a T10.
- `ToolGateway.execute()` decide sobre o `AuthorityContext` recebido e não compara sua revisão com fontes canônicas atuais. Relacionado a T11.
- Não há ainda Delegation Gate/Port nem Instruction Adapter executável para T06/T08/T09.

## Ports

- `harness/ports/`: interfaces estáveis para Runtime, Model, Tool, Memory, Workspace, Source e State.
- A ausência atual de Delegation/Instruction ports é dívida arquitetural explícita; não deve ser suprida por lógica ad hoc em providers/runtimes.

## Adapters

- `harness/adapters/models/fake.py`: Model Adapter determinístico para testes.
- `harness/adapters/models/openai_responses.py`: adapter fino para Responses API por cliente injetado; chamada live continua gate separado.
- `harness/adapters/state/in_memory.py`: `StatePort` in-memory com cópia defensiva e ledger idempotente persistido por interface.
- `harness/adapters/tools/fake.py`: `ToolPort` fake para provar bloqueio de effects quando gates falham.
- `harness/adapters/sources/`: adapters de fontes; `InMemorySourceAdapter` para testes/desenvolvimento.
- `harness/adapters/runtimes/fake/`: runtime fake que prova que o Core executa sem LangGraph.
- `harness/adapters/runtimes/langgraph/runtime.py`: adapter por superfície mínima de grafo compilado. Usa `run_id` como `thread_id`, traduz estado técnico para `RunState`, preserva refs canônicos apenas do Core e retoma static interrupts com `input=None` conforme `RuntimePort` V0.1.

## Prova física LangGraph

- `tests/test_langgraph_real.py`: integração contra `langgraph==1.2.11` real, `StateGraph`, compilação, `MemorySaver`, static interrupt/breakpoint e resume do mesmo thread.
- `pyproject.toml`: LangGraph é fixado em extras `dev`/`langgraph`; não integra `[project].dependencies`, preservando removibilidade do framework.
- A prova física A3 não resolve o resume canônico T10; runtime técnico e freshness institucional são responsabilidades distintas.

## Tests

- `tests/test_contracts.py`: invariantes contratuais.
- `tests/test_identity_authority.py`: identidade, três cadeias, interseção, precedência e fail-closed.
- `tests/test_context_bootstrap.py`: Bootstrap, contexto mínimo, POINTER_ONLY, budget e re-bootstrap parcial.
- `tests/test_state_checkpoint.py`: persistência, checkpoint/resume e ledger idempotente.
- `tests/test_tool_gateway.py`: authority/competence/approval/idempotency/evidence gates.
- `tests/test_model_routing.py`: provider/model routing e independência da identidade.
- `tests/test_langgraph_adapter.py`: boundary do LangGraph Adapter por stub.
- `tests/test_langgraph_real.py`: prova física LangGraph real.
- `tests/test_core_errors.py`: compatibilidade da refatoração de `HarnessResolutionError`.
- `tests/test_schema_drift_check.py`: regressões Git reais para schema tracked/untracked/ignored/clean.

## CI e geração

- `scripts/export_schemas.py`: exportação reproduzível a partir de `CANONICAL_CONTRACTS`.
- `scripts/check_schema_drift.py`: fail-closed sobre qualquer estado Git em `harness/schemas`, inclusive `??` e `!!`.
- `.github/workflows/harness-core-ci.yml`: `pytest → export_schemas.py → check_schema_drift.py`.

## Documentação operacional

- `docs/IMPLEMENTATION_LOG.md`: histórico operacional consolidado.
- `docs/IMPLEMENTATION_REPORT.md`: estado implementado e gates atuais.
- `docs/POST_INCREMENT_AUDIT_1_7.md`: auditoria transversal/gates pós-Incrementos 1–7.
- `docs/GT_INTEGRATION_AUDIT_2026-08-29.md`: integração dos quatro workers e nova auditoria T01–T12.
- `docs/workers/`: evidência isolada de cada Elemento, incluindo o Gap Map ARCH-01 do BASE_SHA.
