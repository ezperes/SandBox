# FINDINGS — CI-01-SCHEMA-DRIFT

## Finding 1 — blind spot confirmado
`git diff --exit-code -- harness/schemas` não considera arquivos untracked. Um schema novo gerado pode existir no filesystem e ainda produzir exit code `0` no check antigo.

## Finding 2 — baseline canônico ausente do Git no BASE_SHA
No commit `59d3eb987136ec628bcaba4b45949fb81b2616a2`, o tree não contém `harness-core-v0.1/harness/schemas/**`, embora `scripts/export_schemas.py` gere esse diretório e 17 contratos estejam em `CANONICAL_CONTRACTS`.

Consequência: o verificador corrigido detectará imediatamente o baseline atual como untracked. Isso é comportamento correto, mas impede CI verde até os schemas atuais serem materializados/versionados.

## SCOPE_EXPANSION_REQUEST
Solicitada autorização de escrita para `harness-core-v0.1/harness/schemas/**` exclusivamente para materializar a saída atual do exportador sem alterar contratos.

Não executado por este worker porque o WRITE SET autoriza workflow, testes/scripts de validação e `docs/workers/CI-01-SCHEMA-DRIFT/`, não os artefatos gerados.

## OPPORTUNITY_FOUND
Após o baseline ser versionado, considerar um teste que execute o exportador duas vezes e compare hashes/estado Git para explicitar a determinismo da geração. Não necessário para corrigir o blind spot atual e não implementado.
