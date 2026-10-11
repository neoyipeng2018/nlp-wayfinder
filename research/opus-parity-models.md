# Open models that could reach Opus parity on free GPUs

**Retrieval date:** 2026-10-11
**Scope:** Evidence for [Find open models that could reach Opus parity on free GPUs](https://github.com/neoyipeng2018/nlp-wayfinder/issues/134), under map [Train a Signal specialist to Opus parity](https://github.com/neoyipeng2018/nlp-wayfinder/issues/133).
**Sources:** Model cards, papers, official framework docs, vendor spec pages, and this repo's own Kaggle run log. Where a number is my estimate rather than a published figure, it says **estimate** and shows the arithmetic.

## Answer

The ranked shortlist for a dev screen:

1. **`Qwen/Qwen3-8B` + LoRA + a classification head** (`Qwen3ForSequenceClassification`). This is the largest capacity jump that still trains on a free Kaggle T4. It uses QLoRA, about one epoch per 12-hour session (**estimate**). It has a standard attention architecture, an Apache-2.0 license, and a sequence-classification class in `transformers`. The best published analogue is LLaMA-2-7B with LoRA and a label head, which beat RoBERTa-Large on four classification sets, including financial tweet sentiment.
2. **`answerdotai/ModernBERT-large`, full fine-tune.** This is a drop-in on the existing `train4.py` recipe, with the same tokenizer and an 8,192-token context. It costs about 3.5 h per seed on a T4 (**estimate**, scaled from our measured base run). It is the cheap control. Expect only a small gain: published GLUE is 90.4 vs 88.4 for base.
3. **Paid escalation: `Qwen/Qwen3.5-9B` (or `Qwen3-14B`), bf16 LoRA + classification head on one A100 80 GB.** Run it only if candidate 1 beats candidate 2 on dev. Unsloth advises against QLoRA for Qwen3.5, and 9B bf16 LoRA needs 22 GB, so it does not fit a free T4 well. On an A100 at USD 1.99/h, three seeds cost roughly USD 6–10 (**estimate**), inside the USD 20 cap.

Not shortlisted:

- **DeBERTa-v3-large:** it is about 6× slower than ModernBERT-base and has 512 positions, which truncate 4.5% of our examples. Its GLUE edge over ModernBERT-large is small.
- **Gemma 4:** no `ForSequenceClassification` class exists in `transformers` main, so it would have to be a generator.
- **Ettin-encoder-1B:** this is the reserve encoder if ModernBERT-large shows real scaling.

**Caveat on the bar.** Published model-size gains on classification are 1–3 points. Our gap to Opus is 0.13–0.2 macro-F1, depending on Opus's self-agreement. Self-agreement has not been measured. Measure it before the screen, because it sets whether the target is about 0.80 or about 0.88+. No source found shows a model change closing a gap of this size by itself. If the LLM classifier does not move dev by about 0.05 or more over ModernBERT-large, the gap is probably in the labels or task definition, not model capacity.

## Our input lengths

These are computed locally from the 13,256 rows in `.scratch/quick-loop/clean-v3.json`. Each row is serialized as in `train.py`: the passage, company, and aspect. Only statistics are reported, no text.

| Measure | mean | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| Passage characters | 1,080 | 916 | 1,815 | 2,267 | 3,610 | 5,978 |
| ModernBERT tokens (serialized) | 256 | 222 | 399 | 499 | 835 | 3,058 |
| Qwen3 tokens (serialized) | 253 | 224 | — | 487 | 792 | 2,482 |

- With the ModernBERT tokenizer, 4.45% of examples exceed 512 tokens and 0.69% exceed 1,024, which is the current `MAX_EXAMPLE_TOKENS`.
- One epoch is about 3.4 M tokens with either tokenizer.
- Every candidate except DeBERTa-v3 (512) covers 100% of examples natively.

## Compute baseline: our measured run

The repo's own Kaggle log for #132 (`kaggle4/out/nlp-wayfinder-signal-v4.log`) measured ModernBERT-base on 13,256 examples on one T4. The setup was micro-batch 4 × accumulate 8, 1,024 max tokens, and 3 epochs.

- It took **about 1,515 s per epoch**, or about 77 min per seed including gold scoring. Three seeds took 13,884 s in total.
- Scoring 2,136 gold rows took about 65 s, so **inference is about 30 s per 1k passages on a T4**.

Hardware facts:

- **T4:** 65 FP16 TFLOPS and 16 GB GDDR6 ([NVIDIA T4](https://www.nvidia.com/en-us/data-center/tesla-t4/)).
- **No bf16 or FlashAttention-2 on T4:** FlashAttention-2 supports Ampere, Ada, and Hopper. bf16 "requires Ampere, Ada, or Hopper". Turing (T4) needs the separate `flash-attention-turing` repo ([FlashAttention README](https://github.com/Dao-AILab/flash-attention)).
- **Kaggle quota:** I found no first-party Kaggle quota page that renders without JavaScript. The 12 h / 16 GB / T4×2-or-P100 limits used here are the map's stated constraints.
- **Paid GPU prices:** on-demand A100 80 GB SXM costs USD 1.99/h, H100 PCIe USD 3.29/h, and A10 USD 1.29/h ([Lambda pricing](https://lambda.ai/service/gpu-cloud/pricing)).

## Candidates

### Encoders (full fine-tune, classification head)

| Model | Params | Max context | License | Fit at 13k (T4) | Inference / 1k (T4) | Evidence |
|---|---:|---:|---|---|---|---|
| ModernBERT-base (current) | 149M | 8,192 | Apache-2.0 | 25 min/epoch (**measured**) | ~0.5 min (**measured**) | 0.772 vs Opus gold |
| **ModernBERT-large** | 395M | 8,192 | Apache-2.0 | ~70 min/epoch, ~3.5 h/seed (**estimate**: ×2.8 from paper throughput 147.3 vs 52.9 ktok/s) | ~1.5 min | GLUE 90.4 vs 88.4 base |
| DeBERTa-v3-large | 435M (304M backbone + 131M embedding) | 512 positions | MIT | ~2.5 h/epoch, ~7.5 h/seed (**estimate**: ×6 from paper fixed-length throughput 148.1 vs 24.6) | ~3 min | Best large encoder on GLUE; ModernBERT-large "almost match[es]" it |
| Ettin-encoder-1B | ~1B | ~8k (`max_position_embeddings` 7,999) | MIT | ~3 h+/epoch (**estimate**, no published throughput) | ~4 min | GLUE avg 91.6 vs ModernBERT-large 90.4; MNLI 91.8 vs 90.8 |

Sources:

- **ModernBERT:** sizes, 8,192 context, and GLUE come from [Warner et al. 2025](https://arxiv.org/abs/2412.13663). Throughput comes from its Table 2, measured on an RTX 4090. Card: [ModernBERT-large @ `45bb465`](https://huggingface.co/answerdotai/ModernBERT-large).
- **DeBERTa-v3-large:** parameters are from the [card @ `64a8c8e`](https://huggingface.co/microsoft/deberta-v3-large). Its config has `max_position_embeddings: 512`, with relative position buckets.
- **Ettin:** [Weller et al. 2025, Table 3](https://arxiv.org/abs/2507.11412) and the [card @ `befd76b`](https://huggingface.co/jhu-clsp/ettin-encoder-1b). The paper also finds that "a 400M encoder outperforms a 1B decoder on classification" when both are trained identically. That argues against small decoders, but it says nothing about 8B+ decoders.

**Read:** all published large-vs-base encoder deltas are about 2 GLUE points. ModernBERT-large is the cheap, low-risk step. It is unlikely to close 0.13+ alone.

### Open LLMs (LoRA/QLoRA, used as classifier or generator)

| Model | Params | Max context | License | Seq-cls class in `transformers` | Free-T4 fit | Paid A100 fit |
|---|---:|---:|---|---|---|---|
| **Qwen3-8B** | 8.2B | 32,768 native | Apache-2.0 | `Qwen3ForSequenceClassification` | QLoRA; ~3–5 h/epoch (**estimate**) | bf16 LoRA ~0.5 h/epoch (**estimate**) |
| Qwen3-14B | 14.8B | 32,768 native | Apache-2.0 | yes | QLoRA fits 16 GB (Unsloth); ~6–9 h/epoch (**estimate**), one epoch borderline | ~1 h/epoch (**estimate**) |
| **Qwen3.5-9B** | 9.65B (vision-language, hybrid Gated DeltaNet + attention) | 262,144 | Apache-2.0 | `Qwen3_5ForSequenceClassification` | Poor: bf16 LoRA needs 22 GB, QLoRA "not recommended", T4 has no bf16 | Yes |
| Qwen3.5-4B | 4.66B | 262,144 | Apache-2.0 | yes | bf16 LoRA 10 GB, but T4 lacks bf16; risky | Yes |
| Gemma 4 12B | 11.95B | 256K | Apache-2.0 | **none** (only `Gemma4ForCausalLM`) | QLoRA VRAM not published for 12B | Generator only |
| Gemma 4 E4B | 4.5B effective (8B with embeddings) | 128K | Apache-2.0 | none | QLoRA 10 GB, free T4 notebook | Generator only |

Sources:

- **Qwen3:** cards [Qwen3-8B @ `b968826`](https://huggingface.co/Qwen/Qwen3-8B) and [Qwen3-14B @ `40c0698`](https://huggingface.co/Qwen/Qwen3-14B). Unsloth says "Qwen3 (14B) fits comfortably in a … 16GB VRAM Tesla T4" ([Unsloth Qwen3](https://unsloth.ai/docs/models/qwen3-how-to-run-and-fine-tune)).
- **Qwen3.5:** cards [Qwen3.5-9B @ `c202236`](https://huggingface.co/Qwen/Qwen3.5-9B) and [Qwen3.5-4B @ `851bf6e`](https://huggingface.co/Qwen/Qwen3.5-4B). Unsloth gives LoRA VRAM of 4B: 10 GB and 9B: 22 GB. It says: "It is not recommended to do QLoRA (4-bit) training on the Qwen3.5 models" ([Unsloth Qwen3.5 fine-tune](https://unsloth.ai/docs/models/qwen3.5/fine-tune)).
- **Gemma 4:** cards [gemma-4-12B @ `023679e`](https://huggingface.co/google/gemma-4-12B) and [gemma-4-E4B @ `411aa17`](https://huggingface.co/google/gemma-4-E4B). Unsloth says E4B QLoRA needs 10 GB and lists a T4 notebook. It also notes an fp16 overflow bug on T4 in the audio path ([Unsloth Gemma 4 train](https://unsloth.ai/docs/models/gemma-4/train)).
- **Classes:** checked in `transformers` main, `models/{qwen3,qwen3_5,gemma4}/modeling_*.py`, on 2026-10-11.
- **Llama:** no new small dense Llama since 3.x. Llama 3.x has a gated custom license and is older than Qwen3, so it is not considered.

**Fit-time arithmetic (estimates).** LoRA training costs about 6·N·T FLOPs per epoch with gradient checkpointing. That is forward, backward through the frozen weights, and recompute, with no weight gradients.

- For Qwen3-8B: 6 × 8.2e9 × 3.4e6 ≈ 1.7e17 FLOPs.
- On a T4 at 10–16 effective TFLOPS (15–25% of the 65 peak, minus QLoRA dequant cost), that is about 3–5 h per epoch.
- On an A100 at about 100 effective bf16 TFLOPS, it is about 0.5 h per epoch.
- Inference is 2·N·T per example: 2 × 8.2e9 × 256 ≈ 4.2 TFLOPs. That gives **about 3–7 min per 1k passages on a T4**, or about USD 0.07–0.15 per 1k on an A10 at USD 1.29/h. Encoders cost about USD 0.01–0.03 per 1k.

**Classifier vs generator.** Use a classification head for the screen.

- It gives calibrated 3-way softmax that plugs into the existing scoring (`SIGNAL`, prior τ). It needs one forward pass per example and no decoding.
- LS-LLaMA found a label-supervised LLaMA-2-7B with LoRA beats instruction-tuned generation. It also beats RoBERTa-Large by 1.26 / 0.90 / 0.92 / 2.67 points accuracy on SST-2 / AGNews / Twitter-Financial-News / SST-5 ([Li et al. 2023](https://arxiv.org/abs/2310.01208)).
- In the same paper, 13B did not beat 7B on the small datasets. Do not assume bigger is better at 13k examples.

## Evidence that small fine-tuned models match an LLM teacher

- **[LoRA Land (Zhao et al. 2024)](https://arxiv.org/abs/2405.00732):** 310 4-bit LoRA models across 10 base models and 31 tasks. On average they "outperform … GPT-4 by 10 points" and beat their base models by 34 points. The comparison is against *prompted* GPT-4 on the task's own gold labels, not against a teacher's self-agreement.
- **[Bucher & Martini 2024](https://arxiv.org/abs/2406.08660):** fine-tuned smaller models beat zero-shot GPT-3.5/GPT-4/Claude Opus on sentiment, stance, and emotion classification of news and social text, "in all cases". Same caveat: the comparison is to zero-shot LLMs, not distillation to teacher parity.
- **[Distilling step-by-step (Hsieh et al., Findings ACL 2023)](https://arxiv.org/abs/2305.02301):** a 770M T5 student outperforms few-shot PaLM-540B. It trains on teacher **rationales** as a multi-task target alongside labels, using e-SNLI, ANLI, CQA, and SVAMP. Rationales beat label-only distillation at every data size; for example, 12.5% of ANLI unlabeled data was enough to beat standard distillation on the full set. **Do rationales help? Yes, in that setting.** But the student was a seq2seq generator, and the gain was largest at small data sizes. It applies only to a generative LoRA student, not to a classification head. We already have 13k labels.
- **Gap in the literature:** I found no primary source that measures a fine-tuned open model against a *frontier LLM teacher's self-agreement* on a target-conditioned financial classification task. Every comparison above uses a fixed gold set or a prompted LLM baseline. Whether we can get within 0.05 of Opus is an empirical question for the dev screen.

## Recommended dev screen

These run on gold-v3 + gold-v4 dev, 3-class macro-F1, using the current `train4.py` data path.

1. **ModernBERT-large:** frozen v2 settings with the LR lowered to about 2e-5, the usual large-encoder practice. One seed on free T4. This is the control, at about 3.5 h.
2. **Qwen3-8B QLoRA + `Qwen3ForSequenceClassification`:** r = 16, 1 epoch, max length 1,024, fp16 on free T4. One seed, about 5 h (**estimate**). Run it on the second T4 in parallel with 1.
3. **If 2 beats 1 by ≥ 0.03 on dev:** Qwen3.5-9B (or Qwen3-14B) bf16 LoRA + classification head on a paid A100 80 GB, 3 seeds, about USD 6–10.

**Before the screen:** measure Opus self-agreement on a few hundred dev rows with blind Opus relabels. A student trained on many Opus labels learns Opus's *modal* label. So student-vs-Opus agreement can in principle approach or exceed Opus-vs-Opus agreement, which makes the 0.05 bar reachable even if some labels are noisy.
