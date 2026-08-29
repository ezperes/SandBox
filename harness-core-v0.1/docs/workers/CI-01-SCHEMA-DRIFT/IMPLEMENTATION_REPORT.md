# IMPLEMENTATION_REPORT — CI-01-SCHEMA-DRIFT

## Estado
`READY_FOR_INTEGRATION`

A alteração do worker está isolada e funcional. Existe uma dependência de integração explícita: o BASE_SHA não contém `harness/schemas/**` rastreado; portanto o novo check, corretamente, acusará o baseline atual como untracked até que o Integrador autorize/materialize os schemas gerados em uma alteração separada.

## Identidade
- WORK_TASK_ID: `CI-01-SCHEMA-DRIFT`
- BASE_BRANCH: `harness-core-v0.1`
- BASE_SHA: `59d3eb987136ec628bcaba4b45949fb81b2616a2`
- WORK_BRANCH: `worker/ci-schema-drift`
- commit funcional: `63a6d0ff88e71a85a0fa255436b200ab86bb7cbd`

## Objetivo
Eliminar o blind spot da CI em que `git diff --exit-code -- harness/schemas` retorna sucesso para schemas completamente novos/untracked produzidos pelo exportador.

## Resultado final
- CI passa a executar `python scripts/check_schema_drift.py` após `python scripts/export_schemas.py`.
- O verificador usa Git porcelain, escopado a `harness/schemas`, e detecta:
  - modificações/deleções/adições rastreadas;
  - arquivos untracked (`??`);
  - arquivos ignorados (`!!`), evitando mascaramento por `.gitignore`.
- Nenhuma dependência nova.
- Nenhum contrato canônico, IdentityResolver, AuthorityResolver, ToolGateway ou comportamento funcional do Harness foi alterado.

## Ambiente de validação
- Python: `3.13.5`
- Git: `2.47.3`
- pytest: `9.0.2`
- GitHub Actions alvo permanece Python `3.11` e dependências do `pyproject.toml` existente.

## Arquivos criados/alterados
- `.github/workflows/harness-core-ci.yml` — troca o check incompleto pelo verificador novo.
- `harness-core-v0.1/scripts/check_schema_drift.py` — detector de drift Git para schemas.
- `harness-core-v0.1/tests/test_schema_drift_check.py` — regressão com repositórios Git temporários reais.
- `harness-core-v0.1/docs/workers/CI-01-SCHEMA-DRIFT/IMPLEMENTATION_LOG.md` — diário estruturado.
- `harness-core-v0.1/docs/workers/CI-01-SCHEMA-DRIFT/FINDINGS.md` — achados e expansão de escopo necessária.
- `harness-core-v0.1/docs/workers/CI-01-SCHEMA-DRIFT/IMPLEMENTATION_REPORT.md` — este relatório.

## Sequência de implementação
1. Resolvido o BASE_SHA diretamente da branch `harness-core-v0.1`.
2. Criada `worker/ci-schema-drift` exatamente a partir do BASE_SHA.
3. Inspecionados workflow, exportador, tree do repositório e configuração de testes.
4. Confirmado que o tree do BASE_SHA não contém `harness-core-v0.1/harness/schemas/**`.
5. Reproduzido o blind spot em Git real.
6. Implementado detector com `git status --porcelain=v1 --untracked-files=all --ignored=matching -- harness/schemas`.
7. Criados quatro testes de regressão.
8. Atualizado workflow.
9. Commit funcional criado e branch atualizada.
10. Revisado diff contra BASE_SHA: somente WRITE SET autorizado foi tocado.

## Demonstração obrigatória
`estado inicial -> schema novo gerado -> comportamento antigo -> comportamento corrigido`

- estado inicial: `Existing.schema.json` rastreado, worktree limpo;
- schema novo: `New.schema.json` criado sem `git add`;
- comportamento antigo: `git diff --exit-code -- harness/schemas` => exit `0`, sem output;
- comportamento corrigido: `python scripts/check_schema_drift.py` => exit `1`, `?? harness/schemas/New.schema.json`.

## Testes
Comando local:
`python -m pytest -q`

Resultado:
`4 passed in 0.11s`

Cobertura específica:
- untracked novo;
- tracked modificado;
- estado limpo;
- arquivo ignorado não mascarado.

A suíte completa do Harness não foi executada no sandbox porque o ambiente não consegue resolver `github.com` para clonar o repositório. O patch não altera runtime/core/contracts e os testes novos foram executados isoladamente com Git real. O workflow da branch worker também não dispara em `push`, pois o YAML existente restringe push à branch `harness-core-v0.1`; não foi aberto PR porque review/integração pertencem ao Integrador.

## Decisão técnica
Preferido `git status --porcelain` a combinar `git diff` + `git ls-files` porque:
- usa uma única visão Git do estado;
- detecta tracked e untracked no mesmo mecanismo;
- permite explicitar arquivos ignorados como drift;
- não altera o índice;
- não adiciona dependências;
- mantém o check escopado ao diretório de schemas.

## Tentativa que falhou -> causa -> solução correta
- falha: primeira demonstração CLI executou o script fora do layout do repositório e `git status` retornou 128;
- causa: `ROOT` é derivado da localização real de `scripts/check_schema_drift.py`;
- solução: executar/copiar o script em `repo/scripts/`, reproduzindo o layout de produção;
- resultado correto: check antigo exit `0`; novo check exit `1` com o schema untracked identificado.

## SCOPE_EXPANSION_REQUEST
Componente: `harness-core-v0.1/harness/schemas/**`.

Motivo: no BASE_SHA nenhum schema gerado está rastreado, apesar de o exportador gerar um arquivo por contrato e `all.schemas.json`. O novo check revelará corretamente esse drift preexistente.

Necessidade: para CI verde após integração, materializar/versionar o baseline atual dos schemas sem alterar os contratos.

Não implementado porque `harness/schemas/**` não consta no WRITE SET deste worker.

## INTERPRETATION_DIVERGENCE
A missão fala em "schema já rastreado", enquanto a base observada não contém schemas rastreados. Recomenda-se interpretar que os schemas devem ser artefatos versionados e que a ausência atual é precisamente parte do blind spot histórico.

## Riscos residuais
- Integrar apenas o commit deste worker, sem materializar o baseline de schemas, fará a CI falhar após o exportador. Isso é fail-closed e evidencia o estado real; não é mascarado pelo worker.
- A execução remota da suíte completa deve ser feita pelo Integrador no conjunto final.

## Passos mínimos de reprodução
1. Em clone do repositório, checkout do commit funcional/branch worker.
2. `cd harness-core-v0.1`.
3. `python -m pip install -e '.[dev]'`.
4. `pytest tests/test_schema_drift_check.py`.
5. Em repo temporário, criar schema novo untracked e confirmar que `git diff --exit-code -- harness/schemas` retorna `0` enquanto `python scripts/check_schema_drift.py` retorna `1`.
6. Após baseline de schemas ser autorizado/versionado, executar `python scripts/export_schemas.py && python scripts/check_schema_drift.py`; estado determinístico deve retornar `0`.

## Referência ao code-map
Nenhuma alteração no `CODE_MAP.md` global, conforme regra de documentação paralela. O Integrador deve consolidar a entrada após integração.
