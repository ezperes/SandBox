# CORE-FRESHNESS-GATE — Preparação de Reauditoria Arquitetural

Data: 2026-08-29
Branch: `worker/core-freshness-gate`
PR: #17 (draft)
Status: **READY_FOR_ARCHITECTURAL_REAUDIT — NÃO CANÔNICO ATÉ MERGE**

## Por que este documento existe

`docs/POST_INCREMENT_AUDIT_1_7.md` registra corretamente o último estado canônico integrado, no qual T10 e T11 estão `CONTRADICTED`. Não se deve sobrescrever essa história antes da integração. Este documento registra a nova evidência da PR #17 e define o gate que poderá promover as classificações.

## Evidência nova

### T07 — revisão e rebuild seletivo
- `ResumeFreshnessGate` deriva `changed_chains` comparando revisions capturadas com revisions atuais.
- `ContextBuilder.rebuild_partial()` é acionado apenas para cadeias afetadas.
- `RevalidationAuditRecord` persiste as cadeias alteradas e a transição usada no boundary.
- Candidato a promoção após cenário formal T07: alteração de autoridade técnica mid-run deve invalidar/reconstruir somente a cadeia técnica e preservar tática/normativa.

### T10 — resume institucional
Caminho candidato atual:

`Checkpoint/RunState válido → Core freshness → re-resolve identity/authority → detectar changed_chains → rebuild seletivo → persistir RV-* + decision_ref → rebind run → RuntimePort.resume()`

Provas já existentes:
- resume sem freshness gate falha fechado;
- autoridade alterada não resolvível impede qualquer chamada ao runtime;
- alteração tática recompõe somente a cadeia afetada;
- registro auditável é persistido antes da chamada externa.

### T11 — side effect institucional
Caminho candidato atual:

`ToolDescriptor side-effect → AuthorityFreshnessGate → authority/competence/approval → ledger → ToolPort`

Provas já existentes:
- revisão atual permite prosseguimento;
- `rev-A → rev-B` invalida contexto antigo antes do adapter;
- ausência de revision suficiente falha fechado;
- adapter não é chamado sob snapshot stale/unverificável.

### T12 — rastreabilidade da decisão
- `RV-*` melhora a trilha persistida com snapshot, refs anteriores/novas, Bootstrap trace, changed_chains e boundary.
- Isso não prova sozinho todo T12: ainda é necessário testar conflito institucional não resolvido terminando em `ESCALATE`/fail-closed com fundamentos rastreáveis.

## Gate de reauditoria obrigatório

Reexecutar T07/T10/T11/T12 contra o HEAD final da PR #17 e classificar cada cenário como:

`PROVEN | PARTIAL | NOT_PROVEN | CONTRADICTED`

Critérios mínimos:

1. **T07:** mudança somente técnica mid-run → somente cadeia técnica é reconstruída; demais cadeias preservadas; transição persistida.
2. **T10:** nenhum caminho de `StateManager.resume()` alcança `RuntimePort.resume()` sem freshness/re-resolution aplicável; resultado da revalidação persiste antes do runtime.
3. **T11:** nenhum side effect alcança ToolPort com `AuthorityContext` stale/unverificável; revogação posterior é observada antes do adapter.
4. **T12:** conflito/lacuna não resolvido não inventa autoridade e gera saída fail-closed/ESCALATE com trilha suficiente para auditoria.

## Regra de integração

A PR #17 só deve deixar draft/ser integrada se:
- CI verde no HEAD final;
- code review sem regressão A1/A2/A3/A5;
- reauditoria T07/T10/T11/T12 concluída;
- nenhuma nova `CONTRADICTED` introduzida;
- incongruence check entre código, testes, schemas, Code Map, Implementation Log/Report e Plano de Implementação.

Após merge:
1. executar CI na branch canônica;
2. atualizar `POST_INCREMENT_AUDIT_1_7.md` com as novas classificações;
3. atualizar o Plano de Implementação no Drive;
4. decidir A4/provider e autorização para o primeiro E2E.

## Próximo passo único

**Executar agora a reauditoria arquitetural T07/T10/T11/T12 sobre a PR #17.**
