# A2 — Idempotency Ledger — Implementation Report

## Objetivo
Eliminar ambiguidade de retries de side effects e permitir reconciliação auditável.

## Resultado final
Ledger implementado no Core/StatePort com estados `PENDING`, `COMPLETED`, `FAILED` e `UNKNOWN`, mantendo resultado, evidence refs, erro, contador de tentativa e flag de reconciliação.

## Arquivos alterados
- `harness/ports/__init__.py`
- `harness/adapters/state/in_memory.py`
- `harness/core/state/manager.py`
- `harness/core/tools/gateway.py`
- `tests/test_state_checkpoint.py`

## Sequência
1. StatePort ganhou CRUD mínimo do ledger.
2. Adapter in-memory ganhou criação atômica e update/load por valor.
3. StateManager ganhou lifecycle e reconciliação.
4. ToolGateway passou a marcar UNKNOWN quando a chamada externa lança exceção e COMPLETED quando retorna.
5. Testes foram migrados do claim binário para lifecycle completo.

## Decisões
- `PENDING` e `UNKNOWN` nunca sofrem retry automático.
- `FAILED` só pode ser reaberto com intenção explícita (`retry_failed=True`).
- Timeout/exceção depois do boundary é tratado conservadoramente como `UNKNOWN`, não `FAILED`, pois o efeito externo pode ter ocorrido.
- Resultado retornado marca o ledger como `COMPLETED` antes de eventual `VERIFICATION_FAILED` por falta de evidência, evitando repetir um side effect que já ocorreu.

## Tentativa que falhou → causa → solução correta
Claim binário → não representava resultado incerto nem falha confirmada → ledger persistido com estados e reconciliação explícita.

## Reprodução mínima
`python -m pip install -e '.[dev]' && pytest && python scripts/export_schemas.py`

## Próximo passo
A5 — formalizar `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` como refs-only ou materializados sob budget/proveniência.
