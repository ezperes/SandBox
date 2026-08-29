# A5 — Supporting Refs Semantics — Implementation Report

## Resultado
A ambiguidade de budget/proveniência dos supporting refs foi encerrada para a V0.1.

`procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs` são contratos de apontamento, não blocos de Active Context. `TaskContext.supporting_ref_semantics` explicita `POINTER_ONLY` e o validator rejeita sua promoção implícita a `MATERIALIZED_CONTEXT`.

## Efeito arquitetural
A economia de tokens fica preservada: o agente pode carregar apontadores sem carregar conteúdo. Quando algum apontador precisar virar contexto ativo, essa transformação deverá ocorrer por etapa explícita e auditável, sujeita a budget, proveniência, revisão e deduplicação.

## Validação
Testes comprovam que:
- supporting refs são preservados no `TaskContext`;
- suas fontes não são lidas durante o build normal;
- não alteram `estimated_tokens`;
- `MATERIALIZED_CONTEXT` nesses campos falha fechado na V0.1.

## Arquivos principais
- `harness/contracts/_models.py`
- `tests/test_context_bootstrap.py`
- `docs/POST_INCREMENT_AUDIT_1_7.md`
- `docs/A5_SUPPORTING_REFS_SEMANTICS_IMPLEMENTATION_LOG.md`

## Próximo gate
A3 — integração física com LangGraph real, mantendo LangGraph atrás de `RuntimePort` e sem transferir identidade, autoridade ou estado institucional ao framework.
