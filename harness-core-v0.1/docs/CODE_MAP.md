# Code Map — Harness Core V0.1

- `harness/contracts/`: contratos canônicos Pydantic e enums/erros.
- `harness/ports/`: interfaces estáveis para Runtime, Model, Tool, Memory, Workspace, Source e State.
- `harness/core/identity/`: resolução de `AgentIdentity` exclusivamente por `SourcePort`, com falha fechada e revisão da fonte.
- `harness/core/authority/`: resolução das cadeias tática/técnica/normativa, `AuthoritySnapshot` e decisão determinística `ALLOW/DENY/REQUIRE_APPROVAL/ESCALATE`.
- `harness/core/context/bootstrap.py`: resolve até três rotas segmentadas sem materializar conteúdo; produz `BootstrapResolution` e `trace_id`.
- `harness/core/context/builder.py`: materializa o menor contexto suficiente, aplica orçamento, deduplicação, proveniência por cadeia e Re-Bootstrap parcial sem reler cadeias preservadas.
- `harness/core/state/manager.py`: persistência canônica de `RunState`, criação/validação de `Checkpoint`, resume e gate de idempotência para side effects.
- `harness/core/tools/registry.py`: `ToolDescriptor`, registro explícito e resolução de tools disponíveis.
- `harness/core/tools/gateway.py`: boundary obrigatório antes de tools; aplica autoridade, competência, aprovação, business key/idempotência e exigência de evidência.
- `harness/adapters/state/in_memory.py`: `StatePort` in-memory com cópia defensiva e claim atômico de idempotência.
- `harness/adapters/tools/fake.py`: `ToolPort` fake para provar que side effects não são executados quando os gates falham.
- `harness/adapters/sources/`: adapters de fontes; `InMemorySourceAdapter` para testes e desenvolvimento.
- `harness/adapters/runtimes/fake/`: adapter in-memory que prova desacoplamento de runtime.
- `harness/schemas/`: JSON Schemas gerados a partir dos contratos.
- `tests/`: validação de contratos, identidade/autoridade, Bootstrap/Context Builder, estado/checkpoint/idempotência, Tool Gateway e fronteiras arquiteturais.
- `scripts/export_schemas.py`: geração reproduzível dos schemas.
- `.github/workflows/harness-core-ci.yml`: CI do Harness Core.
