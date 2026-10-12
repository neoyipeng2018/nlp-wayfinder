# Encoders that could match Qwen3-8B on the Signal task

**Retrieval date:** 2026-10-12
**Scope:** Evidence for [Find encoders that could match Qwen3-8B on the Signal task](https://github.com/neoyipeng2018/nlp-wayfinder/issues/141).
**Builds on:** [research/opus-parity-models.md](https://github.com/neoyipeng2018/nlp-wayfinder/blob/research/opus-parity-models/research/opus-parity-models.md). That memo already covers ModernBERT-base/large, DeBERTa-v3-large (dropped) and Ettin-1B (reserve), plus the Qwen3/Qwen3.5/Gemma 4 decoder options. This memo does not repeat that work.
**Sources:** Papers, model cards and configs on the Hugging Face Hub, and `transformers` source at commit [`55c3cc9`](https://github.com/huggingface/transformers/tree/55c3cc9f03cd4fbf2d27d382dcc8fcc544631f8e). Every number I derived rather than read is marked **estimate**, and the arithmetic is shown under [Cost model](#cost-model).

## Answer

**No pure encoder is likely to match Qwen3-8B.** The best open encoders differ by only 1–2 GLUE points from ModernBERT-large, and ModernBERT-large is 0.057 macro-F1 below Qwen3-8B on our dev set. No source shows an encoder of 1B or smaller closing a gap that size against a fine-tuned 7B+ decoder. The two papers that compare them directly found the reverse: fine-tuned 7B–70B decoders beat RoBERTa-large by 1–4 points.

**What might match Qwen3-8B at lower cost is a smaller decoder converted to bidirectional attention.** Two papers support this:
- Gemma Encoder: switching Gemma-2 2B from causal to bidirectional attention raised GLUE from 84.5 to 89.4.
- T5Gemma: its 9B encoder scored 91.4 on SuperGLUE vs 82.5 for decoder-only Gemma 2 9B.

**Neither route is likely to reach the 0.889 gold-v5 line.** Qwen3-8B itself scores 0.861 on gold-v4. Every candidate below is a bet on getting to about 0.84 more cheaply, not on passing 0.889.

**Ranked shortlist for one dev seed each against Qwen3-8B (0.840 pooled dev):**

| # | Candidate | Why | Est. fit / epoch on T4 | Est. inference / 1k | Risk |
|---|---|---|---|---|---|
| 1 | **Qwen3-4B + bidirectional attention** (`McGill-NLP/LLM2Vec-Qwen3-4B-mntp` adapter merged into `Qwen/Qwen3-4B`), LoRA + classification head | The only route with published evidence of beating a same-size causal decoder on classification. It has half the parameters of 8B. | ~3.2 h | ~240 T4-s, ~$0.09 | Needs a ~60-line custom model class. LS-LLaMA found causal attention better for sequence classification on small sets. |
| 2 | **Qwen3-4B, causal, `Qwen3ForSequenceClassification`** (the current 8B recipe with a different model id) | Zero-code control for #1. Its base MMLU is 73.0 vs 76.9 for 8B. | ~3.2 h | ~240 T4-s, ~$0.09 | Probably 0.01–0.04 below 8B (**estimate**). |
| 3 | **T5Gemma 2B-2B encoder only** (`T5GemmaForSequenceClassification(is_encoder_decoder=False)`) | Strongest published encoder-vs-decoder classification result (SuperGLUE 88.1 vs 75.5 for Gemma 2 2B). Native `transformers` class. | ~1.6 h | ~145 T4-s, ~$0.06 | Gemma license and gated weights. Trained in bf16, so fp16 on a T4 is unproven. Context is not stated on the card. |
| 4 | **Ettin-encoder-1B**, full fine-tune with 8-bit AdamW | Best pure encoder: GLUE 91.6 vs 90.4 for ModernBERT-large. MIT license, native ModernBERT class. | ~3.3 h (~10 h for 3 epochs) | ~80 T4-s, ~$0.03 | Expect about 0.79–0.80 on dev (**estimate**). Useful only as a cheap-inference fallback. |
| 5 | Qwen3-1.7B, causal classification head, fp16 LoRA | Shows how quickly accuracy falls off with model size. | ~1.4 h | ~110 T4-s, ~$0.04 | Base MMLU is 62.6, a big step down from 4B. |

Upside option outside the cost brief: `LLM2Vec-Qwen3-8B-mntp`, i.e. the current 8B with bidirectional attention. It costs the same as today's run. It is the most likely candidate to *beat* 0.840, but it is not cheaper.

**Dropped:**
- NeoBERT: GLUE 89.0, below ModernBERT-large.
- mmBERT: English GLUE 86.3, below ModernBERT-base's 87.4.
- EuroBERT: no English GLUE reported. The authors themselves say no model "significantly outperforms all others" on classification.
- XLM-R XL/XXL: 514 positions, and only +0.3 GLUE over RoBERTa-large.
- Finance BERTs: BERT-base size with 512 positions.
- Gemma 3 with `use_bidirectional_attention`: this works, but it duplicates #3 under the same license, with less evidence.

**Cost is not the binding constraint.** Qwen3-8B inference is about $0.19 per 1k passages. The cheapest candidate saves about $0.16 per 1k, or about $16 per 100k passages. So only switch to a smaller model if its dev score stays within noise of 0.840.

## Our task, in the terms the sources use

- 3 classes, about 13.3k training rows. Inputs are serialized passage + company + aspect: median about 222 tokens, p95 about 500, max about 3k (from the prior memo).
- Hardware: Kaggle T4, 16 GB, fp16 only. FlashAttention-2 and bf16 need Ampere or newer ([FlashAttention README](https://github.com/Dao-AILab/flash-attention)).
- Measured anchors from our runs:
  - ModernBERT-base: about 25 min per epoch, about 30 T4-s per 1k at inference.
  - ModernBERT-large full fine-tune: about 4 h per seed.
  - Qwen3-8B nf4 QLoRA r16: about 6.5 h per epoch, about 500 T4-s per 1k (about $0.19).

## Candidates in detail

### A. Larger or newer encoders

| Model | Params | Context | License | `transformers` seq-cls | Classification evidence | Est. T4 fit (13k, per epoch) | Est. VRAM | Est. inference / 1k |
|---|---:|---:|---|---|---|---|---|---|
| **Ettin-encoder-1B** | ~1.0B (28 L × 1792) | 7,999 | MIT | `ModernBertForSequenceClassification` (native) | GLUE 91.6 / MNLI 91.8 vs ModernBERT-large 90.4 / 90.8. "A 400M encoder outperforms a 1B decoder on MNLI" (91.3 vs 89.9). | ~3.3 h | Full FT with standard AdamW is ~16 GB + activations: **does not fit**. With 8-bit AdamW, ~10 GB + activations ≈ 13 GB. LoRA fits easily. | ~80 s, $0.03 |
| NeoBERT | 250M (28 L × 768) | 4,096 | MIT | Remote code (`NeoBERTForSequenceClassification`). The card asks for `xformers==0.0.28.post3`. | GLUE 89.0 vs ModernBERT-large 90.5 and DeBERTa-v3-large 91.4 | ~50 min | ~5 GB | ~40 s, $0.015 |
| mmBERT-base | 307M (110M non-embedding) | 8,192 | MIT (card) | Native ModernBERT class | English GLUE 86.3 vs ModernBERT-base 87.4 | ~30 min | ~6 GB | ~35 s |
| EuroBERT-2.1B | 2.1B (32 L × 2304, GQA) | 8,192 | Apache-2.0 | `EuroBertForSequenceClassification`, now native in `transformers` main | No English GLUE. XNLI 84.1 / PAWS-X 93.0 vs XLM-R-XL 83.7 / 92.9. The authors say no model "significantly outperforms all others" on sequence classification. | LoRA fp16: ~1.7 h | ~8 GB with LoRA | ~135 s, $0.05 |
| XLM-R XL | 3.5B | **514 positions** | MIT | `XLMRobertaXLForSequenceClassification` (native) | GLUE +0.3 avg over RoBERTa-large; XNLI +1.8 over XLM-R | LoRA fp16: ~2.8 h | ~10 GB | ~195 s, $0.07 |
| XLM-R XXL | 10.7B | **514 positions** | MIT | Same class | XNLI +2.4 over XLM-R | QLoRA: ~8.5 h | ~10 GB with nf4 | ~610 s, $0.23 (more expensive than Qwen3-8B) |
| FinBERT (ProsusAI), SEC-BERT | 110M, BERT-base | 512 | FinBERT: no license in metadata. SEC-BERT: CC-BY-SA-4.0. | `BertForSequenceClassification` | Domain-pretrained BERT-base. LS-LLaMA's LLaMA-2-7B beat RoBERTa-large on Twitter-Financial-News by +0.92. | ~15 min | ~3 GB | ~30 s |

Sources:
- **Ettin:** [Weller et al. 2025](https://arxiv.org/abs/2507.11412), Table 7 for GLUE and Table 9 / Fig. 1 for the encoder-vs-decoder comparison. Config from [`jhu-clsp/ettin-encoder-1b`](https://huggingface.co/jhu-clsp/ettin-encoder-1b): `hidden_size` 1792, 28 layers, `max_position_embeddings` 7999, `model_type: modernbert`. The paper also tried continuing a decoder's training with MLM: that encoder-from-decoder reached 87.6 MNLI at 400M vs 91.3 for the native encoder.
- **NeoBERT:** [Le Breton et al. 2025](https://arxiv.org/abs/2502.19587). Card and config at [`chandar-lab/NeoBERT`](https://huggingface.co/chandar-lab/NeoBERT); the config `auto_map` points to remote code.
- **mmBERT:** [Marone et al. 2025](https://arxiv.org/abs/2509.06888). The license comes from the [`jhu-clsp/mmBERT-base`](https://huggingface.co/jhu-clsp/mmBERT-base) card. The paper's own page lists CC BY 4.0, which is the paper's license.
- **EuroBERT:** [Boizard et al. 2025](https://arxiv.org/abs/2503.05500). Card and config at [`EuroBERT/EuroBERT-2.1B`](https://huggingface.co/EuroBERT/EuroBERT-2.1B). The class is at `transformers/models/eurobert/modeling_eurobert.py` @ `55c3cc9`.
- **XLM-R XL/XXL:** [Goyal et al. 2021](https://arxiv.org/abs/2105.00572). Configs at [`facebook/xlm-roberta-xl`](https://huggingface.co/facebook/xlm-roberta-xl) and [`-xxl`](https://huggingface.co/facebook/xlm-roberta-xxl) show `max_position_embeddings: 514`. Our data has 4.45% of rows over 512 tokens (prior memo).
- **Finance encoders:** [`ProsusAI/finbert`](https://huggingface.co/ProsusAI/finbert) and [`nlpaueb/sec-bert-base`](https://huggingface.co/nlpaueb/sec-bert-base). Neither card reports results against current encoders or LLMs. The 7B-vs-RoBERTa finance number is from [LS-LLaMA](https://arxiv.org/abs/2310.01208).

**Read:** the encoder frontier is Ettin-1B, at +1.2 GLUE over ModernBERT-large. Our ModernBERT base-to-large step was +1.0 GLUE in the paper but only +0.005 pooled dev for us. So by the same logic, Ettin-1B should add about 0.01–0.02 at best (**estimate**), well short of 0.057. The multilingual families (mmBERT, EuroBERT, XLM-R) trade English quality for language coverage we do not need.

### B. LLM-to-encoder conversions (bidirectional decoders)

| Model | Params | Context | License | `transformers` seq-cls | Classification evidence | Est. T4 fit (13k, per epoch) | Est. VRAM | Est. inference / 1k |
|---|---:|---:|---|---|---|---|---|---|
| **LLM2Vec-Qwen3-4B-mntp** (adapter on `Qwen/Qwen3-4B`) | 4.0B | 40,960 (`max_position_embeddings`) | Adapter MIT, base Apache-2.0 | No native class. The repo ships `modeling_qwen3_encoder.py`, which sets `is_causal=False` on `Qwen3Attention` and needs `transformers` ≥ 4.56.2. A classification head goes on top (mean or last-token pool). | See the evidence list below this table. | ~3.2 h (QLoRA) | ~8 GB with nf4 | ~240 s, $0.09 |
| LLM2Vec-Qwen3-8B-mntp | 8.2B | 40,960 | MIT / Apache-2.0 | Same | Same | ~6.5 h | ~13 GB with nf4 (same as now) | ~500 s, $0.19 |
| **T5Gemma 2B-2B, encoder only** | ~2B encoder (6B total enc-dec per card) | Not stated on card (Gemma 2 base: 8,192) | Gemma Terms, gated | `T5GemmaForSequenceClassification(config, is_encoder_decoder=False)`, native | SuperGLUE with a classification head on the encoder: 2B-2B 88.1 vs decoder-only Gemma 2 2B 75.5; 9B-9B 91.4 vs 82.5 (pretrained checkpoints) | LoRA fp16: ~1.6 h | ~7 GB | ~145 s, $0.06 |
| T5Gemma 9B-9B, encoder only | ~9B encoder | Same | Same | Same | Same | QLoRA: ~7 h | ~12 GB | ~525 s, $0.20 |
| Gemma 3 1B / 4B, `use_bidirectional_attention=True` | 1B / 4B | 32K / 128K | Gemma Terms | `Gemma3TextForSequenceClassification` / `Gemma3ForSequenceClassification`; the config flag is native | Gemma Encoder (Gemma 2): bidirectional 89.4 vs causal 84.5 GLUE at 2B | ~0.8 h / ~3.2 h | ~5 / ~10 GB | ~67 / ~215 s |
| T5Gemma 2 (270M–4B per side) | 0.27–4B | 128K | Gemma Terms | `T5Gemma2ForSequenceClassification` exists but pools the **decoder's** last token, so it needs the full encoder-decoder. No encoder-only path. | No classification results in the paper | — | — | — |

Evidence:

- **Gemma Encoder** ([Suganthan et al. 2025](https://arxiv.org/abs/2503.02656)). They swapped causal for bidirectional attention *only during fine-tuning*, with no extra pretraining, and added a pooler and 10% dropout.
  - Gemma-2 2B: GLUE 89.4 bidirectional vs 84.5 causal. With the best pooling: 91.1 at 2B and 92.1 at 9B.
  - The paper says code and weights would come in "a forthcoming revision". I found no released checkpoint, but the recipe can be copied with the Gemma 3 flag above.
- **T5Gemma** ([Zhang et al. 2025](https://arxiv.org/abs/2504.06225)): "encoder-decoder LLMs perform consistently better than decoder-only LLMs on SuperGLUE". Checkpoints are listed under [`google/t5gemma-*`](https://huggingface.co/google/t5gemma-2b-2b-ul2) (gated, "License: Gemma", bf16).
- **LLM2Vec** ([BehnamGhader et al. 2024](https://arxiv.org/abs/2404.05961)). Steps: bidirectional attention, then masked next-token prediction (MNTP), then optional SimCSE.
  - With MNTP, word-level tasks improved over causal: for example, Mistral-7B chunking went from 87.5 to 91.2.
  - The paper reports no supervised sequence-classification fine-tuning, only embedding probes. So its evidence for our setting is indirect.
  - Qwen3 checkpoints from 0.6B to 8B are on [`McGill-NLP`](https://huggingface.co/McGill-NLP/LLM2Vec-Qwen3-4B-mntp) (MIT, PEFT LoRA r16).
- **LS-LLaMA counter-evidence** ([Li et al. 2023](https://arxiv.org/abs/2310.01208)). Removing the causal mask from LLaMA-2-7B ("LS-unLLaMA") helped a lot on NER (CoNLL F1 93.2 vs 74.8). For sequence classification, though, causal LS-LLaMA was best on the smaller sets, and unLLaMA won only on the large SST-2 and AGNews. Our 13k rows sit between those regimes.
- **Ettin cross-objective result:** continuing a decoder's training with MLM gives a worse encoder than pretraining one natively. That argues against expecting an encoder-from-decoder to beat Ettin *per parameter*. Here, though, the comparison is a 4B converted decoder vs an 8B causal decoder, where the converted model has the size advantage.

**Read:** bidirectional conversion is the one lever with published gains of several GLUE points at a fixed model size. That is the size of gain we would need for a 4B model to make up the 4B-to-8B gap. It is unproven on target-conditioned 3-class tasks.

### C. Small decoders with a classification head (Qwen3 0.6B–4B)

| Model | Params (layers × hidden) | Context | License | `transformers` seq-cls | Evidence | Est. T4 fit / epoch | Est. VRAM | Est. inference / 1k |
|---|---|---:|---|---|---|---|---|---|
| **Qwen3-4B** | 4.0B (36 × 2560) | 40,960 (`max_position_embeddings`; 32K native per report) | Apache-2.0 | `Qwen3ForSequenceClassification` (native) | Base MMLU 73.0 vs 8B 76.9; BBH 72.6 vs 78.4 | ~3.2 h QLoRA | ~8 GB nf4, or ~12 GB fp16 LoRA | ~240 s, $0.09 |
| Qwen3-1.7B | 1.7B (28 × 2048) | 40,960 | Apache-2.0 | Same | MMLU 62.6, BBH 54.5 | ~1.4 h fp16 LoRA | ~6 GB | ~110 s, $0.04 |
| Qwen3-0.6B | 0.6B (28 × 1024) | 40,960 | Apache-2.0 | Same | MMLU 52.8, BBH 41.5. Ettin found a 400M encoder beats a 1B decoder on classification, so this is likely no better than ModernBERT-large. | ~0.6 h full FT | ~10 GB | ~50 s, $0.02 |

Sources: configs at [`Qwen/Qwen3-4B`](https://huggingface.co/Qwen/Qwen3-4B), [`-1.7B`](https://huggingface.co/Qwen/Qwen3-1.7B) and [`-0.6B`](https://huggingface.co/Qwen/Qwen3-0.6B). Base benchmarks are from the [Qwen3 technical report](https://arxiv.org/abs/2505.09388), Table 8. The class is at `transformers/models/qwen3/modeling_qwen3.py` @ `55c3cc9`.

Size scaling, from fine-tuned classification papers:
- **LS-LLaMA:** 13B did not consistently beat 7B on small datasets.
- **[Advancing single- and multi-task text classification (2024)](https://arxiv.org/abs/2412.08587):** full-fine-tuned Llama3-70B beat RoBERTa-large by 3.8 points on 20NG-20 (91.9 vs 88.1) and by 0.7 on MASSIVE intent (90.8 vs 90.1).
- **[Are LLMs good classifiers? (2024)](https://arxiv.org/abs/2410.02028):** QLoRA 7–13B decoders with classification heads reached 84.3 macro-F1 vs 82.2 for RoBERTa-base on edit-intent classification.

So the measured advantage of 7B+ decoders over encoders is usually 1–4 points. Our observed gap of 5.7 is at the high end of that range. This suggests the Signal task rewards decoder knowledge more than typical benchmarks do, which is another reason to keep the decoder lineage rather than move to an encoder.

## Cost model

All numbers in this section are **estimates** unless marked measured.

- **Inference** is about 25 s fixed overhead + 60 s per billion non-embedding parameters, per 1k passages on a T4. The fit is from two measured points: ModernBERT-base (≈0.11B non-embedding) at 30 s, and Qwen3-8B (≈7.6B non-embedding) at 500 s.
- **Dollars** use the rate implied by the measured Qwen3-8B figure: $0.19 / 500 s ≈ $0.00038 per T4-second.
- **LoRA/QLoRA fit time** scales linearly with total parameters from the measured 6.5 h/epoch for Qwen3-8B. That is about 0.8 h per billion parameters per epoch at our token count. fp16 LoRA, with no nf4 dequantization, is probably somewhat faster, so these figures are conservative.
- **Encoder full fine-tune time** scales with non-embedding parameters from the measured runs: ModernBERT-base at about 25 min/epoch, and ModernBERT-large at about 4 h/seed, about 80 min/epoch if 3 epochs. Ettin-1B has about 0.91B non-embedding parameters vs 0.34B for ModernBERT-large, a factor of 2.6, giving about 3.3 h/epoch.
- **VRAM:**
  - Full fine-tune with AMP + AdamW is about 16 bytes/parameter; with 8-bit AdamW, about 10 bytes/parameter.
  - fp16 LoRA is about 2 bytes/parameter for frozen weights; nf4 is about 0.55 bytes/parameter.
  - Add 2–4 GB of activations at micro-batch 4 × 1,024 tokens with gradient checkpointing.

## Suggested next step

1. Run one dev seed of #2 (causal Qwen3-4B, a model-id swap in the current QLoRA notebook).
2. In parallel on the second T4, run one dev seed of #1: the same recipe after merging the `LLM2Vec-Qwen3-4B-mntp` adapter and loading the bidirectional model class.
3. If #1 reaches ≥ 0.83 pooled dev, run 8B bidirectional next. That is the only candidate here with a plausible path *above* 0.840.
4. Keep Ettin-1B in reserve only as a cheap-inference fallback. Do not spend a T4 day on the other encoders.
