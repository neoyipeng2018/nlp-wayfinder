# Evidence memo: techniques to close the specialist-to-GPT gap

**Retrieval date:** 2026-09-19  
**Scope:** Evidence for [“Research techniques to close the specialist-to-GPT gap”](https://github.com/neoyipeng2018/nlp-wayfinder/issues/66), under the map [“Run the sealed Stage 1 financial-news comparison”](https://github.com/neoyipeng2018/nlp-wayfinder/issues/46). This memo uses papers, official repositories, and the project code. It makes no paid model call. The sampling check in the ceiling section is a local simulation, not a measurement.

## Answer

No published technique is likely to close a large gap alone. The ceiling of the student is the accuracy of its silver labels on the human label conventions. Published students trained on LLM labels usually land within a few points of their teacher. Sometimes they are a few points better ([Zhao, 2023](https://arxiv.org/abs/2312.10185); [Hellwig et al., 2026](https://arxiv.org/abs/2603.01778)). They do not jump far past it.

The Stage 1 test is also stricter than the margin suggests. With 400 blind examples, the 95% interval of the macro-F1 difference is about 0.05 to 0.09 wide. Thus, the lower limit reaches −0.03 only when the true specialist score is about equal to or above the GPT score. A true gap of −0.03 passes in about 1–6% of simulated runs (see [Ceiling](#ceiling-and-the-non-inferiority-margin)).

Inside the current rules, do these four things before zero-change confirmation. They cost USD 0 and have low risk:

1. Train on the full calibrated Dawid–Skene probability vector, not only on the top label. The present code sends only the top label to the backend.
2. Correct the class prior to the balanced blind design.
3. Make sure that the silver set has enough realistic `insufficient evidence` examples.
4. Average the three seed checkpoints in place of selecting one on 200 development examples.

The one lever that matters most is **silver-label accuracy against the human reference**. The best early estimate is the out-of-fold development macro-F1 of the gold-anchored ensemble. The current rules cannot improve the voters. They can only improve how the student uses the voters' output. The largest levers outside the current rules are a better or additional free voter, and GPT-derived labels. GPT-derived labels break the GPT-independent claim, so they are not a real option.

## Code finding: soft labels are dropped

[`research/compact-model-review.md`](compact-model-review.md) required soft cross-entropy on silver probability vectors. `CONTEXT.md` also says that aggregation “produces a calibrated soft label”. The present code does not pass that vector to training:

- `aggregate_silver` keeps each accepted example as `{"candidate_id", "label": top_label, "probability": calibrated[top_label]}` (`nlp_wayfinder/stage_run.py`, near line 3049).
- `train_specialist` builds each training row as `{**_specialist_input(candidate), "label": silver_labels[...]}` (near line 3574). Thus, the backend receives one hard label.

The full raw posterior and the temperature are sealed in `silver-aggregation-log.jsonl`. Thus, the soft vector exists. A change to pass it to the backend is a code change before zero-change confirmation. It does not change a frozen rule.

Also note that the vote prompt, the GPT prompt, and the specialist input all send `company_id`, not the company name (`_vote_prompt`, `_gpt_prompt`, `_specialist_input`). The human input from `admit-example` uses `company["name"]`. If `company_id` is a slug such as `harbor-grid`, every model receives a weaker target cue than the human. This does not change the gap, because all models receive the same field. It can lower every model score. Confirm the `company_id` form in the annex before the seal.

## Ranked techniques

The rank uses the expected macro-F1 effect on this task, the strength of the evidence, and the rule cost. “Effect” is the effect in the cited source. It is not a forecast for this task, unless the row says so. The bucket labels are:

- **B1:** inside the current rules. The change must be fixed before zero-change confirmation.
- **B2:** needs a new planning decision.
- **B3:** needs a new destination.

| Rank | Technique | Bucket | Expected macro-F1 effect (source) | Cost against USD 100 | Risk |
|---:|---|---|---|---|---|
| 1 | **Class-prior correction** to the balanced blind design. Use logit adjustment by the log of the silver class prior, for each aspect, or use a class-balanced loss. | B1 | Logit adjustment is consistent for the balanced error, which averages per-class errors. It improves long-tail benchmarks ([Menon et al., 2021](https://arxiv.org/abs/2007.07314)). No financial or NLP result. For this task: 0 to several points. The effect grows with the skew of the accepted silver prior against the 25-per-cell blind design. | USD 0 | Low. Estimate the prior from silver data only. Freeze the rule before confirmation. It can overcorrect if the silver prior is noisy. |
| 2 | **Realistic `insufficient evidence` coverage.** In the annex, expand each target to all four Stage 1 aspects, so that unsupported aspects of a present target occur naturally. Report the accepted class counts. | B1 if fixed in the annex before the seal | No direct measurement. The blind set has 100 `insufficient evidence` examples, and no more than 10% are target-absent. A fixed confidence threshold under-selects hard classes ([Zhang et al., 2021, FlexMatch](https://arxiv.org/abs/2110.08263)). The 0.70 acceptance rule can do the same to this class. The effect can be large if the class is starved. | USD 0. It uses candidate inspections under the 6,668 limit. | Medium. More aspects per passage can lower yield, and the source already has a yield problem. |
| 3 | **Soft-label training** on the calibrated Dawid–Skene vector (knowledge-distillation loss). | B1 (code change) | For pretrained-LM end models, soft labels beat hard labels “in most cases” ([Zhang et al., 2021, WRENCH](https://arxiv.org/abs/2109.11377)). Distillation from soft targets transfers class similarity ([Hinton et al., 2015](https://arxiv.org/abs/1503.02531)). The expected gain is small, about 0–2 points, because accepted posteriors are at least 0.70 and are often near one-hot. | USD 0 | Low. |
| 4 | **Seed averaging.** Average the logits of the three seed checkpoints. Do not select one checkpoint on 200 development examples. | B1 | Fine-tuning results change a lot with only the seed ([Dodge et al., 2020](https://arxiv.org/abs/2002.06305)). A 200-example development set cannot rank three close seeds reliably. The gain is mostly lower variance. Expect less than about 1 point in mean. | USD 0 more training. Three M3 inference passes over 400 examples. | Low. The report must name the ensemble as the specialist. |
| 5 | **Fixed LR, epoch, and length settings from published sweeps,** or selection on a held-out silver split. | B1 | ModernBERT's own GLUE sweep chose base learning rates from 5e-5 to 8e-5 and 1 to 10 epochs for each task ([Warner et al., 2025, Table 6](https://arxiv.org/abs/2412.13663)). A poor setting can cost several points. Tuning past a sound default gives little. | Extra GPU runs, each far below the USD 5 pilot limit (estimate). They must fit the USD 35 projection. | Low. The development set cannot tune these settings after confirmation. |
| 6 | **Input formatting.** Use the company name, not the ID. Keep the passage, company, and aspect as explicit fields. | B1 if all systems change together before the seal | An auxiliary target-and-aspect sentence improved BERT ABSA ([Sun et al., 2019](https://aclanthology.org/N19-1035/)). The present input already has explicit fields. The expected gain is small, unless `company_id` is an opaque slug. | USD 0 | Low. Target markers change the model input only. That breaks the identical-input rule, so markers are B2. |
| 7 | **Silver weighting and noise-robust losses** on accepted examples. | B1 | BERT is fairly robust to injected noise. Noise-handling methods “do not always improve its performance, and may even deteriorate it” ([Zhu et al., 2022](https://arxiv.org/abs/2204.09371)). Expect about 0. | USD 0 | Low, but it is probably wasted effort. |
| 8 | **Better silver sources:** a fourth free route, or a stronger free route. | B2 | Weak supervision works well only when the sources are good ([WRENCH](https://arxiv.org/abs/2109.11377)). The same-item errors of LLM judges can leave nine judges with about two effective votes ([Kohli, 2026](https://arxiv.org/abs/2605.29800), a one-author preprint that is not financial). The gain depends on how independent and strong the route is. This is the largest possible gain inside the destination. | USD 0 if free. It uses route quota and schedule time. | Medium. Routes need account evidence and training permission, and the panel is frozen for each stage. |
| 9 | **Use rejected or low-confidence candidates** through self-training or probability weighting, in place of the hard 0.70 filter. | B2 (changes the accepted-silver rule) | “Uncovered data should be used” ([WRENCH](https://arxiv.org/abs/2109.11377)). COSINE self-training on weak labels is “competitive with fully-supervised fine-tuning” on 7 benchmarks ([Yu et al., 2021](https://arxiv.org/abs/2010.07835)). The benchmarks are not financial. Expect a few points if accepted data is thin or skewed. | USD 0–small GPU | Medium. Self-training can confirm the voters' errors. |
| 10 | **Task-adaptive pretraining** (masked-LM on the sealed candidate passages), or domain-adaptive pretraining on clean-core news. | B2. It changes the pinned initial weights. | In news, domain pretraining gave +0.0 on AG News and +1.6 on Hyperpartisan. Task pretraining gave +0.6 and +3.8 ([Gururangan et al., 2020, Table 5](https://arxiv.org/abs/2004.10964)). ModernBERT already saw 2T tokens, so expect less. | Small GPU cost. It uses unlabeled clean-core text only. | Low to medium. It adds an unpinned checkpoint. |
| 11 | **Evidence-span auxiliary loss** from the non-GPT vote spans (rationale distillation). | B2 | Teacher explanations can help students, and the effect depends on the method ([Pruthi et al., 2022](https://arxiv.org/abs/2012.00893)). Distilling step-by-step beat 540B PaLM with a 770M T5, but the student is generative ([Hsieh et al., 2023](https://arxiv.org/abs/2305.02301)). No encoder or financial result. Effect uncertain. | USD 0 | Medium. Voter spans can be wrong. |
| 12 | **Synthetic or counterfactual augmentation** from free routes. | B2 | LLM-annotated lightweight ABSA models came close to their teacher: 49.85 against 51.10 F1 on Rest16 ([Hellwig et al., 2026](https://arxiv.org/abs/2603.01778)). No financial or four-class evidence. Effect uncertain. | USD 0. It uses route quota. | Medium to high. Synthetic text has no clean-core rights record and moves away from real news. |
| 13 | **GPT-derived labels.** | B2 in the ticket. In practice it breaks the destination. | It is probably the strongest gap closer, because the student would copy the comparator. That makes the comparison circular, and it removes the “GPT-independent” claim. | Training-scale GPT calls. The USD 25 GPT allocation covers the blind run only. | Fatal to the claim. Do not use it. |
| 14 | **Larger encoder** (ModernBERT-large, 395M). | B3 | GLUE 90.4 against 88.4 for base ([Warner et al., 2025, Table 1](https://arxiv.org/abs/2412.13663)). This is +2.0 on general tasks. No financial result. | About 2–3 times the training cost. Probably inside USD 35. M3 inference is plausible. | Low technical risk, but it changes the only initialization. |
| 15 | **Different initialization** (for example, a DeBERTa ABSA checkpoint). | B3 | On 1,334 Bloomberg target texts, a fine-tuned DeBERTa ABSA model scored 0.66 macro-F1 ([Muhammad et al., 2025, Table 3](https://aclanthology.org/2025.clicit-1.74.pdf)). It has a 512-token limit. No gain over ModernBERT is shown. | Same as now | Medium. It has a 512-token limit, and the project already rejected it. |
| 16 | **Small generative classifier** (0.6–1.7B decoder). | B3 | Paired models of equal training show that encoders are better at classification. A 400M encoder beat a 1B decoder on MNLI ([Weller et al., 2025, Ettin](https://arxiv.org/abs/2507.11412)). Expect no gain for its size. | More GPU. Tighter on 8 GB M3. | Medium to high. |
| 17 | **Calibrated-decision RL** (typesafe.ai RLCD, or RLCR). | B3 | RLCR improves calibration with “no loss in accuracy”. It does not claim an accuracy gain ([Damani et al., 2025](https://arxiv.org/abs/2507.16806)). No macro-F1 evidence. Expect about 0. | GPU RL. The cost is unknown. | High. It has no published recipe for this class of model. |

## Ceiling and the non-inferiority margin

### What the literature says about the gap

- **Human-labeled compact models against frontier LLMs, target-based financial news.** DeBERTa ABSA, fine-tuned with 5-fold cross-validation, scored 0.66 macro-F1. Zero-shot scores were ChatGPT-4 0.77, ChatGPT-o1 0.80, and DeepSeek-R1 0.81. Five-shot DeepSeek-R1 scored 0.87. Gemma 2 27B scored 0.69 zero-shot ([Muhammad et al., 2025, Table 3](https://aclanthology.org/2025.clicit-1.74.pdf)). The task has three classes and 1,334 texts.
- **The opposite direction with a weaker LLM.** On FinEntity, fine-tuned FinBERT-CRF scored 0.85 macro, and zero-shot GPT-3.5 scored 0.56 ([Tang et al., 2023, Table 3](https://aclanthology.org/2023.emnlp-main.956/)). That task also includes entity extraction.
- **General text classification.** Fine-tuned small models beat zero-shot GPT-4 and Claude Opus. The gain starts at about 200–500 human labels ([Bucher and Martini, 2024](https://arxiv.org/abs/2406.08660)). These are human labels, not silver labels.
- **Mid-size open models against frontier models on financial entity sentiment.** FinEntity F1 was 0.298 for Gemma 2 27B, 0.483 for Qwen 2 72B, 0.523 for GPT-4o, and 0.655 for Claude 3.5 Sonnet ([FLaME, Matlin et al., 2025, Table 2](https://arxiv.org/abs/2506.15846)). These are 2024 models, not the current voters.
- **SEntFiN.** RoBERTa and FinBERT reach about 93% F1 on headlines ([Sinha et al., 2022](https://arxiv.org/abs/2305.12257)). FinABSA reports 87% accuracy on an “arbitrarily extracted” split ([repository](https://github.com/guijinSON/FinABSA/tree/23f7172d246662bff269d3234bc13af0f60fbe11)). No GPT comparison on the same split was found. The headlines are short and have no aspect or `insufficient evidence` class, so these results do not predict this task.
- **FiQA.** The found FiQA sentiment results use MSE on a regression task, so they are not usable here ([FLaME](https://arxiv.org/abs/2506.15846)).

The evidence is thin. No study measures a four-class, supplied-aspect, financial task. No study measures a student trained on silver labels from mid-size open LLMs against a current frontier LLM. The closest financial evidence shows frontier LLMs about 0.10–0.15 macro-F1 above both mid-size open LLMs and human-labeled compact models. The current voters (Mistral Small 4, GLM-4.7-flash, Qwen3.6-27B) are newer than that evidence. Correlated errors limit what three voters can add over the best one ([Kohli, 2026](https://arxiv.org/abs/2605.29800)).

The specialist has one real advantage. Dawid–Skene is anchored to the same person's development labels, so the silver labels can learn that person's conventions. Examples are the narrowest-aspect rule and the `insufficient evidence` class. GPT-5.6-sol receives one zero-shot prompt. This advantage is largest on the `insufficient evidence` and aspect-boundary cases. Those cases are half of the question in a 16-cell balanced set.

### What the Stage 1 test requires

The report passes a source only when the lower limit of the 95% paired event-group bootstrap interval is −0.03 or more. A local simulation (`numpy`, 400 examples, 100 for each class, 320 event groups, GPT accuracy 0.80, 1,000 bootstrap draws, 150 runs for each cell) gave these results:

| True specialist − GPT gap | Pass rate, moderate error correlation | Pass rate, high error correlation |
|---:|---:|---:|
| +0.04 | 0.93 | 1.00 |
| +0.02 | 0.74 | 0.93 |
| 0.00 | 0.40 | 0.59 |
| −0.02 | 0.06 | — |
| −0.03 | 0.06 | 0.01 |
| −0.05 | 0.01 | — |

The interval was 0.05–0.09 wide. This is a simplified model with uniform errors and no real clustering. It shows the shape of the test, not a precise power figure. **In practice, the test requires true parity or better. It does not permit a small real loss.**

### Verdict

- **Chance of a pass:** low. Judgement: about 10–25%. For this chance, the silver ensemble must reach GPT-5.6-sol's accuracy on the human conventions, and the student must keep nearly all of it. The published gap between frontier and mid-size models is larger than the margin. The student effects in the ranked table are each about 0–3 points.
- **The one lever that matters:** silver-label accuracy against the human reference. Inside the rules, act on it through ranks 1–3. These ranks make the student use the anchored posteriors fully and match the blind prior. Outside the rules, only a stronger or more independent free voter (rank 8) moves it.
- **A cheap early warning.** Aggregation already makes out-of-fold calibrated posteriors on the development set. Report their macro-F1 as a diagnostic before GPU or GPT spend. It is a near-upper bound for the student. A stop rule based on it would change the frozen stop rules, so it needs a planning decision before confirmation. As a report-only number, it needs no rule change.

## typesafe.ai “System One / Jev”

**What the post says.** The [post](https://typesafe.ai/blog/introducing-system-one-models-and-jev) (Diogo Almeida, 2026-09-18) presents Jev as a model for fast structured decisions. It uses “Reinforcement Learning for Calibrated Decisions (RLCD)” and a “parallel sampler”. It returns typed values with “calibrated probabilities”. It claims 70–500 ms latency and a large cost advantage over frontier LLMs. It limits choice cardinality to 255 and gives up string generation.

**Why it is weak evidence.**

- The post gives no model size, base model, training data, reward, or recipe. No paper, model card, or weights are linked. Only a Python adapter repository is named. The linked evals page returned HTTP 404 on the retrieval date.
- The eval uses “the average of GPT-6 Astra and Fable 5.1 as the reference answer”. The post also says that this reference “biases answers towards OpenAI and Anthropic's models”. Thus, it measures agreement with other LLMs, not accuracy against human labels. That design cannot show a result better than the reference, and it cannot support a non-inferiority claim against a GPT model.
- The post calls its headline speed and cost gains “on the higher end of real world gains”. It reports no human-labeled task, no confidence interval, and no calibration metric.
- It is vendor marketing for a product.

**What transfers.** Little, and the project already has most of it.

- **Calibrated-probability training.** RLCR shows that a reward from a bounded proper scoring rule, such as the Brier score, gives calibrated and accurate outputs ([Damani et al., 2025](https://arxiv.org/abs/2507.16806)). A classifier with a softmax head gets the same property from cross-entropy, which is also a proper scoring rule. When the targets are the calibrated Dawid–Skene vectors, the student learns calibrated probabilities directly. This is rank 3. RL is a solution for generative models that cannot be trained on a probability target directly. An encoder does not have that problem. The transferable part is: “train on calibrated probabilities with a proper scoring rule”. The present code does not do this yet (see [Code finding](#code-finding-soft-labels-are-dropped)).
- **Soft references from several strong models.** Jev's reference is an average of LLM probabilities. The project's reference for training is a gold-anchored Dawid–Skene posterior over three non-GPT routes. That is the better design, because it is corrected against human development labels.
- **Fixed-choice structured output.** The project already uses a strict four-label schema.

Calibration does not raise macro-F1 by itself. Argmax decisions do not change under temperature scaling ([Guo et al., 2017](https://proceedings.mlr.press/v70/guo17a.html)). Calibration helps rank 1 (prior correction) and the development-set diagnostic. It does not close the gap.

## Limits

- No source measures this exact task. Most effect sizes come from general, English, non-financial benchmarks.
- The ceiling estimate is judgement from indirect evidence and a simplified simulation. The first real number is the out-of-fold ensemble development macro-F1.
- The current voters and GPT-5.6-sol have no published financial aspect results.
- GPU cost estimates are not quotes. The measured USD 5 pilot and the USD 35 projection in `train_specialist` decide the cost.
