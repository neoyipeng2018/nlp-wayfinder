# Weak-supervision label model selection

Date: 2026-09-05

## Decision

Use Crowd-Kit 1.4.2 `DawidSkene` as the label model. Use one fitted model for each passage source. Do not use Snorkel `LabelModel` for this experiment.

The exact base fit is:

```python
from crowdkit.aggregation import DawidSkene

model = DawidSkene(n_iter=100, tol=1e-8)
posteriors = model.fit_predict_proba(votes, true_labels=human_labels)
```

Freeze `crowd-kit==1.4.2` and the complete transitive package lock. Crowd-Kit 1.4.2 was released on 2025-10-13. The release commit is `cad794bb64686fdd9868ce0ab1282ef61b639c7f`. [Crowd-Kit 1.4.2 release](https://github.com/Toloka/crowd-kit/releases/tag/v1.4.2) [release commit](https://github.com/Toloka/crowd-kit/commit/cad794bb64686fdd9868ce0ab1282ef61b639c7f)

## Why this method fits

The experiment has three fixed model voters, four target classes, and 200 human reference labels for each passage source. Crowd-Kit Dawid–Skene learns one 4 by 4 confusion matrix for each voter. It uses the human labels to fix the known task probabilities during each EM iteration. It returns one four-class probability vector for each task. It also exposes the class priors, voter confusion matrices, and loss history for audit. [Crowd-Kit Dawid–Skene documentation and source](https://crowd-kit.readthedocs.io/en/latest/classification/#crowdkit.aggregation.classification.DawidSkene)

Crowd-Kit starts from majority-vote probabilities. Its EM procedure is deterministic for fixed input row order. Its code clips zero confusion values and zero class priors to `1e-10`. This value is the frozen smoothing floor. Do not pass `initial_error`; that input changes initialization and does not add a prior in every EM iteration. [Crowd-Kit 1.4.2 source](https://github.com/Toloka/crowd-kit/blob/v1.4.2/crowdkit/aggregation/classification/dawid_skene.py)

## Comparison

| Method | Result for this experiment |
| --- | --- |
| Crowd-Kit 1.4.2 Dawid–Skene | Select it. It supports multiple classes, missing votes, human reference labels, class-specific voter errors, and full soft posteriors. The project is maintained. |
| Snorkel 0.10.0 `LabelModel` | Do not select it. It supports multiple classes, abstention, and soft posteriors. However, `Y_dev` only sets class balance. It does not use the 200 human labels to fit voter confusion. The current class also states that it assumes conditional independence. Its fit uses random initialization unless a seed is fixed. The latest open-source release is from 2024-02-27. [Snorkel source](https://github.com/snorkel-team/snorkel/blob/v0.10.0/snorkel/labeling/model/label_model.py) [Snorkel release](https://github.com/snorkel-team/snorkel/releases/tag/v0.10.0) |
| cleanlab 2.9.0 CROWDLAB | Do not select it for label production. It is newer and maintained. It needs out-of-sample probabilities from a trained classifier in addition to the voter labels. This adds a fourth signal. Use of ModernBERT for this signal would make the label and training path circular. Its main output is a consensus label and its quality score, not the simple voter confusion audit required here. [cleanlab multi-annotator API](https://docs.cleanlab.ai/stable/cleanlab/multiannotator.html) [CROWDLAB paper](https://cleanlab.github.io/multiannotator-benchmarks/paper.pdf) [cleanlab 2.9.0 release](https://github.com/cleanlab/cleanlab/releases/tag/v2.9.0) |
| FlyingSquid | Do not select it. The method uses triplets and can model stated dependencies. Its public implementation has no commit after 2020. The fixed panel has only one triplet. This removes its main scale and speed benefit. [FlyingSquid paper](https://proceedings.mlr.press/v119/fu20a.html) [FlyingSquid repository](https://github.com/HazyResearch/flyingsquid) |
| GLAD, MACE, and one-coin Dawid–Skene | Do not select them. They use a smaller voter-skill or spam model. They do not keep the full class-specific confusion pattern needed for four financial labels. [Crowd-Kit classification methods](https://crowd-kit.readthedocs.io/en/latest/classification/) |

“Modern” is not sufficient by itself. CROWDLAB is the newest suitable maintained candidate, but its required classifier changes the experiment. The older Dawid–Skene equation is a better fit because the experiment already pays for human reference labels.

## Frozen data and fit procedure

For each passage source:

1. Use exactly three frozen non-GPT routes.
2. Encode `positive`, `neutral`, `negative`, and `insufficient_evidence` as the four classes.
3. Encode a vendor abstention by omitting that route’s row for that task. Do not make abstention a fifth class.
4. Keep all 200 human development tasks and all silver-candidate tasks in one Crowd-Kit long table with `task`, `worker`, and `label` columns.
5. Pass only the 200 human labels in `true_labels`. Crowd-Kit fixes those task posteriors during EM.
6. Fit `DawidSkene(n_iter=100, tol=1e-8)` once after all three vote files are complete.
7. Fail the fit if it reaches 100 iterations without a final loss change below `1e-8`, if any output is not finite, or if repeated fits on the same sorted input are not byte-identical after canonical serialization.
8. Keep the returned four-class posterior for each accepted silver item. Do not keep only the winning class.

Sort tasks, routes, and class columns before fit and serialization. Save the raw vote files, human-label file, their SHA-256 hashes, the package lock, the code commit, `priors_`, `errors_`, `loss_history_`, the raw posteriors, and the calibrated posteriors.

## Calibration

Use fixed stratified five-fold cross-validation on the 200 human tasks. Use seed `20260905`. For each fold, pass the other four folds as `true_labels`; leave the held-out fold unclamped. Collect the held-out four-class posteriors.

Fit one scalar temperature `T` to these 200 out-of-fold posteriors by minimum multiclass negative log likelihood. Use the bounded interval `[0.25, 4.0]` and tolerance `1e-8`. Use `T=1` if the fitted value does not improve out-of-fold log loss by more than `1e-8`. Apply the frozen temperature to the final Dawid–Skene logits. Temperature scaling changes confidence but does not change the class order. [Original temperature-scaling paper](https://proceedings.mlr.press/v70/guo17a.html)

Report out-of-fold macro F1, multiclass log loss, multiclass Brier score, expected calibration error with ten fixed equal-width bins, and accepted coverage. Also report the same measures for unweighted majority vote and Snorkel 0.10.0 with seed `20260905`. This comparison is an audit. It does not let the code select a different estimator without a new decision.

Two hundred human labels give about 50 labels for each class only when the class counts are balanced. If any human class has fewer than 25 examples, stop that source. Add human labels or change the class design before fit. Twenty-five examples give a worst-case standard error of about 0.10 for one confusion proportion. Fifty examples give about 0.071. These values are diagnostics, not accuracy guarantees.

## Dependency rule

Do not fit voter-dependency parameters. Three voters and 200 human labels are too few for stable four-class pairwise tables.

Before fit, confirm that the routes do not use the same base checkpoint, fine-tune, or provider-side deployment. After the human votes are complete, report pairwise residual agreement within each human class. If the review finds a material shared dependency, replace one route before silver collection. Do not count two dependent routes as two votes.

This rule makes conditional independence a checked design condition. It does not claim that the voters are independent.

## Acceptance and tie rules

Accept a silver item only when all these conditions are true:

- At least two routes give a valid vote.
- At least two routes vote for the top posterior class.
- The largest calibrated posterior is at least `0.70`.
- The difference between the two largest calibrated posteriors is greater than `1e-12`.
- All schema, source-rights, and passage checks pass.

Reject the item in all other cases. In particular, reject all-abstain items, one-vote items, three-way disagreements, probability ties within `1e-12`, and results below `0.70`. Do not use route order, class order, random choice, or a later human decision to break a tie.

## Limits

Dawid–Skene assumes conditional independence after the true class is known. The three-voter panel cannot support a useful dependency-rich model. The temperature step can correct overall confidence, but it cannot remove a systematic shared error. The route-independence gate and conservative acceptance rule control this risk.

No model call, account creation, or payment was required for this research.
