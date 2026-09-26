# jev (TypeSafe AI) route evidence

Retrieval date: 2026-09-26

Scope: Public first-party TypeSafe sources only (docs.typesafe.ai, typesafe.ai blog and legal pages, evals.typesafe.ai). No account API call was made; an unauthenticated `GET https://api.typesafe.ai/v1/models` returns `403`. Nothing here is legal advice. Question: [#91](https://github.com/neoyipeng2018/nlp-wayfinder/issues/91), for the confidence calibration comparison map [#90](https://github.com/neoyipeng2018/nlp-wayfinder/issues/90).

## Verdict

jev exists and has an exact, pinnable route: `POST https://api.typesafe.ai/v1/systemone` with `"model": "jev-1.13.0"`. Its Choice question returns a native probability over a closed label set plus a derived `confidence`. The Stage 1 bounded input fits easily within its context limit. It is usable as a panel system if we accept three constraints:

1. It cannot take the GPT-5.6-sol frozen prompt as a generative prompt, and it cannot fill in a verbalized "confidence field". The prompt has to be recast as one Choice question (`instructions` plus one `criteria` entry per label). Its confidence is the native probability, not a verbalized value.
2. There is no temperature or seed control, and repeated calls are not bit-identical.
3. Access is "early access" off a waitlist, and whether our account has access is unverified.

TypeSafe publishes no calibration metric (ECE, Brier, or reliability diagram) for jev. Its calibration is only a training-objective claim.

## Source facts

### Access and route

- Released 2026-09-15 "in early access"; developers are brought "off the waitlist as quickly as we can". [Launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- There is one endpoint for every model: `POST https://api.typesafe.ai/v1/systemone`, with Bearer API key auth. Keys come from `console.typesafe.ai/keys`. [API reference](https://docs.typesafe.ai/api), [Quick start](https://docs.typesafe.ai/introduction/quickstart)
- Errors: `401`, `422` (validation), `429` (rate limit), and `529` (overloaded). [API reference](https://docs.typesafe.ai/api)

### Model identifier and versioning

- The current versioned ID is **`jev-1.13.0`** (Jev 1.13). [Models](https://docs.typesafe.ai/models)
- The aliases `jev-latest` and `jev-preview` both point to `jev-1.13.0` today. "An alias moves when a new release ships"; the docs advise: "pin that version's ID instead of the alias".
- The response `model` field reports the versioned ID that answered (e.g. `"model": "jev-1.13.0"`). This gives the preflight a route-identity check.
- `GET /v1/models` lists aliases only. Versioned IDs "are accepted by the `model` field whether or not they appear in the list."
- The version is semantic, not dated, and no deprecation or retirement policy was found. MCA §2 says TypeSafe "may from time to time update the Services" with "commercially reasonable efforts" at advance notice. [MCA](https://typesafe.ai/legal/mca)
- Caveat: the jaggedness page's own example uses `model="jev-1.13"` (two-part). Pin the full `jev-1.13.0` string and assert on the response `model`. [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

### How it reports confidence

jev does not generate text. It returns typed answers only. [Models](https://docs.typesafe.ai/models), [Launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

| Question type | Returned | Confidence signal |
| --- | --- | --- |
| Choice (1 of ≤255 options) | `choice`, `probabilities` (map, sums to 1), `confidence` | **Native probability distribution**, plus a derived scalar |
| Score (2–10 ordered levels) | `score` (probability-weighted), `legend`, `probabilities`, `confidence` | Same |
| Noul (yes/no) | `noul` in [0,1] | Probability only, no `confidence` field |

- `confidence` is "a statistic computed from the probability distribution": 1.0 when all mass is on one option, falling as mass spreads out. The docs demo uses `(K·p_max − 1)/(K − 1)` "to approximate" it for K = 3, and they do not publish the exact production formula. [Confidence](https://docs.typesafe.ai/confidence)
- The probabilities are neither logprobs nor verbalized. They are the model's native output, trained with "Reinforcement Learning for Calibrated Decisions (RLCD)". [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer)
- Implication for #90: use the `probabilities` entry of the chosen label (top-label probability) as jev's confidence for top-label ECE and Brier. Record the derived `confidence` alongside it as the native signal. The two are not the same quantity.
- Non-determinism: TypeSafe's own repeat test measured a mean probability std dev of 0.0098 (max 0.0515) for a Choice over repeats. "Small changes can still switch the top label when two labels are close." There is no temperature or seed parameter. [Self-consistency: choices](https://docs.typesafe.ai/cookbooks/consistency_choice_cookbook)
- Structural caveat: a Noul and a yes/no Choice on the same question give non-comparable numbers (0.22 vs 0.01 in their example), and question negations do not sum to 1. [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

### Strict output schema

- The schema is enforced by construction. The answer is always one of the `criteria` keys you define: "Possible outputs and structure are defined in advance. The model never makes type errors." Schema matching is "guaranteed". [Launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- There is no JSON Schema or `response_format` parameter, because the schema *is* the question map. `instructions` and `criteria` may be a string, an object, or an array. [API reference](https://docs.typesafe.ai/api), [Advanced: structure](https://docs.typesafe.ai/primitives/advanced)
- Consequence: a jev answer can never be a refusal, free text, or an off-schema value. An `insufficient evidence` answer happens only if it is one of the Choice options.

### Price and rate limits

| Item | Value |
| --- | --- |
| Input | USD 0.042 per million tokens (USD 42 per billion) |
| Output | Free ("Output tokens are free") |
| Rate limits | 250,000 tokens/s; 1,200 requests/min |
| Context | 64k tokens per request; 32k for `state` + longest question |
| Input modality | Text only (string, JSON object, or array) |

Source: [Models](https://docs.typesafe.ai/models). The rate limits carry a warning: they "are adjusting dynamically" and "can change without notice". Billing is prepaid credits. Purchased credits expire at the earlier of term end or 12 months, and they are non-refundable. [MCA §8](https://typesafe.ai/legal/mca)

Rough cost: a 1,024-token input plus instructions and criteria (~1.5k tokens) costs about USD 0.00006 per call. Even 10,000 calls cost under USD 1, so cost is not a constraint for the #90 spend cap.

### Data retention and training use

- Training: MCA §4.1 says TypeSafe "will not include Customer Data in a dataset used to train (i.e., to modify the model weights of) any artificial intelligence or machine learning models without Customer's prior consent." The Privacy Policy says it "will not train or fine tune any … models on Input". [MCA](https://typesafe.ai/legal/mca) (last updated 2026-09-23), [Privacy Policy](https://typesafe.ai/legal/privacy-policy) (last updated 2025-11-19)
- Retention: there is no fixed period. MCA §4.1(c) licenses Customer Data "in perpetuity" to derive Telemetry, to monitor fraud and abuse, and for legal compliance. §4.3 lets TypeSafe process Telemetry ("technical logs, hashes, summary statistics and classifications…") "without restriction". The DPA says personal data is "retained for as long as necessary", and §10.3 says TypeSafe may delete at any time and may keep backups. [DPA](https://typesafe.ai/legal/data-processing) (last updated 2026-04-24), [MCA](https://typesafe.ai/legal/mca)
- Zero data retention is "for enterprise customers" by contacting sales. It is not available on the self-serve route. [Legal](https://docs.typesafe.ai/legal)
- Output restriction: MCA §2.3(b) forbids using the Services or Output "to perform model distillation, train a model to imitate the output of the Services, or develop … a similar or competing product". The #90 comparison only scores jev and does not train on its answers, so this clause does not apply. jev outputs must still never enter any specialist training or selection data. No clause restricting publication of benchmarks was found in the MCA.
- Subprocessors are listed at `trust.typesafe.ai/subprocessors` (not fetched).

### Published calibration evidence

- **No quantitative calibration evidence was found.** There is no ECE, Brier, reliability diagram, or held-out calibration set for jev on any TypeSafe page reviewed. The FAQ says: "We deliberately chose *not* to publish performance against *public* benchmarks." [Launch blog FAQ](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- Calibration is stated as a training objective (RLCD) and a definition ("Outcomes assigned a probability of 0.2 should occur about 20% of the time"), not as a measurement. [AI primer](https://docs.typesafe.ai/introduction/machine-learning-primer), [System One](https://docs.typesafe.ai/concepts/system-one)
- The docs also say that Score levels "are weak in numerical calibration". [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- The only published eval measures **accuracy** against consensus labels, not calibration. On four in-house workflows, the reference is the average of GPT-6 Astra and Claude Fable 5.1 at high thinking. Jev scored 67.8% at USD 0.0004 and 0.4 s per case, against sol at 74.1% and opus 5 at 73.1%. TypeSafe notes that the workflows were written by its own capabilities team and that the reference biases toward OpenAI and Anthropic models. [Workflow evals](https://evals.typesafe.ai/), [Launch blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

## Fit with the Stage 1 bounded input

| Check | Result |
| --- | --- |
| Size: ≤1,024 ModernBERT tokens + prompt | Fits: limit is 32k for `state` + longest question |
| Text-only input | Fits |
| Four labels incl. `insufficient evidence` | Fits: Choice with 4 options (max 255) |
| Frozen GPT-5.6-sol prompt, verbatim | **Does not fit as-is.** The prompt must be mapped into Choice `instructions` and `criteria`, and jev reads instructions literally |
| "Plus one confidence field" (verbalized) | **Not possible.** jev returns only native probabilities and the derived `confidence` |
| Refusal or off-schema answer | Cannot occur. Transport errors (`429`/`529`) still can |
| Language | English is the primary language, which matches Stage 1 |
| Known weak spots relevant to the task | Literal reading, indirection, adversarial or argumentative text in `state`, and large irrelevant context [Jev 1.13 jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13) |

## Open items for the map

- Confirm that our account has API access (waitlist) and that `jev-1.13.0` is accepted, using a non-label preflight.
- Decide how the frozen prompt maps into `instructions` and `criteria`. This departs from "same prompt for every panel system" and should be recorded as a jev-specific adaptation.
- Decide which scalar feeds the headline metrics: the top-label `probabilities` value (recommended) or the derived `confidence`.
- Self-serve retention is unbounded telemetry with no zero data retention. Check that this is acceptable for the blind reference set passages.
