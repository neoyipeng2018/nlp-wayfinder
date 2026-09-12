# Historical local mirror: sub-$100 financial aspect sentiment specialist

> This file is not the current plan. [Chart a staged $100 financial aspect sentiment specialist](https://github.com/neoyipeng2018/nlp-wayfinder/issues/1) is canonical and now uses pinned ModernBERT Base as the only specialist initialization.

Canonical GitHub issue: [Chart a sub-$100 financial aspect sentiment specialist](https://github.com/neoyipeng2018/nlp-wayfinder/issues/1)

## Destination

Reach a build-ready, preregistered experiment specification and an evidence-based build/no-build decision for a locally runnable specialist model. The specified experiment must stay under USD 100 in marginal external spend and test statistical non-inferiority to a frozen GPT-5.6-sol baseline plus parity with the strongest reproducible specialist on target-conditioned English cross-source financial aspect classification.

## Notes

- This map plans and decides; it does not run the full training or evaluation effort.
- Use `research`, `grilling`, `domain-modeling`, and `prototype` as each ticket requires. Keep the canonical language in the repository working tree's `CONTEXT.md` current whenever a term is resolved.
- Inputs are bounded English passages from financial news, company announcements, earnings calls, regulatory filings, and financial social media. The financial target and aspect are supplied; retrieval and end-to-end extraction are outside the task.
- Financial targets are publicly traded companies or normalized, news-level macro indicators. Instruments, assets, governments, and stand-alone institutions are outside the first experiment.
- Outputs are family-specific: company target-condition polarity is positive, neutral, negative, or insufficient evidence; macro-indicator direction is increase, unchanged, decrease, or insufficient evidence.
- The blind reference set contains 500 examples labeled by one human; 15–20% is blindly relabeled after a washout period to estimate self-consistency.
- The primary result is pooled across sources with predeclared per-source guardrails.
- OmniRoute is transport only. Collect separate named-model calls and retain every raw vote and its provenance; do not use Fusion output as an independent vote. GPT-5.6-sol participates as one teacher, with a no-GPT-5.6-sol ablation.
- The specialist must perform inference locally on the current Apple M3 machine with 8 GB memory and make no external model calls. Cloud training is allowed within the budget.
- The external-spend budget covers all marginal compute, model/API calls, storage, and paid data; existing hardware, subscriptions, and human time are excluded.
- No paid call or external spend is authorized while resolving this planning map unless the user explicitly authorizes it later.
- GitHub Issues are authoritative; this `.scratch/` tree is a local mirror. Because the repository still has no initial commit and all agents share one worktree, research artifacts live under `research/` beside this map and their answers are mirrored into GitHub ticket comments.

## Decisions so far

- [Find defensible data and evaluation precedents](https://github.com/neoyipeng2018/nlp-wayfinder/issues/2): Public data covers only part of the target task, so use a fresh 500-example event-grouped blind set, pooled paired cluster-bootstrap non-inferiority, coarse source guardrails, and an experiment-built open specialist comparator.
- [Design auditable OmniRoute weak supervision](https://github.com/neoyipeng2018/nlp-wayfinder/issues/3): Use pinned named-model routes with validated identity and schema, append-only provenance and cost records, correlation-aware probabilistic aggregation with abstention, and explicit GPT-vote-removal and no-teacher ablations.
- [Bound the local model and $100 training frontier](https://github.com/neoyipeng2018/nlp-wayfinder/issues/4): Lead with full-tuned ModernBERT-base, challenge it with Qwen3.5-2B BF16 LoRA, gate any 4B model on an exact-device no-swap test, and provision roughly $40 gross compute.
- [Make the OmniRoute label-source inventory inspectable](https://github.com/neoyipeng2018/nlp-wayfinder/issues/5): Connected ChatGPT Plus and Claude Max 5x OAuth routes expose 36 named models including `cx/gpt-5.6-sol`; exact remaining quotas and inference callability stay untested under the no-model-call constraint.
- [Choose financial target families and the shared aspect ontology](https://github.com/neoyipeng2018/nlp-wayfinder/issues/6): Limit targets to publicly traded companies and nine normalized news-level macro concepts, with a fixed 12-aspect union, company polarity labels, and objective macro-direction labels.
- [Choose the data portfolio and split policy](https://github.com/neoyipeng2018/nlp-wayfinder/issues/7): Use a research-first two-lane portfolio, an adaptive 160–240-example development set, a fixed 500-example balanced blind set, a 4k–8k silver-training range, and strict event, issuer, time, and duplicate controls.
- [Draft and test the labeling manual](https://github.com/neoyipeng2018/nlp-wayfinder/issues/10): Use target and aspect gates, specific-aspect priority, stated-measure direction, speaker-neutral evidence, explicit no-material-effect neutrality, and conservative conflict handling.
## Not yet specified

- Label-source correlation and abstention behavior may expose diversity, calibration, or active-learning decisions that cannot be stated precisely until the weak-supervision evidence is known.
- The measured cost–quality frontier may expose quantization, compression, or staged-training decisions that cannot be stated precisely until candidate models and hardware costs are known.

## Out of scope

- Training the full model, executing the preregistered comparison, or making a performance claim from completed results.
- End-to-end target/aspect extraction, full-document retrieval, document segmentation, production ingestion, monitoring, or serving integration.
- Multilingual inputs in the first experiment.
- Return forecasting, trading signals, portfolio decisions, or investment advice.
- General parity with GPT-5.6-sol outside the frozen classification task.
- A multi-annotator consensus study in the first experiment.
- Instrument, asset, government, or stand-alone institution targets, including securities, currencies, commodities, market indices, and central banks.
- Market-performance or valuation aspects in the first ontology.
