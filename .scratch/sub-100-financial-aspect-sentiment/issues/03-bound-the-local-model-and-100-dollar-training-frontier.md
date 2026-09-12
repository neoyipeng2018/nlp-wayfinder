# Bound the local model and $100 training frontier

GitHub: https://github.com/neoyipeng2018/nlp-wayfinder/issues/4

Type: research
Status: resolved
Blocked by:

Research artifact: [local model and budget frontier](../research/local-model-and-budget-frontier.md)

## Question

Which current model families, licenses, adaptation methods, training services, and compression/runtime options could plausibly learn this task within the USD 100 external-spend cap and perform inference without external calls on an Apple M3 with 8 GB memory? Establish decision-grade cost and memory bounds, compare specialist encoders with small generative models, and identify the experiments needed to reject infeasible candidates early.

## Answer

[The local model and budget frontier](../research/local-model-and-budget-frontier.md) recommends full-tuned ModernBERT-base as the primary route, with FinBERT and DeBERTa-v3-base controls, and Qwen3.5-2B BF16 LoRA as the reasoning-oriented challenger. Qwen3.5-4B is conditional on an exact-device 4-bit load test: published runtime estimates are 3.5 GB for the 0.8B/2B 4-bit tier and 5.5 GB for 4B, so reliable no-swap operation on the 8 GB M3—not cloud training—is the binding constraint. Train Qwen3.5 in BF16 LoRA and quantize only after merging; its current framework advises against QLoRA. A provisional $40 gross-list-price model-compute ceiling buys roughly 37–39 hours on an A6000/L4 configuration, while a staged load, 100-step billing, formulation, scaling, and quantization funnel rejects infeasible or dominated candidates before the blind evaluation.
