# Choose the data portfolio and split policy

GitHub: https://github.com/neoyipeng2018/nlp-wayfinder/issues/7

Type: grilling
Status: closed
Blocked by: 01, 05

## Question

Which licensed datasets and newly collected passages will supply training, development, and the blind reference set; how will examples be allocated across sources, target families, aspects, and family-specific classes; and which entity, event, time, deduplication, and contamination controls will keep development information out of the final comparison?

## Answer

Use a two-lane data portfolio. The main experiment can use the research-only lane. Keep a separate clean-core checkpoint when the available source rights permit it. A license problem does not stop the research experiment. It limits text release, model release, and commercial claims. Do not use a source when its terms clearly prohibit the planned collection or model use.

### Source roster

Use FiQA, Financial PhraseBank, and FinLin as research-only auxiliary data. SEntFiN, FinEntity, Aiera Transcript Sentiment, and SubjECTive-QA can enter the research-only lane after an access and provenance check. Keep SemEval-2017 Task 5, TweetFinSent, and FNSPID out because they add no necessary coverage and have unresolved terms.

Do not convert old labels directly to the new schema. Use the passages as auxiliary text. Apply the family-specific target–aspect labeling policy again when an example enters this experiment.

Use these fresh passage streams:

- Financial news: use GDELT to find current publisher pages. Keep restricted publisher text private.
- Company announcements: use issuer investor-relations releases.
- Earnings calls: use issuer-hosted transcripts or project transcripts from issuer-hosted audio.
- Regulatory filings: use SEC EDGAR filings.
- Financial social media: use public Bluesky posts that discuss the supplied company or macro indicator.

Do not use Guardian developer content, Reddit API content, unauthorized Stocktwits collection, or X content. Stack Exchange finance posts can be auxiliary material, but they cannot replace financial social media.

For restricted passages, release only a manifest with the source identifier, URL, time, revision, content hash, and labels. Release full text only when its terms permit release. Do not describe a restricted checkpoint as commercially reusable.

### Training and development

The accepted silver training pool has a minimum of 4,000 examples and a stretch limit of 8,000 examples. No passage source supplies less than 15%. Macro-indicator targets supply at least 25%. Every applicable family–aspect pair must meet a fixed floor. The budget and teacher-panel decisions must freeze the final floor before collection starts. A candidate that receives an abstention does not count as an accepted silver example.

The development set starts with 160 fresh human-labeled examples. Use 32 examples per source and approximately 70% company targets and 30% macro-indicator targets. Add one batch of 40 examples when teacher ranks, calibration, abstention thresholds, or important slice errors are unstable. Stop at 240 examples. The development set never enters specialist-model training.

### Blind reference set

Use 500 fresh examples with this fixed target matrix:

| Passage source | Company | Macro indicator | Total |
|---|---:|---:|---:|
| Financial news | 40 | 60 | 100 |
| Company announcements | 90 | 10 | 100 |
| Earnings calls | 85 | 15 | 100 |
| Regulatory filings | 85 | 15 | 100 |
| Financial social media | 50 | 50 | 100 |
| **Total** | **350** | **150** | **500** |

Balance the family-specific classes as follows:

| Class group | Company | Macro indicator | Total |
|---|---:|---:|---:|
| Positive / increase | 88 | 37 | 125 |
| Neutral / unchanged | 87 | 38 | 125 |
| Negative / decrease | 88 | 37 | 125 |
| Insufficient evidence | 87 | 38 | 125 |

Each source has at least 20 examples from each class group. Each applicable company aspect has at least 25 examples. Each applicable macro-indicator aspect has at least 20 examples. Do not require each source–family–aspect–class combination. No more than 12 insufficient-evidence examples can use an absent target as the main reason for the label.

The blind set measures balanced capability. It does not estimate natural prevalence. Do not use synthetic examples to fill a quota. If a quota cannot be met, record a feasibility failure and return to the map.

### Split and contamination controls

Split documents and event groups before target–aspect expansion. Use separate time periods for training, development, and blind data. Keep all passages, amendments, reports, social discussion, targets, and aspects from one event group in one split.

One blind event group can supply at most two target–aspect examples. The 500 blind examples must contain at least 400 event groups. At least 25% of blind company examples must use unseen issuers. One issuer can supply no more than five blind examples.

For a company event, group by company, event type, and event date. For a macro event, group by indicator, geography, reference period, and release. Send uncertain event matches to human review.

Remove exact normalized-text duplicates. Send a pair to human review when its character 5-gram Jaccard similarity is at least 0.85. Also send a pair to human review when its embedding cosine similarity is at least 0.95. Test and freeze these review thresholds before the blind manifest is locked.

Use this final sequence:

1. Close training collection.
2. Collect and use the later development set.
3. Sample newer blind inputs from separate event groups.
4. Lock the blind-input manifest.
5. Freeze all models, prompts, thresholds, and analysis rules.
6. Label the blind set.
7. Open the blind labels once for the final comparison.

Keep the blind inputs and labels out of teacher labeling, prompt work, training, threshold selection, error analysis, and model selection.
