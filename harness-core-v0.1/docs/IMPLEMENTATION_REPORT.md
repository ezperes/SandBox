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
Implementados contratos neutros `ModelRequest`, `ModelSelection` e `ModelResponse`; `ModelPort` tipado; `ModelRouter`; `FakeModelAdapter`; e `OpenAIResponsesAdapter` com cliente injetado. Provider/modelo permanecem substituíveis e não alteram `AgentIdentity`, `AuthorityContext` ou `TaskContext`. A tradução de provider está coberta por stub; chamada live ainda não foi comprovada.

## Incremento 7 — Resultado
Implementado `LangGraphAdapter` atrás de `RuntimePort`, sem importar LangGraph no Core e sem promover o runtime a fonte institucional. O adapter usa uma superfície mínima compatível com grafo compilado (`invoke`), projeta `run_id` para `configurable.thread_id`, traduz o estado técnico para `RunState` e permite resume do thread existente com `input=None`. Os testes atuais usam `StubGraph`; integração contra pacote LangGraph real permanece pendente.

### Retificações pós-auditoria
- `NAO_APLICAVEL_JUSTIFICADO` agora exige justificativa textual não vazia. A antiga justificativa genérica automática foi removida; ausência de justificativa falha fechado com `AUTHORITY_UNRESOLVED`.
- `LangGraphAdapter` deixou de aceitar `decision_refs` e `canonical_checkpoint_ref` vindos do runtime. Referências canônicas de decisão/checkpoint só podem vir do estado canônico anterior/Core.
- A linguagem dos Incrementos 6 e 7 foi ajustada: há adapters compatíveis e testados por stubs, mas integração live OpenAI e integração com pacote LangGraph real ainda não foram comprovadas.

### Auditoria transversal — gates antes do primeiro E2E completo
Documento canônico de auditoria no repositório: `docs/POST_INCREMENT_AUDIT_1_7.md`.

1. **A1 — Autoridade por interseção — CONCLUÍDO:** `allowed_scopes` efetivo agora é a interseção de todos os allow-lists declarados pelas cadeias aplicáveis. Cadeia sem allow-list não adiciona whitelist; ausência total de allow-list é representada por `*`; interseção vazia não autoriza ação e leva a `ESCALATE`; proibição explícita continua prevalecendo.
2. **A2 — Ledger idempotente — PRÓXIMO:** o claim binário atual bloqueia repetição, mas não distingue operação pendente, completada ou resultado desconhecido. É obrigatório criar ledger com estados e estratégia de retry/reconciliação antes de side effects reais.
3. **A5 — Semântica dos refs de tarefa:** `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` precisam ser formalizados como apontadores não materializados ou entrar no pipeline de budget/proveniência.
4. **A3 — LangGraph físico:** integração real com biblioteca/checkpointer/interrupt deve ser testada antes de declarar o runtime físico comprovado.
5. **A4 — Provider live:** o E2E deve declarar se usa FakeModelAdapter ou realizar uma chamada live; não tratar teste por stub como integração live.

### Regras comprovadas por código/teste até aqui
- identidade vem de `SourcePort` e não do provider/runtime;
- até três cadeias de autoridade são resolvidas e versionadas;
- autorização positiva segue a interseção das cadeias aplicáveis que declaram allow-list;
- interseção vazia não produz autorização implícita;
- ausência de whitelist é explícita por `*`, sem neutralizar proibições;
- proibição explícita vence;
- competência ausente não vira autorização implícita;
- Bootstrap/Context Builder preservam segregação por cadeia e Re-Bootstrap parcial;
- `RunState`/`Checkpoint` canônicos ficam fora do runtime;
- Tool Gateway barra side effects antes do boundary quando gates falham;
- provider/modelo não reescrevem identidade;
- runtime não pode injetar refs canônicos de decisão/checkpoint;
- Core continua executável com Runtime fake sem LangGraph.

## Ambiente
Python 3.11+; Pydantic 2.x; pytest 8.x.

## Reprodução mínima
`python -m pip install -e '.[dev]' && pytest && python scripts/export_schemas.py`

## Tentativa que falhou → causa → solução correta
Incremento 1: `python scripts/export_schemas.py` → `ModuleNotFoundError: harness` → raiz ausente do `sys.path` → script passou a inserir `ROOT` antes do import.
Incremento 3: reconstrução total do contexto → I/O desnecessário → Re-Bootstrap materializa somente cadeias alteradas.
Incremento 4: idempotência no Runtime poderia repetir side effect após troca/retry → claim atômico foi colocado no `StatePort`; auditoria posterior mostrou que o claim binário ainda precisa evoluir para ledger com estados antes de side effects reais.
Incremento 6: teste comparou duas instâncias inteiras de `AgentIdentity` → `resolved_at` naturalmente diferente causou falso negativo → comparação passou a congelar apenas campos semanticamente estáveis da identidade.
Incremento 7: dependência obrigatória de LangGraph foi evitada → adapter usa protocolo mínimo; auditoria posterior identificou que refs canônicos ainda podiam ser lidos do estado nativo → correção aplicada para ignorar `decision_refs`/`canonical_checkpoint_ref` do runtime.
Pós-auditoria R1: `NAO_APLICAVEL_JUSTIFICADO` sem texto real era aceito com fallback genérico → isso criava exceção não auditável → fallback removido e justificativa passou a ser obrigatória.
Pós-auditoria A1: união de `allowed_scopes` permitia autoridade positiva por apenas uma cadeia → violava `TÁTICA ∩ TÉCNICA ∩ NORMATIVA` → resolução passou a calcular interseção das allow-lists declaradas. Durante a correção foi identificado um segundo caso: interseção vazia e ausência de whitelist eram indistinguíveis por lista vazia; solução correta foi representar ausência explícita de whitelist por `*` e reservar lista vazia para `nenhuma ação comum autorizada`.

## Code map
`docs/CODE_MAP.md`.

## Próximo passo
**A2 — ledger idempotente com estado**, antes do E2E: substituir claim binário por registro de execução com estados, evidência/resultado quando conhecidos e regras explícitas de retry/reconciliação.
