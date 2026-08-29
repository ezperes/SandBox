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

### Arquivos principais do Incremento 6
- `harness/contracts/model.py`: contratos Pydantic neutros.
- `harness/core/routing/model_router.py`: seleção por capacidade/preferência/prioridade e validação do retorno.
- `harness/adapters/models/fake.py`: adapter determinístico.
- `harness/adapters/models/openai_responses.py`: tradução para Responses API sem dependência do SDK no Core.
- `tests/test_model_routing.py`: seleção, preferência, identidade estável e tradução de provider.

### Regras comprovadas
- Troca de provider/modelo não modifica identidade institucional do agente.
- `ModelPort` opera apenas por contratos neutros.
- Core não importa SDK OpenAI.
- Resposta de adapter com `run_id`, request, provider ou modelo incompatível é rejeitada.
- Preferências explícitas podem selecionar provider/modelo sem reescrever identidade ou autoridade.
- CI executou pytest, exportação de schemas e verificação de drift com sucesso após a correção do teste.

## Ambiente
Python 3.11+; Pydantic 2.x; pytest 8.x.

## Reprodução mínima
`python -m pip install -e '.[dev]' && pytest && python scripts/export_schemas.py`

## Tentativa que falhou → causa → solução correta
Incremento 1: `python scripts/export_schemas.py` → `ModuleNotFoundError: harness` → raiz ausente do `sys.path` → script passou a inserir `ROOT` antes do import.
Incremento 3: reconstrução total do contexto → I/O desnecessário → Re-Bootstrap materializa somente cadeias alteradas.
Incremento 4: idempotência no Runtime poderia repetir side effect após troca/retry → claim atômico foi colocado no `StatePort`.
Incremento 6: teste comparou duas instâncias inteiras de `AgentIdentity` → `resolved_at` naturalmente diferente causou falso negativo → comparação passou a congelar apenas campos semanticamente estáveis da identidade.

## Code map
`docs/CODE_MAP.md`.

## Próximo incremento
LangGraphAdapter: implementar o primeiro `RuntimeAdapter` real atrás de `RuntimePort`, traduzindo estado/checkpoint/interrupt nativos para contratos do Core sem promover LangGraph a fonte de identidade, autoridade ou estado institucional.
