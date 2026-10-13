# AnyJev's levels of calibration, and which apply to the Signal specialist

**Retrieval date:** 2026-10-13
**Scope:** [#143 "Survey AnyJev's levels of calibration"](https://github.com/neoyipeng2018/nlp-wayfinder/issues/143). Primary sources only: the AnyJev repository at commit `b03158e` (2026-10-12, release 0.3.0), the tag `v0.2.0` in the same repository, and the AnyJev Technical Report ([arXiv:2610.00831v1](https://arxiv.org/abs/2610.00831), 2026-09-30). No passage text or label data appears in this note.

## Answer

AnyJev has four levels across its history: `raw`, `L0`, `L1`, and `L2`. Only `raw` and `L0` exist in the current release. Release 0.3.0 removed `L1` and `L2`. They remain at tag `v0.2.0` ([CHANGELOG 0.3.0](https://github.com/nokia-applied-research/AnyJev/blob/b03158e9ba18e84c01054aaa393481925088db07/CHANGELOG.md)). The technical report also describes a label-free early-exit variant, "L2-mono".

All of these levels assume one thing: the probabilities come from a causal LM's next-token distribution over option-label tokens in a prompt. Our specialist does not work that way. It is Qwen3-8B with QLoRA and a sequence-classification head, so it outputs a 3-way softmax that has no option list and no label tokens (`train5.py` writes `logits.softmax(-1)` per example). As a result:

- **`L0` permutation (rotations): does not apply.** Our head has no option order to rotate.
- **`L0` label prior (batch or content-free): technically applies, but it is not recommended.** It would replace our label-informed prior shift with a label-free one that assumes a roughly flat label marginal. AnyJev's own measurements show that this assumption hurts accuracy on skewed marginals. "No signal" dominates our gold data.
- **`L1` temperature scaling: applies, and it is cheap.** It changes probabilities, not the argmax. Under our threshold rule, it can change a few labels only after `t` is re-tuned. It is optional for the parity call and useful only if we later need calibrated probabilities.
- **`L2` closed-form head on hidden states: not a calibration of our model.** It is a different, label-trained classifier. It would need hidden states that we do not save.

**Recommendation for the gold-v5 parity call:** add no AnyJev level. Macro-F1 depends only on labels. Our rule already contains the two label-relevant knobs that AnyJev offers: the per-aspect prior shift and the dev-tuned `t`. If we want calibrated probabilities for later use, such as ECE, abstention, or signal scoring, fit one temperature `T` on pooled gold-v3 + gold-v4 dev. Re-tune `t` after fitting `T`. Freeze both values in `final-v5-t.json` before the gold-v5 look. Report ECE beside the score; it does not decide the call.

## The levels

### `raw`

- **What it is:** one prompt, with the softmax over the next-token logits restricted to the option-label tokens. It applies no correction ([docs/levels.md](https://github.com/nokia-applied-research/AnyJev/blob/b03158e9ba18e84c01054aaa393481925088db07/docs/levels.md)). The v0.2.0 docs say: "`raw` exists so the bench can show the gap. Do not ship it." ([v0.2.0 docs/levels.md](https://github.com/nokia-applied-research/AnyJev/blob/v0.2.0/docs/levels.md))
- **Our analogue:** the specialist's softmax output.

### `L0`: debiased, with zero labels

L0 has two parts that can be switched separately ([docs/levels.md](https://github.com/nokia-applied-research/AnyJev/blob/b03158e9ba18e84c01054aaa393481925088db07/docs/levels.md); report §4.1–4.2).

**(a) Cyclic-shift marginalisation, which fixes position bias.**

- **Method:** read the K options in all K rotations. Average log-probabilities per option, then renormalise (`anyjev/calibrate/permute.py`, `marginalize(combine="logmean")`). If the logit of option *i* at position *j* is `c_i + b_j`, this recovers `softmax(c)` exactly (report Eq. 3).
- **Data needed:** none. It costs K prefills per decision. The rotation budget (`calibrate/stopping.py`) cuts that with a stopping threshold, which is certified on unlabelled states against the full-K answer with a Clopper–Pearson bound.
- **Effect:** it changes labels. For example, the report gives an order-flip rate of 0.33 → 0.14 on banking20, plus accuracy gains on 11 of 11 models.
- **Fit to us: not applicable.** A seq-cls head has no prompt option list, so there is no position bias to average out.

**(b) Label-prior division, which fixes label prior bias.**

- **Method:** `p ∝ p̃ / q̂^α`, with α = 0.75 by default (report Eq. 2; `calibrate/contextual.py`).
- **Two estimators for `q̂`:**
  - **Batch prior** (Zhou et al., ICLR 2024). This is the default. `q̂` is the running mean predicted distribution over the inputs scored so far, and it is used from 8 inputs onward.
  - **Content-free prior** (Zhao et al., ICML 2021), which is opt-in. `q̂` is the output on the inputs "N/A", "", and "[MASK]".
- **Data needed:** unlabelled inputs only. The authors say α was chosen against gold labels on 230 (model, question) pairs (report §4.1).
- **Effect:** it changes labels.
- **Caveat stated by the authors:** the method "assumes the label marginal of the inputs is not extreme, and it lowers accuracy where that assumption fails" (report §4.1). Their own study found −0.025 mean gain for the batch prior alone on typed `choice` questions. It lost 0.20–0.44 accuracy on questions with majority-label shares of 0.74–0.89 ([v0.2.0 docs/when_l0_helps.md](https://github.com/nokia-applied-research/AnyJev/blob/v0.2.0/docs/when_l0_helps.md)). On the 46,320-item BEV test, adding the batch prior lowered accuracy from 68.01% to 65.01% on Qwen3.5-9B (report §7.3).
- **Fit to us: applicable in form, but worse than what we already do.** `v4.predict` already multiplies by `TARGET_PRIOR / TRAIN_PRIOR` per aspect. That is the prior shift from the clean-v3 training marginal to the gold-v3 marginal, and it uses labelled marginals. AnyJev's batch prior would divide by the model's mean prediction on the scoring batch. That pushes predictions toward a flat 1/3 marginal, which is the failure case the authors document for a dominant "No signal" class. It would also make predictions depend on batch composition, unless `q̂` is frozen from dev.
- **Cost:** one mean over N×3 numbers. It is negligible.

**What L0 does not do:** "it does not make the model's own uncertainty calibrated … That needs labels" ([v0.2.0 docs/levels.md](https://github.com/nokia-applied-research/AnyJev/blob/v0.2.0/docs/levels.md)).

### `L1`: calibrated on labels (removed in 0.3.0, present at `v0.2.0`)

- **Method:** temperature scaling (Guo et al., 2017). A single `T` is fitted by golden-section search on log T to minimise NLL on 100–500 labelled examples of the same question. It is applied on top of L0 ([v0.2.0 `anyjev/calibrate/posthoc.py`](https://github.com/nokia-applied-research/AnyJev/blob/v0.2.0/anyjev/calibrate/posthoc.py), `TemperatureScaler`; report §4.3). The L0 prior is frozen into the artifact, so the result depends only on the calibration set.
- **What it fixes:** over-confidence or under-confidence, measured by ECE and NLL. In the report, ECE went from 0.223 to 0.088 on banking20, and ECE fell for 7 of 8 models. The authors also note that "one global temperature cannot correct a model whose confidence is wrong in different directions on different items" (report §6–7.2).
- **Labels:** "It reshapes confidence; it does not change the ranking" (v0.2.0 docs). A positive `T` leaves the argmax unchanged (report §4.3).
- **Planned but never shipped:** Dirichlet calibration, histogram binning, and split-conformal abstention ("Planned for L1", v0.2.0 docs).
- **Fit to us: applicable, and a direct fit.** It needs only our per-passage 3-class probabilities and the pooled gold-v3 + gold-v4 dev labels. It touches neither gold-v5 nor the model.
  - **Interaction with our rule:** `predict` outputs "No signal" when `ns = q₂ / Σq ≥ t`, and otherwise the argmax of +/−. Scaling `log q` by `1/T` never changes the +/− choice. For each passage, `ns` moves monotonically in `T`. The ordering of `ns` across passages can still shift, because it also depends on the split between +/−. So with `t` re-tuned after `T`, a small number of labels can change. With `t` held fixed, `T` acts like a shift of `t`. Do not expect a macro-F1 gain; any change is second-order.
  - **Where `T` goes matters.** Apply `T` to the raw head log-probabilities before the prior shift, or after it. Fit and freeze `T` in the same position you will use it.
  - **Leakage rule:** `T` is a second knob fitted on dev, so the existing rule applies to it. Fit `T`, then `t`, on pooled dev only. Write both to the frozen file before the single gold-v5 look.
- **Cost:** the fit is about 60 NLL evaluations over N × 3 floats, which takes milliseconds on CPU with numpy. There is no GPU and no re-inference.

### `L2`: a closed-form head on the hidden state (removed in 0.3.0, present at `v0.2.0`)

- **Method:** run one forward of the labelled states on the frozen LM. Then solve a shrunk-LDA, ridge, diff-means, or reduced-rank head on the last-position hidden state, at about two-thirds of the depth. Layer, head kind, and temperature are chosen by out-of-fold NLL ([v0.2.0 `anyjev/heads.py`](https://github.com/nokia-applied-research/AnyJev/blob/v0.2.0/anyjev/heads.py); v0.2.0 docs).
- **Data needed:** at least max(8, 2K) labels, and 100–300 in practice.
- **Effect:** it changes labels, because it is a new classifier.
- **Reported result:** Qwen3-8B reached 0.771 accuracy at 67% depth with 300 labels per question, against 0.648 for L1. It ran at 0.68× the time of a full forward (CHANGELOG 0.1.0).
- **Fit to us: not a calibration of our specialist.** It is an alternative to QLoRA fine-tuning, a linear probe on frozen-LM hidden states. It would need hidden-state extraction, which means re-running inference on Kaggle, and we currently save only softmax outputs. At most, it could serve as a cheap baseline in a future screen. It is out of scope for the parity call.

### "L2-mono" (report only, label-free)

- **Method:** the forward is truncated at block *b*. An affine map, fitted on unlabelled inputs, translates block *b* into the final-layer space for the original LM head. *b* is chosen by agreement with the full-depth answers (report Fig. 1c, §7.3).
- **Purpose:** this is a speed technique, not calibration. On BEV it cost 0.61 points.
- **Fit to us:** none. It relies on the LM head's label tokens, and our seq-cls head has none. The current README lists label-free early exit as an unfinished roadmap item.

### Also not calibration

`Tacit` (self-distilled checkpoints) and its `adaptive` chain-of-thought escalation are model and routing choices, not calibration levels ([README](https://github.com/nokia-applied-research/AnyJev/blob/b03158e9ba18e84c01054aaa393481925088db07/README.md)). They do not apply here.

## Summary table

| level | fixes | data needed | changes labels? | applies to our seq-cls specialist? | cost on our outputs |
|---|---|---|---|---|---|
| `raw` | nothing | none | — | is our baseline output | — |
| `L0` rotations | position bias of the option list | none (K prefills) | yes | **no**: there is no option list | n/a |
| `L0` batch / content-free prior | label-prior bias | unlabelled inputs (α set on labels by authors) | yes | in form only; **not recommended**. Our label-based prior shift already does this, and the flat-marginal assumption fails for a dominant "No signal" class | negligible |
| `L1` temperature | over/under-confidence (ECE, NLL) | 100–500 labels: pooled dev | argmax: no; under our `t` rule only after re-tuning `t`, marginally | **yes**, optional; freeze `T` and `t` before gold-v5 | milliseconds on CPU |
| `L2` hidden-state head | replaces readout with a probe | 100–300 labels plus hidden states | yes | **no**: it is a different classifier and needs re-inference | a Kaggle re-run to extract states |
| L2-mono | depth / latency | unlabelled | yes | no | n/a |

## Licence and usability

- **Licence:** Apache-2.0, for the repository and the `anyjev` PyPI package ([LICENSE](https://github.com/nokia-applied-research/AnyJev/blob/b03158e9ba18e84c01054aaa393481925088db07/LICENSE); `pyproject.toml`). The Tacit models carry their base models' Apache-2.0 licence, and datasets keep their own licences.
- **As a library for us: reference only.**
  - `anyjev` 0.3.0 ships only `raw` and `L0`. Its `Decider` needs a causal-LM backend (HF, vLLM, SGLang, or llama.cpp) that it prompts itself, so it cannot use a seq-cls head's outputs.
  - The pure-numpy helpers in `anyjev.calibrate` (`batch_prior`, `apply_contextual`, `cp_upper`) could be imported. However, they are a few lines each, and we would not use the prior helpers anyway.
  - `TemperatureScaler` exists only in `anyjev==0.2.0`, which the authors say to pin for L1 and L2. Pinning a superseded pre-alpha release for a 20-line golden-section fit is not worth the dependency. If we adopt `T`, write the fit in the scorer, or use `scipy.optimize.minimize_scalar` if scipy is already installed.

## Sources

- AnyJev repository, `main` at `b03158e9ba18e84c01054aaa393481925088db07`: `README.md`, `docs/levels.md`, `docs/limitations.md`, `CHANGELOG.md`, `anyjev/calibrate/{contextual,permute,stopping}.py`, `pyproject.toml`, `LICENSE`.
- AnyJev tag `v0.2.0`: `docs/levels.md`, `docs/when_l0_helps.md`, `anyjev/calibrate/posthoc.py`, `anyjev/heads.py`.
- Zhang et al., *AnyJev Technical Report*, arXiv:2610.00831v1 (2026-09-30): Fig. 1, §4.1–4.3, §7.1–7.3.
- Our side, local and not public: `.scratch/quick-loop/final5.py` (shared `t` tuned on pooled dev, frozen to `final-v5-t.json`), `.scratch/quick-loop/v4.py` (`predict`: prior shift and the "No signal" threshold rule), and `.scratch/quick-loop/train5.py` (writes per-example softmax probabilities).
