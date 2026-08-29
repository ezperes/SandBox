# CORE-FRESHNESS-GATE — Reauditoria Arquitetural

Data: 2026-08-29
Branch auditada: `worker/core-freshness-gate`
PR: #17 (draft)
HEAD_SHA auditado e congelado: `61cd47670909469d0c684396d73b4572a1e4463a`
Status da reauditoria: **REWORK — NÃO INTEGRAR AINDA**

## Escopo

Reauditoria independente de T07, T10, T11 e T12 sobre o SHA acima. A análise considerou código produtivo, testes adicionados na PR e a ordem real dos boundaries sensíveis. O critério permanece:

`FUNCIONAL ∩ CONTRATUAL ∩ ARQUITETURAL ∩ AUTORIZADO ∩ TESTADO ∩ RASTREÁVEL`

## Resultado executivo

| Teste | Classificação | Parecer |
|---|---|---|
| T07 | `PARTIAL` | Mecanismo existe e deriva `changed_chains`, mas falta prova executável específica de mudança somente técnica mid-run e há lacuna de identidade/revisão anterior persistida. |
| T10 | `PROVEN` para o boundary atual | `StateManager.resume()` exige freshness, re-resolve, rebuilda contexto aplicável, persiste `RV-*`/RunState e somente então chama `RuntimePort.resume()`. Falha de freshness impede o runtime. |
| T11 | `CONTRADICTED` | `ToolGateway` recebe `freshness_gate` opcional; quando não configurado, um side effect pode atravessar autorização/ledger/ToolPort sem qualquer freshness check. |
| T12 | `PARTIAL` | Fail-closed continua presente, mas falhas de freshness não geram trilha persistente equivalente ao `RV-*`; conflito/lacuna ainda não possui decision trace completo e persistido. |

Parecer da PR #17: **REWORK**.

## T07 — PARTIAL

### Evidência positiva

`ResumeFreshnessGate._changed_chains()` compara `source_revision_refs` capturados com `revision_ref` atual e marca apenas as cadeias divergentes. `ContextBuilder.rebuild_partial()` é chamado com esse conjunto. `RevalidationAuditRecord.changed_chains` persiste a transição usada no resume.

O teste existente prova alteração exclusivamente tática e preservação da cadeia técnica.

### Gap

O critério de reauditoria exigia cenário formal de mudança **somente técnica** mid-run, preservando tática e normativa. Não existe prova executável dedicada desse cenário no SHA auditado.

Além disso, `ResumeFreshnessGate` sempre re-resolve a identidade atual, mas V0.1 não persiste o `AgentIdentity` anterior. O próprio código reconhece essa limitação. `identity_changed` é inferido comparando authority refs anteriores/atuais, não comparando a revisão/semântica da identidade anterior. Portanto uma mudança na identidade que conserve os mesmos refs de autoridade pode não ser distinguida historicamente como mudança de identidade.

### Classificação

`PARTIAL`.

## T10 — PROVEN no boundary StateManager.resume

### Ordem efetivamente implementada

`Checkpoint/RunState válido`
→ exige `freshness_gate`
→ `freshness_gate.prepare(run)`
→ re-resolve identidade
→ re-resolve autoridade
→ detecta cadeias alteradas
→ rebuild parcial ou rebind de contexto
→ constrói `RevalidationAuditRecord`
→ persiste `RV-*`
→ rebind `HarnessRun.authority_context_ref/task_context_ref`
→ acrescenta `RV-*` a `RunState.decision_refs`
→ persiste `RunState`
→ somente então `RuntimePort.resume()`.

A ausência de freshness gate falha fechado antes do runtime. Uma autoridade alterada que deixa de resolver também falha antes do runtime. O teste `AuditAwareRuntime` confirma que, dentro da chamada de resume do runtime, o `RV-*` já existe no StatePort e o `RunState` já aponta para ele.

### Limite da classificação

A classificação `PROVEN` vale para o boundary institucional atualmente materializado em `StateManager.resume()`. Não significa que todo T10 futuro esteja resolvido para qualquer coordenador alternativo que ignore `StateManager`.

### Classificação

`PROVEN` para o fluxo V0.1 auditado.

## T11 — CONTRADICTED

### Falha arquitetural encontrada

O código da PR define:

`ToolGateway(..., freshness_gate: AuthorityFreshnessGate | None = None)`

E executa freshness somente quando:

`descriptor.side_effect and self.freshness_gate is not None`.

Logo existe caminho executável válido pela própria API do Core:

`ToolGateway sem freshness_gate`
→ side effect registrado
→ `AuthorityResolver.decide()` sobre `AuthorityContext` antigo
→ ledger
→ `ToolPort.invoke()`.

Esse caminho contradiz diretamente o requisito:

“nenhum side effect alcança ToolPort com AuthorityContext stale/unverificável”.

Os testes T11 criam explicitamente o gateway **com** `AuthorityFreshnessGate`, portanto demonstram apenas o caminho configurado corretamente e não eliminam o bypass pela configuração default.

### Correção mínima necessária

Para side effects, freshness não pode ser opt-in. Uma das soluções aceitáveis deve tornar estruturalmente impossível construir/executar o boundary de side effect sem freshness Core-owned, por exemplo:

- exigir `AuthorityFreshnessGate` no construtor sem default; ou
- exigir `SourcePort` e construir o gate internamente; ou
- falhar fechado em `execute()` quando `descriptor.side_effect` e o gate estiver ausente.

A escolha deve preservar `CORE ← PORTS ← ADAPTERS` e não transferir autoridade ao adapter.

Adicionar teste de regressão obrigatório:

`side effect + ToolGateway sem freshness configurado → fail-closed → ToolPort.calls == []`.

### Classificação

`CONTRADICTED`.

## T12 — PARTIAL

### Evidência positiva

Freshness não resolvível gera `HarnessResolutionError(AUTHORITY_UNRESOLVED)` e não inventa autoridade. O `RV-*` registra snapshot/contexto/Bootstrap/changed_chains para revalidações bem-sucedidas de resume.

### Gap

No caminho negativo de T10, o próprio teste confirma:

`state_port._revalidation_records == {}`.

Isto significa que uma tentativa de resume bloqueada por freshness não deixa um `RevalidationAuditRecord` persistido explicando a falha.

No T11, falha de freshness também ocorre antes de qualquer trilha persistente equivalente ao `RV-*`. A exceção contém causa em processo, mas não há decision trace institucional persistido com fonte, revisão esperada/atual, boundary e decisão final.

Assim, o requisito de reconstrução posterior do motivo de bloqueio ainda não está completo.

### Correção mínima recomendada

Persistir um registro de tentativa de revalidação também para o caminho fail-closed, contendo ao menos:

- run_id;
- boundary;
- source/authority ref;
- revisão esperada;
- revisão observada quando disponível;
- código de erro/decisão;
- resultado `BLOCKED/ESCALATED`;
- timestamp;
- refs de contexto/snapshot anteriores quando existentes.

Não é necessário transformar `RevalidationAuditRecord` em contrato canônico nesta etapa; porém o formato interno precisa ser consistente e testável.

### Classificação

`PARTIAL`.

## Invariantes transversais

Não foi encontrada regressão evidente nos princípios:

- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`;
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`;
- runtime/provider sem autoridade institucional;
- checkpoint técnico ≠ checkpoint canônico;
- supporting refs permanecem `POINTER_ONLY`;
- A1/A2/A3/A5 não são redefinidos pela PR.

## Decisão de integração

**NÃO integrar a PR #17 no estado auditado.**

Motivo bloqueante: T11 continua `CONTRADICTED` devido ao freshness gate opcional no `ToolGateway`.

T12 permanece incompleto por ausência de trilha persistida no caminho de bloqueio. T07 precisa de prova dedicada para mudança técnica e melhor tratamento histórico da identidade antes de promoção.

## Ordem mínima de correção

1. Fechar o bypass T11 tornando freshness obrigatório/fail-closed para todo side effect.
2. Adicionar teste de regressão do gateway sem freshness.
3. Persistir decision/revalidation trace também em falhas de freshness relevantes para T12.
4. Adicionar teste T07 técnico-only e revisar limitação de identity revision histórica.
5. Executar CI completa.
6. Reauditar novamente T07/T10/T11/T12.

## Parecer final

`REWORK`

`HARNESS STATUS = ARCHITECTURAL_BLOCKER` permanece até a nova reauditoria demonstrar que T11 não possui mais caminho contraditório.
