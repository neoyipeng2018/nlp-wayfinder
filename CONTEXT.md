# Financial Aspect Classification

This context defines the language used to compare a low-cost specialist classifier with a frontier general-purpose model across financial text sources.

## Language

**Target-conditioned financial aspect classification**:
The task of assigning positive, neutral, negative, or insufficient evidence to an explicitly supplied company target and aspect within a financial passage.
_Avoid_: Generic financial sentiment, document sentiment, end-to-end aspect extraction

**Financial passage**:
A bounded English excerpt from financial news, a company announcement, an earnings call, a regulatory filing, or financial social media.
_Avoid_: Document, article

**Evidence-preserving bounded input**:
One target–aspect input of no more than 1,024 ModernBERT tokens, including the passage, company, aspect, and special tokens. It uses consecutive complete sentences, stays identical for every human and model, and is rejected when its target and required label evidence do not fit.
_Avoid_: Full document, post-label truncation, model-specific passage

**Staged source benchmark**:
A sequence of source-specific evaluations. Stage 1 uses financial news. Stage 2 adds company announcements and regulatory filings. Stage 3 adds earnings calls and financial social media. Each new source must pass its gate before the experiment continues.
_Avoid_: Pooled cross-source benchmark, simultaneous source rollout

**Staged source data allocation**:
Stage 1 uses 4,000 accepted silver training examples, 200 development examples, and 400 blind examples from financial news. Each later source adds 2,000 accepted silver training examples, 200 development examples, and 400 blind examples. The complete plan has 12,000 accepted silver training examples, 1,000 development examples, and 2,000 blind examples. Collection can inspect no more than 20,000 silver-label candidates in total.
_Avoid_: 4,000 training examples for each later source, pooled development set, pooled blind set

**Issuer-hosted earnings-call transcript**:
An earnings-call transcript published on the company website, or a project transcript made from company-hosted call audio. It is a clean-core candidate only after an audit confirms content ownership, website terms, automated-access permission, and the required evaluation, training, weight-release, and redistribution rights.
_Avoid_: Automatically licensed transcript, third-party transcript

**Financial target**:
The explicitly supplied publicly traded company whose named aspect is being evaluated. Securities, assets, governments, macro indicators, and institutions treated independently of a company are outside the scope.
_Avoid_: Target entity, subject, topic

**Company target**:
A publicly traded issuer, including a bank, insurer, exchange, or other financial firm when treated as a company. The company's shares, bonds, and other securities are distinct instrument targets and are outside the first experiment.
_Avoid_: Issuer security, stock target, institution target

**Aspect**:
The explicitly supplied facet of a financial target against which sentiment is evaluated.
_Avoid_: Topic, keyword

**Company aspect ontology**:
A fixed set of stable company facets, rather than named events. Stage 1 uses a four-aspect subset. Later stages can add aspects only through a new map decision.
_Avoid_: Universal aspect list, free-text aspect, event type

**Company aspect**:
One of financial performance; demand and commercial traction; operations, supply, and capacity; financial position and funding; capital allocation; management and governance; legal and regulatory position; risk and resilience; or outlook and expectations.
_Avoid_: Company event type, stock-performance aspect

**Stage 1 aspect set**:
Financial performance; demand and commercial traction; operations, supply, and capacity; and outlook and expectations.
_Avoid_: Full company-aspect ontology

**Narrowest-supported-aspect rule**:
Evidence belongs to the most specific applicable aspect that it independently supports. For a company target, a specific subject aspect takes priority over the general outlook aspect. Future time alone does not make a claim an outlook claim. Use outlook and expectations when the claim is about the expectation itself or about the company's broad outlook. Use risk and resilience only when exposure, uncertainty, weakness, or the ability to absorb a shock is the focus. Do not copy one claim across aspects only because its effects can reach them.
_Avoid_: Consequence labeling, catch-all risk, implicit outlook

**Speaker-neutral evidence rule**:
Treat a clearly attributed claim as passage evidence, but do not give it more or less weight only because of the speaker's role. If attributed claims conflict and the passage gives no resolution or basis to combine them, assign insufficient evidence. If the passage rejects a reported claim, do not treat the rejected claim as fact.
_Avoid_: Analyst-priority rule, management-priority rule, annotator trust ranking

**No-material-effect rule**:
For a company target, an explicit statement of no material effect supports neutral for the specific applicable aspect. The statement can refer to a future period when that aspect is the focus.
_Avoid_: Automatic outlook reassignment, missing-evidence label

**Aspect applicability**:
The schema-level status of an aspect for a financial-target family: applicable when the pairing has a defined meaning, or invalid when it must be rejected before sentiment classification. An applicable pairing without adequate passage evidence receives insufficient evidence; invalid applicability is never a sentiment label.
_Avoid_: Aspect relevance, neutral applicability, unsupported aspect

**Target–aspect example**:
One classification input formed from a financial passage, one supplied financial target, and one applicable aspect. A passage may yield multiple examples for the same target when it independently supports multiple aspects.
_Avoid_: Passage label, event label, multi-aspect label

**Event group**:
All documents and passages that report, repeat, amend, or discuss the same underlying event, including syndicated text and reports from different sources. One event group belongs to only one data split.
_Avoid_: Row group, publisher group, exact-duplicate group

**Sealed candidate manifest**:
The ordered list of all candidate examples for one source and stage. A source annex fixes acquisition, rights, extraction, normalization, target-and-aspect expansion, event grouping, duplicate review, split boundaries, limits, and software versions before labeling. Candidate order is the ascending SHA-256 of `nlp-wayfinder + stage + source + split + candidate_id + 20260905`. Each inspected silver candidate counts against its source limit. Only the next eligible candidate from the same source and required cell can replace an excluded development or blind candidate.
_Avoid_: Curated sample, favorable replacement, unordered candidate pool, post-label intake change

**Company target-condition polarity**:
The favorable, neutral, unfavorable, or unsupported implication of the evidence for a company target's specified aspect: positive, neutral, negative, or insufficient evidence.
_Avoid_: Macro direction, market-impact polarity, authorial tone, lexical polarity

**Specialist model**:
A model or fixed model pipeline adapted specifically for target-conditioned financial aspect classification.
_Avoid_: General-purpose LLM, financial chatbot

**Only specialist initialization**:
`answerdotai/ModernBERT-base` at revision `8949b909ec900327062f0ebf497f51aef5e6f0c8`, with a new four-class classification head and explicit passage, target, and aspect fields. This effort has no alternate initialization or fallback model.
_Avoid_: DeBERTa primary, fallback branch, model bake-off

**GPT-independent ensemble specialist**:
A specialist model trained from silver labels that a fixed ensemble of non-GPT labeling sources produces. GPT-5.6-sol supplies no training label, development signal, prompt-selection signal, or other training artifact.
_Avoid_: Gold-trained model, GPT-distilled model, independent specialist

**Conditional free labeling ensemble**:
The fixed routes `mistral/mistral-medium-3-5`, `cf/@cf/zai-org/glm-4.7-flash`, and `groq/qwen/qwen3.6-27b`. The ensemble can run only after exact-route, free-limit, and training-permission checks pass. A free-limit error stops collection and cannot cause paid use, fallback, or model substitution.
_Avoid_: Free router, automatic fallback, Fusion ensemble, opaque model alias

**GPT-5.6-sol baseline**:
A frozen GPT-5.6-sol evaluation configuration with medium reasoning effort, used as the only general-purpose comparison system and called only on the blind test set.
_Avoid_: GPT-5.6 generally, frontier LLMs generally

**Audit-repeatable GPT comparison**:
A GPT comparison whose inputs, prompt, route, schema, manifest, attempt records, and returned model identity are preserved so another run can follow the same procedure. It does not claim identical output when the route has no dated model snapshot or effective random seed.
_Avoid_: Bit-for-bit repeatable GPT run, frozen GPT weights

**Blind reference set**:
A fresh, single-human-labeled set of roughly 300–500 examples withheld from model training, prompt development, and model selection; 15–20% is blindly relabeled after a washout period to measure self-consistency.
_Avoid_: Gold set, validation set, public benchmark test split

**Blind self-consistency check**:
A second label from the same human for a hidden sample of blind examples after a washout period. The first label stays as the reference label. The second label measures repeatability and does not change the benchmark result.
_Avoid_: Adjudication, corrected reference label, second annotator

**Balanced capability blind set**:
A blind reference set deliberately balanced across financial-passage sources and constrained by target-family, aspect, and family-specific class minimums to test breadth of capability. It does not estimate the naturally occurring prevalence of sources, targets, aspects, or labels.
_Avoid_: Representative sample, prevalence benchmark

**Manifest-only blind passage**:
An externally authored passage retained privately for blind evaluation when redistribution rights have not been established, while only its source identifier, URL, timestamp, content hash, and labels may be released. Manifest-only status is not permission to override source terms that prohibit collection, retention, or model evaluation.
_Avoid_: Licensed passage, redistributable passage, public-domain passage

**Development set**:
A separately sampled, human-labeled set used by a fully confirmed procedure for labeling-source calibration, model selection, thresholds, and error analysis, but never for specialist-model training or procedure revision.
_Avoid_: Training set, blind reference set

**Zero-change confirmation**:
The human confirmation of the complete stage manifest before any development result exists. After confirmation, the experiment cannot change a prompt, threshold, candidate rule, route, seed, training configuration, checkpoint rule, calibration rule, metric, tie rule, or software version. A semantic change stops and invalidates the run. The append-only decision log records the confirmation and each attempted later change.
_Avoid_: Change allowance, development-based revision, unfavorable-seed replacement, post-confirmation tuning

**Three-period split**:
A split policy that closes training collection first, collects development data in a later period, freezes the policy and selected systems, and then collects blind data in a new period. Documents and event groups cannot cross these periods.
_Avoid_: Random split, row-level split, overlapping time split

**Two-lane data portfolio**:
A data portfolio that keeps a commercially usable core separate from non-commercial or otherwise restricted auxiliary material, which may be used only in explicitly isolated experiments and ablations.
_Avoid_: Mixed-license training pool, commercially clean dataset

**Clean-core checkpoint**:
A specialist-model checkpoint trained without non-commercial, unlicensed, or otherwise restricted auxiliary material and eligible for downstream use under the recorded data and model terms.
_Avoid_: Main checkpoint, unrestricted checkpoint

**Quarantined dataset**:
A dataset that has a license for its repository or data files but has no completed rights audit for the underlying passage text. It cannot enter the clean core until the audit clears its required uses.
_Avoid_: Clean dataset, licensed dataset, research-only dataset

**Hard insufficient-evidence example**:
A target–aspect example in which the supplied target is usually present but the bounded passage does not support the supplied aspect, misattributes evidence to another target, or remains genuinely ambiguous. Target-absent examples are the easy subtype and form no more than 10% of this class in the balanced capability blind set.
_Avoid_: Random negative, neutral example

**Unseen issuer**:
A company target that has no example in the training or development sets and first occurs in the blind reference set.
_Avoid_: New document, new event

**Independent model vote**:
A raw label produced by one named model call through OmniRoute and retained with its model, prompt, confidence, provenance, and cost metadata before weak-supervision aggregation.
_Avoid_: Fusion answer, judge synthesis, ensemble truth

**Silver label**:
A machine-generated training label aggregated from multiple labeling sources through weak supervision; it is not authoritative evaluation truth.
_Avoid_: Silver truth, ground truth, gold label

**Accepted silver example**:
A target–aspect example whose weak-supervision result passes the frozen support, confidence, and abstention rules and can enter specialist-model training.
_Avoid_: Candidate passage, teacher vote

**Weak-supervision aggregation**:
A source-specific, gold-anchored Dawid–Skene combination of three valid non-GPT model votes that uses human development labels to estimate each voter’s four-class confusion pattern. It produces a calibrated soft label and rejects an example unless two valid routes support the top class and its probability is at least 0.70.
_Avoid_: Snorkel LabelModel, majority truth, model judge, GPT adjudication

**Statistical non-inferiority**:
Evidence that the specialist model is no worse than the GPT-5.6-sol baseline by more than a predeclared evaluation margin on the blind reference set.
_Avoid_: Similar performance, roughly as good

**Valid blind comparison run**:
A blind comparison in which both the specialist model and the GPT-5.6-sol baseline return one valid label for every scheduled example, with no failed attempt, invalid response, route mismatch, or missing prediction. Any such failure makes the complete run invalid and requires human investigation; an invalid run has no benchmark result.
_Avoid_: Partly scored run, failure-as-error run, automatic repair run

**Source guardrail**:
A predeclared source-specific non-inferiority gate. Each new source and each earlier regression source must pass separately; a pooled score is diagnostic only and cannot offset a failed source.
_Avoid_: Per-source average, post-hoc slice metric, pooled pass gate

**External-spend budget**:
The hard USD 100 cap for all stages combined. It covers all marginal compute, API evaluation, storage, and paid data costs, while it excludes existing hardware, subscriptions, and human time.
_Avoid_: Training budget, GPU budget

**External-spend allocation**:
The USD 100 cap assigns USD 0 to silver-label calls, USD 35 to specialist training and device checks, USD 25 to the GPT blind comparison, USD 20 to data and storage, and USD 20 to contingency. A move between these limits needs a new recorded decision. Contingency cannot pay for label-route overflow, an alternate model, or a source that does not have the required rights.
_Avoid_: Soft budget, paid label overflow, shared untracked balance

**Staged feasibility gate**:
Before one stage starts, each source in that stage must have a recorded access method and permission for private evaluation, model training, and the planned release. All accepted free non-GPT label routes must show account-specific free limits and permission for training use. At least three routes must pass, and the complete accepted route set must stay fixed during the stage. A later-stage failure does not block an earlier approved stage.
_Avoid_: Global five-source preflight, public-access assumption, web-crawl license, estimated account quota, exactly-three-route rule, mid-stage route change

**Frozen staged build specification**:
The complete confirmed experiment design and its stop rules. It gives a credible conditional path to the source-specific non-inferiority test, but it does not give permission to start a stage whose feasibility gate has not passed.
_Avoid_: Build authorization, guaranteed completion, unconditional build plan

**Build eligibility**:
Permission to start one experiment stage after that stage's source rights, free label routes, quotas, schedule, and cost preflight checks pass. Stage 1 is not build-eligible while its financial-news source or the minimum free route panel fails these checks.
_Avoid_: Build-ready specification, planning completion, later-stage readiness
