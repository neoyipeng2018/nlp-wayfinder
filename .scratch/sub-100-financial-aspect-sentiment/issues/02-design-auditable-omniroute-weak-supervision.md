# Design auditable OmniRoute weak supervision

GitHub: https://github.com/neoyipeng2018/nlp-wayfinder/issues/3

Type: research
Status: resolved
Blocked by:

Research artifact: [OmniRoute weak supervision](../research/omniroute-weak-supervision.md)

## Question

Using official OmniRoute documentation and source plus primary weak-supervision research, what auditable architecture can collect independent structured votes from named models, preserve prompt/model/provenance/cost metadata, estimate correlated source quality with one human annotator, aggregate probabilistic silver labels, support abstention, and run a no-GPT-5.6-sol ablation? Distinguish explicit named-model calls from routing, fallback, and Fusion synthesis, and identify security, licensing, reliability, and budget constraints.

## Answer

[OmniRoute weak supervision](../research/omniroute-weak-supervision.md) recommends using OmniRoute only as a pinned transport/telemetry layer. A labeling source is an immutable named provider/model + prompt + label map + decoder + schema tuple, called separately through a dedicated provider route; `auto`, combos, bare model IDs, fallback substitutions, and Fusion are not independent votes. Validate returned route identity and JSON locally, preserve append-only request/response/provenance/cost records, and map refusals, malformed output, timeouts, or substitutions to `ABSTAIN`, distinct from the task class `insufficient_evidence`.

Fit and freeze the simplest development-set winner among majority, calibrated weighted, conditionally independent, and sparse correlation-aware multi-class label models. Anchor class-conditional source quality with a separate, blinded single-annotator development set and 15–20% washout relabeling; retain posterior soft labels and reject low-support/high-entropy items. Report both a GPT-vote-removal ablation and, if claiming no teacher use, a strict pipeline excluding all GPT-derived artifacts. Enforce spend in the collector against snapshotted prices and provider invoices because OmniRoute's cost view is an estimate, and allowlist upstream APIs/terms because OmniRoute's ToS flags do not block routing.
