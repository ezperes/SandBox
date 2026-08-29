# A5 — Supporting Refs Semantics — Implementation Log

Data: 2026-08-29

## Objetivo
Eliminar ambiguidade entre apontadores e conteúdo materializado em `TaskContext` para `procedural_refs`, `knowledge_refs`, `risk_refs` e `memory_refs`.

## Decisão
Na V0.1 esses quatro campos são exclusivamente `POINTER_ONLY`.

## Regras
- presença do ref não implica leitura da fonte;
- ref não consome budget de contexto ativo;
- ref não entra em `token_usage` ou proveniência de conteúdo materializado;
- materialização posterior deve passar por caminho explícito sujeito a budget, proveniência, revisão e deduplicação;
- `MATERIALIZED_CONTEXT` nesses campos é inválido na V0.1.

## Implementação
- adicionado enum `ReferenceSemantics`;
- adicionado `TaskContext.supporting_ref_semantics`, default `POINTER_ONLY`;
- validator fail-closed rejeita `MATERIALIZED_CONTEXT` para supporting refs no contrato V0.1;
- testes adicionados para provar ausência de leitura das fontes e ausência de consumo de budget.

## Tentativa/risco evitado → causa → solução correta
Tratar os refs como se já fossem conteúdo ativo teria subcontado tokens e escondido proveniência. Materializá-los automaticamente também aumentaria I/O/tokens sem necessidade. Solução: manter apontadores explícitos e exigir materialização separada quando necessária.
