# Evidence memo: frontier calibration panel routes and confidence elicitation

**Retrieval date:** 2026-09-26
**Scope:** Evidence for [“Research confidence elicitation and routes for GPT-5.6-sol, Anthropic, and Google”](https://github.com/neoyipeng2018/nlp-wayfinder/issues/92), under the map [#90](https://github.com/neoyipeng2018/nlp-wayfinder/issues/90). It covers three members of the **frontier calibration panel** for the **confidence calibration comparison**: GPT-5.6-sol (as frozen), Claude Opus 5.5, and the current Google Gemini flagship. jev (typesafe.ai) is out of scope. This memo uses official provider documentation, pinned source code, and primary papers. It makes no model call. Items marked **Unverified** need a check before any freeze.

## Decision summary

1. **No panel route gives token logprobs together with a strict schema and reasoning on.** GPT-5.6-sol at the frozen medium effort does not (and the frozen Codex transport strips the field anyway). The Claude Messages API has no logprobs at all. Google marks `responseLogprobs` and `logprobs` as deprecated for Gemini 3.x. Plan for **verbalized confidence only**. A "native confidence signal" from logprobs is not available for these three systems.
2. **Pinnable routes:**
   - GPT-5.6-sol: `cx/gpt-5.6-sol-medium` (frozen). It has no dated snapshot. The public API ID `gpt-5.6-sol` is its own single snapshot.
   - Claude Opus 5.5: `claude-opus-5-5`, a pinned snapshot. It retires no sooner than 2027-09-22.
   - Google: `gemini-3.8-flash` (stable, GA 2026-09-02) or `gemini-3.1-pro-preview` (preview). This choice is a **human decision**. See §3.
3. **Cost for about 600 blind calls each, at a conservative ceiling** (1,600 input and 2,048 output tokens per call):
   - GPT-5.6-sol: about USD 28.4 shadow cost. The marginal cost is USD 0 on the Codex subscription route.
   - Opus 5.5: about USD 28.4, or USD 14.2 through the Batch API.
   - Gemini 3.8 Flash: about USD 5.3. Gemini 3.1 Pro Preview: about USD 16.7.

   At typical sizes (1,000 input and 600 output tokens), the costs are about USD 9.6, USD 9.6, USD 1.8, and USD 5.5.
4. **Data use:**
   - Anthropic API and Gemini **paid** tier: no training on inputs by default.
   - OpenAI **API**: no training by default.
   - The frozen GPT route is a **personal ChatGPT/Codex plan**. Its training use follows the account's "Improve the model for everyone" setting, so that setting must be off. **Partly unverified.**
   - The Gemini **free** tier *is* used to improve Google products. Do not use it for blind passages.
5. **Literature:** a verbalized top-label confidence is enough for top-label ECE, a reliability diagram, a risk-coverage curve, and a *binary* (top-label) Brier score. It is **not** enough for the standard multiclass Brier score or for class-wise ECE. Both need the full four-class vector, which the specialist already produces. Eliciting a full four-class distribution makes the panel directly comparable to the specialist. The cost is a frozen normalization rule, because schemas cannot force the values to sum to 1. This choice changes the "one confidence field" standing decision in #90, so it needs **human approval**.

## 1. Frozen baseline inputs used here

From `docs/stage-1-run.md` and `nlp_wayfinder/stage_run.py` on `issue-82-widened-rules`:

- Route `cx/gpt-5.6-sol-medium`, reasoning effort `medium`, one zero-shot prompt (`GPT_BLIND_SYSTEM_PROMPT`, about 110 words), and a strict schema `{label ∈ {positive, neutral, negative, insufficient evidence}}` with `additionalProperties: false`.
- Declared `max_tokens` is 2,048 (`GPT_MAX_OUTPUT_TOKENS`). The Codex transport strips it. See §2.
- Bounded input: the serialized passage, company, and aspect is at most **1,024 ModernBERT tokens**. There is no truncation. The test forecast uses 1,200 prompt tokens per example.
- Up to three identical attempts for transport failures only (5 s and 20 s delays).

The cost ceiling below is 1,024 + about 176 prompt and JSON overhead ≈ 1,200 tokens. Allowing +35% for tokenizer differences gives **1,600 input tokens**. Output uses the declared 2,048-token cap, which includes reasoning. For the "typical" case I assume 1,000 input and 600 output tokens. These are estimates, not measurements. Replace them with a non-blind development measurement, as the GPT forecast does.

## 2. GPT-5.6-sol (frozen)

**Route and snapshot.** OpenAI's [model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol) lists one snapshot, `gpt-5.6-sol`. The `gpt-5.6` alias routes to it. Reasoning efforts are `none`, `low`, `medium` (default), `high`, `xhigh`, and `max`. The frozen route stays `cx/gpt-5.6-sol-medium` through OmniRoute's Codex provider. The OmniRoute suffix sets effort, not a snapshot ([prior memo](comparison-systems-evidence.md), pinned [Codex executor](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/open-sse/executors/codex.ts)).

**Retirement risk on the frozen route.** The Codex [models page](https://learn.chatgpt.com/docs/models.md) now recommends GPT-6 Sol. It says "GPT-5.6 Sol, GPT-5.6 Terra, and GPT-5.6 Luna remain available during the rollout." It gives no end date. The API ID `gpt-5.6-sol` has no deprecation entry on the [deprecations page](https://developers.openai.com/api/docs/deprecations.md). It is a named replacement target there. #90 requires a fresh call with the frozen configuration. Calls through Codex could therefore fail later if the Codex route is withdrawn.

**Logprobs.** Not available on the frozen configuration:

- The GPT-6 guide ([Using GPT-6](https://developers.openai.com/api/docs/guides/latest-model)) says: "When reasoning effort is not `none`, remove `temperature`, `top_p`, and `top_logprobs`. For Chat Completions, also remove `logprobs`. For Responses, remove `message.output_text.logprobs` from `include`." The GPT-5.6 guide ([gpt-5.6](https://developers.openai.com/api/docs/guides/latest-model/gpt-5.6.md)) and the model page do not say either way. **Unverified for GPT-5.6-sol specifically**, but the frozen effort is `medium`, not `none`.
- The Responses API still defines `top_logprobs` (0–20) and `include: ["message.output_text.logprobs"]` ([reference](https://developers.openai.com/api/reference/resources/responses/methods/create.md)).
- The frozen transport's Codex executor keeps only an allowlist of Responses fields: `model, input, instructions, tools, tool_choice, stream, store, reasoning, service_tier, include, previous_response_id, prompt_cache_key, client_metadata, text`. It deletes `top_logprobs`, `temperature`, and `max_output_tokens` ([codex.ts, lines ~1442–1530](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/open-sse/executors/codex.ts)).
- A logprob signal would need effort `none` on the public API. That is a different configuration, not the frozen baseline.

**Strict schema with reasoning.** Supported. Structured outputs are listed for the model. The prior memo documents that `text.format` passes through the Codex executor. Adding a confidence field changes the frozen schema. Record it as a panel-only schema, and never rewrite the sealed Stage 1 file.

**Price.** USD 4 per 1M input tokens, USD 0.40 per 1M cached input tokens, and USD 20 per 1M output tokens, including reasoning. This promotional price holds "at least through November 21, 2026". Requests over 272K input tokens cost 2× input and 1.5× output. Batch is supported ([model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol)).

**Estimate (600 calls).**

| Case | Cost |
|---|---|
| Ceiling: 0.96M input, 1.23M output | **USD 28.42** shadow cost |
| Typical: 0.60M input, 0.36M output | **USD 9.60** |

Marginal external spend on the Codex Plus route is USD 0, within the plan's usage limits.

**Data use.**

- The API does not use data for training by default. Abuse-monitoring logs keep content for up to 30 days, and ZDR or Modified Abuse Monitoring are available on approval ([Your data](https://developers.openai.com/api/docs/guides/your-data)).
- The frozen route is a **personal ChatGPT plan through Codex**, not the API. OpenAI's Help Center article [“How your data is used to improve model performance”](https://help.openai.com/en/articles/5722486) says that on personal plans, content may be used for training unless "Improve the model for everyone" is off, and that this setting also applies to Codex. **Unverified:** the page returned HTTP 403 to automated fetch. This statement comes from the search index snippet. Confirm it in a browser, and record a screenshot of the setting in the route evidence.

## 3. Claude Opus 5.5

**Route and snapshot.** `claude-opus-5-5`. Anthropic says: "Every Claude model ID is a pinned snapshot, including the dateless IDs used from the 4.6 generation on" ([models overview](https://platform.claude.com/docs/en/about-claude/models/overview.md)). It was released on 2026-09-22 ([Opus 5.5 overview](https://platform.claude.com/docs/en/models/opus-5-5/overview.md)). The same ID is used on Google Cloud, Foundry, and Claude Platform on AWS. Bedrock uses `anthropic.claude-opus-5-5`. The [deprecations page](https://platform.claude.com/docs/en/about-claude/model-deprecations.md) says it is Active and retires "Not sooner than September 22, 2027". Use the first-party Claude API directly, not an aggregator alias. **Unverified:** whether the installed OmniRoute exposes an exact `claude-opus-5-5` route.

**Reasoning.** Adaptive thinking is always on. `thinking: {type: "disabled"}` and `budget_tokens` both return 400 at every effort level. The default effort is `medium` ([effort docs](https://platform.claude.com/docs/en/build-with-claude/effort.md)). Set `output_config.effort: "medium"` explicitly to match the GPT baseline's effort *name*. This does not mean the two models reason equally. Thinking tokens are billed as output and count against `max_tokens`. Sampling parameters are removed: the Messages API reference says models after Opus 4.6 reject any `temperature` other than 1.0.

**Strict schema.** Supported through `output_config.format` (JSON schema) and `strict: true` tools ([structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)). The only listed incompatibilities are Citations and assistant prefill, not thinking. Forced `tool_choice` (`any`/`tool`) returns 400 on Opus 5.5, so use `output_config.format`.

**Logprobs.** **None.** The full Messages API reference ([api/messages](https://platform.claude.com/docs/en/api/messages.md), about 1 MB) has no logprob parameter or field.

**Price.** USD 4 per 1M input tokens, USD 20 per 1M output tokens, and USD 0.20 per 1M cache hits. Batch is USD 2 input and USD 10 output ([pricing](https://platform.claude.com/docs/en/about-claude/pricing.md)).

**Estimate (600 calls).**

| Case | Standard | Batch |
|---|---|---|
| Ceiling | **USD 28.42** | **USD 14.21** |
| Typical | **USD 9.60** | USD 4.80 |

A 2,048-token cap can truncate a long thinking turn (`stop_reason: max_tokens`). Freeze how to score that as an abstention. Do not retry it.

**Data use.** Commercial API inputs and outputs are not used for training by default ([Privacy Center, 2026-08-18](https://privacy.claude.com/en/articles/7996868-is-my-data-used-for-model-training)). They are deleted within 30 days, except for Usage Policy enforcement, legal requirements, or agreed arrangements ([retention article, 2026-07-01](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data)). Flagged content may be kept for up to 2 years ([API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention.md)). Opus 5.5 is not listed as a Covered Model, which would carry mandatory 30-day retention; only Fable 5/5.1 and Mythos 5/5.1 are listed.

## 4. Google Gemini

**Which model is the "flagship"?** A human decision. Two candidates:

| | `gemini-3.8-flash` | `gemini-3.1-pro-preview` |
|---|---|---|
| Google description | "Our most intelligent Flash model"; subject of the current [latest-model page](https://ai.google.dev/gemini-api/docs/latest-model) | "Our 3rd generation Pro model"; the only current Pro text model |
| Status | **Stable**, released 2026-09-02, no shutdown date | **Preview**, released 2026-02-19, no shutdown date |
| Thinking | `low`, `medium` (default), `high`; `minimal` returns an error | Supported (levels not listed on model page) |
| Structured outputs | Supported | Supported |
| Price (paid, per 1M tokens) | USD 0.75 input and USD 3.75 output through 2026-12-31; USD 1.50 and USD 7.50 from 2027-01-01 | USD 2 input and USD 12 output (≤200K prompt) |
| 600 calls: ceiling / typical | **USD 5.33 / 1.80** (USD 10.66 / 3.60 at 2027 prices) | **USD 16.67 / 5.52** |

Sources: [models](https://ai.google.dev/gemini-api/docs/models), [3.8 Flash page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [3.1 Pro page](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview), [pricing](https://ai.google.dev/gemini-api/docs/pricing), [deprecations](https://ai.google.dev/gemini-api/docs/deprecations).

**Pinning.** Google defines stable IDs as follows: "Points to a specific stable model. Stable models usually don't change." Preview models "will be deprecated with at least 2 weeks notice" ([models, version patterns](https://ai.google.dev/gemini-api/docs/models)). Neither route is a dated immutable snapshot in the Anthropic sense. `gemini-3.8-flash` is the closer match to "exact route pinned". **Recommendation:** use `gemini-3.8-flash` at an explicit `thinking_level: "medium"`, and record the returned `modelVersion` on every call. `gemini-3.1-pro-preview` is the choice if "flagship" must mean the Pro tier. It carries the preview withdrawal risk.

**Logprobs.** **Not usable.** The Gemini API `GenerationConfig` still documents `responseLogprobs` and `logprobs` (0–20) ([API reference](https://ai.google.dev/api/generate-content)). Google Cloud's reference warns that the `responseLogprobs` and `logprobs` parameters are "deprecated for Gemini 3.x models and will soon be completely deprecated" ([Agent Platform inference reference, updated 2026-09-25](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/inference)). **Unverified (secondary):** developer-forum reports say the Gemini API returns an error for 3.x models ([forum](https://discuss.ai.google.dev/t/missing-logprobs-support-in-the-newest-gemini-models-3-1-pro-3-6-flash-on-vertex-ai-and-ai-studio/176557)).

**Data use.** Paid Services: "Google doesn't use your prompts … or responses to improve our products". Prompts and responses are logged "for a limited period of time" only for abuse detection. Unpaid Services, including AI Studio and the free quota, may use content to improve products, with human review ([Gemini API Additional Terms, effective 2026-03-23](https://ai.google.dev/gemini-api/terms)). The pricing table repeats this ("Used to improve our products: Free Yes / Paid No"). **Use a billing-enabled project only.**

## 5. Primary literature: top-label confidence vs a full four-class distribution

**What each metric needs.**

- *Top-label (confidence) ECE* bins the maximum predicted probability and compares it with accuracy. It needs only the predicted label and one confidence number ([Guo et al., ICML 2017](https://arxiv.org/abs/1706.04599)).
- The *multiclass Brier score* is the squared error summed over all classes ([Brier 1950](https://doi.org/10.1175/1520-0493(1950)078%3C0001:VOFEIT%3E2.0.CO;2)). It needs the full vector. With only a top-label confidence, only the binary "confidence vs correctness" Brier can be computed. That is a different number from the specialist's multiclass Brier.
- *Class-wise ECE* needs per-class probabilities ([Kull et al., NeurIPS 2019](https://arxiv.org/abs/1910.12656); [Nixon et al., 2019](https://arxiv.org/abs/1904.01685), which also finds that class-conditional measures give more effective evaluations).
- *Canonical* (full-vector) calibration is strictly stronger than confidence calibration ([Vaicenavicius et al., AISTATS 2019](https://arxiv.org/abs/1902.06977)).
- [Gupta & Ramdas (ICLR 2022)](https://arxiv.org/abs/2107.08353) argue that confidence calibration, which does not condition on the predicted class, is hard to interpret for decisions. They propose *top-label* calibration, which conditions on the predicted label. With four labels including `insufficient evidence`, a per-predicted-label reliability breakdown is a useful diagnostic.

**How well LLMs verbalize confidence.**

- [Tian et al. (EMNLP 2023)](https://arxiv.org/abs/2305.14975) studied ChatGPT, GPT-4, and Claude 2. Their verbalized confidences were "typically better-calibrated than the model's conditional probabilities", often cutting ECE by about 50% relative. Prompting the model "to produce several answer choices before giving its confidence scores significantly improves calibration" (their Verb. 1S/2S top-k prompts give k guesses, each with a probability). They also show RLHF worsens logprob calibration.
- [Xiong et al. (ICLR 2024)](https://arxiv.org/abs/2306.13063) found that verbalized confidence is overconfident and that values "predominantly fall within the 80% to 100% range and are typically in multiples of 5". With 10 fixed bins, most mass will sit in the top 2–3 bins, and the reliability diagram will be sparse elsewhere.
- [Yang et al. (2024)](https://arxiv.org/abs/2412.14737) found that reliability "strongly depends on how the model is asked". This supports one frozen prompt for all panel members.
- [Wang et al. (2024)](https://arxiv.org/abs/2410.06707) prompted Claude and Mixtral for full class distributions (2, 6, and 60 classes). The models can do it, but "some LLMs fail to produce probability distributions that sum to 1". Any rescaling must handle that. Post-hoc recalibration is out of scope for #90, so only the normalization rule matters here.
- [Lin, Hilton & Evans (TMLR 2022)](https://arxiv.org/abs/2205.14334) and [Kadavath et al. (2022)](https://arxiv.org/abs/2207.05221) are background. They show that models can express calibrated uncertainty in words or through P(True) in suitable formats.

**Estimation caveats.** Binned ECE is a biased estimator, and its bias grows with more bins and fewer samples ([Kumar et al., NeurIPS 2019](https://arxiv.org/abs/1909.10155)). Nixon et al. show that ranking conclusions change with binning choices. With about 600 examples, report bootstrap intervals and avoid ranking claims. This is already consistent with #90's "no winner" rule.

**Implication for the #90 design** (for a human decision, not decided here):

- **Option A, keep "one confidence field"** (top-label probability, 0–1). This is the smallest schema change. It supports top-label ECE, the reliability diagram, risk-coverage, and a *top-label binary Brier*. The specialist must then also be scored with the top-label binary Brier as the headline, so both sides use the same metric. Class-wise ECE is impossible for the panel.
- **Option B, a four-class distribution field** (four numbers in fixed label order, plus the label). This allows the multiclass Brier and class-wise ECE on the same footing as the specialist. Tian et al.'s evidence on considering alternatives suggests it may also reduce overconfidence. **Not established for this task.** It needs frozen rules for:
  1. a sum that is not 1 (for example, renormalize if the sum is within [0.9, 1.1], otherwise treat as malformed);
  2. `label` ≠ argmax (for example, the scored label is `label`, and its probability is the confidence);
  3. ties.

  JSON Schema cannot enforce the sum.

## 6. Open items before any panel freeze

- Confirm in a browser the ChatGPT "Improve the model for everyone" wording and state for the Codex account. Record it as route evidence.
- Confirm whether GPT-5.6-sol stays selectable in Codex through the Stage 1 addendum run. Decide the replacement rule if it is withdrawn. #90 lists this as not yet specified.
- Choose the Google model (§4) and Option A or B (§5).
- Run a non-blind development preflight for each route: schema, confidence field present, returned model identity (`model` / `modelVersion`), and measured tokens. Use the measured tokens to replace the estimates in this memo and set the panel's hard spend cap.
- Check that OmniRoute (if used for Anthropic or Google) exposes exact, non-aliased routes with no fallback. Otherwise, call the providers directly.
