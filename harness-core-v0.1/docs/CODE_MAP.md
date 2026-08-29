# Code Map — Harness Core V0.1

- `harness/contracts/`: contratos canônicos Pydantic e enums. `TaskContext.supporting_ref_semantics` permanece fixado em `POINTER_ONLY` na V0.1 para `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs`.
- `harness/contracts/model.py`: `ModelRequest`, `ModelSelection` e `ModelResponse` neutros a provider.
- `harness/ports/`: interfaces estáveis para Runtime, Model, Tool, Memory, Workspace, Source e State. `StatePort` inclui persistência e recuperação run-scoped de registros de revalidação.
- `harness/core/errors.py`: proprietário neutro de `HarnessResolutionError`; `harness.core.identity` mantém re-export compatível do mesmo objeto de classe.
- `harness/core/identity/`: resolução de `AgentIdentity` exclusivamente por `SourcePort`, com falha fechada e revisão da fonte.
- `harness/core/authority/`: resolução das cadeias tática/técnica/normativa, `AuthoritySnapshot` e decisão determinística `ALLOW/DENY/REQUIRE_APPROVAL/ESCALATE`; autorização positiva respeita a interseção das allow-lists aplicáveis. Campo `allowed_scopes` ausente é diferente de `allowed_scopes=[]`; lista vazia é restrição vazia/revogação.
- `harness/core/context/bootstrap.py`: resolve até três rotas segmentadas sem materializar conteúdo; produz `BootstrapResolution` e `trace_id`.
- `harness/core/context/builder.py`: materializa o menor contexto suficiente, aplica orçamento, deduplicação, proveniência por cadeia e Re-Bootstrap parcial sem reler cadeias preservadas.
- `harness/core/freshness/gate.py`: `AuthorityFreshnessGate`, boundary Core-owned para T11. Compara `source_revision_refs` capturados com `revision_ref` atual da fonte canônica e falha fechado antes de side effect se freshness não puder ser provado. Side effect exige gate concreto.
- `harness/core/freshness/resume.py`: `ResumeFreshnessGate`, boundary Core-owned para T10. Re-resolve identidade/autoridade, compara revisão anterior de identidade, detecta cadeias alteradas e faz rebuild seletivo do Active Context antes de `RuntimePort.resume()`.
- `harness/core/freshness/audit.py`: `RevalidationAuditRecord`, registro auditável de boundary sensível. Ciclo persistido: `PENDING → RELEASED | BLOCKED | FAILED`, com lineage anterior/atual, decisão/outcome/erro e cadeia de eventos.
- `harness/core/state/manager.py`: persistência canônica de `RunState`, criação/validação de `Checkpoint`, resume e ledger de idempotência `PENDING|COMPLETED|FAILED|UNKNOWN`. `resume()` exige `ResumeFreshnessGate` Core-owned concreto, persiste `RV-*` antes do runtime e restaura `decision_refs` Core-owned após o adapter.
- `harness/core/tools/registry.py`: `ToolDescriptor`, registro explícito e resolução de tools disponíveis.
- `harness/core/tools/gateway.py`: boundary obrigatório antes de tools; para side effects exige `AuthorityFreshnessGate` concreto, aplica autoridade, competência, aprovação, business key/idempotência e exigência de evidência. BLOCKED/FAILED são persistidos; falha externa incerta deixa ledger `UNKNOWN` com reconciliação requerida.
- `harness/core/routing/model_router.py`: seleção de recurso cognitivo por capacidade/preferência/prioridade sem alterar `AgentIdentity`.
- `harness/adapters/models/fake.py`: Model Adapter determinístico para testes.
- `harness/adapters/models/openai_responses.py`: adapter fino para Responses API por cliente injetado, sem dependência do SDK no Core; integração live permanece gate separado.
- `harness/adapters/state/in_memory.py`: `StatePort` in-memory com cópia defensiva, ledger de idempotência, armazenamento e recuperação run-scoped de registros de revalidação.
- `harness/adapters/tools/fake.py`: `ToolPort` fake para provar que side effects não são executados quando os gates falham.
- `harness/adapters/sources/`: adapters de fontes; `InMemorySourceAdapter` para testes e desenvolvimento.
- `harness/adapters/runtimes/fake/`: adapter in-memory que prova desacoplamento de runtime.
- `harness/adapters/runtimes/langgraph/runtime.py`: Runtime Adapter substituível; projeta `run_id` em `thread_id`, traduz estado técnico para `RunState`, preserva refs canônicos somente do Core e usa resume estático no mesmo thread. A3 comprovou fisicamente `StateGraph + MemorySaver + interrupt_before + resume` com LangGraph `1.2.11`; LangGraph permanece dependência opcional/dev.
- `harness/schemas/`: 17 JSON Schemas individuais + `all.schemas.json`, gerados exclusivamente dos contratos e versionados como baseline.
- `scripts/export_schemas.py`: geração determinística dos schemas.
- `scripts/check_schema_drift.py`: valida drift de schemas usando Git porcelain; detecta modificações rastreadas, novos arquivos `??` e arquivos ignorados `!!`.
- `tests/test_authority_freshness_gate.py`: prova stale authority/revision mismatch antes de ToolPort e falha fechada em revision ausente.
- `tests/test_resume_freshness_gate.py`: prova re-resolução, identity revision drift, rebuild seletivo incluindo technical-only e bloqueio antes do runtime quando freshness não resolve.
- `tests/test_revalidation_audit.py`: prova persist-before-boundary, recuperação de `RV-*`, caminhos RELEASED/BLOCKED e reconstrução de lineage.
- `tests/test_state_checkpoint.py`: checkpoint/resume, gate concreto, proteção de refs Core-owned e idempotência associada.
- `tests/test_tool_gateway.py`: side-effect gate obrigatório, DENY/ESCALATE/approval/idempotency, ToolPort failure `FAILED/UNKNOWN` e ausência de chamada externa quando bloqueado.
- `tests/test_langgraph_real.py`: prova física A3 com LangGraph real e prova de que o Core/FakeRuntime executa sem imports `langgraph*`.
- `tests/test_schema_drift_check.py`: regressões do hardening da CI para tracked/untracked/ignored schemas.
- `tests/test_core_errors.py`: propriedade neutra e compatibilidade pública de `HarnessResolutionError`.
- `tests/`: suíte funcional/contratual/arquitetural; SHA de auditoria independente `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff` validado com **68 testes**, 17 schemas exportados e schema drift limpo.
- `docs/ARCH_02_REAUDIT_FINDINGS.md`: achados históricos da reauditoria independente que motivou o ciclo P0; não representa a classificação do SHA corrigido.
- `docs/CORE_FRESHNESS_GATE_REAUDIT.md`: histórico do blocker e requisitos de reauditoria.
- `docs/IMPLEMENTATION_REPORT.md`: estado consolidado do ciclo P0, distinção entre SHA funcional, SHA congelado para auditores e branch de higiene pós-freeze.
- `docs/workers/CORE-FRESHNESS-GATE/WORK_CONTRACT.md`: contrato de trabalho histórico do worker.
- `docs/workers/CORE-FRESHNESS-GATE/IMPLEMENTATION_LOG.md`: log histórico `tentativa → causa → solução correta`; placeholders/status/readmes intermediários foram removidos na higiene pré-integração.
- `docs/workers/ARCH-01-T01-T12-GAP-ANALYSIS/`: gap map T01–T12 e evidências da auditoria independente do BASE_SHA.
- `.github/workflows/harness-core-ci.yml`: CI do Harness Core; executa testes, exporta schemas e usa `check_schema_drift.py` para fail-closed contra drift inclusive untracked.

## Estado de integração

A implementação de freshness/revalidation está na `worker/core-freshness-gate`, PR draft #17. O SHA funcional de correção é `865255b37c683f3fd1f13a8e06ba56936d2ea95d`; o SHA entregue aos três auditores independentes é `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff`. Commits posteriores na branch são somente higiene/documentação e não substituem o alvo congelado de auditoria.

Status: `CORRECTIONS_IMPLEMENTED_AWAITING_INDEPENDENT_REAUDIT — DO_NOT_MERGE`.

Próximo gate: `ARCH-03 + VERIFY-SEC-01 + TRACE-02 → consolidação do Integrador → ACCEPT | ACCEPT_WITH_FIXES | REWORK`. Se aprovado, congelar HEAD final de integração, executar CI final, merge, CI pós-merge e atualizar a auditoria canônica. A4/E2E permanece fora de escopo até esse gate ser vencido.
