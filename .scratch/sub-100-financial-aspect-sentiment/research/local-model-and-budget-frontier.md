# Local model and USD 100 training frontier

Research snapshot: 2026-08-24. Prices and software support can change; re-check them when execution starts.

## Decision

The proposed specialist experiment is technically and financially plausible, but parity with GPT-5.6-sol remains an empirical hypothesis. The binding constraint is not cloud training: it is reliable, no-swap inference on the exact 8 GB M3 Mac after quantization.

Use this ordered frontier:

1. **Primary route — full-tuned encoder:** start with `answerdotai/ModernBERT-base`, retain `ProsusAI/finbert` and `microsoft/deberta-v3-base` as controls, and promote `ModernBERT-large` only if the base model's learning curve has not saturated. This is the highest-probability route for a fixed four-way classification task.
2. **Reasoning-oriented challenger — decoder LoRA:** train `Qwen/Qwen3.5-2B` with BF16 LoRA and a one-label completion objective, with its vision path disabled. It has a safe-looking local-memory envelope only after post-training quantization.
3. **Conditional stretch — `Qwen3.5-4B`:** train it only after its unmodified 4-bit checkpoint passes the exact-device memory test and the 2B model shows material validation headroom over the best encoder. Do not begin with 4B.
4. **Capacity floor — `Qwen3.5-0.8B`:** use it to learn whether the generative formulation works at all, not as the presumed winner.
5. **Fallback, not another broad sweep:** `microsoft/Phi-4-mini-instruct` is a permissively licensed 3.8B alternative if Qwen3.5's recent hybrid architecture causes training or export failures. Do not pay to tune both 4B-class families unless the first fails for an engineering reason.

Do **not** put dense models above 4B, decoder full fine-tuning, long-context training, or H100-class hardware on the initial frontier. Do **not** use QLoRA for Qwen3.5: its current fine-tuning framework explicitly warns that 4-bit training produces unusually large quantization differences. Train a BF16 LoRA and quantize the merged result afterward.

This is a feasibility decision, not a performance claim. A narrow specialist can beat a general LLM on the frozen task, but no model card or parameter count establishes that result.

## Evidence convention

- **Measured/source fact** means the value is reported by the model or framework owner and is cited.
- **Calculation** means arithmetic from a reported parameter count or list price; it excludes unreported runtime overhead unless stated.
- **Feasibility inference** means the conclusion still needs the rejection test specified below.

## Exact-device boundary

The local target was verified as an Apple M3 MacBook Air with 8 GB unified memory and Metal support. Apple explains that CPU and GPU access the same physical memory pool on Apple silicon, so nominal GPU and system requirements cannot be added as if they were separate pools ([MLX unified-memory documentation](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html)). The operating system, runtime, model, activations, caches, and input batch all compete for the same 8 GB.

That makes weight-file size a necessary but insufficient fit test. The task supplies a bounded evidence passage rather than a whole filing, so the model contract should initially cap inputs at 512 tokens, test 1,024 as a robustness tier, use batch size 1 locally, and generate at most one label token plus terminator. The 8K or 262K contexts advertised by candidate models provide no benefit here and would make memory conclusions misleading.

### Candidate facts and memory bounds

| Candidate | Owner-reported facts | Calculated or reported local bound | Place on frontier |
|---|---|---|---|
| ModernBERT-base | 149M parameters, 22 layers, up to 8,192 tokens; Apache-2.0 ([model card](https://huggingface.co/answerdotai/ModernBERT-base)) | F32 weights alone are about 0.56 GiB (`149M × 4 bytes`); actual runtime is higher but comfortably below 8 GB | Primary full-fine-tune candidate |
| ModernBERT-large | 395M parameters, 28 layers, up to 8,192 tokens; Apache-2.0 ([model card](https://huggingface.co/answerdotai/ModernBERT-large)) | F32 weights alone are about 1.47 GiB; comfortable local inference, but training and search cost exceed base | Promote only on an unsaturated base-model learning curve |
| ProsusAI FinBERT | BERT-base-shaped, 12 layers, hidden size 768, 512-token limit; three financial-tone labels; Apache-2.0 source repository ([checkpoint/config](https://huggingface.co/ProsusAI/finbert), [source and license](https://github.com/ProsusAI/finBERT)) | Roughly 110M parameters / 0.41 GiB F32 weights; current head must be replaced for the fourth label and aspect conditioning | Mandatory finance-specific baseline and initialization ablation, not an assumed winner |
| DeBERTa-v3-base | 86M backbone parameters plus 98M embedding parameters; MIT ([model card](https://huggingface.co/microsoft/deberta-v3-base)) | About 0.69 GiB F32 weights from the reported 184M total | Strong conventional NLU control |
| Fin-ModernBERT | Continual pretraining of ModernBERT-base on a claimed 20M deduplicated finance records at 1,024 tokens; Apache-2.0 ([uploader's model card](https://huggingface.co/clapAI/Fin-ModernBERT)) | Similar scale to ModernBERT-base | Optional initialization ablation only after checking source-dataset licenses and overlap; low adoption and a self-reported card are not validation |
| Qwen3.5-0.8B | 0.8B language parameters, 24 layers, native 262K context; Apache-2.0 ([model card](https://huggingface.co/Qwen/Qwen3.5-0.8B)) | Unsloth reports 3.5 GB total memory for its 4-bit small-model tier ([runtime guide](https://unsloth.ai/docs/models)) | Cheap decoder formulation/capacity floor |
| Qwen3.5-2B | 2B language parameters, 24 layers, native 262K context; Apache-2.0 ([model card](https://huggingface.co/Qwen/Qwen3.5-2B)) | Same guide reports 3.5 GB at 4-bit and 5 GB at 6-bit for the grouped 0.8B/2B tier | Primary decoder challenger; 6-bit and 4-bit both testable on 8 GB |
| Qwen3.5-4B | 4B language parameters, 32 layers; Apache-2.0 ([model card](https://huggingface.co/Qwen/Qwen3.5-4B)) | Unsloth reports 5.5 GB total at 4-bit, 7 GB at 6-bit, and 14 GB at BF16 ([runtime guide](https://unsloth.ai/docs/models)) | 4-bit is only a conditional fit: 5.5 GB leaves little room for macOS and the runner |
| Phi-4-mini-instruct | 3.8B dense decoder, 128K context; MIT; the BF16 repository is 7.69 GB ([model card/files](https://huggingface.co/microsoft/Phi-4-mini-instruct)) | BF16 cannot be assumed to fit. A supported 4-bit build needs the same device test as Qwen3.5-4B | Engineering-diversity fallback only |

Unsloth's table is a framework-owner estimate for its quantized artifacts, not a measurement on this exact Mac. It puts Qwen3.5-9B at 6.5 GB even at 4-bit; that leaves only about 1.5 GB for everything else and is therefore outside the reliable frontier despite nominal loadability. The 4B model is already borderline. This conclusion should not be relaxed merely because SSD swap lets a model start.

## Why the encoder leads

| Dimension | Bidirectional classifier | Small generative model |
|---|---|---|
| Task match | Directly maps `(target, aspect, passage)` to four logits in one forward pass | Must learn prompt format and emit a valid label as text |
| Data efficiency | Every example directly supervises all class logits; soft silver posteriors can train with cross-entropy/KL | Completion loss supervises label tokens; using the full silver posterior is less direct |
| Cost and local memory | 110M–395M candidates fit without aggressive compression | 0.8B–4B and post-training quantization are required |
| Calibration | Native logits make temperature scaling and abstention straightforward | Label-token probabilities can be normalized, but parsing and tokenization introduce extra failure modes |
| Potential advantage | Efficient pattern and representation learning for a fixed ontology | Better chance of retaining expectation-relative reasoning and handling varied natural-language target/aspect descriptions |
| Operational risk | Export/operator compatibility | Chat-template drift, invalid output, reasoning-mode drift, quantization loss, and newer runtime support |

This task's fixed ontology and bounded evidence passage strongly favor an encoder. The decoder earns its place because the proposed label semantics require financial reasoning relative to expectations, not because generation is intrinsically useful. It should run in direct/non-thinking mode, with constrained decoding over exactly the four label strings; rationales are not part of the target and would waste memory, latency, and supervision.

## Adaptation decision

### Encoders: full fine-tuning first

Replace the existing classification head and serialize inputs with explicit fields such as `TARGET`, `ASPECT`, and `PASSAGE`. ModernBERT does not use BERT token-type IDs, so explicit field delimiters are the portable representation ([ModernBERT usage notes](https://huggingface.co/answerdotai/ModernBERT-base)). Train the complete encoder with both the silver posterior and its hard class, while preserving an ablation that uses hard labels only.

A simple Adam-state calculation is informative: 16 bytes per parameter for FP32 parameters, gradients, and two moment buffers is about 2.22 GiB for ModernBERT-base and 5.89 GiB for ModernBERT-large before activations and allocator overhead. This is a calculation, not a measured peak, but it makes 24 GB cloud cards a plausible first target at 512 tokens. LoRA is unnecessary for base unless the 100-step memory pilot disproves that inference; using it prematurely gives up adaptation capacity for little budget benefit.

### Decoders: BF16 LoRA, then quantize

LoRA freezes pretrained weights and adds low-rank trainable matrices; the original paper reports major trainable-parameter and memory reductions without inference latency after merging ([LoRA paper](https://arxiv.org/abs/2106.09685)). Current Unsloth documentation reports BF16-LoRA VRAM of about 3 GB, 5 GB, and 10 GB for Qwen3.5 0.8B, 2B, and 4B respectively, and says full fine-tuning uses roughly four times as much. It also supports language-only tuning for the Qwen3.5 vision-language checkpoints ([Qwen3.5 fine-tuning guide](https://unsloth.ai/docs/models/qwen3.5/fine-tune)). Those values put every proposed LoRA pilot on a 24 GB L4/A10, but not necessarily on the 8 GB Mac once macOS overhead is included.

QLoRA ordinarily backpropagates through a frozen 4-bit base into LoRA adapters; its paper demonstrated a 65B model on one 48 GB GPU ([QLoRA paper](https://arxiv.org/abs/2305.14314)), and Hugging Face PEFT supports all-linear QLoRA-style adapters ([PEFT LoRA documentation](https://huggingface.co/docs/peft/main/package_reference/lora)). Nevertheless, Unsloth currently says QLoRA is **not recommended for Qwen3.5** because of higher-than-normal quantization differences. Therefore:

- Qwen3.5: BF16 LoRA in the cloud, merge, then make 6-bit and 4-bit deployment artifacts.
- Older Qwen3 or Phi fallback: QLoRA is allowed only if its framework/version pilot shows lower cost without a validation loss.
- No decoder full fine-tuning unless 0.8B LoRA clearly underfits, its full-tune pilot fits 24 GB, and the remaining ledger can pay for it.

Use completion-only loss on the label, not the prompt; Hugging Face TRL supports prompt-completion datasets and masking prompt tokens from loss ([SFTTrainer documentation](https://huggingface.co/docs/trl/sft_trainer)).

## Local compression and runtime

### Encoder deployment

Start with PyTorch's MPS backend, which maps models and tensors to Metal Performance Shaders on macOS ([PyTorch MPS documentation](https://docs.pytorch.org/docs/stable/notes/mps.html)). It minimizes conversion variables for the first local proof. If packaging or latency matters, export the frozen winner to ONNX and test ONNX Runtime's CoreML execution provider, which can use CPU, GPU, and Neural Engine but only accelerates supported subgraphs ([CoreML provider documentation](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)). Do not assume conversion preserves every ModernBERT operation; compare logits and predictions against PyTorch before accepting it.

### Decoder deployment

Use two independent export paths during validation:

- **GGUF + llama.cpp Metal** for the reproducible deployment artifact. llama.cpp treats Apple silicon/Metal as a supported backend and supports integer quantization; its quantizer warns against requantizing an already quantized model, so quantize once from the merged BF16/FP16 checkpoint ([project README](https://github.com/ggml-org/llama.cpp), [quantization guide](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md)).
- **MLX-LM** as the Apple-native cross-check. MLX-LM supports generation, low-rank/full tuning, and quantized models on Apple silicon ([MLX-LM README](https://github.com/ml-explore/mlx-lm)); current source contains a [Qwen3.5 implementation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/models/qwen3_5.py) and can report peak memory. It also exposes 4-bit weight and KV-cache quantization. Because Qwen3.5 support is recent and hybrid architectures have had active fixes, pin the exact runtime commit/version and require golden-output parity rather than trusting a floating install.

For the decoder winner, compare merged BF16 in the cloud with local 6-bit and 4-bit builds on the same validation records. Prefer 2B/6-bit if it fits and preserves more accuracy; prefer 4B/4-bit only if its measured task gain survives quantization and the exact Mac stays out of swap.

## Current cloud-cost frontier

### Source facts

Modal lists per-second GPU charges of $0.000222 for L4, $0.000306 for A10, $0.000583 for A100-40GB, and $0.000694 for A100-80GB; CPU, memory, and storage are billed separately. It also advertises $30/month Starter credit, which should be recorded but not relied upon for reproducibility ([Modal pricing](https://modal.com/pricing)). NVIDIA reports that both L4 and A10 have 24 GB memory and BF16 tensor support ([L4 specifications](https://www.nvidia.com/en-au/data-center/l4/), [A10 specifications](https://www.nvidia.com/en-in/data-center/products/a10-gpu/)).

Lambda's current instance table lists A6000 48 GB at $1.09/GPU-hour, A10 24 GB at $1.29, and A100 40 GB at $1.99, with applicable tax extra ([Lambda instances/pricing](https://lambda.ai/instances)).

### Cost calculations

The Modal “illustrative all-in” column below adds two physical CPU cores and 16 GiB RAM at its posted rates. It omits volume storage and tax. Lambda hours use the posted instance price. These are ceilings, not throughput predictions.

| Service/hardware | Listed GPU or instance price | Illustrative all-in hourly price | Hours for a provisional $40 model-compute envelope | Absolute hours if the entire $100 were wrongly spent on compute |
|---|---:|---:|---:|---:|
| Modal L4 24 GB | $0.7992/h GPU | $1.0214/h | 39.2 | 97.9 |
| Modal A10 24 GB | $1.1016/h GPU | $1.3238/h | 30.2 | 75.5 |
| Modal A100 40 GB | $2.0988/h GPU | $2.3210/h | 17.2 | 43.1 |
| Lambda A6000 48 GB | $1.09/h instance | $1.09/h | 36.7 | 91.7 |
| Lambda A10 24 GB | $1.29/h instance | $1.29/h | 31.0 | 77.5 |
| Lambda A100 40 GB | $1.99/h instance | $1.99/h | 20.1 | 50.3 |

Feasibility inference: 24 GB is enough to *attempt* all encoder full-tune pilots and the reported 10 GB Qwen3.5-4B BF16 LoRA. A6000's 48 GB provides debugging headroom at nearly the A10 price. A100 is justified only by a measured wall-clock saving that lowers total dollars; H100 is outside this experiment's rational frontier.

Use Modal for short, metered pilots and Lambda A6000 for a longer run if the environment is easier to reproduce there. Count gross list-price compute in the research ledger even when free credits reduce cash paid. That prevents a “sub-$100” result from depending on a one-time promotion.

The final budget ticket must account for OmniRoute labeling, GPT-5.6-sol evaluation, storage, and tax before assigning training funds. A **provisional $40 gross-list-price ceiling for all model work** is conservative and already buys about 37–39 hours of an A6000/L4 configuration. That is ample in hardware-hours only if the 100-step pilots confirm the expected throughput; no unmeasured training-time assertion should replace that pilot.

Record every run as:

`cost = GPU seconds × GPU rate + CPU-core seconds × rate + GiB-memory seconds × rate + storage + tax`

The run manifest should also record provider, hardware, wall time, training steps, examples/tokens processed, peak VRAM, checkpoint, code revision, and whether credit changed cash paid.

## Early-rejection experiment funnel

No blind gold-test labels are used anywhere in this funnel.

### Gate 0 — exact-Mac load test ($0 cloud)

Before training, run the official/prepared inference artifact for ModernBERT-base, ModernBERT-large, Qwen3.5-0.8B/2B at 6- and 4-bit, and Qwen3.5-4B at 4-bit. Use batch 1, 512- and 1,024-token inputs, and at least 100 repeated predictions.

Capture peak process memory, MLX/llama.cpp peak memory where available, macOS memory-pressure state, swap delta, load time, p50/p95 latency, and prediction parse rate. Reject a configuration if it OOMs, enters sustained red memory pressure, increases swap materially during steady-state predictions, or produces anything outside the four-label grammar. If Qwen3.5-4B fails, rule out it and every larger dense decoder immediately.

### Gate 1 — 100-step cloud meter

For every remaining architecture, run exactly 100 optimizer steps at the intended 512-token cap, including first-run compilation. Record peak VRAM, examples/second, compile time, and billed dollars. Extrapolate the planned epochs and seeds from measured throughput. Reject any candidate whose projected cost plus a 20% contingency exceeds the *remaining* model-compute ledger. This converts framework VRAM claims into project-specific facts before an expensive sweep.

### Gate 2 — formulation pilots

Train one fixed-seed, fixed-subset pilot for:

- FinBERT full tune with a new four-way head;
- ModernBERT-base full tune;
- DeBERTa-v3-base full tune;
- optional Fin-ModernBERT initialization, only after provenance review;
- Qwen3.5-0.8B BF16 LoRA; and
- Qwen3.5-2B BF16 LoRA.

Use the same train/development split, input contract, and silver posterior. Compare macro-F1, per-source/aspect floors, calibration, invalid-output rate, local latency/memory, and dollars. Drop any Pareto-dominated model—lower validation quality while costing more and using more local memory. The 0.8B decoder survives only if it validates the generative approach or wins the efficiency frontier.

### Gate 3 — conditional promotions

- Promote ModernBERT-large only if ModernBERT-base's 10%→25%→50% data curve is still improving and capacity-related errors dominate.
- Promote Qwen3.5-4B only if its untrained 4-bit artifact passed Gate 0 and the 2B decoder materially beats the encoder or exhibits clear correctable under-capacity.
- Invoke Phi-4-mini only for a Qwen-specific runtime/export failure, not merely to add another model.

### Gate 4 — scaling, seeds, and quantization

For only the best encoder and best decoder, build 10%/25%/50%/100% silver-data curves. Run multiple seeds only after the one-seed ordering is stable. Quantize the decoder from the merged high-precision checkpoint to 6-bit and 4-bit, then compare task predictions and label-token probabilities against the high-precision reference. Predeclare an allowable degradation—suggested starting point: no more than 0.5 macro-F1 points and no source/aspect guardrail breach. If 4B/4-bit loses to 2B/6-bit after this test, ship 2B.

### Gate 5 — freeze before the blind comparison

Choose the winner, runtime, quantization, prompt/input serialization, and calibration using development data only. Lock the hashes and spend ledger before the one-time human-gold and GPT-5.6-sol evaluation. Model selection after seeing the blind result would invalidate the non-inferiority claim.

## Decision-ready shortlist

If a later model-strategy ticket needs a default without further research, use:

- **Baseline:** ProsusAI FinBERT, new four-class head.
- **Primary:** ModernBERT-base full fine-tune with soft silver posteriors.
- **Classical challenger:** DeBERTa-v3-base full fine-tune.
- **Scale challenger:** ModernBERT-large, gated by the base learning curve.
- **Generative challenger:** Qwen3.5-2B BF16 LoRA → merged 6-bit and 4-bit artifacts.
- **Conditional stretch:** Qwen3.5-4B BF16 LoRA → 4-bit only, gated by exact-device fit and 2B results.
- **Runtime:** PyTorch MPS first for encoders; llama.cpp Metal GGUF first and MLX-LM cross-check for decoders.
- **Provisional model-work budget:** $40 gross list price, enforced by per-run billing logs and 20% projected-cost contingency.

This shortlist is permissively licensed at the model-weight level (Apache-2.0 or MIT), but that does not clear training-data, source-text, or generated-label rights. Those remain separate data-governance decisions.
