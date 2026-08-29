# B1-CORE-ERRORS — FINDINGS

## Mapa confirmado

| Item | Localização |
|---|---|
| Definição anterior | `harness/core/identity/resolver.py` |
| Re-export anterior | `harness/core/identity/__init__.py` |
| Consumidor | `harness/core/authority/resolver.py` |
| Consumidor | `harness/core/state/manager.py` |
| Consumidor | `harness/core/tools/gateway.py` |
| Enum canônico | `harness/contracts/_models.py` — `HarnessErrorCode` |
| Teste dependente | `tests/test_identity_authority.py` |
| Teste dependente | `tests/test_state_checkpoint.py` |
| Teste dependente | `tests/test_tool_gateway.py` |

## SCOPE_EXPANSION_REQUEST

Nenhum.

## INTERPRETATION_DIVERGENCE

Nenhuma bloqueante.

A única tensão relevante era entre mover a propriedade conceitual para `core.errors` e preservar consumidores do import histórico `harness.core.identity`. Foi resolvida sem alterar arquitetura ou contrato: definição neutra + re-export de compatibilidade apontando para a mesma classe.

## OPPORTUNITY_FOUND

### GitHub Actions — aviso de depreciação de Node.js 20

A CI emitiu aviso de que `actions/checkout@v4` e `actions/setup-python@v5` ainda têm metadata direcionada a Node.js 20 e estão sendo executadas sob Node.js 24 pelo runner.

- Impacto atual em B1: nenhum; a CI terminou com sucesso.
- Cadeia afetada: infraestrutura/CI, não Core Errors.
- Recomendação: tratar em tarefa própria quando houver necessidade de manutenção da pipeline.
- Ação neste worker: nenhuma, por estar fora do `WRITE SET`.

## Riscos residuais

- O módulo declarado da classe muda de `harness.core.identity.resolver` para `harness.core.errors`, consequência necessária da movimentação de responsabilidade.
- Compatibilidade de importação foi preservada com alias no pacote Identity.
- Não foram encontrados contratos/testes que persistam exceções ou dependam de `HarnessResolutionError.__module__`.

## Invariantes verificadas

- `HarnessErrorCode`: sem alteração.
- Raises existentes: sem alteração de códigos, mensagens ou referências.
- Gates de Tools: sem alteração lógica.
- State/Checkpoint/Idempotency: sem alteração lógica.
- Authority decision semantics: sem alteração lógica.
- Identity resolution semantics: sem alteração lógica.
