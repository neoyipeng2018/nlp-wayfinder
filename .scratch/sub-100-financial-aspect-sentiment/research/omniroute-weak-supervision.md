# Auditable OmniRoute weak supervision

Research date: 2026-08-24  
OmniRoute version inspected: `release/v3.8.50`, commit `8f390efffd40bb8b35fa9a96879a8edcdd4f07a8`

## Decision

Use OmniRoute only as a **pinned transport and telemetry layer**, not as the ensemble or label aggregator. One weak-supervision source is an immutable tuple:

`(provider, resolved model/version, prompt template, label map, decoding parameters, output schema)`

For every passage, call each registered source separately, keep its raw response, and map it to one of the four task labels—`positive`, `neutral`, `negative`, or `insufficient_evidence`—or to the weak-supervision sentinel `ABSTAIN`. `ABSTAIN` is missing source output, not a fifth task label. The label model must retain a posterior over the four task labels; the result should be called a **probabilistic silver label**, not “silver truth.”

Do not use OmniRoute `auto`, ordinary routing/fallback combos, bare model IDs, or Fusion to obtain votes. Use a dedicated provider route and a fully qualified named model, verify the model and provider returned in response telemetry, and turn any substitution into `ABSTAIN`. The later panel-selection ticket should choose the exact models; this architecture deliberately does not.

## Why OmniRoute modes are not interchangeable

| OmniRoute path | What it returns | Use for weak-supervision votes? |
| --- | --- | --- |
| Dedicated `/v1/providers/<provider>/chat/completions` plus fully qualified model | A request validated against one provider; mismatched models return `400` | **Yes, primary path**, subject to response identity verification |
| Ordinary `/v1/chat/completions` with a fully qualified `provider/model` | Normally one named target, but still verify returned identity and routing trace | Fallback path only |
| Bare model ID | Can be shadowed by a combo with the same name and routed through its targets | **No** |
| `auto` / `auto/*` | Chooses a provider/model dynamically for each request and may try another candidate after failure | **No** |
| Priority, cost, random, or other combo | Selects one target and can silently move along the chain | **No** |
| Fusion | Fans out, anonymizes panel answers, and asks a judge to synthesize one final answer; with one survivor it returns that answer directly | **No** |

The dedicated-provider API is explicitly documented as performing provider-specific model validation ([OmniRoute user guide](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/guides/USER_GUIDE.md#L723-L734)). Bare IDs are unsafe because OmniRoute intentionally resolves an exact combo-name collision before bare-model resolution ([Auto-Combo documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/routing/AUTO-COMBO.md#L131-L180)). `auto` performs per-request selection ([Auto-Combo documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/routing/AUTO-COMBO.md#L110-L129)), while Fusion returns a judge-authored synthesis rather than the panel's independent records ([Fusion documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/routing/AUTO-COMBO.md#L290-L359)).

“Separate calls” means separately observable votes, not a claim of statistical independence. Models that share a base family, training lineage, provider alias, or prompt can make correlated errors; the aggregation stage must model that dependence.

## Collection architecture

### 1. Freeze a run manifest

Every labeling run starts from a read-only manifest containing:

- `run_id`, UTC start time, code commit, lockfile hash, OmniRoute version/commit, and a hash of non-secret OmniRoute settings;
- ontology and labeling-manual version/hash;
- dataset snapshot ID, split manifest hash, and immutable `example_id` / text hash pairs;
- a source registry with requested provider/model, observed upstream model version when available, prompt and label-map hashes, schema hash, sampling parameters, maximum input/output tokens, timeout, retry rule, and price snapshot;
- the external-spend cap allocated by the budget ticket and the amount reserved for evaluation/training;
- an allowlist of provider endpoints whose automation, output retention, and use for model training have been checked against current terms.

Changing any source-defining field creates a new `source_id`; it must not silently overwrite the old source. Dynamic aliases and model versions without a recorded run date are not reproducible identities.

### 2. Issue one explicit request per source and item

Use non-streaming requests with:

- the dedicated provider endpoint and a fully qualified model;
- `X-OmniRoute-No-Cache: true` and `x-omniroute-no-memory: true`;
- no tools, browsing, memory, or retrieval;
- compression disabled and a fixed, recorded guardrail configuration;
- `temperature: 0`, a fixed seed where the upstream supports one, and a small fixed output-token cap;
- a unique request ID and a strict `response_format: json_schema` request;
- the financial passage delimited as inert data, never concatenated into the system instructions.

OmniRoute documents the cache and memory bypass headers and returns a routing trace, request ID, version, resolved model/provider, tokens, latency, cost estimate, and fallback count in response headers ([API reference](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/reference/API_REFERENCE.md#L64-L89)). Accept a vote only when `X-OmniRoute-Decision` reports `strategy=single` and the returned provider/model match the source registry. A transient same-target retry is one attempt at the same labeling function, not another vote. A cross-provider/model substitution is an abstention.

OmniRoute may retry transient network, timeout, rate-limit, and upstream-server failures, with a default cross-provider policy of up to three attempts ([provider failover documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/OMNIROUTE_PROVIDER_FAILOVER.md#L1-L9)). Therefore route choice must be verified from the response rather than inferred from the request.

### 3. Use a minimal auditable vote schema

The logical response should be equivalent to:

```json
{
  "example_id": "immutable-id",
  "label": "positive | neutral | negative | insufficient_evidence | abstain",
  "confidence_band": "high | medium | low",
  "evidence_start": 0,
  "evidence_end": 42,
  "evidence_text": "an exact substring of the passage",
  "reason_code": "short-enumerated-code",
  "abstain_reason": null
}
```

The production schema should use enumerations, require all fields, reject additional properties, and allow null evidence only for `insufficient_evidence` or `abstain`. The local collector must validate JSON, enum membership, item identity, and exact evidence offsets. Preserve self-reported confidence, but do not treat it as a probability or aggregation weight until its relationship to accuracy is calibrated on human-labeled development data. Prompted language-model probabilities and confidence thresholds are not automatically calibrated ([Smith et al., 2022, §3.3](https://arxiv.org/html/2205.02318v1#S3.SS3)).

Structured output is not uniformly enforced upstream. At this inspected revision, OmniRoute turns `response_format` into a system-prompt instruction for Claude ([source](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/open-sse/translator/request/openai-to-claude.ts#L468-L483)), converts it to native Gemini JSON schema controls ([source](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/open-sse/translator/request/openai-to-gemini.ts#L598-L618)), and downgrades it for some OpenAI-compatible providers ([source](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/open-sse/executors/default.ts#L622-L683)). Local validation is consequently mandatory. Permit at most one same-source repair request; retain both attempts, charge both, and map the final failure/refusal/timeout to `ABSTAIN`.

`insufficient_evidence` and `ABSTAIN` must remain distinct:

- `insufficient_evidence` is a valid semantic judgment that the passage does not support a sentiment label for the supplied target-aspect pair;
- `ABSTAIN` means this labeling function supplied no trustworthy observation, for example because it explicitly declined, failed schema validation, was filtered, timed out, or was substituted.

### 4. Store an append-only provenance record

For every attempt, retain these fields in append-only JSONL/Parquet plus content-addressed raw blobs:

| Group | Required fields |
| --- | --- |
| Input | `run_id`, `example_id`, split, source/domain/target family/aspect, text hash; source URL/license pointer rather than duplicating restricted text |
| Source | `source_id`, provider, requested and returned model, model-family/dependency-group IDs, prompt/label-map/schema hashes, decoding settings |
| Request | UTC timestamp, endpoint class, serialized request hash, OmniRoute version, unique request ID, retry ordinal |
| Response | HTTP status, selected routing/cost headers, raw-body hash and encrypted blob pointer, finish/refusal reason, parsed vote, parse/evidence checks, abstain reason |
| Usage | input/output/reasoning/cache tokens, latency, attempts/fallback count, price-snapshot estimate, provider invoice/project ID, reconciled marginal cost |

Do not store provider secrets, access tokens, or Authorization headers. Hash-chain and sign the final run manifest and artifact index so later edits are detectable. Keep the human calibration labels and the blind evaluation set in separate access-controlled stores.

## Correlation-aware probabilistic aggregation

Programmatic weak supervision is designed for sources that can conflict or abstain; it estimates source behavior and emits probabilistic labels rather than simply taking a majority ([Ratner et al., 2016](https://proceedings.neurips.cc/paper/2016/hash/6709e8d64a5f47269ed5cea9f625f7ab-Abstract.html)). Prompted weak supervision specifically maps multiple language-model queries to labels or abstentions and then trains an end model from the denoised votes ([Smith et al., 2022](https://arxiv.org/html/2205.02318v1#S3)).

### Human calibration with one annotator

Create a **calibration/development set separate from the final blind test**. Draw it before looking at votes, stratify it across text source, target family, aspect, and expected class difficulty, and have the sole annotator label it while blinded to model outputs. Start with roughly 120 examples and add batches of 40 until source rankings, posterior thresholds, and per-stratum confusion estimates stabilize, with a practical ceiling near 240. Blindly relabel 15–20% after a washout period and report intra-annotator agreement and resolved differences.

This follows the prompted-weak-supervision workflow, which uses a small manually labeled development set—typically dozens to hundreds of examples—to choose prompts and modeling settings ([Smith et al., 2022, §3.1](https://arxiv.org/html/2205.02318v1#S3.SS1)). One annotator can anchor source-quality estimates to a documented policy, but cannot estimate inter-annotator reliability or establish universal ground truth. Report that limitation explicitly and attach bootstrap/credible intervals to source metrics.

### Label model

Represent the collected votes as a matrix `Λ[item, source]`, with four categorical task labels plus missing/abstain. Fit a multi-class generative factor-graph label model with:

1. stratum-aware class priors with hierarchical shrinkage rather than unpooled estimates for every domain/aspect;
2. source coverage and class-conditional confusion parameters, anchored by the human development labels and pooled when sample counts are small;
3. sparse pairwise dependency factors between correlated sources;
4. the human development labels observed and the silver-training labels latent;
5. posterior predictive checks for class prevalence, agreement, disagreement, and per-source coverage.

Predeclare dependency edges when sources share an underlying model family, model alias/weights, provider-side aggregator, prompt family, or generated rationale. Then examine residual dependence on the unlabeled vote matrix and add only sparse, stable edges. Research shows that source-dependency structure affects estimated labels and can be learned from unlabeled source outputs ([Bach et al., 2017](https://proceedings.mlr.press/v70/bach17a.html)); a later robust-PCA method outperformed conditionally independent weak-supervision models by up to 4.64 F1 on its evaluated tasks ([Varma et al., 2019](https://proceedings.mlr.press/v97/varma19a.html)). Those results motivate dependency modeling but do not guarantee a gain here, so selection must be empirical.

Treat alternate prompts to the same model and multiple endpoints serving the same base model as correlated labeling functions, never as independent replicas. Prefer complementary financial questions or partial heuristics over superficial prompt paraphrases; prompted-weak-supervision research found that multiple distinct queries can expose complementary signals ([Smith et al., 2022](https://arxiv.org/html/2205.02318v1#S3.SS2)).

Compare the proposed model on the frozen human development set against:

- unweighted majority vote;
- calibrated weighted vote using class-conditional development-set accuracy;
- a conditionally independent multi-class label model;
- the correlation-aware label model.

Select the simplest method within uncertainty of the best development log loss and macro-F1, and freeze it before generating final silver labels. If there are fewer than three meaningfully distinct model-family groups, too little overlapping coverage, unstable dependency edges, or no development gain over calibrated weighted voting, use the conservative weighted-vote fallback rather than claiming identifiable unsupervised source quality.

### Aggregate abstention and soft targets

The label model emits `p(y | Λ)` for all four task labels. Accept an item for specialist training only when:

- at least two distinct dependency/model-family groups contribute a non-abstaining vote;
- maximum posterior probability and normalized entropy pass thresholds frozen on the human development set; and
- no hard policy validator fails.

Otherwise leave the item unlabeled; do not force a plurality class. Preserve the complete posterior and train the specialist with a soft-target cross-entropy/KL objective, optionally weighting examples by a frozen confidence function. Report silver coverage as well as estimated error: a high-precision label set that covers only easy news passages is not sufficient for the cross-source destination.

## GPT-5.6-sol ablations

Produce two named variants from the same immutable examples and non-GPT votes:

1. **Vote-removal ablation:** delete every GPT-5.6-sol source column, refit all source-quality/dependency parameters, and reapply the same frozen model-selection and abstention procedure. This measures GPT's marginal value as a voter.
2. **Strict no-teacher pipeline:** additionally exclude GPT-generated rationales, prompt revisions, example selection, adjudication, and synthetic text. Human-authored prompts/manuals and the same non-GPT raw votes may be reused. This supports the stronger claim that the specialist was not trained through GPT-5.6-sol.

Train full-panel and strict-no-teacher specialists from the same base checkpoint, data IDs, optimizer settings, and seed schedule. Evaluate both once on the untouched blind set, alongside GPT-5.6-sol as the comparison system. Report silver coverage, posterior calibration, end-model score, and cost for both. If only the vote-removal experiment is feasible, describe the result as a **GPT-vote ablation**, not a no-teacher result.

## Spend controls under the external `$100` cap

The budget-allocation ticket should reserve a labeling sub-cap. The collector enforces that cap independently of OmniRoute:

```text
worst_case_cost =
  sum over scheduled calls and permitted retries of
  (max_input_tokens * input_price + max_output_tokens * output_price
   + max_reasoning_tokens * reasoning_price) / 1,000,000
```

Use a staged funnel:

1. a small route/schema smoke test;
2. a stratified pilot across candidate sources;
3. freeze a diversity-per-dollar panel;
4. schedule the full run only when its worst-case cost plus the protected reserve is below the cap;
5. stop before each batch when the reconciled spend plus worst-case outstanding work would breach the cap.

Use short passages and concise JSON outputs. Prefer one source/item request for clean failure accounting; if prompt overhead makes fixed micro-batches necessary, give every item its own schema record and treat batch membership as a dependence/provenance field. Duplicate only a small 2–5% sample to measure model replay stability, and never count the duplicate as another independent vote.

OmniRoute's cost dashboard is not an invoice: its documentation calls the number a savings estimate, notes that unknown prices contribute zero, and says subscription/free traffic can still accrue estimated cost ([cost documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/guides/COST_TRACKING.md#L16-L37)). It also recomputes historical cost from the current pricing table ([cost documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/guides/COST_TRACKING.md#L82-L99)). Snapshot prices, keep the response telemetry, use provider-side project keys and hard spend caps where available, and reconcile against actual invoices/top-ups. An unpriced response is “unknown,” not automatically free. Existing flat-rate subscriptions should enter the marginal ledger at their actual incremental spend, consistent with the project's agreed budget definition.

## Security, licensing, and reliability constraints

- **Credentials:** Self-host on loopback with a dedicated least-privilege project key. Set `STORAGE_ENCRYPTION_KEY`; OmniRoute stores credentials in plaintext passthrough mode when it is absent ([security policy](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/SECURITY.md#L53-L64)). Use OmniRoute's documented per-key `noLog` option when a separately encrypted audit store is authoritative, avoiding a second call-log copy ([security policy](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/SECURITY.md#L142-L150)).
- **Untrusted passages:** Disable tools and external retrieval, delimit passage text as data, and log—but do not silently rewrite—prompt-injection flags. OmniRoute describes its prompt-injection detector as best effort with both false positives and false negatives, and its guardrail framework fails open on exceptions ([security policy](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/SECURITY.md#L66-L101)). Never send confidential or material non-public information unless every upstream is approved for it.
- **Provider terms:** Use only official, automation-permitted provider/API access. OmniRoute's own ToS flags are advisory and do not prevent flagged providers from entering routing or fallback ([free-tier documentation](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/docs/reference/FREE_TIERS.md#L62-L66)). Do not use consumer-web/OAuth routes for bulk dataset generation without an explicit terms review.
- **Licenses:** OmniRoute itself is MIT-licensed ([license](https://github.com/diegosouzapw/OmniRoute/blob/8f390efffd40bb8b35fa9a96879a8edcdd4f07a8/LICENSE#L1-L20)); that grants no rights to source passages, upstream services, model weights, or generated outputs. Record the applicable dataset and provider/output terms. If redistribution is restricted, publish hashes, IDs, prompts, and reconstruction scripts rather than raw text/responses.
- **Model drift:** Prefer versioned upstream model IDs. Run a frozen canary set at the start and end of collection, store observed response model IDs and timestamps, and create a new source/run if the alias, response behavior, or schema success changes materially.
- **Reproducibility:** Pin OmniRoute and dependency versions; `temperature: 0` is not a determinism guarantee. Report replay agreement on the duplicated 2–5% sample and retain all malformed/refused responses.

## Handoff acceptance tests

Before the downstream panel-selection and aggregation tickets can adopt this design, a prototype must demonstrate:

1. a named-model call cannot be accepted when provider/model telemetry differs from the source registry;
2. `auto`, combo, Fusion, cache hits, memory injection, and bare model IDs are rejected by configuration/tests;
3. valid, invalid, refusal, timeout, content-filter, and retry cases map reproducibly to a task label or `ABSTAIN`;
4. every normalized vote traces to an immutable input, exact prompt/schema, raw response hash, provider/model, attempt, and cost record;
5. synthetic correlated-source tests show the correlation-aware path does not count duplicate sources as independent evidence;
6. majority, weighted, independent, and correlation-aware aggregators can be compared without accessing the blind test;
7. full-panel, GPT-vote-removal, and strict-no-teacher artifacts can be regenerated from the same manifest; and
8. the collector hard-stops before exceeding its allocated external-spend cap even when retries and unpriced responses occur.

This architecture makes OmniRoute useful without confusing routing redundancy with epistemic diversity. Its main cost is procedural: a separate calibration set and strict provenance are required for a defensible claim.
