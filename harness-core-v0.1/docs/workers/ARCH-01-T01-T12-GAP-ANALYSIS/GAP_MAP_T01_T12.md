# Gap Map Arquitetural T01–T12

WORK_TASK_ID: `ARCH-01-T01-T12-GAP-ANALYSIS`  
BASE_SHA: `59d3eb987136ec628bcaba4b45949fb81b2616a2`  
WORK_BRANCH: `worker/arch-t01-t12-audit`

## Regra de classificação

- `PROVEN`: comportamento completo demonstrado executavelmente contra o requisito canônico.
- `PARTIAL`: parte relevante está implementada/testada, mas o cenário canônico completo não está demonstrado.
- `NOT_PROVEN`: não há comportamento executável suficiente; contrato/documentação isolados não contam como prova do cenário.
- `CONTRADICTED`: existe caminho executável que pode violar diretamente o requisito.

Critério canônico adicional aplicado: cada cenário T01–T12 deve produzir decisão, contexto, estado, evidência e trace coerentes. Testes unitários isolados são prova parcial quando não compõem o cenário.

## Resumo priorizado

| Teste | Status | Severidade | Prioridade | Síntese |
|---|---|---:|---:|---|
| T10 | CONTRADICTED | CRITICAL | P0 | Resume chama Runtime diretamente sem re-resolver/reconstruir Active Context. |
| T11 | CONTRADICTED | CRITICAL | P0 | Side effect pode usar AuthorityContext antigo sem validar revisão da fonte. |
| T08 | NOT_PROVEN | HIGH | P1 | Não há fluxo executável de mudança de Fração/GT/domínio com nova identidade/autoridade/bootstrap/profile. |
| T09 | NOT_PROVEN | HIGH | P1 | Não há Delegation Gate nem adapters de Instruction Profile por provider/interface. |
| T03 | NOT_PROVEN | HIGH | P1 | CrossDomainEvent existe como contrato, mas nenhum fluxo cria/reconcilia obrigações nem separa conclusão local/global. |
| T07 | PARTIAL | HIGH | P1 | Re-bootstrap parcial existe, mas detecção de mudança de autoridade técnica e versionamento no Run não. |
| T06 | PARTIAL | HIGH | P1 | Competência insuficiente bloqueia execução, porém não delega para Elemento competente. |
| T12 | PARTIAL | HIGH | P1 | Há ESCALATE fail-closed em lacunas, mas falta conflito explícito + decision trace completo/persistido. |
| T05 | PARTIAL | MEDIUM | P2 | Interseção pode rejeitar método, porém não preserva objetivo e seleciona alternativa técnica. |
| T04 | PARTIAL | MEDIUM | P2 | Proibição bloqueia tool call, mas cenário completo não produz contexto/estado/evidência/trace integrados. |
| T02 | PARTIAL | MEDIUM | P2 | Cadeias Comercial/TI são separadas em Authority/Context, sem prova E2E de objetivo vs método sem mistura. |
| T01 | PARTIAL | MEDIUM | P2 | Same-as-tactical + normativa + contexto mínimo são testados separadamente, sem cenário completo integrado. |

Contagem: `PROVEN=0 | PARTIAL=7 | NOT_PROVEN=3 | CONTRADICTED=2`.

---

## T01 — Elemento inteiramente dentro da própria cadeia

**Requisito:** tática/técnica coincidentes, normativa aplicável, execução permitida e contexto mínimo.

**Código relevante:** `core/authority/resolver.py`, `core/context/builder.py`, `core/tools/gateway.py`.

**Teste existente:** `test_same_tactical_chain_is_explicit_not_implicit`; `test_context_builder_materializes_minimum_context_with_provenance`; testes de ALLOW no AuthorityResolver/ToolGateway.

**Evidência:** `MESMA_CADEIA_TATICA` é explícito; normativa pode coexistir; ContextBuilder aplica budget/proveniência; decisão ALLOW existe.

**Lacuna:** nenhuma prova compõe identidade → autoridade → contexto → decisão/tool → estado → evidência/trace em um único cenário. Não há Run Coordinator que materialize o ciclo completo.

**Status:** `PARTIAL`.

**Risco:** componentes verdes podem mascarar falha de integração/ordenação dos gates.

**Menor correção necessária:** um teste arquitetural de composição do Core para T01, usando adapters in-memory/fake, sem provider/runtime real obrigatório.

**Dependência de outro worker:** nenhuma. A3 não é necessário para prova lógica com Runtime fake.

## T02 — Comercial com autoridade técnica de TI

**Requisito:** objetivo da cadeia Comercial; método/padrões da TI; sem mistura de autoridade.

**Código relevante:** `core/authority/resolver.py`, `core/context/bootstrap.py`, `core/context/builder.py`.

**Teste existente:** `test_authority_resolves_three_chains_and_snapshot`; `test_bootstrap_resolves_three_segmented_routes`; provenance por `ChainType`.

**Evidência:** rota tática `COMERCIAL` e técnica `TI` são preservadas separadamente; ContextBuilder mantém refs/proveniência segmentadas.

**Lacuna:** não existe representação/asserção executável de “objetivo” versus “método” no cenário; nenhum teste prova que conteúdo técnico não redefine missão/prioridade tática ou vice-versa.

**Status:** `PARTIAL`.

**Risco:** separação estrutural de refs não garante separação semântica durante decisão/execução.

**Menor correção necessária:** teste de composição com instruções conflitantes por dimensão e asserção sobre output/decision trace.

**Dependência:** nenhuma.

## T03 — Venda com devolução multidomínio

**Requisito:** fato nasce no Comercial, cria obrigações rastreáveis para Financeiro, Contábil, Estoque/Logística e Fiscal quando aplicável; conclusão local ≠ global.

**Código relevante:** contratos `CrossDomainEvent` e `DomainObligation` em `contracts/_models.py`.

**Teste existente:** `test_cross_domain_event_preserves_correlation_and_obligation` constrói manualmente um evento com uma obrigação Financeira.

**Evidência:** contrato valida correlation e obrigação/status.

**Lacuna:** nenhum Core produz obrigações a partir do fato; nenhum dispatcher/reconciler roteia domínios; nenhum gate impede conclusão global com obrigação obrigatória pendente; o teste não cobre múltiplos domínios nem ciclo de status.

**Status:** `NOT_PROVEN`.

**Risco:** evento pode ser serializado sem produzir qualquer consequência operacional rastreável.

**Menor correção necessária:** serviço/port de roteamento interdomínio + regra de fechamento global + teste arquitetural do ciclo completo. Não é correção autorizada nesta missão.

**Dependência:** não presumida. Nenhum dos workers paralelos é considerado solução até integração.

## T04 — Ordem tática conflitante com proibição normativa

**Requisito:** `DENY` ou `ESCALATE` conforme conflito; side effect não ocorre.

**Código relevante:** `AuthorityResolver.decide`, `ToolGateway.execute`.

**Teste existente:** `test_deterministic_decision_precedence`; `test_forbidden_scope_never_reaches_adapter`.

**Evidência:** forbidden scope retorna DENY; ToolGateway converte em `ACTION_FORBIDDEN`; FakeToolAdapter permanece sem chamadas.

**Lacuna:** cenário não está integrado a TaskContext/RunState/Evidence/decision trace; não há teste arquitetural que prove a cadeia normativa que originou a proibição no mesmo Run.

**Status:** `PARTIAL`.

**Risco:** baixo no boundary de tool, médio na rastreabilidade institucional.

**Menor correção necessária:** teste de composição T04 preservando origem normativa e decisão no estado/evidência.

**Dependência:** nenhuma.

## T05 — Método tático viola padrão técnico obrigatório

**Requisito:** preservar objetivo tático, rejeitar método, escolher alternativa tecnicamente válida ou `ESCALATE`.

**Código relevante:** interseção de `allowed_scopes` em `AuthorityResolver`.

**Teste existente:** ação só tática → `ESCALATE`; interseção vazia → `ESCALATE`.

**Evidência:** uma cadeia isolada não cria autorização positiva contra outra cadeia aplicável.

**Lacuna:** action scope não distingue objetivo de negócio de método técnico; não há mecanismo de seleção de alternativa tecnicamente válida nem preservação explícita do objetivo após rejeição do método.

**Status:** `PARTIAL`.

**Risco:** conflito pode terminar seguro, porém sem cumprir a missão tática por alternativa permitida.

**Menor correção necessária:** contrato/decisão que represente objetivo + método e um teste que mantenha o objetivo enquanto altera/rejeita o método.

**Dependência:** nenhuma.

## T06 — Autoridade válida, competência insuficiente

**Requisito:** não executar; delegar para Elemento competente mantendo contrato/evidência.

**Código relevante:** `AuthorityResolver.decide`, `ToolGateway.execute`; `ports/__init__.py`.

**Teste existente:** `test_missing_competence_escalates_before_tool_call`.

**Evidência:** competência insuficiente não chega ao adapter e vira `COMPETENCE_INSUFFICIENT`.

**Lacuna:** não existe DelegationPort/Gate no snapshot nem `DelegationRequest` materializado no bundle atual; o fluxo termina em erro em vez de encaminhar subtrabalho sob contrato/evidência.

**Status:** `PARTIAL`.

**Risco:** fail-closed é preservado, mas trabalho legitimamente delegável fica bloqueado e sem trilha de delegação.

**Menor correção necessária:** contrato de delegação + Delegation Gate/Port + resolução do destino + teste de autoridade transferida/retida, hops e evidência.

**Dependência:** não presumida.

## T07 — Mudança de autoridade técnica durante o Run

**Requisito:** invalidar somente cadeia técnica/contexto afetado, preservar demais segmentos válidos e registrar versões.

**Código relevante:** `ContextBuilder.rebuild_partial`, `AuthorityResolver`/`AuthoritySnapshot`.

**Teste existente:** `test_partial_rebootstrap_reads_only_changed_chain_context_sources`.

**Evidência:** quando o chamador informa `{TECHNICAL}`, o builder preserva tática/normativa e relê apenas tarefa + fonte técnica alterada; AuthorityResolver captura revision refs em snapshot.

**Lacuna:** não há detector que compare snapshot/revisões antigas com fontes atuais; `changed_chains` é fornecido externamente; não há persistência/ligação explícita entre snapshot antigo, novo e RunState/decision trace.

**Status:** `PARTIAL`.

**Risco:** mudança técnica real pode não disparar invalidação; instrução técnica obsoleta pode sobreviver por falta de detecção.

**Menor correção necessária:** revalidator de autoridade/contexto no Core que compare revisions por cadeia, derive `changed_chains`, invoque rebuild parcial e persista trace/versionamento antes de side effect relevante.

**Dependência:** nenhuma; A3 só seria relevante para prova física do runtime, não para a semântica da invalidação.

## T08 — Mudança de Fração/GT/domínio

**Requisito:** nova resolução de identidade/autoridade, novo Bootstrap e novo Instruction Profile do destino.

**Código relevante:** contratos `InstructionProfile` e `CrossDomainEvent`; Identity/Authority/Context resolvers isolados.

**Teste existente:** nenhum cenário de transferência de Fração/GT/domínio.

**Evidência:** há tipos de dados que podem participar do fluxo, mas não comportamento que faça a transição.

**Lacuna:** não existe coordenador/transição que detecte mudança organizacional, resolva destino, reexecute Identity/Authority/Bootstrap e gere novo profile. Não existe InstructionAdapterPort.

**Status:** `NOT_PROVEN`.

**Risco:** autoridade/contexto do domínio de origem podem ser reutilizados indevidamente no destino.

**Menor correção necessária:** boundary de mudança de domínio com re-resolução obrigatória e geração de profile; teste que demonstre não herança.

**Dependência:** não presumida.

## T09 — Delegação entre providers sem herança indevida

**Requisito:** Claude↔Codex sem presumir herança de CLAUDE.md/AGENTS.md; gerar Instruction Profile mínimo e adapter específico.

**Código relevante:** `InstructionProfile` contract; `ModelRouter`/Model adapters.

**Teste existente:** ModelRouter prova troca de provider/modelo sem alterar identidade, mas não há teste de delegação/instruções.

**Evidência:** provider/modelo são substituíveis no roteamento e não reescrevem AgentIdentity.

**Lacuna:** ausência de Delegation Gate/Port; ausência de InstructionAdapterPort e adapters Claude/Codex; nenhum teste gera profile do subtrabalho nem prova não herança de arquivos proprietários.

**Status:** `NOT_PROVEN`.

**Risco:** delegação futura pode transportar contexto/autoridade por conveniência do provider, criando herança implícita.

**Menor correção necessária:** Instruction Compatibility Layer + Delegation Gate, com teste cross-provider usando profiles mínimos explícitos.

**Dependência:** nenhuma presumida; ModelRouter existente é apenas pré-requisito parcial.

## T10 — Resume sem repetir side effects e com Active Context reconstruído

**Requisito:** retomada após checkpoint reconstrói Active Context pelas revisões/apontadores e não repete side effects comprovados.

**Código relevante:** `StateManager.resume`, `RuntimePort.resume`, `LangGraphAdapter.resume`, ledger de idempotência.

**Teste existente:** `test_checkpoint_persists_and_resume_uses_canonical_state`; `test_idempotency_ledger_completes_and_blocks_duplicate`; `test_resume_uses_existing_langgraph_thread_and_preserves_canonical_refs`.

**Evidência positiva:** checkpoint canônico é validado; ledger bloqueia duplicata por `run_id:operation:business_key`; LangGraph preserva refs canônicos fornecidos pelo Core.

**Contradição:** `StateManager.resume()` carrega Checkpoint/RunState e chama imediatamente `runtime.resume(run, state)`. O RuntimePort não recebe SourcePort, AuthorityContext ou TaskContext. O LangGraphAdapter retoma o thread com `input=None`. Logo o caminho de resume existente pode executar antes de reconstruir Active Context/revalidar revisões.

**Status:** `CONTRADICTED`.

**Risco:** retomada pode continuar sob contexto/autoridade obsoletos; o ledger reduz duplicação de side effects, mas não corrige autorização/contexto stale.

**Menor correção necessária:** mover resume semântico para um coordenador do Core: validar checkpoint → revalidar identidade/autoridade/revisões → reconstruir/re-bootstrap contexto → só então chamar RuntimePort; preservar ledger como gate independente.

**Dependência:** A3 pode provar LangGraph físico, mas não fecha esta contradição sem mudança do fluxo Core.

**Reprodução diagnóstica recomendada:** checkpoint em rev-A → alterar fonte técnica/normativa para rev-B → chamar `StateManager.resume()` → verificar que Runtime foi chamado sem qualquer leitura de SourcePort/ContextBuilder.

## T11 — Fonte canônica muda durante execução

**Requisito:** preservar snapshot histórico do passo executado e re-resolver próximos passos conforme política; nunca reescrever retrospectivamente autoridade.

**Código relevante:** `AuthoritySnapshot`; `AuthorityResolver.resolve`; `ToolGateway.execute`.

**Teste existente:** snapshot guarda revision refs durante resolução. Não há teste de mudança de fonte durante Run.

**Evidência positiva:** revision refs são capturados em `AuthoritySnapshot`.

**Contradição:** `ToolGateway.execute()` aceita um `AuthorityContext` pronto e decide somente sobre seus campos; não consulta SourcePort nem compara `authority_snapshot_ref`/revision refs com a fonte atual. Assim, depois de uma mudança tecnicamente detectável da fonte, o mesmo contexto antigo pode autorizar novo side effect sem re-resolução.

**Status:** `CONTRADICTED`.

**Risco:** side effect novo pode ocorrer sob autoridade revogada/alterada. É risco institucional, não apenas de observabilidade.

**Menor correção necessária:** freshness/revision gate antes de próximos passos/side effects relevantes, com política explícita `keep historical snapshot | re-resolve | block | ESCALATE`; snapshots históricos precisam permanecer apontados/persistidos.

**Dependência:** nenhuma.

**Reprodução diagnóstica recomendada:** resolver autoridade em rev-A → alterar source record para rev-B removendo permissão → reutilizar AuthorityContext rev-A em ToolGateway → observar que o gateway não possui mecanismo de detectar rev-B.

## T12 — Conflito não resolvido → ESCALATE

**Requisito:** conflito sem precedência mecanicamente resolvível produz `ESCALATE` com trace completo; modelo não improvisa autoridade.

**Código relevante:** `AuthorityResolver.decide`, `AuthorityContext`/`ResolutionChain`.

**Teste existente:** cadeia `UNRESOLVED`, competência ausente, unknown scope e interseção vazia levam a `ESCALATE`; enum contém ESCALATE.

**Evidência:** fail-closed está implementado em vários casos e não há fallback para ALLOW.

**Lacuna:** não existe representação explícita de `AUTHORITY_CONFLICT` no `HarnessErrorCode` atual, nem objeto/registro de decision trace com fundamentos, fontes e revisões; `ToolGateway` transforma ESCALATE em erro sem persistir trace completo.

**Status:** `PARTIAL`.

**Risco:** decisão segura ocorre, mas pode ser impossível auditar por que e entre quais cadeias o conflito existiu.

**Menor correção necessária:** materializar conflito/decision trace rastreável e teste que force colisão não resolvível, assegurando `ESCALATE`, zero side effects e refs/revisões das cadeias conflitantes.

**Dependência:** nenhuma.

---

## Findings transversais

1. **Ausência de Run Coordinator/Agent Loop executável:** os mecanismos existem como módulos, mas nenhum componente no snapshot compõe o ciclo canônico completo. Isso impede `PROVEN` para T01–T12 sob o critério de cenário completo.
2. **Delegação não materializada:** ports não incluem DelegationPort; o bundle contém CrossDomainEvent/InstructionProfile, mas não DelegationRequest/Result executáveis.
3. **Instruction Compatibility Layer não materializada:** InstructionProfile é contrato, sem geração/projeção por interface/provider.
4. **Snapshots existem, freshness gate não:** AuthoritySnapshot captura revisões, mas não existe gate que invalide contexto/autoridade antiga antes de novo side effect/resume.
5. **Resume técnico está adiantado em relação ao resume canônico:** checkpoint e thread retomam, mas re-bootstrap/re-resolução não são parte do caminho obrigatório.
6. **Fail-closed é uma força real do snapshot:** DENY/ESCALATE/APPROVAL/competência/idempotência bloqueiam boundary externo em vários testes; a maior lacuna está na coordenação e na evolução do estado durante o Run.

## Testes diagnósticos

Nenhum teste propositalmente vermelho foi commitado. Como o ambiente desta auditoria não conseguiu executar o repositório localmente por indisponibilidade de rede, adicionar um teste falho sem poder validar sua própria sintaxe/fixture aumentaria risco sem melhorar a evidência. As reproduções mínimas de T10 e T11 foram registradas acima para transformação em tickets/testes pelo Integrador.
