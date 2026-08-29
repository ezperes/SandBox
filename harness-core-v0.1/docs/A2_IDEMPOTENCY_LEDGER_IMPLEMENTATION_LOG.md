# A2 — Idempotency Ledger — Implementation Log

Data: 2026-08-29

## Objetivo
Substituir o claim binário de idempotência por um ledger com estado, resultado/evidência e reconciliação explícita antes de side effects reais.

## Implementação
- `StatePort`: substituído `claim_idempotency()` por `create_idempotency_record`, `load_idempotency_record` e `update_idempotency_record`.
- `InMemoryStateAdapter`: ledger atômico por chave com cópia defensiva.
- `StateManager`: adicionados `IdempotencyStatus`, `IdempotencyRecord`, `begin_side_effect`, `complete_side_effect`, `fail_side_effect`, `get_side_effect` e `reconcile_side_effect`.
- Estados: `PENDING | COMPLETED | FAILED | UNKNOWN`.
- Retry de `FAILED` exige `retry_failed=True`; `PENDING`/`UNKNOWN` bloqueiam retry até reconciliação.
- `ToolGateway`: inicia ledger antes do boundary externo; exceção de adapter marca `UNKNOWN`; retorno normal marca `COMPLETED` com resultado/evidence refs antes de eventual falha de verificação de evidência.

## Tentativa que falhou → causa → solução correta
O claim binário anterior registrava apenas "já visto". Em timeout ou falha após o boundary, não distinguia execução concluída, falha confirmada ou resultado incerto. Solução: ledger de ciclo de vida persistido no `StatePort`, com reconciliação explícita e retry somente após estado seguro.

## Validação
Testes cobrem: PENDING→COMPLETED, bloqueio de duplicidade concluída, UNKNOWN após timeout, reconciliação UNKNOWN→FAILED, retry explícito FAILED→PENDING com incremento de tentativa e independência por business key.
