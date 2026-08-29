# Implementation Report — Harness Core V0.1

## Estado consolidado

Os Incrementos 1–7 e o GT paralelo de 2026-08-29 estão consolidados em staging. Resultado técnico conjunto: **50 testes verdes**, schemas versionados e CI endurecida. O Harness, porém, **não está pronto para E2E institucional** porque T10 e T11 permanecem `CONTRADICTED`.

## Incrementos 1–7

### Incremento 1 — contratos, ports e runtime fake
Contratos Pydantic V0.1, Ports estáveis e `FakeRuntimeAdapter` sem framework obrigatório. JSON Schema é gerado dos contratos.

### Incremento 2 — identidade e autoridade
`IdentityResolver` lê identidade exclusivamente de `SourcePort`. `AuthorityResolver` mantém cadeias tática/técnica/normativa separadas, snapshots de revisão e autorização positiva pela interseção das cadeias aplicáveis. Fail-closed em conflito/lacuna.

### Incremento 3 — bootstrap e contexto
`BootstrapResolver` + `ContextBuilder` com segmentação por cadeia, budget, deduplicação, proveniência e Re-Bootstrap parcial. Supporting refs permanecem `POINTER_ONLY` na V0.1.

### Incremento 4 — estado, checkpoint e idempotência
`StatePort`, `InMemoryStateAdapter` e `StateManager` possuem `RunState`, `Checkpoint` canônico e ledger `PENDING|COMPLETED|FAILED|UNKNOWN`. Checkpoint nativo de runtime não substitui o canônico.

### Incremento 5 — Tool Registry/Gateway
`ToolGateway` bloqueia boundary externo antes de autoridade/escopo, competência, aprovação e idempotência. Evidência obrigatória é validada após execução. Débito P0 atual: freshness de autoridade antes de side effect (T11).

### Incremento 6 — roteamento/model provider
Contratos neutros `ModelRequest`, `ModelSelection`, `ModelResponse`; `ModelRouter`; Fake adapter; `OpenAIResponsesAdapter` por cliente injetado. Provider/modelo não altera identidade/autoridade. Chamada live permanece gate separado A4.

### Incremento 7 — Runtime Adapter LangGraph
`LangGraphAdapter` permanece atrás de `RuntimePort`. A3 comprovou fisicamente LangGraph `1.2.11` com `StateGraph`, `MemorySaver`, `interrupt_before`, checkpoint técnico e resume no mesmo `thread_id`. LangGraph é dependência opcional/dev, não do Core. O runtime não injeta `decision_refs`/`checkpoint_ref` canônicos. Débito P0 atual: resume institucional precisa revalidar contexto/autoridade antes do runtime (T10).

## Gates/retificações concluídos

- **R1:** `NAO_APLICAVEL_JUSTIFICADO` exige justificativa real.
- **R2:** runtime não injeta refs canônicos de decisão/checkpoint.
- **A1:** autorização por `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`/interseção de allow-lists aplicáveis.
- **A2:** ledger idempotente com estado e reconciliação.
- **A3:** prova física LangGraph real concluída.
- **A5:** supporting refs explicitamente `POINTER_ONLY`.
- **B1:** `HarnessResolutionError` movido para `harness.core.errors`, mantendo alias legado idêntico.
- **CI-01:** schema drift detecta tracked/untracked/ignored; baseline de schemas foi versionado.

## GT paralelo — decisões do Integrador

| Worker | Resultado | Decisão |
|---|---|---|
| `worker/b1-core-errors` | propriedade neutra de `HarnessResolutionError`, compatibilidade preservada | `ACCEPT` |
| `worker/a3-langgraph-real` | LangGraph real comprovado sem ganho de autoridade institucional | `ACCEPT` |
| `worker/ci-schema-drift` | detector correto; BASE_SHA não possuía baseline rastreado | `ACCEPT_WITH_FIXES` |
| `worker/arch-t01-t12-audit` | gap map independente, sem produção alterada | `ACCEPT` |

Correção do Integrador para CI-01: materializar `harness/schemas/**` pelo próprio `scripts/export_schemas.py` em GitHub Actions/Python 3.11, sem alterar contratos. Foram versionados 17 schemas individuais + `all.schemas.json`.

## Ordem de integração executada em staging

`B1 → A3 → CI-01 → materialização de schemas → ARCH-01 → CI conjunta → auditoria final`

A branch integradora principal avançou concorrentemente com B1 durante o trabalho. O evento foi auditado: era o mesmo B1 aceito, sem divergência semântica; nenhum merge final foi feito silenciosamente sobre base desconhecida.

## CI conjunta

GitHub Actions `Harness Core CI` sobre o merge testado da integração:

- Ubuntu 24.04;
- CPython `3.11.16`;
- Pydantic `2.13.5`;
- pytest `8.4.2`;
- LangGraph `1.2.11`;
- `pytest`: **50 passed in 0.69s**;
- `export_schemas.py`: **17 schemas exportados**;
- `check_schema_drift.py`: **schema export matches the Git-tracked state**.

## Auditoria T01–T12

`PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`

| Classe | Testes |
|---|---|
| `PARTIAL` | T01, T02, T04, T05, T06, T07, T12 |
| `NOT_PROVEN` | T03, T08, T09 |
| `CONTRADICTED` | **T10, T11** |

### T10 — P0
`StateManager.resume()` chama `RuntimePort.resume()` depois de validar checkpoint/estado, mas antes de qualquer re-resolução de identidade/autoridade/revisões ou reconstrução do Active Context. A3 prova mecânica física de resume; não prova segurança institucional desse fluxo.

### T11 — P0
`ToolGateway.execute()` decide sobre o `AuthorityContext` recebido sem freshness gate contra as revisões atuais das fontes. Uma revogação posterior pode não ser observada antes de novo side effect.

Detalhes completos: `docs/POST_INCREMENT_AUDIT_1_7.md` e `docs/workers/ARCH-01-T01-T12-GAP-ANALYSIS/GAP_MAP_T01_T12.md`.

## Invariantes preservados

- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`;
- identidade pertence ao Core/fontes canônicas;
- autoridade pertence ao Core/fontes canônicas;
- provider/modelo não redefine `AgentIdentity`;
- checkpoint nativo não substitui `Checkpoint` canônico;
- `procedural_refs`, `knowledge_refs`, `risk_refs`, `memory_refs` continuam `POINTER_ONLY`;
- side effects passam pelo Tool Gateway e ledger;
- conflitos/lacunas conhecidos mantêm postura fail-closed.

## Tentativa que falhou → causa → solução correta

- Exportador inicial não importava `harness` → raiz não estava em `sys.path` → script passou a inserir `ROOT`.
- Rebuild total de contexto relia fontes desnecessárias → violava economia de tokens/I/O → Re-Bootstrap parcial.
- Claim binário de idempotência não distinguia resultado desconhecido → risco de retry duplicado → ledger com estados + reconciliação.
- Comparação integral de `AgentIdentity` falhou por `resolved_at` → timestamp não é mutação institucional → comparação de campos semanticamente estáveis.
- Runtime aceitava refs canônicos do estado nativo → framework ganhava poder indevido → refs canônicos somente do Core.
- A3 tentou validação local com clone/package → ambiente sem resolução de `github.com` → GitHub Actions executou a prova física com versão fixada.
- CI antiga usava apenas `git diff` → arquivos novos/untracked não eram vistos → `git status --porcelain` escopado a schemas.
- BASE_SHA não tinha schemas rastreados → hardening correto tornaria CI imediatamente vermelha → Integrador materializou o baseline com o exportador canônico no mesmo tipo de ambiente da CI.
- Durante integração, base principal avançou → outro fluxo integrou B1 → base foi re-auditada; por ser o mesmo worker/conteúdo aceito, a integração continuou via PR recalculada, sem overwrite silencioso.

## Riscos residuais

1. **T11 — autoridade stale antes de side effect — P0.**
2. **T10 — resume com contexto stale — P0.**
3. T03/T06/T08/T09 — coordenação/delegação/transição organizacional ainda incompletas.
4. T07/T12 — detector de revisions e decision trace persistido incompletos.
5. A4 — provider live ainda não provado.
6. Pydantic não está lockado; drift futuro será detectado pela CI, mas precisará revisão explícita.

## Code map

`docs/CODE_MAP.md`.

## Estado e próximo passo

`HARNESS STATUS = ARCHITECTURAL_BLOCKER`

Próximo passo executável prioritário: **implementar um freshness/revision gate Core-owned antes de side effects no `ToolGateway` para fechar T11, falhando fechado quando o `AuthorityContext` não corresponder às revisões atuais das fontes.** O mesmo primitivo deverá ser reutilizável posteriormente no resume para fechar T10.
