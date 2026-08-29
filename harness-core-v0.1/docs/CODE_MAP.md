# Code Map — Harness Core V0.1

- `harness/contracts/`: contratos canônicos Pydantic e enums. `TaskContext.supporting_ref_semantics` permanece fixado em `POINTER_ONLY` na V0.1 para `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs`.
- `harness/contracts/model.py`: `ModelRequest`, `ModelSelection` e `ModelResponse` neutros a provider.
- `harness/ports/`: interfaces estáveis para Runtime, Model, Tool, Memory, Workspace, Source e State.
- `harness/core/errors.py`: proprietário neutro de `HarnessResolutionError`; `harness.core.identity` mantém re-export compatível do mesmo objeto de classe.
- `harness/core/identity/`: resolução de `AgentIdentity` exclusivamente por `SourcePort`, com falha fechada e revisão da fonte.
- `harness/core/authority/`: resolução das cadeias tática/técnica/normativa, `AuthoritySnapshot` e decisão determinística `ALLOW/DENY/REQUIRE_APPROVAL/ESCALATE`; autorização positiva respeita a interseção das allow-lists aplicáveis.
- `harness/core/context/bootstrap.py`: resolve até três rotas segmentadas sem materializar conteúdo; produz `BootstrapResolution` e `trace_id`.
- `harness/core/context/builder.py`: materializa o menor contexto suficiente, aplica orçamento, deduplicação, proveniência por cadeia e Re-Bootstrap parcial sem reler cadeias preservadas.
- `harness/core/freshness/gate.py`: `AuthorityFreshnessGate`, boundary Core-owned para T11. Compara `source_revision_refs` capturados com `revision_ref` atual da fonte canônica e falha fechado antes de side effect se freshness não puder ser provado.
- `harness/core/freshness/resume.py`: `ResumeFreshnessGate`, boundary Core-owned para T10. Re-resolve identidade/autoridade, detecta cadeias alteradas e faz rebuild seletivo do Active Context antes de `RuntimePort.resume()`.
- `harness/core/freshness/audit.py`: `RevalidationAuditRecord`, registro auditável do resultado de revalidação: snapshot de autoridade, refs anteriores/novas, Bootstrap trace, TaskContext, cadeias alteradas e boundary sensível.
- `harness/core/state/manager.py`: persistência canônica de `RunState`, criação/validação de `Checkpoint`, resume e ledger de idempotência `PENDING|COMPLETED|FAILED|UNKNOWN`. `resume()` agora exige freshness Core-owned, persiste a trilha `RV-*` antes do runtime e só então chama `RuntimePort.resume()`.
- `harness/core/tools/registry.py`: `ToolDescriptor`, registro explícito e resolução de tools disponíveis.
- `harness/core/tools/gateway.py`: boundary obrigatório antes de tools; aplica freshness para side effects, autoridade, competência, aprovação, business key/idempotência e exigência de evidência. Snapshot stale/unverificável não atravessa o adapter.
- `harness/core/routing/model_router.py`: seleção de recurso cognitivo por capacidade/preferência/prioridade sem alterar `AgentIdentity`.
- `harness/adapters/models/fake.py`: Model Adapter determinístico para testes.
- `harness/adapters/models/openai_responses.py`: adapter fino para Responses API por cliente injetado, sem dependência do SDK no Core; integração live permanece gate separado.
- `harness/adapters/state/in_memory.py`: `StatePort` in-memory com cópia defensiva, ledger de idempotência e armazenamento de registros de revalidação usados pela prova T10.
- `harness/adapters/tools/fake.py`: `ToolPort` fake para provar que side effects não são executados quando os gates falham.
- `harness/adapters/sources/`: adapters de fontes; `InMemorySourceAdapter` para testes e desenvolvimento.
- `harness/adapters/runtimes/fake/`: adapter in-memory que prova desacoplamento de runtime.
- `harness/adapters/runtimes/langgraph/runtime.py`: Runtime Adapter substituível; projeta `run_id` em `thread_id`, traduz estado técnico para `RunState`, preserva refs canônicos somente do Core e usa resume estático no mesmo thread. A3 comprovou fisicamente `StateGraph + MemorySaver + interrupt_before + resume` com LangGraph `1.2.11`; LangGraph permanece dependência opcional/dev.
- `harness/schemas/`: 17 JSON Schemas individuais + `all.schemas.json`, gerados exclusivamente dos contratos e versionados como baseline.
- `scripts/export_schemas.py`: geração determinística dos schemas.
- `scripts/check_schema_drift.py`: valida drift de schemas usando Git porcelain; detecta modificações rastreadas, novos arquivos `??` e arquivos ignorados `!!`.
- `tests/test_authority_freshness_gate.py`: prova T11 de que `rev-A → rev-B` invalida `AuthorityContext` antigo antes do ToolPort; ausência de revision também falha fechado.
- `tests/test_resume_freshness_gate.py`: prova T10 de re-resolução e rebuild seletivo antes do runtime; mudança não resolvível impede qualquer resume externo.
- `tests/test_revalidation_audit.py`: prova que o registro `RV-*` é persistido antes de `RuntimePort.resume()` e referencia snapshot/contexto/Bootstrap usados para liberar a retomada.
- `tests/test_langgraph_real.py`: prova física A3 com LangGraph real e prova de que o Core/FakeRuntime executa sem imports `langgraph*`.
- `tests/test_schema_drift_check.py`: regressões do hardening da CI para tracked/untracked/ignored schemas.
- `tests/test_core_errors.py`: propriedade neutra e compatibilidade pública de `HarnessResolutionError`.
- `tests/`: suíte funcional/contratual/arquitetural; estado candidato da PR #17 validado com **57 testes**, 17 schemas exportados e schema drift limpo.
- `docs/POST_INCREMENT_AUDIT_1_7.md`: auditoria transversal canônica do último estado integrado e seção de evidência candidata da PR #17. A classificação T07/T10/T11/T12 só deve ser promovida após reauditoria e merge.
- `docs/workers/CORE-FRESHNESS-GATE/`: contrato de trabalho, findings, log e report da implementação de freshness/revalidation.
- `docs/workers/ARCH-01-T01-T12-GAP-ANALYSIS/`: gap map T01–T12 e evidências da auditoria independente do BASE_SHA.
- `.github/workflows/harness-core-ci.yml`: CI do Harness Core; executa testes, exporta schemas e usa `check_schema_drift.py` para fail-closed contra drift inclusive untracked.

## Estado de integração

A implementação de freshness/revalidation está na `worker/core-freshness-gate`, PR draft #17. Este Code Map descreve o **estado candidato da branch de trabalho**, não declara ainda que T10/T11 foram promovidos no estado canônico integrado. Próximo gate: reauditar T07/T10/T11/T12; se aprovado, integrar PR #17 e repetir CI/auditoria pós-merge.
