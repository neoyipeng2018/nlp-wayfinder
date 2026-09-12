# Data and evaluation precedents for a sub-$100 financial aspect-sentiment experiment

Research date: 2026-08-24

## Decision

The proposed experiment is defensible only if it treats the public datasets as **training and diagnostic material**, not as the blind test. Public data can seed company/equity news and social-media supervision, but no located corpus simultaneously covers the five required sources, broad financial-target families, a supplied target and aspect, market-impact polarity, and a separate `insufficient evidence` label. The missing coverage must therefore come from newly sampled passages and a frozen annotation policy.

Use the largest planned blind set, **500 document/event-grouped examples**, and phrase the result narrowly: agreement with one preregistered operational labeling policy. With 100 examples per source, source results are useful guardrails but are too imprecise for tight source-by-source non-inferiority claims. A pooled 5-percentage-point non-inferiority margin is also likely underpowered at 500 unless the two systems disagree unusually rarely; a 7.5-point margin is more plausible, but the margin must be justified by practical value rather than chosen to make the test pass.

The reported literature leader closest to the exact task is not a defensible reproducible comparator because no code or checkpoint is linked. The experiment should consequently distinguish three things: a reproducible generic financial-sentiment control, a reproducible target/aspect-conditioned specialist built under the experiment's own data rules, and literature-only results that are not directly comparable.

## Dataset and rights audit

| Resource | What it supplies | License/access evidence | Decision for this experiment |
|---|---|---|---|
| **FiQA 2018 Task 1** | 1,173 English financial headlines/posts in the published follow-on paper; target, a two-level aspect, and continuous sentiment in `[-1,1]`. Its four top-level aspects are Corporate, Stock, Economy, and Market, with 27 finer aspects. | The [official challenge page](https://sites.google.com/view/fiqa/home) says train and test data are available only for non-commercial use. | Closest public schema precedent and a useful non-commercial auxiliary set. It covers news/social, is heavily company/stock oriented, and has no separate insufficient-evidence class. Do not use its public test as the experiment's blind test. |
| **SemEval-2017 Task 5** | Company/stock-targeted sentiment in financial microblogs and news; continuous score in `[-1,1]`. The task had 32 participating teams. | The [official task paper](https://aclanthology.org/S17-2089/) documents task and data construction, but does not establish a reusable data license. The ACL paper's license is not a license to the underlying posts/news. | Historical metric/task precedent only unless the distributed corpus's terms are separately verified. No aspect or insufficient-evidence label. |
| **Financial PhraseBank** | 4,840 financial-news sentences, 16 finance-aware annotators, 5--8 judgments per sentence, and positive/neutral/negative investor-impact labels at four nested agreement thresholds. | The maintainer/author's [dataset card](https://huggingface.co/datasets/takala/financial_phrasebank/blob/refs%2Fpr%2F10/README.md) states CC BY-NC-SA 3.0; the [original paper](https://arxiv.org/abs/1307.5336) documents annotation. | Strong label-semantics precedent for expected stock-price impact. Auxiliary company-news data only: no supplied target/aspect or insufficient-evidence class. The agreement subsets are nested and must never be put in different splits. Commercial reuse requires separate rights review. |
| **SEntFiN 1.0** | 10,753 Indian business-news headlines and 14,404 entity-sentiment annotations; 2,847 headlines contain multiple entities and 1,233 contain conflicting entity sentiments. Three management/MBA annotators labeled from an investor viewpoint. | The [paper](https://arxiv.org/html/2305.12257v1) documents the annotation and counts; the [official repository](https://github.com/pyRis/SEntFiN) applies MIT to the repository/data files. Rights in underlying news headlines remain a separate upstream-content question. | Valuable target-conditional news supervision. Its `neutral` definition includes both no sentiment and targets for which financial sentiment is inapplicable, so it must not be mechanically mapped to this project's distinct neutral and insufficient-evidence classes. Split by original headline, not expanded entity instance. |
| **FinEntity** | 979 Reuters paragraphs with 2,131 company, organization, and asset-class entities jointly tagged for span and positive/neutral/negative sentiment; 12 finance/business students, three judgments per example, and a high-agreement retained subset. | The [EMNLP paper](https://aclanthology.org/2023.emnlp-main.956/) documents construction and results; the [official repository](https://github.com/yixuantt/FinEntity) states ODC-By. | Useful open entity-level news auxiliary and target-family extension. It is an entity extraction plus sentiment task, not supplied-target/aspect classification; it has no insufficient-evidence label and no non-news coverage. |
| **FinLin** | 3,811 automotive-company texts from StockTwits, news, company reports, and investor reports, with target, continuous sentiment, relevance, individual labels, and evidence spans. | The [paper](https://arxiv.org/abs/2003.04073) documents 3,204 StockTwits posts, 394 news items, 127 company reports, and 86 investor reports. The [official repository](https://github.com/TDaudert/FinLin) states CC BY-NC-SA 4.0 and says the corpus is obtained from the author. | Best located precedent for keeping target relevance separate from polarity and for cross-source annotation difficulty. It is narrow (automotive companies and one 2018 period), has no aspect labels, and does not substitute for earnings-call or regulatory-filing data. |
| **TweetFinSent** | Stock-specific social posts labeled by expected/realized return direction. | The [ACL paper](https://aclanthology.org/2022.finnlp-1.5/) and [official repository](https://github.com/jpmcair/tweetfinsent) expose the resource, but no explicit data license was located in the repository as of the research date. | Semantically useful social precedent, but exclude from training until permission and platform/content terms are resolved. Publication or downloadability alone is not reuse permission. |
| **Aiera transcript sentiment** | 700 pre-segmented earnings-call extracts with positive/neutral/negative labels. | The [official dataset repository](https://huggingface.co/datasets/Aiera/aiera-transcript-sentiment/tree/c3101579577ad81a35dfcc0ff0c5dd1f90c18582) declares MIT. The visible card does not document annotators, instructions, agreement, transcript provenance, or target/aspect construction. | Audit-first auxiliary data, not reference-quality evidence. It partially fills the earnings-call source gap but not the target/aspect/schema gap. |
| **SubjECTive-QA** | Earnings-call question-answer pairs annotated for assertiveness, caution, optimism, specificity, clarity, and relevance. | The [paper](https://arxiv.org/abs/2410.20651) documents the resource; the [official gated dataset](https://huggingface.co/datasets/gtfintechlab/SubjECTive-QA/tree/main) states CC BY 4.0. | Potential source-text or auxiliary tone/relevance material, not a direct sentiment-label mapping. Do not collapse `optimistic` into market-impact positive. |
| **SEC EDGAR** | Fresh primary-source regulatory filings and official metadata/API access. | The SEC documents [bulk/API access and fair-access rules](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) and provides [data.sec.gov](https://data.sec.gov/). | Preferred source stream for fresh filing passages. Public accessibility does not automatically settle redistribution rights in issuer-authored text; retain URLs, accession numbers, timestamps, and a content-rights review for any released corpus. |

License decisions should be recorded at the exact revision acquired. “Can be used for a non-commercial experiment,” “can be redistributed,” and “can support commercially deployed model weights” are different questions. Repository licenses also may not grant rights to upstream news, social-post, transcript, or report text.

## What the public record covers—and does not

| Required passage source | Defensible public precedent | Remaining gap |
|---|---|---|
| Financial news | FiQA, PhraseBank, SEntFiN, FinEntity, FinLin | Exact four-label target-plus-aspect schema and broad non-company targets |
| Financial social media | FiQA, FinLin; TweetFinSent after a rights decision | Insufficient-evidence separation, shared aspects, and targets beyond stocks/companies |
| Company announcements | FinLin has a small company-report slice, but no exact announcement corpus was located | Fresh issuer investor-relations sampling and manual/silver labeling |
| Earnings calls | Aiera sentiment; SubjECTive-QA tone/relevance | Documented target/aspect market-impact annotation with provenance and agreement |
| Regulatory filings | EDGAR supplies primary text, not labels | All required labels/aspects; passage sampling that avoids boilerplate and duplicate amendments |

Company/equity targets dominate every directly relevant corpus. FinEntity adds organizations and asset classes, while FiQA nominally includes Economy and Market aspects, but neither provides balanced evidence for governments, macro indicators, institutions, currencies, commodities, bonds, or other instruments. The proposed broad target scope therefore cannot be validated by simply pooling existing datasets.

FiQA's 27 fine aspects are a useful seed vocabulary, not a ready shared ontology. They mix company events (for example appointments, dividends, M&A, and legal issues), stock-market behavior (price action and technical analysis), and macro/market concepts. A shared 8--12-aspect ontology should instead define applicability by target family and make the distinction explicit:

- `neutral`: the passage contains relevant evidence whose expected market impact is genuinely balanced or approximately zero;
- `insufficient evidence`: the target/aspect relation is absent, inapplicable, too ambiguous, or unsupported by the bounded passage.

That distinction cannot be learned safely by relabeling the `neutral` class in SEntFiN, PhraseBank, FinEntity, Aiera, or similar three-class corpora. Those examples need a fresh rule-based filter, human review, or must remain auxiliary-only.

## Reproducible specialist baseline

The closest published exact-task system is Du et al.'s target/aspect-conditioned, knowledge-enabled RoBERTa. On FiQA it reports MSE `0.0490` and R-squared `0.711`, using 10-fold cross-validation because the official hidden gold test was unavailable; it also reports two seeded runs. See the authors' [accepted paper](https://w.sentic.net/targeted-aspect-based-financial-sentiment-analysis.pdf). Those numbers are not directly comparable to four-way classification on a fresh five-source blind set, and the paper links no implementation or checkpoint; no author artifact was located during this review.

Use this baseline ladder instead:

1. **Frozen generic control:** [ProsusAI FinBERT](https://github.com/ProsusAI/finBERT), whose code is Apache-2.0 and whose [published checkpoint](https://huggingface.co/ProsusAI/finbert) predicts generic three-way financial sentiment. It is intentionally not an exact target/aspect model.
2. **Exact reproducible specialist:** an open encoder conditioned on `(passage, target, aspect)` and trained only on the declared portfolio of gold, silver, and permitted auxiliary data. Freeze repository revision, data manifest and licenses, preprocessing, label mapping, seeds, configuration, checkpoint hash, and inference code before the blind run.
3. **Literature-only context:** report Du et al.'s result, FinEntity's specialist results, and public benchmark scores only as historical context, with their different task, split, and metric made visible.

The phrase “strongest reproducible specialist” should mean the strongest system that a third party can actually rerun on this experiment's frozen inputs—not the highest incompatible public-benchmark number. If multiple specialist candidates are tuned, select among them on a development set before blind labels are opened and count all training/inference spend in the budget.

## Leakage-resistant data protocol

The unit of splitting and resampling must be the **original document/event**, never an expanded `(passage, target, aspect)` row. Apply these controls before any labels reach a teacher or candidate model:

1. Assign every passage a source URL or accession, publication timestamp, publisher/issuer, target identifiers, document hash, and event/document group.
2. Keep every passage window, target, aspect, amendment, transcript segment, and label derived from the same document/event in one split. Keep syndicated and near-duplicate news in the same group even across publishers.
3. Prefer a temporal blind holdout made of fresh documents after training-data collection. Public benchmark test sets are diagnostic only because modern models may have seen them.
4. Deduplicate exact normalized text and review near duplicates across train, development, and blind data. Check public-dataset mirrors and the nested PhraseBank agreement subsets explicitly.
5. Freeze the blind inputs before annotation. No GPT-5.6-sol/OmniRoute teacher label, rationale, adjudication, prompt selection, or model selection may use the blind labels. Preserve the planned no-teacher ablation.
6. Give every evaluated model the same bounded passage, target, aspect, output schema, and retry/parser policy. Freeze model IDs/revisions, prompts, decoding, and failure handling.
7. Open the blind labels once, after ontology, annotation manual, hypotheses, primary metric, non-inferiority margin, slice guardrails, checkpoints, prompts, and cost accounting are signed off.

These controls are more important than reproducing any public random split. In particular, expanding a multi-entity headline or a multi-aspect passage into rows and then randomly splitting rows can leak nearly identical inputs between train and test.

## What 300--500 blind examples can establish

### Pooled non-inferiority

Predeclare the paired difference as `Delta = specialist metric - GPT-5.6-sol metric` and an unacceptable loss `delta > 0`. Declare non-inferiority only when the one-sided 97.5% lower confidence bound for `Delta` is greater than `-delta`. The [FDA non-inferiority guidance](https://www.fda.gov/media/78504/download) is not an NLP standard, but it provides a rigorous general precedent for justifying the margin before seeing outcomes and testing with a confidence bound. For paired NLP systems, [Dror et al.](https://aclanthology.org/P18-1128/) recommend paired resampling/randomization rather than treating system scores as independent.

For macro-F1 or another nonlinear pooled metric, use at least 10,000 **source-stratified paired cluster-bootstrap** replicates, resampling document/event groups and recomputing both systems' scores and their difference each time. Report the point difference, two-sided 95% interval, and one-sided 97.5% lower bound. A matched-accuracy sensitivity analysis can use an exact paired interval consistent with the matched binary methods reviewed by [Yang et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC9447366/).

An illustrative normal approximation for paired accuracy shows the sample-size limit. If the systems disagree on fraction `r` of examples, 80% power at one-sided alpha `0.025` is approximately

`n = (1.96 + 0.842)^2 * r / delta^2`.

With `r = 0.20` and a 5-point margin, this is about **628 examples**. At the same assumptions, power is approximately 49% at `n=300` and 71% at `n=500`. With a 7.5-point margin and `r=0.30`, the approximation requires about 419 examples and gives roughly 87% power at `n=500`. These are planning illustrations, not guarantees: macro-F1, clustered data, source imbalance, and a rare insufficient-evidence class can make precision worse. Estimate the paired confusion/discordance structure on a separate pilot and simulate the exact frozen analysis before preregistration.

This implies:

- choose `n=500`, balanced at roughly 100 examples per source;
- do not claim a tight 5-point margin is assured under this cap;
- justify the margin by downstream acceptability, not observed results or desired power;
- if a practically acceptable margin is at most 5 points, enlarge the blind set or accept that the study may be inconclusive.

### Per-source guardrails

At 300--500 total examples, each source has only 60--100 examples. At 80% accuracy, the ordinary two-sided 95% binomial half-width is approximately 10.1 points for 60 examples and 7.8 points for 100. Paired differences can be tighter, but only when systems make highly correlated errors. Per-source results should therefore be preregistered **catastrophic-regression guardrails**, not five separate tight non-inferiority claims. Report each paired point difference and interval; predeclare an absolute floor or maximum tolerable drop based on product risk, and avoid interpreting a noisy slice pass as parity.

### Single-annotator claim boundary

A one-person reference set is not a universal gold standard and cannot estimate inter-annotator reliability. It can support a narrower statement: system agreement with a documented operational policy administered by that annotator.

Keep the annotator blind to system/teacher outputs, randomize order, hide repeats, and preserve the first and repeat decisions before any reconciliation. Relabeling 15--20% after a washout yields 45--100 repeated judgments. If observed self-agreement is 90%, an approximate 95% half-width ranges from 8.8 points at 45 repeats to 5.9 points at 100. Report raw agreement with a Wilson interval, the repeated-label confusion matrix, and Cohen's kappa, while acknowledging prevalence sensitivity. The historical difficulty is real: FinLin reports overall sentiment Fleiss' kappa of `0.5610` across its expert annotators, with lower source-specific values for news and reports in the [original study](https://arxiv.org/abs/2003.04073).

The annotation manual should require a short evidence span and confidence/ambiguity flag for every decision. Disagreements between first and repeat judgments should remain auditable, with any final reconciliation performed without model outputs. Phrase conclusions as performance against the frozen reference policy, not “ground truth human sentiment.”

## Build/no-build gates

Proceed with the experiment only if all of the following are true before blind annotation:

- rights and permitted uses are recorded per data revision; no unlicensed TweetFinSent/SemEval material enters training;
- the ontology gives examples and counterexamples for every target-family/aspect pairing and sharply separates neutral from insufficient evidence;
- all five source streams and broad target families are represented in the fresh blind sampling frame, with document/event grouping metadata;
- the exact reproducible specialist, frozen GPT comparator, prompts, parsing, no-teacher ablation, primary metric, margin, source guardrails, and cost ledger are frozen;
- a pilot-based clustered simulation shows the chosen sample size and margin can answer a decision the team actually cares about;
- claims are limited to the five-source sampling frame and the single-annotator policy.

Under those conditions, a sub-$100 study can credibly test **narrow pooled parity/non-inferiority to a frozen GPT-5.6-sol configuration**. It cannot establish general financial-language-model superiority, human-consensus validity, or reliable parity for each source and every target family from 300--500 examples.
