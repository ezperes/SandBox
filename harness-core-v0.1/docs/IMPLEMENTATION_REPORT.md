# Implementation Report — Harness Core V0.1

## Estado consolidado

Os Incrementos 1–7 e o GT paralelo estão consolidados no estado canônico anterior. O trabalho `CORE-FRESHNESS-GATE` está implementado em branch isolada e PR draft #17, ainda **não integrada** à branch canônica.

Estado canônico anterior: T10/T11 `CONTRADICTED`, Harness em `ARCHITECTURAL_BLOCKER`.
Estado candidato da PR #17: caminhos inseguros conhecidos de T10/T11 foram bloqueados por freshness/revalidation Core-owned, com persistência auditável antes do boundary de resume. A promoção da classificação depende de reauditoria e merge.

## Incrementos 1–7

- Incremento 1: contratos/ports/runtime fake.
- Incremento 2: IdentityResolver + AuthorityResolver e interseção das cadeias aplicáveis.
- Incremento 3: Bootstrap + ContextBuilder + rebuild parcial.
- Incremento 4: RunState, Checkpoint, StatePort e ledger idempotente.
- Incremento 5: Tool Registry/Gateway e gates antes de side effect.
- Incremento 6: contratos/model routing/provider adapters neutros à identidade.
- Incremento 7: LangGraphAdapter atrás de RuntimePort; A3 físico comprovado com LangGraph `1.2.11`.

## Gates já consolidados

- R1: N/A técnico exige justificativa real.
- R2: runtime não injeta refs canônicos.
- A1: autorização positiva por interseção das cadeias aplicáveis.
- A2: ledger `PENDING|COMPLETED|FAILED|UNKNOWN`.
- A3: LangGraph real comprovado.
- A5: supporting refs `POINTER_ONLY`.
- B1: `HarnessResolutionError` em `harness.core.errors` com compatibilidade legada.
- CI-01: drift tracked/untracked/ignored detectado; baseline versionado.

## CORE-FRESHNESS-GATE — resultado candidato

### 1. Boundary de side effect — T11
`AuthorityFreshnessGate` compara as revisions capturadas no `AuthorityContext` com as revisions atuais das fontes canônicas via `SourcePort`.

Fluxo:

`AuthorityContext → freshness → decisão de autoridade → idempotência → ToolPort`

Se freshness não puder ser provado, o fluxo termina fail-closed antes do adapter. O cenário obrigatório `rev-A → rev-B/revogação → contexto rev-A reutilizado` é bloqueado antes do ToolPort.

### 2. Boundary de resume — T10
`ResumeFreshnessGate` executa:

`re-resolve AgentIdentity → re-resolve AuthorityContext → detectar changed_chains → rebuild parcial do Active Context → preparar snapshot/contexto atual → StateManager → RuntimePort.resume`

`StateManager.resume()` agora exige um freshness gate Core-owned. Sem ele, não atravessa o runtime.

### 3. Persistência auditável
Foi criado `RevalidationAuditRecord` com ID `RV-*`.

O registro preserva, antes do resume:
- boundary sensível;
- refs anteriores e atuais de autoridade;
- refs anteriores e atuais de TaskContext;
- `AuthoritySnapshot` atual;
- Bootstrap trace;
- cadeias alteradas;
- flag de mudança de identidade;
- vínculo ao run.

O `RV-*` é persistido e referenciado por `RunState.decision_refs` **antes** da chamada externa ao runtime. Isso transforma a revalidação de um estado apenas in-process em uma evidência histórica recuperável.

## Arquitetura preservada

- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`.
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`.
- Fonte canônica continua sendo acessada via `SourcePort`.
- Tool/Runtime adapters não decidem autoridade/freshness institucional.
- LangGraph continua substituível.
- Supporting refs continuam `POINTER_ONLY`.
- Nenhum contrato canônico/schema foi alterado apenas para acomodar a implementação.

## Validação executável

Última CI funcional registrada após persistência auditável:
- CPython 3.11;
- LangGraph 1.2.11 instalado no ambiente de CI;
- **57 testes passed**;
- **17 schemas exportados**;
- schema drift clean;
- job SUCCESS.

## Tentativa que falhou → causa → solução correta

1. Teste local via clone não executou → ambiente sem resolução DNS para GitHub → usar GitHub Actions sobre o merge ref da PR.
2. Primeiro teste T10 exigiu lista exata de refs → Bootstrap também inclui route ref legítimo → corrigir a expectativa para a invariante arquitetural, sem mudar produção.
3. Após introduzir persistência auditável, test double antigo não possuía snapshot/trace suficientes → o double não representava mais uma preparação válida → atualizar o double; manter a nova exigência de auditoria.

## Situação T01–T12

A tabela canônica do último estado integrado ainda não deve ser sobrescrita antes da reauditoria. A PR #17 fornece nova evidência para:
- T07: detector de revision/changed_chains + rebuild seletivo + trilha de transição;
- T10: freshness/re-resolution/rebuild/persistência antes de resume;
- T11: freshness fail-closed antes de side effect;
- T12: melhora de decision trace por `RV-*`, embora conflito institucional explícito ainda precise ser reavaliado.

Portanto, nesta etapa:

`STATUS DA PR #17 = READY_FOR_ARCHITECTURAL_REAUDIT`

Não declarar ainda `PROVEN` nem liberar E2E antes do review formal.

## Riscos residuais

- Reauditoria formal T07/T10/T11/T12 ainda não executada sobre o HEAD final da PR.
- T03/T06/T08/T09 continuam gaps independentes de coordenação/delegação/transição/instruction compatibility.
- A4 provider-live permanece gate separado.
- O `InMemoryStateAdapter` prova semântica de persistência, não durabilidade de produção.
- Pydantic segue sem lockfile rígido; CI detecta drift, mas upgrade exige revisão explícita.

## Code map

`docs/CODE_MAP.md` foi atualizado para incluir `harness/core/freshness/**`, persistência `RV-*` e testes relacionados.

## Estado e próximo passo

A implementação do blocker comum foi materializada, porém segue isolada na PR draft #17.

Próximo passo prioritário:

`reauditar T07/T10/T11/T12 → se ACCEPT, integrar PR #17 → executar CI pós-merge → atualizar auditoria canônica → decidir A4/E2E`.
