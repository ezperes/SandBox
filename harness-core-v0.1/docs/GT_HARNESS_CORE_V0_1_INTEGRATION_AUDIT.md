# GT Harness Core V0.1 — Relatório de Integração e Auditoria Arquitetural

Data: 2026-08-29  
BASE_SHA comum dos workers: `59d3eb987136ec628bcaba4b45949fb81b2616a2`  
Staging autoritativa: `integrator/gt-harness-v0.1`  
PR final de integração: `#12`  

Regra de aceitação aplicada:

`FUNCIONAL ∩ CONTRATUAL ∩ ARQUITETURAL ∩ AUTORIZADO ∩ TESTADO ∩ RASTREÁVEL`

`resultado funcionando ≠ resultado aceitável`

## 1. Estado recebido

Quatro workers independentes partiram do mesmo BASE_SHA congelado:

| Worker | Branch | HEAD_SHA | Resultado recebido |
|---|---|---|---|
| A3-LANGGRAPH-REAL | `worker/a3-langgraph-real` | `66d8c0a62646d8818d4ea805e976350b9e59ea85` | LangGraph real, docs e testes |
| B1-CORE-ERRORS | `worker/b1-core-errors` | `10c01bba5378c7341af22b186844707830bcf9c8` | refatoração de `HarnessResolutionError` |
| CI-01-SCHEMA-DRIFT | `worker/ci-schema-drift` | `3c2561a628656d86f9ed0a17dbafbfe24d21a971` | checker de drift e CI |
| ARCH-01-T01-T12-GAP-ANALYSIS | `worker/arch-t01-t12-audit` | `88fc69566838b33153521df9d5714e8fd7396f95` | gap map T01–T12 |

Os quatro HEADs descendem diretamente do BASE_SHA comum. Não foi identificado commit estranho herdado por worker.

## 2. Resultado de cada worker

### A3-LANGGRAPH-REAL — `ACCEPT`

Prova física aceita com `langgraph==1.2.11`: `StateGraph` real, grafo compilado, `MemorySaver`, interrupt estático real, resume na mesma thread, `thread_id == run_id`, checkpoint técnico distinto do checkpoint canônico e tradução para `RunState`.

LangGraph permanece dependência opcional/dev e não entra nas dependências obrigatórias do Core. O runtime não recebe `agent_id`/`authority_context_ref` e não pode injetar `decision_refs` ou `checkpoint_ref` canônicos.

A divergência entre interrupt estático e `interrupt() + Command(resume=...)` foi resolvida em favor do contrato canônico existente: `RuntimePort.resume(run, state)` não possui payload externo. Não foi inventado payload no adapter.

### B1-CORE-ERRORS — `ACCEPT`

`HarnessResolutionError` passa a ter propriedade canônica em `harness.core.errors`. O import legado por `harness.core.identity` continua apontando para a mesma classe. Campos, `HarnessErrorCode`, mensagens e formato de `__str__` foram preservados.

Mudança observável residual: `__module__` passa naturalmente a ser `harness.core.errors`. Não há contrato/teste atual que trate esse metadado interno como semântica persistida.

### CI-01-SCHEMA-DRIFT — `ACCEPT_WITH_FIXES`

O checker novo usa `git status --porcelain=v1 --untracked-files=all --ignored=matching -- harness/schemas` e detecta modificação rastreada, schema novo untracked e schema ignorado.

O worker descobriu corretamente que o BASE_SHA não tinha baseline de schemas versionado. Seu `SCOPE_EXPANSION_REQUEST` foi aceito pelo Integrador exclusivamente para materializar a saída atual do exportador. Foram versionados os 17 schemas canônicos e `all.schemas.json`; nenhum contrato foi alterado para produzir esse baseline.

### ARCH-01-T01-T12-GAP-ANALYSIS — `ACCEPT`

Aceito como auditoria histórica do BASE_SHA e mapa de gaps. Não contém alteração de produção. Suas classificações foram reavaliadas após a integração; os workers A3/B1/CI não fecham as lacunas semânticas T10/T11.

## 3. Conflitos e dissonâncias

### Integração concorrente

Durante a integração surgiram múltiplas staging branches/PRs em paralelo. Isso criou duplicação de história de merge, não divergência semântica de código.

Decisão explícita: `integrator/gt-harness-v0.1` foi escolhida como staging autoritativa por ser a linha mais avançada contendo B1 → A3 → CI → baseline de schemas → ARCH. Histórias temporárias paralelas não são reconciliadas entre si.

A branch canônica recebeu B1 separadamente antes da PR final. Por isso a PR final não reaplica os arquivos de B1; o diff final contém apenas A3, CI, ARCH, schemas e documentação consolidada.

### CI baseline

`INTERPRETATION_DIVERGENCE`: schemas versionados versus schemas efêmeros. Vence a interpretação de artefato versionado, porque a missão exige detectar schema novo não versionado e schema rastreado modificado. Sem baseline, a política de drift não teria estado de referência.

### A3 resume

`INTERPRETATION_DIVERGENCE`: dynamic HITL versus contrato V0.1. Vence a preservação do contrato canônico. Dynamic resume payload fica como incremento futuro Core-owned.

## 4. Decisões de integração

- preservar `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`;
- não alterar contratos para acomodar LangGraph;
- não mover autoridade/identidade para runtime/provider;
- aceitar `HarnessResolutionError` em `core.errors` com re-export legado;
- ativar checker de schemas somente com baseline materializado pelo exportador canônico;
- aceitar a auditoria T01–T12 sem tratá-la como correção dos gaps;
- não corrigir T10/T11 silenciosamente durante integração, pois exigem novo incremento arquitetural Core.

## 5. Ordem de merge

Ordem efetiva na staging autoritativa:

`B1 → validar → A3 → validar → CI-01 → materializar baseline → validar → ARCH-01 → CI combinada → documentação do Integrador → CI final → merge canônico`

A branch canônica recebeu B1 por PR própria antes do merge final. O merge final deve usar a PR `#12`, que aplica apenas o delta ainda ausente na branch canônica.

## 6. Correções realizadas pelo Integrador

1. Autorizada a expansão estritamente necessária de CI para `harness/schemas/**`.
2. Materializado o baseline com o exportador canônico: 17 schemas + agregado.
3. Removido o workflow temporário de materialização; ele não faz parte do diff final.
4. Fechadas PRs duplicadas/supérfluas quando detectadas; nenhuma reconciliação semântica silenciosa foi feita.
5. Consolidada esta auditoria e os artefatos globais de documentação.

## 7. Testes e CI

CI combinada da PR `#12`, workflow `Harness Core CI`, run `33277407796` / run number `91`:

- Ubuntu 24.04;
- CPython `3.11.16`;
- `langgraph==1.2.11` instalado de fato;
- `pytest`: **50 passed in 0.69s**;
- exportador: **17 schemas**;
- `python scripts/check_schema_drift.py`: **PASS** — `schema export matches the Git-tracked state`.

O workflow de PR executou contra o merge virtual de staging + branch canônica, portanto valida a composição que será integrada, não apenas cada worker isoladamente.

## 8. Auditoria T01–T12

| Teste | Estado pós-integração | Síntese |
|---|---|---|
| T01 | `PARTIAL` | gates existem isoladamente; falta ciclo completo identity→authority→context→decision→state→evidence/trace |
| T02 | `PARTIAL` | cadeias Comercial/TI permanecem segmentadas; falta prova semântica objetivo vs método |
| T03 | `NOT_PROVEN` | contratos multidomínio existem; falta roteamento/reconciliação e fechamento global |
| T04 | `PARTIAL` | proibição normativa bloqueia side effect; falta cenário institucional completo |
| T05 | `PARTIAL` | interseção falha fechado; falta preservar objetivo e selecionar método alternativo |
| T06 | `PARTIAL` | competência insuficiente bloqueia; falta Delegation Gate/Port |
| T07 | `PARTIAL` | re-bootstrap parcial existe; falta detector de revisão e transição persistida |
| T08 | `NOT_PROVEN` | falta boundary de mudança de Fração/GT/domínio com nova resolução/bootstrap/profile |
| T09 | `NOT_PROVEN` | falta Delegation Gate + Instruction Compatibility Layer cross-provider |
| T10 | `CONTRADICTED` | resume técnico pode ocorrer antes de revalidar identidade/autoridade/revisões/contexto |
| T11 | `CONTRADICTED` | `AuthorityContext` antigo pode chegar a novo side effect sem freshness/revision gate |
| T12 | `PARTIAL` | fail-closed/ESCALATE existe; falta conflito explícito + decision trace completo persistido |

Contagem: `PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`.

## 9. Invariantes arquiteturais verificadas

- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA` permanece regra de autorização positiva.
- Contratos canônicos não foram alterados pelos quatro workers desta rodada.
- LangGraph permanece atrás de Runtime Adapter e opcional para o pacote-base.
- checkpoint LangGraph é técnico; `Checkpoint`/`RunState` canônicos permanecem Core-owned.
- provider/runtime não reescrevem `AgentIdentity`.
- runtime não recebe prerrogativa de autoridade institucional.
- side effects continuam atrás de `ToolGateway` e ledger/idempotência Core-owned.
- A1, A2 e A5 não tiveram mudança semântica nesta integração e a suíte combinada permaneceu verde.
- `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` continuam `POINTER_ONLY` na V0.1; não houve alteração do contrato e os schemas regenerados preservam `supporting_ref_semantics` com default `POINTER_ONLY`.

## 10. Riscos residuais

### P0 — T10: resume canônico incompleto

`StateManager.resume()` pode chegar ao runtime sem obrigar re-resolução de identidade/autoridade/revisões e reconstrução do Active Context. Idempotência evita duplicação conhecida, mas não evita continuação sob contexto stale.

### P0 — T11: autoridade stale antes de side effect

`ToolGateway` recebe `AuthorityContext` já construído e não possui freshness gate que compare revisões com fontes canônicas atuais. Uma permissão revogada após rev-A pode continuar sendo usada se o contexto antigo for reutilizado.

### Outros

- `MemorySaver` prova checkpoint físico, não durabilidade de produção.
- dynamic HITL ainda não tem payload de resume canônico Core-owned.
- provider OpenAI live continua gate independente; stub não é prova live.
- GitHub Actions avisa de metadata Node.js 20 em `checkout@v4`/`setup-python@v5`; não afeta o resultado atual.

## 11. Débitos técnicos

1. `P0` — Core freshness/revalidation boundary cobrindo T10/T11.
2. `P1` — Run Coordinator/Agent Loop que componha o ciclo institucional completo.
3. `P1` — Delegation Gate/Port e evidência de delegação.
4. `P1` — detector de revisão de autoridade/contexto e versionamento de transição.
5. `P1` — mudança de domínio/Fração/GT com nova Identity/Authority/Bootstrap/Profile.
6. `P1` — Instruction Compatibility Layer para delegação cross-provider.
7. `P1` — decision trace persistido para conflitos T12.
8. `P1` — roteamento/reconciliação de obrigações multidomínio T03.
9. `P2` — decidir durable checkpointer de runtime para produção.
10. `P2` — atualizar GitHub Actions quando conveniente para eliminar depreciação Node 20.

## 12. Oportunidades de melhoria

- criar uma suíte `tests/architecture/test_t01_t12.py` orientada aos cenários canônicos, não apenas unidades;
- introduzir um objeto Core-owned de resume input para HITL dinâmico depois do freshness gate;
- materializar um coordenador de “próximo passo relevante” que centralize revalidação antes de runtime/tool boundary;
- manter schemas como artefatos gerados versionados e usar o checker atual como proteção anti-drift.

## 13. Commits finais

Workers:

- A3: `66d8c0a62646d8818d4ea805e976350b9e59ea85`;
- B1: `10c01bba5378c7341af22b186844707830bcf9c8`;
- CI-01: `3c2561a628656d86f9ed0a17dbafbfe24d21a971`;
- ARCH-01: `88fc69566838b33153521df9d5714e8fd7396f95`.

Integração intermediária relevante:

- baseline de schemas materializado: `2fe9cf4d7a5b2a7a124f2e8d9f582aafd144e92c`;
- staging após ARCH: `e24a215316d7aa7b21b15486949ba566ddc0f8d7`.

O SHA do merge canônico final é registrado no handoff externo após o merge; o documento não tenta referenciar o SHA do próprio commit futuro.

## 14. Estado do Harness após integração

As quatro missões paralelas são integráveis e a composição é funcional/testada. A3 está fisicamente comprovado com LangGraph real; B1 preserva a semântica pública; CI detecta drift rastreado/untracked/ignored com baseline real; ARCH produz mapa T01–T12.

Isso **não** torna o Harness pronto para o primeiro E2E institucional.

`HARNESS STATUS = ARCHITECTURAL_BLOCKER`

Motivo: T10 e T11 estão `CONTRADICTED` e envolvem autoridade/contexto stale antes de retomada/novo side effect. São riscos institucionais P0.

## 15. Próximo passo executável

**ÚNICO PRÓXIMO PASSO PRIORITÁRIO:** implementar `CORE-FRESHNESS-GATE` orientado pelos testes arquiteturais T10 e T11.

Ordem interna do incremento:

`teste T10/T11 falhando → Core revalida revisions/identity/authority → reconstrói Active Context afetado → só então RuntimePort.resume/ToolGateway side effect → persistir snapshot/decision trace → testes verdes`.

Não iniciar E2E antes desse gate.