# B1-CORE-ERRORS — IMPLEMENTATION LOG

**WORK_TASK_ID:** `B1-CORE-ERRORS`  
**BASE_SHA:** `59d3eb987136ec628bcaba4b45949fb81b2616a2`  
**WORK_BRANCH:** `worker/b1-core-errors`

## 1. Inventário antes da alteração

- Definição única de `HarnessResolutionError`: `harness/core/identity/resolver.py`.
- Re-export anterior: `harness/core/identity/__init__.py`.
- Consumidores no Core:
  - `harness/core/authority/resolver.py`;
  - `harness/core/state/manager.py`;
  - `harness/core/tools/gateway.py`.
- Testes que importavam o erro por Identity:
  - `tests/test_identity_authority.py`;
  - `tests/test_state_checkpoint.py`;
  - `tests/test_tool_gateway.py`.
- `HarnessErrorCode` permanece definido em `harness/contracts/_models.py`; seus valores não foram alterados.

## 2. Decisão de implementação

`harness.core.errors` passa a ser o proprietário canônico de `HarnessResolutionError`.

`harness.core.identity` mantém apenas um re-export de compatibilidade para consumidores existentes. A definição da classe não permanece no domínio Identity.

Sem `INTERPRETATION_DIVERGENCE` bloqueante. A auditoria canônica B1 já prescrevia a movimentação para `core.errors`, e o re-export preserva compatibilidade de importação sem manter a responsabilidade conceitual em Identity.

## 3. Sequência executada

1. Criado `harness/core/errors.py` com a mesma estrutura pública do erro: `code`, `message`, `source_ref` e `__str__`.
2. Removida a definição de `HarnessResolutionError` de `identity/resolver.py`; o resolver passou a importar do módulo neutro.
3. Alterados os imports de Authority, State e Tools para `harness.core.errors`.
4. Alterados os testes diretamente dependentes para o novo caminho canônico.
5. Adicionado `tests/test_core_errors.py` cobrindo:
   - identidade entre o import canônico e o alias legado;
   - preservação de `code`, `message` e `source_ref`;
   - preservação exata da representação textual com e sem `source_ref`.
6. Criado commit de implementação `968d5b946b9b4c17383f2bb30c6f74e866c91796`.
7. Aberta PR draft #2 exclusivamente para executar CI e fornecer superfície de integração ao Integrador; nenhum merge foi realizado.

## 4. Tentativa que falhou → causa → solução correta

**Tentativa:** usar clone local do repositório para executar busca/validação no container.  
**Falha:** `Could not resolve host: github.com`.  
**Causa:** ambiente local de execução sem resolução/acesso de rede ao GitHub.  
**Solução correta:** inspeção e escrita no `BASE_SHA` exato via integração GitHub, seguida de validação no GitHub Actions através da PR draft.

## 5. Validação do commit de implementação

GitHub Actions — Harness Core CI, run #77:

- Python: 3.11.16;
- `python -m pip install -e '.[dev]'`: sucesso;
- `pytest`: **43 passed in 0.18s**;
- `python scripts/export_schemas.py`: **17 schemas exportados**;
- `git diff --exit-code -- harness/schemas`: sucesso, sem drift.

## 6. Expansão e desvios

- `SCOPE_EXPANSION_REQUEST`: nenhum.
- `INTERPRETATION_DIVERGENCE`: nenhuma bloqueante.
- Código fora do `WRITE SET`: não alterado.
- Valores de `HarnessErrorCode`: não alterados.
- Política de decisão, contratos institucionais e comportamento dos gates: não alterados.
