# IMPLEMENTATION_LOG — CI-01-SCHEMA-DRIFT

## Identidade
- WORK_TASK_ID: `CI-01-SCHEMA-DRIFT`
- BASE_BRANCH: `harness-core-v0.1`
- BASE_SHA: `59d3eb987136ec628bcaba4b45949fb81b2616a2`
- WORK_BRANCH: `worker/ci-schema-drift`

## Estado observado
- O workflow executava `python scripts/export_schemas.py` seguido de `git diff --exit-code -- harness/schemas`.
- `scripts/export_schemas.py` cria `harness/schemas/` e escreve um arquivo por contrato mais `all.schemas.json`.
- No tree do BASE_SHA não existe `harness-core-v0.1/harness/schemas/`; portanto o estado atual produzido pelo exportador é completamente untracked.

## Demonstração do blind spot
`estado inicial -> schema novo gerado -> comportamento antigo -> comportamento corrigido`

1. Repositório Git temporário com `Existing.schema.json` rastreado e limpo.
2. Criado `New.schema.json` sem `git add`.
3. Check antigo: `git diff --exit-code -- harness/schemas` retornou `0` e nenhum output.
4. Check novo: `python scripts/check_schema_drift.py` retornou `1` e reportou `?? harness/schemas/New.schema.json`.

## Implementação
- Novo `scripts/check_schema_drift.py` consulta `git status --porcelain=v1 --untracked-files=all --ignored=matching -- harness/schemas`.
- Qualquer entrada `M`, `D`, `A`, `??` ou `!!` dentro do diretório de schemas é drift e produz exit code `1`.
- Workflow passa a executar o verificador após o exportador.
- Nenhuma dependência nova foi adicionada.

## Testes locais
Comando: `python -m pytest -q`
Resultado: `4 passed in 0.11s`.

Casos cobertos:
- novo schema untracked: check antigo retorna `0`; novo check detecta;
- schema rastreado modificado: novo check detecta;
- estado limpo: novo check retorna vazio/verde;
- schema gerado ignorado por `.gitignore`: novo check detecta `!!`, evitando mascaramento.

## Tentativa que falhou -> causa -> solução correta
- Tentativa: demonstração CLI executando `/tmp/ci01-work/scripts/check_schema_drift.py` contra outro repositório temporário.
- Falha: o script deriva `ROOT` da própria localização; como estava fora do repositório demonstrativo, `git status` executou no diretório errado e retornou 128.
- Causa: harness de teste não reproduzia o layout real `repo/scripts/check_schema_drift.py`.
- Solução correta: copiar o script para `repo/scripts/` e repetir. Resultado: check antigo `0`; novo check `1` com `?? harness/schemas/New.schema.json`.

## SCOPE_EXPANSION_REQUEST
- componente: `harness-core-v0.1/harness/schemas/**`
- motivo: no BASE_SHA nenhum schema exportado está rastreado. Ativar o check correto fará a CI detectar todos os schemas atuais como `??`.
- impacto: para a CI ficar verde após a correção, é necessário materializar e versionar o baseline atualmente gerado.
- necessidade: indispensável para integrar o check mantendo a semântica de "schemas versionados".
- alternativa possível: nenhuma equivalente sem duplicar o baseline em manifesto/fixture fora de `harness/schemas`, o que criaria uma segunda fonte de verdade e reduziria a qualidade da verificação.
- status: NÃO IMPLEMENTADO por estar fora do WRITE SET.

## INTERPRETATION_DIVERGENCE
- questão: a missão pressupõe detecção contínua de "schema já rastreado", mas o BASE_SHA não contém `harness/schemas/**` rastreado.
- interpretação A: os schemas devem ser artefatos versionados e o baseline está ausente por causa do blind spot existente.
- interpretação B: os schemas são intencionalmente efêmeros e não devem ser versionados.
- evidência A: workflow usa `git diff` sobre `harness/schemas`; missão exige falha para schema "novo não versionado" e detecção de schema "já rastreado".
- evidência B: ausência atual do diretório no tree.
- recomendação: interpretação A.
- impacto de escolher errado: A sem materialização deixa CI vermelha; B torna sem sentido a verificação Git de drift pedida pela missão.
- escalonamento: necessário apenas para autorizar a materialização dos schemas atuais fora do WRITE SET deste worker.
