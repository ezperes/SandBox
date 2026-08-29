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

### Arquivos principais
- `harness/core/identity/resolver.py`: resolução e falha fechada de identidade.
- `harness/core/authority/resolver.py`: três cadeias, snapshot e decisão determinística.
- `harness/core/context/bootstrap.py`: resolução das rotas tática/técnica/normativa sem carregar conteúdo.
- `harness/core/context/builder.py`: seleção mínima, budget, deduplicação, proveniência e Re-Bootstrap parcial.
- `harness/core/state/manager.py`: persistência canônica, checkpoint, resume e idempotência.
- `harness/core/tools/registry.py`: descrição e registro explícito de tools.
- `harness/core/tools/gateway.py`: gate do Core para autorização, competência, aprovação, idempotência e evidência.
- `harness/adapters/tools/fake.py`: ToolPort fake para testes de boundary.
- `harness/adapters/state/in_memory.py`: adapter substituível de estado para desenvolvimento/testes.
- `harness/adapters/sources/in_memory.py`: fonte substituível de teste.
- `tests/test_identity_authority.py`: testes de identidade/autoridade.
- `tests/test_context_bootstrap.py`: testes do Bootstrap e Context Builder.
- `tests/test_state_checkpoint.py`: testes de persistência, checkpoint, resume e idempotência.
- `tests/test_tool_gateway.py`: testes de tool gating, aprovação, competência, evidência e side effects.
- `.github/workflows/harness-core-ci.yml`: CI automatizado.

### Regras comprovadas por código/teste
- `organizational_path_ref`, autoridade tática e autoridade técnica continuam vindo da identidade canônica.
- Técnica pode ser explicitamente `MESMA_CADEIA_TATICA` ou `NAO_APLICAVEL_JUSTIFICADO`.
- Proibição explícita prevalece e retorna `DENY`.
- Competência ausente retorna `ESCALATE`; autoridade não implica competência.
- Gate humano retorna `REQUIRE_APPROVAL`.
- Snapshot preserva revisões das fontes consultadas.
- Um Bootstrap produz até três rotas independentes.
- Contexto obrigatório tem precedência; contexto opcional é cortado pelo budget.
- Cada referência carregada preserva a cadeia de origem.
- Re-Bootstrap parcial não relê cadeias preservadas.
- Contexto obrigatório que excede o budget falha fechado em vez de sofrer truncamento silencioso.
- `RunState` e `Checkpoint` persistem fora do Runtime.
- Resume exige coerência entre `run_id`, `run_state_ref` e `checkpoint_ref`.
- Side effect duplicado com mesma chave é bloqueado com `RETRY_BLOCKED`.
- O mecanismo de idempotência pertence ao Core/StatePort e continua válido quando Runtime Adapter for substituído.
- Tool ausente falha com `TOOL_UNAVAILABLE`.
- Tool proibida, sem competência ou aguardando aprovação não chama o adapter externo.
- Side effect exige `business_key` e claim de idempotência antes da chamada externa.
- Evidência obrigatória ausente transforma execução produzida em resultado não aceitável (`VERIFICATION_FAILED`).

## Ambiente
Python 3.11+; Pydantic 2.x; pytest 8.x.

## Reprodução mínima
`python -m pip install -e '.[dev]' && pytest && python scripts/export_schemas.py`

## Tentativa que falhou → causa → solução correta
Incremento 1: `python scripts/export_schemas.py` → `ModuleNotFoundError: harness` → raiz ausente do `sys.path` → script passou a inserir `ROOT` antes do import.
Incremento 2: fonte física do Livro da Vida foi deliberadamente adiada para adapter próprio, evitando acoplamento do Core ao Google Drive.
Incremento 3: primeira abordagem reconstruía todo o contexto e depois restaurava cadeias não afetadas → resultado lógico correto, porém I/O desnecessário e quebra da economia de contexto → Re-Bootstrap passou a preservar refs/token usage de cadeias intactas e materializar somente `changed_chains`.
Incremento 4: idempotência foi deliberadamente colocada atrás de `StatePort`, não em `RuntimePort`; causa evitada: um retry/runtime alternativo poderia repetir side effect se o conhecimento da execução anterior ficasse preso ao executor. Solução: claim atômico em persistência canônica antes do side effect.
Incremento 5: `ToolDescriptor` foi mantido inicialmente como tipo interno do Core, fora do bundle Pydantic canônico. Causa: adicionar contrato ao bundle exigiria migração/versionamento e regeneração coordenada dos schemas durante um incremento focado no gate operacional. Solução correta: implementar o boundary primeiro sem alterar a versão dos contratos; formalização/versionamento do descriptor permanece uma tarefa explícita futura.

## Code map
`docs/CODE_MAP.md`.

## Próximo incremento
ModelPort + primeiro Model Adapter para prova real: definir request/response neutral do Core, adapter substituível e garantir que troca de provider/modelo não altere `AgentIdentity`, autoridade ou TaskContext.
