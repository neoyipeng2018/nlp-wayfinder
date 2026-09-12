# Find defensible data and evaluation precedents

GitHub: https://github.com/neoyipeng2018/nlp-wayfinder/issues/2

Type: research
Status: resolved
Blocked by:

Research artifact: [data and evaluation precedents](../research/data-and-evaluation-precedents.md)

## Question

Which primary datasets, licenses, annotation schemes, source types, target/aspect ontologies, label semantics, leakage controls, current reproducible specialist baselines, and statistical methods can support or constrain this experiment? Produce decision-ready evidence, identify coverage gaps across all five passage sources and broad financial-target families, and assess what a 300–500-example single-annotator blind reference set can credibly establish using pooled non-inferiority with per-source guardrails.

## Answer

The cited [data and evaluation precedents memo](../research/data-and-evaluation-precedents.md) finds that public corpora can seed company/equity news and social supervision, but none covers all five sources, broad targets, supplied target/aspect, market-impact polarity, and a distinct insufficient-evidence label; fresh grouped blind sampling is required. Use 500 examples, document/event-level leakage controls, pooled paired cluster-bootstrap non-inferiority, and per-source catastrophic-regression guardrails only. A 5-point pooled margin is likely underpowered at this cap under ordinary disagreement rates, while the single-annotator design supports agreement with a frozen operational policy—not human-consensus ground truth. Because the closest exact published specialist has no located code/checkpoint, the defensible comparator ladder is frozen open FinBERT, an experiment-built reproducible target/aspect specialist, and literature-only context.
