# Evidence memo: select the first compact model

**Retrieval date:** 2026-09-04  
**Scope:** Evidence for [“Review the best compact model for staged financial ABSA”](https://github.com/neoyipeng2018/nlp-wayfinder/issues/18). This memo uses papers, official model cards, official repositories, and official licenses. It makes no paid model call.

## Decision

Use [`yangheng/deberta-v3-base-absa-v1.1` at revision `10c9dff`](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1/tree/10c9dff335a44073e1352360c3a7bc54dc58eb01) as the first model. Replace its three-class head with a new four-class head. The four classes are `positive`, `neutral`, `negative`, and `insufficient evidence`.

Use the target and aspect as the second input sequence. Use this fixed form:

```text
Target: <company>. Aspect: <aspect>.
```

Use the financial passage as the first input sequence. This design keeps the model target-conditioned and aspect-conditioned. A peer-reviewed ABSA study found that a BERT sentence-pair form improved target-and-aspect sentiment classification. It treated the target and aspect as an auxiliary sentence ([Sun et al., 2019](https://aclanthology.org/N19-1035/)).

Do not start with ModernBERT. Use [`answerdotai/ModernBERT-base` at revision `8949b90`](https://huggingface.co/answerdotai/ModernBERT-base/tree/8949b909ec900327062f0ebf497f51aef5e6f0c8) only as the gated fallback. The fallback gate opens only if one of these conditions is true before blind evaluation:

1. More than 5% of valid examples need more than 512 tokens after the input form is frozen.
2. The DeBERTa checkpoint cannot complete a local training and inference smoke test on the Apple M3 computer with 8 GB memory.

Do not run both full experiments as an automatic model bake-off. This rule protects the USD 100 budget and keeps the blind set free from model selection.

## Why DeBERTa ABSA is first

The closest published comparison used 1,162 human-annotated Bloomberg news articles for target-based financial sentiment. The authors fine-tuned the discriminative models on that data. `deberta-v3-base-absa-v1.1` achieved 0.66 macro-F1. FinBERT achieved 0.54, DistilFinRoBERTa achieved 0.57, and FinBERT-Tone achieved 0.62. Thus, the ABSA-tuned DeBERTa checkpoint was the best compact discriminative model in that comparison ([Muhammad et al., 2025, Table 3](https://aclanthology.org/2025.clicit-1.74.pdf)).

This evidence is not an exact match for this project. The published task has three classes. This project has four classes and also supplies an aspect category. The result is still the closest direct evidence found because it is both target-based and financial.

The official checkpoint card gives these facts:

- The base is `microsoft/deberta-v3-base`.
- The model was tuned for ABSA with PyABSA data and methods.
- The model accepts a passage and an aspect as a text pair.
- The current checkpoint has a 512-token maximum, a three-class head, about 0.2 billion parameters, and a 738 MB F32 safe-tensor file.
- The checkpoint has an MIT license.

The [PyABSA repository](https://github.com/yangheng95/PyABSA) supplies the implementation and an MIT license. The [DeBERTa V3 paper](https://arxiv.org/abs/2111.09543) gives the pretraining method. The official DeBERTa repository reports 86 million backbone parameters for DeBERTa V3 Base. Its 128,100-item vocabulary makes the complete checkpoint about 183 million parameters ([official repository](https://github.com/microsoft/DeBERTa/tree/4d7fe0bd4fb3c7d4f4005a7cafabde9800372098)).

## Candidate comparison

| Candidate | Direct task evidence | Size and input limit | License | Decision |
|---|---|---:|---|---|
| `deberta-v3-base-absa-v1.1` | Best compact discriminative result in the closest target-based financial study; trained first for ABSA | About 183M; 512 tokens | MIT | Primary |
| `ModernBERT-base` | Strong general classification evidence; no direct financial ABSA result found | 149M; 8,192 tokens | Apache-2.0 | Gated fallback |
| `ProsusAI/finbert` | Direct financial sentiment evidence, but not target-and-aspect conditioning | About 110M; 512 tokens | The code repository is Apache-2.0; the checkpoint card does not state a license | Do not select |
| `LFM2.5-Encoder-230M` | Strong new general classification claims; no direct financial ABSA result found | 229.7M; 8,192 tokens | LFM Open License 1.0 | Do not select |
| `FLAN-T5-base` | General instruction and classification evidence; no direct result for this task | About 248M; encoder-decoder generation | Apache-2.0 | Do not select |
| `Qwen3-0.6B` | General generative evidence; no direct result for this task | 0.6B; 32,768 tokens | Apache-2.0 | Do not select |

### ModernBERT

ModernBERT is the strongest fallback for long passages. Its paper reports a GLUE score of 88.4 for ModernBERT Base and 88.1 for DeBERTa V3 Base. It also reports 149 million parameters and an 8,192-token limit. Its memory and speed tests used an NVIDIA RTX 4090, not Apple hardware. Thus, these tests do not prove Apple M3 performance ([Warner et al., 2025, Tables 1 and 2](https://aclanthology.org/2025.acl-long.127/)).

ModernBERT has excellent general evidence. It does not have the direct target-based financial result that the DeBERTa ABSA checkpoint has. Use it only when the 512-token limit or local compatibility blocks the primary model.

### Finance-specific encoders

The official FinBERT paper reports gains on Financial PhraseBank and FiQA sentiment tasks ([Araci, 2019](https://arxiv.org/abs/1908.10063)). Its model is a document-level three-class classifier. It does not receive a separate target and aspect. In the closest target-based financial comparison, it was below the ABSA-tuned DeBERTa model.

There is also a rights problem. The [`ProsusAI/finbert` model card](https://huggingface.co/ProsusAI/finbert) does not state a checkpoint license. The related code repository uses Apache-2.0, but a code license does not necessarily license model weights. The project also used Reuters TRC2 for domain pretraining. TRC2 access is restricted. Do not put this checkpoint in the clean model path without a separate weight-rights decision.

FinBERT2 is not a candidate. Its released base model and its reported finance benchmarks are Chinese, while this experiment uses English financial passages ([official FinBERT2 repository](https://github.com/valuesimplex/FinBERT)).

### New encoders

[`LiquidAI/LFM2.5-Encoder-230M`](https://huggingface.co/LiquidAI/LFM2.5-Encoder-230M) is a new 229.7-million-parameter encoder with an 8,192-token limit. Its official card reports strong results across general supervised classification tasks. It has no direct financial ABSA result. It also needs custom remote code. Its LFM Open License has a commercial-use condition for a legal entity with annual revenue of at least USD 10 million. These facts add technical and rights risk. They do not give a clear gain over the direct DeBERTa ABSA evidence.

### Small generative models

Do not add a small generative model to the first specialist experiment.

[`Qwen3-0.6B`](https://huggingface.co/Qwen/Qwen3-0.6B/tree/c1899de289a04d12100db370d81485cdf75e47ca) is the smallest current clean candidate found. Its official card states 0.6 billion parameters, a 32,768-token context, and an Apache-2.0 license. It has more than three times as many parameters as the primary encoder. It must also decode a label token by token. No direct four-class financial ABSA result was found.

[`google/flan-t5-base`](https://huggingface.co/google/flan-t5-base/tree/7bcac572ce56db69c1ea7c8af255c5d7c9672fc2) has about 248 million parameters and an Apache-2.0 license. It is smaller than Qwen3, but it still uses an encoder-decoder path and serial label generation. Its official evidence covers broad instruction tasks, not this exact task.

A more complex current method, STRIDE, reports 0.933 F1 on FinEntity. It uses T5 Base as a policy model and Llama 3.2 1B as a reward evaluator. It also needs authoritative reward labels. It is not one compact classifier, and it does not fit this project's silver-label design ([Rittikar et al., 2026](https://proceedings.mlr.press/v318/rittikar26a.html)).

## Training and calibration contract

Use this contract for the primary model:

1. Pin checkpoint revision `10c9dff335a44073e1352360c3a7bc54dc58eb01`.
2. Load the pretrained encoder. Replace the existing head with a randomly initialized four-logit head.
3. Put the financial passage in sequence A. Put the fixed target-and-aspect text in sequence B.
4. Set the maximum length to 512. Truncate only with a frozen rule. Record the truncated-example rate by source.
5. Train all model parameters on accepted silver probability vectors. Use soft cross-entropy, not hard labels.
6. Run three fixed random seeds. Select one checkpoint by development macro-F1. Freeze the tie rule before training.
7. Fit one scalar temperature on the human-labeled development set after checkpoint selection. Keep argmax class decisions unchanged. Report Brier score and expected calibration error with macro-F1. Temperature scaling is a simple held-out calibration method ([Guo et al., 2017](https://proceedings.mlr.press/v70/guo17a.html)).
8. Run the selected and calibrated checkpoint once on each blind source set.

Do not use a probability threshold to create `insufficient evidence`. It is a learned fourth class. This rule keeps the label contract the same for the specialist and GPT-5.6-sol.

## Apple M3 and budget feasibility

The primary checkpoint stores about 738 MB of F32 weights. A simple full-training lower-bound estimate is about 3 GB for parameters, gradients, and two Adam moments. Activations, framework state, and macOS also use the shared 8 GB memory. Therefore, 8 GB is plausible but not proven.

Before the first full run, complete a local smoke test with the frozen 512-token input, batch size 1, mixed precision, gradient accumulation, and memory logging. Do not buy cloud compute before this test. If memory is too high, use gradient checkpointing and a shorter frozen input limit. If the model still cannot train, open the ModernBERT fallback gate and test it in the same way.

Model training and local inference can have zero marginal external spend because the project already owns the Apple computer. Thus, this model choice can fit the total USD 100 cap. It does not prove that the complete experiment fits the cap. The complete cap also includes labeling calls, GPT-5.6-sol blind calls, storage, and paid data. Keep a single spend ledger across all stages. Stop before any action that would make committed spend exceed USD 100.

## Limits of the decision

No published model implements this exact four-class, company-target, supplied-aspect task. The primary checkpoint is the best first candidate, not a known final winner. The closest financial benchmark uses three labels and Bloomberg text. The primary checkpoint itself was first trained on non-financial ABSA data. The new silver labels must teach the financial aspects and `insufficient evidence` class.

Do not use the blind set to reopen this model choice. If the selected model fails the blind gate, report the failure. Start a new experiment before testing another model against those labels.
