# Implementation Report — Harness Core V0.1

## Incremento 1 — Resultado
Esqueleto executável do Core criado com contratos Pydantic V0.1, Ports estáveis e FakeRuntimeAdapter sem LangGraph.

## Incremento 2 — Resultado
Implementados `IdentityResolver` e `AuthorityResolver` sem dependência de provider/runtime. A identidade nasce exclusivamente de `SourcePort`; autoridade é resolvida em até três cadeias e produz `AuthoritySnapshot` versionado.

## Incremento 3 — Resultado
Implementados `BootstrapResolver` e `ContextBuilder`. Um único Bootstrap transforma o `AuthorityContext` em até três rotas segmentadas e o ContextBuilder materializa um `TaskContext` mínimo, deduplicado e limitado por budget, preservando proveniência por cadeia. O Re-Bootstrap parcial mantém intactas as cadeias não afetadas e relê somente a cadeia alterada mais a Tarefa de Trabalho.

## Incremento 4 — Resultado
Implementados `StatePort`, `InMemoryStateAdapter` e `StateManager`. O Core agora persiste `RunState`, cria checkpoints canônicos, valida retomadas e bloqueia repetição de side effects por chave de idempotência, sem depender de checkpoint nativo de framework/runtime.

## Incremento 5 — Resultado
Implementados `ToolRegistry`, `ToolDescriptor` e `ToolGateway`. Nenhuma tool registrada atravessa o boundary externo antes de resolução de autoridade/escopo, competência, aprovação e idempotência quando houver side effect. Evidência obrigatória também é validada no retorno.

## Incremento 6 — Resultado
Implementados contratos neutros `ModelRequest`, `ModelSelection` e `ModelResponse`; `ModelPort` tipado; `ModelRouter`; `FakeModelAdapter`; e `OpenAIResponsesAdapter` com cliente injetado. Provider/modelo são recursos substituíveis e não alteram `AgentIdentity`, `AuthorityContext` ou `TaskContext`.

## Incremento 7 — Resultado
Implementado `LangGraphAdapter` atrás de `RuntimePort`, sem importar LangGraph no Core e sem promover o runtime a fonte institucional. O adapter usa uma superfície mínima compatível com grafo compilado (`invoke`), projeta `run_id` para `configurable.thread_id`, traduz o estado técnico para `RunState` canônico e permite resume do thread existente com `input=None`.

### Arquivos principais do Incremento 7
- `harness/adapters/runtimes/langgraph/runtime.py`: tradução LangGraph → `RunState` e resume por `thread_id`.
- `harness/adapters/runtimes/langgraph/__init__.py`: export do adapter.
- `tests/test_langgraph_adapter.py`: tradução, interrupt/resume, isolamento de identidade/autoridade e rejeição de estado estrangeiro.

### Regras comprovadas
- LangGraph não recebe prerrogativa para definir `AgentIdentity`, autoridade, política ou competência.
- `run_id` é a chave técnica de thread; o checkpoint do runtime não substitui `Checkpoint` canônico.
- `RunState` canônico continua sendo reconstruído pelo adapter a partir da execução técnica.
- Resume valida o vínculo do estado com o Run antes de chamar o runtime.
- Idempotência de side effects continua em `StatePort`/`ToolGateway`, não em LangGraph.
- O pacote-base continua executável sem dependência obrigatória do framework LangGraph; remover o adapter não altera contratos ou Core.

## Ambiente
Python 3.11+; Pydantic 2.x; pytest 8.x.

## Reprodução mínima
`python -m pip install -e '.[dev]' && pytest && python scripts/export_schemas.py`

## Tentativa que falhou → causa → solução correta
Incremento 1: `python scripts/export_schemas.py` → `ModuleNotFoundError: harness` → raiz ausente do `sys.path` → script passou a inserir `ROOT` antes do import.
Incremento 3: reconstrução total do contexto → I/O desnecessário → Re-Bootstrap materializa somente cadeias alteradas.
Incremento 4: idempotência no Runtime poderia repetir side effect após troca/retry → claim atômico foi colocado no `StatePort`.
Incremento 6: teste comparou duas instâncias inteiras de `AgentIdentity` → `resolved_at` naturalmente diferente causou falso negativo → comparação passou a congelar apenas campos semanticamente estáveis da identidade.
Incremento 7: foi descartada a inclusão de `langgraph` como dependência obrigatória do pacote-base → isso criaria acoplamento operacional desnecessário e enfraqueceria o critério de substituição → o adapter depende apenas de protocolo mínimo compatível; instalação real do framework pode ser um extra opcional quando a prova E2E física for montada.

## Code map
`docs/CODE_MAP.md`.

## Próximo incremento
Primeira prova End-to-End: conectar 1 agente real, 1 Tarefa de Trabalho, identidade/autoridade, Bootstrap/Context, Model Adapter, LangGraphAdapter, Tool Gateway, RunState/Checkpoint, Evidence, VerificationResult e TelemetryEvent até encerramento rastreável.
