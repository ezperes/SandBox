# Code Map — Harness Core V0.1

- `harness/contracts/`: contratos canônicos Pydantic e enums/erros.
- `harness/ports/`: interfaces estáveis para Runtime, Model, Tool, Memory, Workspace e Source.
- `harness/core/identity/`: resolução de `AgentIdentity` exclusivamente por `SourcePort`, com falha fechada e revisão da fonte.
- `harness/core/authority/`: resolução das cadeias tática/técnica/normativa, `AuthoritySnapshot` e decisão determinística `ALLOW/DENY/REQUIRE_APPROVAL/ESCALATE`.
- `harness/adapters/sources/`: adapters de fontes; `InMemorySourceAdapter` para testes e desenvolvimento.
- `harness/adapters/runtimes/fake/`: adapter in-memory que prova desacoplamento de runtime.
- `harness/schemas/`: JSON Schemas gerados a partir dos contratos.
- `tests/`: validação de contratos, invariantes, resolução de identidade/autoridade e fronteira arquitetural.
- `scripts/export_schemas.py`: geração reproduzível dos schemas.
- `.github/workflows/harness-core-ci.yml`: CI do Harness Core.
