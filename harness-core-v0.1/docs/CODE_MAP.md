# Code Map — Harness Core V0.1

- `harness/contracts/`: contratos canônicos Pydantic e enums/erros.
- `harness/ports/`: interfaces estáveis para Runtime, Model, Tool, Memory, Workspace e Source.
- `harness/adapters/runtimes/fake/`: adapter in-memory que prova desacoplamento de runtime.
- `harness/schemas/`: JSON Schemas gerados a partir dos contratos.
- `tests/`: validação de contratos, invariantes e fronteira arquitetural.
- `scripts/export_schemas.py`: geração reproduzível dos schemas.
