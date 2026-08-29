# IMPLEMENTATION REPORT — ARCH-01-T01-T12-GAP-ANALYSIS

## Resultado

Auditoria arquitetural independente do `BASE_SHA 59d3eb987136ec628bcaba4b45949fb81b2616a2` concluída sem alteração de código de produção.

Produto principal: `GAP_MAP_T01_T12.md`.

Classificação:

| Classe | Quantidade | Testes |
|---|---:|---|
| PROVEN | 0 | — |
| PARTIAL | 7 | T01, T02, T04, T05, T06, T07, T12 |
| NOT_PROVEN | 3 | T03, T08, T09 |
| CONTRADICTED | 2 | T10, T11 |

## Achados prioritários

### P0 — T10 Resume canônico é contradito pelo fluxo atual

`StateManager.resume()` valida Checkpoint/RunState e chama `RuntimePort.resume()` diretamente. Não há re-resolução de identidade/autoridade, comparação de revisões nem reconstrução de TaskContext antes da retomada do runtime. O ledger idempotente reduz repetição de side effects, mas não resolve contexto/autoridade stale.

Menor correção: coordenar resume no Core em ordem `checkpoint → freshness/revision validation → authority re-resolution → context rebuild/re-bootstrap → runtime.resume`.

### P0 — T11 Fonte alterada pode não invalidar autoridade antes de novo side effect

`AuthoritySnapshot` registra revisions, porém `ToolGateway.execute()` recebe AuthorityContext pronto e não possui freshness gate. Uma permissão revogada na fonte após a resolução pode continuar sendo usada por um contexto antigo.

Menor correção: gate de revisão/frescura antes de próximos passos/side effects relevantes, preservando snapshot histórico e produzindo nova resolução para passos futuros.

### P1 — Coordenação/delegação ainda não materializada

- T03: CrossDomainEvent/DomainObligation existem como contratos, mas não há fluxo que derive/reconcilie obrigações nem gate de conclusão global.
- T06: competência insuficiente é bloqueada corretamente, mas não existe Delegation Gate/Port para encaminhar ao Elemento competente.
- T08: mudança Fração/GT/domínio não dispara novo Identity/Authority/Bootstrap/Instruction Profile.
- T09: não existem Instruction Adapters Claude/Codex nem fluxo de delegação cross-provider.

### P1 — Invalidação seletiva existe sem detector

T07 tem um mecanismo correto de `rebuild_partial()` quando `changed_chains` é fornecido. A lacuna está antes dele: detectar qual revisão/cadeia mudou, ligar snapshots ao Run e persistir a transição.

### P1 — Fail-closed existe, decision trace completo não

T12 possui ESCALATE para vários casos de autoridade não resolvida, competência ausente e scope não autorizado. Falta materialização explícita do conflito e trace persistido com fundamentos/fontes/revisões.

## Pontos fortes comprovados parcialmente

- identidade é lida de SourcePort e carrega revision ref;
- tática, técnica e normativa são representadas separadamente;
- allow-lists declaradas são intersectadas;
- proibição explícita prevalece no gate;
- contexto ativo é segmentado, deduplicado e limitado por budget;
- re-bootstrap parcial preserva cadeias não afetadas quando corretamente solicitado;
- ToolGateway bloqueia DENY/ESCALATE/aprovação/competência antes do adapter;
- ledger de idempotência distingue PENDING/COMPLETED/FAILED/UNKNOWN e impede retry cego;
- Runtime LangGraph não injeta refs canônicos de decisão/checkpoint;
- provider/modelo não altera AgentIdentity nos testes existentes.

## Evidência e limites

A auditoria leu código e testes diretamente no BASE_SHA pelo GitHub. A execução local do snapshot não foi possível porque o ambiente desta sessão não resolveu `github.com`. Nenhum status de workflow/commit foi retornado pelo conector para o BASE_SHA. Portanto, este relatório não afirma que `pytest` foi executado por ARCH-01.

Essa limitação não altera os achados T10/T11, que decorrem do fluxo explícito nas assinaturas e implementações auditadas.

## SCOPE_EXPANSION_REQUEST

Nenhum. Nenhuma correção de produção foi necessária ou realizada para concluir a auditoria.

## INTERPRETATION_DIVERGENCE

Nenhuma divergência bloqueante permaneceu. A regra adotada foi conservadora: presença de contrato/schema não equivale a prova de comportamento quando Txx exige coordenação executável.

## OPPORTUNITY_FOUND

### O1 — Criar suíte `tests/architecture/test_t01_t12.py`

Impacto: transforma critérios canônicos em regression suite única e reduz risco de declarar incrementos isolados como arquitetura pronta.

Recomendação: implementar progressivamente pelo Integrador/workers responsáveis, sem enfraquecer cenários que inicialmente falharem.

### O2 — Introduzir boundary único para “próximo passo relevante”

Um coordenador mínimo poderia concentrar freshness de autoridade/contexto, decisão, checkpoint/resume e chamada a Tool/Runtime/Delegation, evitando que callers contornem revalidação. Isso deve ser especificado antes de implementação para não criar monólito ou nova fonte institucional.

## Tentativas que falharam → causa → solução

1. Clone/pytest local falhou por indisponibilidade DNS do ambiente → auditoria passou a usar leitura autenticada do GitHub no mesmo BASE_SHA, sem inventar resultado de teste.
2. Code search incompleto retornou zero para CrossDomainEvent → resultado foi tratado como não conclusivo; leitura direta de `_models.py` encontrou CrossDomainEvent e InstructionProfile e a hipótese foi corrigida.

## Reprodução mínima dos dois achados críticos

### T10

1. Criar RunState/Checkpoint em uma revisão A.
2. Alterar fonte técnica/normativa para revisão B.
3. Chamar `StateManager.resume(run, runtime, checkpoint_id)`.
4. Observar que o fluxo chama `runtime.resume(run, state)` sem SourcePort/AuthorityResolver/ContextBuilder.

### T11

1. Resolver AuthorityContext permitindo uma ação na revisão A.
2. Alterar a fonte para revisão B revogando a ação.
3. Reutilizar o AuthorityContext A em `ToolGateway.execute()`.
4. Observar que o gateway decide apenas sobre o contexto recebido e não compara a revisão B.

## Arquivos produzidos

- `docs/workers/ARCH-01-T01-T12-GAP-ANALYSIS/GAP_MAP_T01_T12.md`
- `docs/workers/ARCH-01-T01-T12-GAP-ANALYSIS/IMPLEMENTATION_LOG.md`
- `docs/workers/ARCH-01-T01-T12-GAP-ANALYSIS/IMPLEMENTATION_REPORT.md`

## Estado

`READY_FOR_INTEGRATION`
