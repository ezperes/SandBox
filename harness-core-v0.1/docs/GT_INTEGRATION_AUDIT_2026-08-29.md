# GT Harness Core V0.1 — Relatório de Integração e Auditoria Arquitetural

Data: 2026-08-29  
BASE_SHA comum dos workers: `59d3eb987136ec628bcaba4b45949fb81b2616a2`  
Branch de integração: `integration/gt-harness-core-v0.1`  
Estado deste relatório: pós-integração dos quatro workers, antes da promoção final à branch canônica.

Regra de aceite aplicada:

`FUNCIONAL ∩ CONTRATUAL ∩ ARQUITETURAL ∩ AUTORIZADO ∩ TESTADO ∩ RASTREÁVEL`

`resultado funcionando ≠ resultado aceitável`

## 1. Estado recebido

Quatro Elementos trabalharam isoladamente a partir do mesmo BASE_SHA:

| Worker | Branch | HEAD recebido | Missão |
|---|---|---|---|
| A3 | `worker/a3-langgraph-real` | `66d8c0a62646d8818d4ea805e976350b9e59ea85` | prova física contra LangGraph real |
| B1 | `worker/b1-core-errors` | `10c01bba5378c7341af22b186844707830bcf9c8` | mover `HarnessResolutionError` para `core.errors` sem drift semântico |
| CI-01 | `worker/ci-schema-drift` | `3c2561a628656d86f9ed0a17dbafbfe24d21a971` | eliminar blind spot de schemas novos/untracked |
| ARCH-01 | `worker/arch-t01-t12-audit` | `88fc69566838b33153521df9d5714e8fd7396f95` | auditoria adversarial T01–T12 do BASE_SHA |

Todos preservaram o BASE_SHA de nascimento; nenhuma branch worker seguiu silenciosamente alterações posteriores da integração.

## 2. Resultado de cada worker

### A3 — `ACCEPT`

Evidência aceita:
- teste com pacote LangGraph real `1.2.11`;
- `StateGraph` compilado real;
- `MemorySaver` real;
- interrupt/breakpoint estático real e resume no mesmo `thread_id`;
- `HarnessRun.run_id` projetado para `thread_id`;
- checkpoint técnico do LangGraph distinto do `Checkpoint` canônico;
- `agent_id` e `authority_context_ref` não são entregues como estado institucional ao grafo;
- runtime não injeta `decision_refs`/`checkpoint_ref` canônicos;
- LangGraph permanece dependência opcional/dev, não dependência obrigatória do Core.

`INTERPRETATION_DIVERGENCE`: venceu a interpretação de que A3 exige interrupt/resume real compatível com o `RuntimePort` V0.1, não a introdução silenciosa de `Command(resume=<payload>)`. O port atual não possui payload de decisão externa; dinâmica HITL deve ser futura decisão contratual do Core.

### B1 — `ACCEPT`

A refatoração centralizou `HarnessResolutionError` em `harness/core/errors.py`. Imports internos foram atualizados e `harness.core.identity.HarnessResolutionError` continua como re-export compatível. Teste dedicado preserva classe, `code`, `message`, `source_ref` e representação textual.

Risco residual aceito: `__module__` passa a apontar para `harness.core.errors`; não foi encontrada semântica canônica que trate esse detalhe de introspecção/pickle como contrato público.

### CI-01 — `ACCEPT_WITH_FIXES`

O worker provou o blind spot: `git diff --exit-code -- harness/schemas` não detecta arquivo novo untracked. O novo verificador usa `git status --porcelain=v1 --untracked-files=all --ignored=matching -- harness/schemas` e cobre tracked, untracked e ignored.

O worker corretamente não extrapolou seu WRITE SET e registrou `SCOPE_EXPANSION_REQUEST`: o BASE_SHA não continha schemas versionados. O Integrador aceitou a interpretação de que os schemas são artefatos gerados versionados e materializou o baseline em alteração separada.

Correção do Integrador: geração em GitHub Actions + versionamento dos 17 schemas canônicos e `all.schemas.json`; o workflow temporário usado para materialização foi removido antes do merge.

### ARCH-01 — `ACCEPT`

A auditoria foi incorporada como baseline histórico do BASE_SHA, sem alterar produção. Sua classificação não foi automaticamente promovida a estado pós-integração; os achados foram reavaliados após A3/B1/CI.

## 3. Conflitos e dissonâncias

Não houve conflito textual de produção entre A3, B1 e CI-01. ARCH-01 tocou apenas documentação própria.

Dissonâncias resolvidas explicitamente:

1. **A3 static vs dynamic interrupt:** prevalece static interrupt na V0.1 enquanto `RuntimePort.resume(run, state)` não possuir contrato de payload externo. Nenhuma decisão humana é inventada pelo adapter.
2. **CI schemas efêmeros vs versionados:** prevalece versionamento. A CI já tratava `harness/schemas` como bundle sujeito a drift e a missão exige distinguir schema rastreado de schema novo não versionado.
3. **B1 compatibilidade:** mudança de localização física do erro é interna; identidade da classe e payload observável são preservados por re-export/teste.
4. **ARCH prova unitária vs cenário arquitetural:** para T01–T12, presença de contrato ou teste unitário isolado não equivale a `PROVEN` quando o cenário exige composição de decisão, contexto, estado, evidência e trace.

## 4. Decisões de integração

- B1 integrado primeiro por ser refatoração mecânica e de baixo acoplamento.
- A3 integrado sobre B1 e validado por CI conjunta.
- Baseline de schemas materializado pelo Integrador antes de CI-01.
- CI-01 integrado apenas depois que o baseline versionado tornou o novo checker semanticamente utilizável e verde.
- ARCH-01 integrado por último como evidência histórica, seguida por esta nova auditoria.

Nenhuma correção de T10/T11 foi realizada silenciosamente porque isso exigiria nova missão de produção e decisão de desenho de coordenação do Core.

## 5. Ordem de merge executada

`B1 → CI → A3?` não foi adotado. A ordem efetiva e validada foi:

`B1 → validar/CI → A3 → validar/CI → schema baseline do Integrador → validar/CI → CI-01 → validar/CI → ARCH-01 → validar/CI`

Commits de merge da branch de integração:
- B1: `627ae2305eccd3c3df5ae60a69b0869934da2e3a`
- A3: `1032e020d71963f7fbd4df7fb845cc9635f9958d`
- schema baseline: `58aea84585e7c35dc7039be98ed3fde9319e98d4`
- CI-01: `85658371f9db06a3cbcb68cd7649bc54a4005a3c`
- ARCH-01: `799278f94d5f0bd59a631148117d8566e58a2197`

## 6. Correções realizadas pelo Integrador

### 6.1 Baseline de schemas

Foi criada uma branch auxiliar a partir do estado B1+A3. Um workflow temporário executou no GitHub Actions:

`pip install -e '.[dev]' → python scripts/export_schemas.py → git add harness/schemas → commit`

Resultado: 17 schemas individuais + `all.schemas.json`. O workflow temporário foi removido; o delta final do baseline contém apenas os schemas.

### 6.2 Nenhuma reconciliação arquitetural silenciosa

T10/T11 não foram “corrigidos” dentro da integração porque a mudança correta exige um boundary de revalidação do Core e deve nascer de especificação/teste arquitetural explícitos.

## 7. Testes e CI

Todas as etapas de integração passaram por `Harness Core CI` antes do merge correspondente.

Evidências principais:
- B1: CI verde antes do merge sequencial.
- A3: CI conjunta B1+A3 verde; prova física do LangGraph real executada.
- schema baseline: `pytest` PASS; exportação PASS; `git diff --exit-code -- harness/schemas` PASS.
- CI-01: execução anterior sem baseline falhou exatamente no checker novo; após materialização, `pytest`, exportação e `python scripts/check_schema_drift.py` passaram.
- ARCH-01 sobre base integrada: `pytest`, exportação e checker de schema passaram.

A CI final usa o checker endurecido, portanto um schema novo untracked ou ignored não é mascarado.

## 8. Auditoria T01–T12 pós-integração

A3, B1 e CI-01 não implementaram os componentes de coordenação/delegação/freshness identificados por ARCH-01. A3 fortaleceu exclusivamente a prova física do runtime. Assim, a classificação pós-integração é:

| T | Estado | Fundamentação resumida |
|---|---|---|
| T01 | `PARTIAL` | same-as-tactical, normativa, ALLOW e contexto mínimo existem, mas falta cenário composto completo com estado/evidência/trace |
| T02 | `PARTIAL` | cadeias Comercial/TI e proveniência são separadas; falta prova semântica completa objetivo vs método |
| T03 | `NOT_PROVEN` | CrossDomainEvent é contrato, mas falta produção/reconciliação de obrigações e conclusão local/global |
| T04 | `PARTIAL` | proibição normativa bloqueia boundary; falta cenário arquitetural completo e trace integrado |
| T05 | `PARTIAL` | interseção rejeita método não comum; falta preservar objetivo e selecionar alternativa técnica válida |
| T06 | `PARTIAL` | competência insuficiente não executa; falta Delegation Gate/contrato operacional para Elemento competente |
| T07 | `PARTIAL` | `rebuild_partial` funciona quando informado; falta detector de revision drift e ligação snapshot→Run |
| T08 | `NOT_PROVEN` | falta transição Fração/GT/domínio com nova identidade/autoridade/bootstrap/profile |
| T09 | `NOT_PROVEN` | falta Delegation Gate + InstructionAdapter Claude/Codex e prova de não herança |
| T10 | `CONTRADICTED` | `StateManager.resume()` ainda chama runtime diretamente sem re-resolução/rebuild do Active Context |
| T11 | `CONTRADICTED` | `ToolGateway` ainda aceita AuthorityContext potencialmente stale sem freshness/revision gate |
| T12 | `PARTIAL` | ESCALATE fail-closed existe; falta conflito/decision trace completo, persistido e fundamentado |

Totais: `PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`.

A3 **não** altera T10: resume físico real do LangGraph e resume canônico seguro são problemas diferentes.

## 9. Invariantes arquiteturais verificadas

### Preservadas

- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`.
- LangGraph não é dependência obrigatória de `[project].dependencies`.
- Runtime não recebe autoridade institucional nem identidade como fonte de verdade.
- Provider/modelo não altera `AgentIdentity`.
- checkpoint técnico LangGraph não substitui `Checkpoint` canônico.
- side effects continuam atravessando `ToolGateway` e ledger de idempotência.
- A1: autorização positiva por interseção permanece coberta e CI verde.
- A2: ledger `PENDING | COMPLETED | FAILED | UNKNOWN` permanece coberto e CI verde.
- A5: `procedural_refs`, `knowledge_refs`, `risk_refs`, `memory_refs` permanecem `POINTER_ONLY`; não são lidos/budgetados automaticamente.
- erro compartilhado B1 não altera decisão, política ou códigos canônicos.
- CI não mascara schema novo não rastreado.

### Ainda não satisfeitas no ciclo completo

- freshness de identidade/autoridade/contexto antes de próximo passo relevante;
- reconstrução canônica de Active Context antes de resume;
- passagem de domínio/delegação governada;
- trace persistido de conflito e decisão;
- conclusão institucional separada de `harness_status=COMPLETED` do runtime em uma composição E2E completa.

## 10. Riscos residuais

1. **CRITICAL — T10:** retomada pode continuar usando contexto/autoridade obsoletos.
2. **CRITICAL — T11:** side effect novo pode usar AuthorityContext resolvido antes de revogação/mudança da fonte.
3. HIGH — ausência de Delegation Gate impede T06/T08/T09 completos.
4. HIGH — falta gate de conclusão global para obrigações interdomínio de T03.
5. HIGH — T12 não persiste trace completo do conflito.
6. MEDIUM — Pydantic está limitado por faixa (`>=2.10,<3`), não por versão exata; schemas versionados podem revelar drift de gerador em futuras resoluções de dependência, o que é seguro/fail-closed mas reduz reprodutibilidade bit-a-bit entre ambientes não lockados.

## 11. Débitos técnicos

- A4: chamada live de provider ainda não foi provada; um futuro E2E pode usar `FakeModelAdapter` se isso for declarado explicitamente.
- `ToolDescriptor` permanece tipo interno; formalizar somente se cruzar boundary/configuração persistida.
- definir contrato Core-owned para resume input caso dynamic `interrupt()`/HITL seja necessário.
- selecionar checkpointer durável somente quando requisito de deployment justificar; `MemorySaver` prova semântica, não produção durável.
- materializar suíte arquitetural executável T01–T12 progressivamente, sem transformar gaps reais em testes enfraquecidos.
- avaliar lock/pin da toolchain de geração de schemas.

## 12. Oportunidades de melhoria

- introduzir um único boundary Core-owned de “revalidar antes do próximo passo relevante”, reutilizável por resume e side effects;
- produzir `DecisionTrace`/conflito estruturado para T12;
- implementar Instruction Compatibility Layer somente junto com Delegation Gate, evitando providers criarem herança implícita;
- usar a futura suíte T01–T12 como gate arquitetural de regressão;
- manter schemas gerados versionados e o checker estrito como proteção de contrato.

## 13. Commits finais da integração até esta auditoria

- `627ae2305eccd3c3df5ae60a69b0869934da2e3a` — B1 integrado.
- `1032e020d71963f7fbd4df7fb845cc9635f9958d` — A3 integrado.
- `58aea84585e7c35dc7039be98ed3fde9319e98d4` — baseline de schemas integrado.
- `85658371f9db06a3cbcb68cd7649bc54a4005a3c` — CI-01 integrado.
- `799278f94d5f0bd59a631148117d8566e58a2197` — ARCH-01 integrado.

A promoção à branch canônica será registrada separadamente após CI final desta consolidação.

## 14. Estado do Harness após integração

Gates anteriores:
- A1 — `CLOSED`.
- A2 — `CLOSED`.
- A3 — `CLOSED`: LangGraph real comprovado.
- A5 — `CLOSED`.
- B1 — `CLOSED`.
- B5/CI schema blind spot — `CLOSED` após baseline + checker estrito.
- A4 — `OPEN`, mas não é o bloqueador arquitetural prioritário.

Bloqueadores atuais:
- T10 — `CONTRADICTED`.
- T11 — `CONTRADICTED`.

Portanto, integrar os quatro trabalhos não autoriza declarar o Harness pronto para E2E.

`HARNESS STATUS = ARCHITECTURAL_BLOCKER`

## 15. Próximo passo executável

**Único próximo passo prioritário:** abrir e executar a missão `RUN-REVALIDATION-GATE` para especificar por testes e implementar no Core um gate obrigatório de revalidação/freshness antes de `resume` e antes de side effect relevante.

Critério mínimo dessa missão:

`revisão atual das fontes → detectar cadeias alteradas → preservar snapshot histórico → re-resolver autoridade → rebuild seletivo de contexto → ESCALATE quando não seguro → somente então runtime/tool boundary`

Essa missão deve atacar primeiro T10/T11 e fornecer a infraestrutura necessária para elevar T07/T12 posteriormente, sem transferir autoridade ao runtime ou ao provider.
