# Evidence memo: freeze the comparison systems and prompts

**Retrieval date:** 2026-09-03  
**Scope:** Evidence for [“Freeze the comparison systems and prompts”](https://github.com/neoyipeng2018/nlp-wayfinder/issues/11). This memo uses only official papers, documentation, model cards, and code repositories. It makes no paid model call.

## Decision summary

No published system is an exact comparator for this project. The project task combines a supplied company or macro target, a supplied aspect, two family-specific four-label schemes, and five source types. The best published result is useful as literature context, but it cannot be the parity system. The parity system must be an **experiment-built, development-selected specialist**.

Use the fixed `answerdotai/ModernBERT-base` revision below as the only initialization for that specialist. Do not call this base model a financial specialist or a published SOTA system. Train and select the task-specific checkpoint on the frozen development set. Freeze that selected checkpoint before access to blind labels.

For the GPT comparison, the installed OmniRoute setup exposes the mutable route `cx/gpt-5.6-sol` and effort suffixes. It does not expose a dated GPT-5.6 Sol snapshot. The most explicit present route is `cx/gpt-5.6-sol-medium`. In OmniRoute, all effort suffixes map to the same upstream `gpt-5.6-sol` name. The `ultra` suffix maps to official effort `max`; it is not a separate OpenAI model or effort level.

## 1. Specialist comparison

### Closest published SOTA: literature context only

Straleger and Frasincar's **FinRoBERTa-TRC2 with HiAGM** is the closest current published SOTA result. The publisher states that it reduces FiQA mean squared error by 5.6% against the prior SOTA. It predicts hierarchical FiQA aspects and continuous sentiment, mainly from financial news and social text. It does not implement this project's supplied-aspect interface, macro-direction labels, `insufficient evidence` label, or five-source test.

- Paper: [Hierarchical aspect-based sentiment analysis Using FinRoBERTa](https://doi.org/10.1016/j.datak.2026.102634), published online 2026-08-04.
- Code revision: [`slstraleger/FinRoBERTa@3df433929b32a1544a0c844fcd464f400e524feb`](https://github.com/slstraleger/FinRoBERTa/tree/3df433929b32a1544a0c844fcd464f400e524feb).
- Reproducibility limits: the repository has no license, release, dependency lock, final checkpoint, or complete data setup. It uses local paths and TRC2-derived weights. Reuters TRC2 access needs signed organization and individual agreements under the [official NIST access process](https://trec.nist.gov/data/reuters/reuters.html).

Therefore, report this result as **published SOTA context**, not as a runnable parity comparator.

### Closest runnable historical control

`amphora/FinABSA` is the closest fixed, runnable, target-conditioned financial checkpoint found. It replaces the target entity with `[TGT]` and uses a T5-Large model to generate `positive`, `neutral`, or `negative` on SEntFiN.

- Checkpoint: [`amphora/FinABSA@10a5aa4701f7c7bddba2a5cd4c44d7e817c0a2d9`](https://huggingface.co/amphora/FinABSA/tree/10a5aa4701f7c7bddba2a5cd4c44d7e817c0a2d9).
- Code: [`guijinSON/FinABSA@23f7172d246662bff269d3234bc13af0f60fbe11`](https://github.com/guijinSON/FinABSA/tree/23f7172d246662bff269d3234bc13af0f60fbe11).
- License: Apache-2.0 in the model card and code repository.
- Limits: the repository reports 87% accuracy on an “arbitrarily extracted” SEntFiN split and warns that longer input reduces performance. The model has no supplied aspect, macro target or direction label, `insufficient evidence`, or five-source coverage.

Use FinABSA only as a **runnable historical control**. Do not use it as the parity specialist.

### Exact parity specialist

Build the parity specialist in this experiment. Use this base model:

- Base checkpoint: [`answerdotai/ModernBERT-base@8949b909ec900327062f0ebf497f51aef5e6f0c8`](https://huggingface.co/answerdotai/ModernBERT-base/tree/8949b909ec900327062f0ebf497f51aef5e6f0c8).
- Training code source: [`AnswerDotAI/ModernBERT@c6d942312f1b0b24d423628b8e477a3e97c7038f`](https://github.com/AnswerDotAI/ModernBERT/tree/c6d942312f1b0b24d423628b8e477a3e97c7038f).
- License: Apache-2.0.
- Limit: this is a 149M-parameter masked-language base model. It is not a trained financial classifier.

Call the final system the **experiment-built, development-selected specialist**. Before blind evaluation, record the training-code commit, data-manifest hash, base revision, preprocessing, random seeds, hyperparameters, calibration method, selection metric and tie rule, inference-code commit, and final checkpoint SHA-256.

## 2. GPT-5.6 Sol through OmniRoute

### Model identity and reasoning

The installed OmniRoute version is 3.8.49. Its fixed upstream source revision is [`c9d4a45f1883d7daf150bbff631f3e83b41aa5b4`](https://github.com/diegosouzapw/OmniRoute/tree/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4). The local authenticated provider is `codex`, alias `cx`, and it uses the ChatGPT Codex Responses endpoint. Inventory shows `cx/gpt-5.6-sol`, but no paid or authorized smoke test was made.

OpenAI's [official GPT-5.6 Sol model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol) names `gpt-5.6-sol` and currently lists no dated immutable snapshot. It lists reasoning efforts `none`, `low`, `medium` (default), `high`, `xhigh`, and `max`. The page states a 1.05M context window and 128K maximum output for the public API.

OmniRoute publishes the base route plus `-low`, `-medium`, `-high`, `-xhigh`, `-max`, and `-ultra` variants in its [Codex provider registry](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/open-sse/config/providers/registry/codex/index.ts). Its [Codex executor](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/open-sse/executors/codex.ts) strips the suffix before the upstream call. `ultra` maps to `max`. Thus, a route suffix fixes effort, not a model snapshot.

Recommended freeze: `cx/gpt-5.6-sol-medium`, standard reasoning mode, and the exact OmniRoute 3.8.49 source revision. Record returned model, provider, request ID, OmniRoute version, date, and usage for every item. State that the upstream model can drift because there is no dated snapshot.

### Output and decoding controls

OpenAI's [Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) supports strict JSON Schema through `text.format`. It documents `temperature` and `top_p`, but no `seed` field. It says that `max_output_tokens` includes visible output and reasoning tokens.

OmniRoute's [Chat-to-Responses translator](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/open-sse/translator/request/openai-responses/toResponses.ts) maps a JSON-schema response format to `text.format`. The Codex executor permits `text`, so the schema should pass through. This still needs one authorized, non-blind smoke test before the freeze.

The Chat compatibility path copies `temperature` and `top_p`, but the Codex executor allowlist removes them. It does not map `seed`. The executor also removes `max_tokens` and `max_output_tokens` because the Codex backend rejects them. Therefore, this transport does not give an effective seed or a fixed output-token limit, and its Chat path does not give effective sampling controls. Freeze these fields as omitted. Do not claim deterministic output.

### Retries and failure handling

OmniRoute has hidden transport retries. Its executor retry configuration allows two same-URL retries after a 429. Its [chat handler](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/open-sse/handlers/chatCore.ts) can also make up to three attempts and rotate Codex accounts after a 429. The current setup has one Codex account, so account rotation cannot add another account. A lower network layer can retry one transient connection failure.

Freeze zero application-level semantic or schema-repair retries. Log every visible attempt, retry ordinal, terminal error, invalid schema, refusal, timeout, token usage, latency, and fallback count. Score terminal failures as errors in the primary metric. This prevents favorable removal of hard examples. Hidden transport retries still limit exact replay.

### Cost fields

The official model page currently lists promotional prices of **$4 per 1M input tokens, $0.40 per 1M cached input tokens, and $20 per 1M output tokens**, through at least 2026-11-21. Requests with more than 272K input tokens use 2× input pricing and 1.5× output pricing for the full request. Cache writes cost 1.25× uncached input. Output usage includes reasoning tokens.

For each actual attempt, store input, cached-input, cache-write, visible-output, reasoning-output, and total tokens when the response provides them. Also store the non-streaming OmniRoute fields described in its [OpenAPI file](https://github.com/diegosouzapw/OmniRoute/blob/c9d4a45f1883d7daf150bbff631f3e83b41aa5b4/docs/openapi.yaml): response cost, tokens in and out, model, provider, latency, cache hit, fallback attempts, request ID, and version.

Keep two cost totals:

1. **Marginal external spend:** presently zero for an included Plus OAuth route, subject to account terms and capacity.
2. **Shadow API-equivalent cost:** calculate from the frozen official price table and all attempts, including retries.

Do not use OmniRoute's local price table as the primary price source. At this revision it still lists $5 input, $0.50 cached input, and $30 output for GPT-5.6 Sol, which conflicts with the current official prices.

## 3. Human decisions required before freeze

1. Confirm that published FinRoBERTa-TRC2 is literature context, FinABSA is an optional historical control, and the parity result is the development-selected specialist.
2. Use the pinned ModernBERT Base checkpoint as the only specialist initialization. Freeze the development metric, tie rule, calibration, seeds, and all artifact hashes. Do not run model-candidate selection.
3. Choose the transport: the present Codex Plus OAuth route, with no dated snapshot and no marginal API charge, or a public OpenAI API route with a separate billing and control record. Confirm that subscription use is permitted for this evaluation.
4. Freeze `medium` or another reasoning effort on development data. If `medium` is chosen, use `cx/gpt-5.6-sol-medium`. Do not describe `ultra` as an official effort.
5. Freeze one prompt after development-only work. Decide zero-shot or fixed demonstrations. If demonstrations are used, record their IDs, order, text, source split, and hashes. Do not use blind examples or labels during prompt development.
6. Freeze the strict JSON Schema. Decide whether to use one family-specific schema per target family or one unified schema. Define all enum values and evidence fields.
7. Accept omitted seed, sampling, and output-limit fields for this transport, or change transport before the freeze. Record that the selected route is not deterministic.
8. Confirm zero semantic-repair retries, the treatment of hidden transport retries, and that all terminal failures count as errors.
9. Freeze the price date and both cost ledgers. Count every attempt, including retries.
10. Commit and hash the route, prompt, demonstrations, schema, collector, specialist artifacts, and scoring rules before blind-label access. After the freeze, allow only documented mechanical fixes that do not use blind labels.

## Reproducibility conclusion

The specialist can be artifact-reproducible if every training and selection input is pinned. The GPT comparison cannot be bit-reproducible through the present route: there is no dated model snapshot, no seed, some controls are removed, and OmniRoute can retry internally. It can still be audit-reproducible if the project freezes the route and prompt contract, isolates all development from the blind set, logs every request and response field, counts failures, and records model and transport provenance for each item.
