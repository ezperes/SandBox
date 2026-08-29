# Implementation Report — Harness Core V0.1

## Incremento 1 — Resultado
Esqueleto executável do Core criado com contratos Pydantic V0.1, Ports estáveis e FakeRuntimeAdapter sem LangGraph.

## Incremento 2 — Resultado
Implementados `IdentityResolver` e `AuthorityResolver` sem dependência de provider/runtime. A identidade nasce exclusivamente de `SourcePort`; autoridade é resolvida em até três cadeias e produz `AuthoritySnapshot` versionado.

### Arquivos principais
- `harness/core/identity/resolver.py`: resolução e falha fechada de identidade.
- `harness/core/authority/resolver.py`: três cadeias, snapshot e decisão determinística.
- `harness/adapters/sources/in_memory.py`: fonte substituível de teste.
- `tests/test_identity_authority.py`: testes de identidade, três cadeias, snapshot, competência e decisões.
- `.github/workflows/harness-core-ci.yml`: CI automatizado.

### Regras comprovadas por código/teste
- `organizational_path_ref`, autoridade tática e autoridade técnica continuam vindo da identidade canônica.
- Técnica pode ser explicitamente `MESMA_CADEIA_TATICA` ou `NAO_APLICAVEL_JUSTIFICADO`.
- Proibição explícita prevalece e retorna `DENY`.
- Competência ausente retorna `ESCALATE`; autoridade não implica competência.
- Gate humano retorna `REQUIRE_APPROVAL`.
- Escopo não resolvido retorna `ESCALATE`, evitando autorização por ausência de dado.
- Snapshot preserva revisões das fontes consultadas.

## Ambiente
Python 3.11+; Pydantic 2.x; pytest 8.x.

## Reprodução mínima
`python -m pip install -e '.[dev]' && pytest && python scripts/export_schemas.py`

## Tentativa que falhou → causa → solução correta
Incremento 1: `python scripts/export_schemas.py` → `ModuleNotFoundError: harness` → raiz ausente do `sys.path` → script passou a inserir `ROOT` antes do import.
Incremento 2: nenhuma tentativa arquitetural descartada foi necessária; fonte física do Livro da Vida foi deliberadamente adiada para adapter próprio, evitando acoplamento do Core ao Google Drive.

## Code map
`docs/CODE_MAP.md`.

## Próximo incremento
Bootstrap Resolver + Context Builder: `1 identidade → até 3 cadeias → 1 Active Context mínimo`, com proveniência por bloco e Re-Bootstrap parcial por cadeia.
