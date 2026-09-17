# Replacement for unavailable Mistral Medium 3.5

**Checked:** 2026-09-18

**Scope:** This memo answers [Research a replacement for unavailable Mistral Medium 3.5](https://github.com/neoyipeng2018/nlp-wayfinder/issues/64). It does not change the Cloudflare or Groq routes. It does not use automatic routing, fallback, or a model call.

## Decision

No current replacement is ready for Stage 1 admission from public evidence alone. Use `mistral/mistral-small-2603` as the replacement candidate. This route names Mistral Small 4 with a fixed GA model ID. Do not admit it to Stage 1 yet. Yi Peng must first record the account evidence and the conservative capacity conversion in this memo.

Do not use `mistral/mistral-small-latest`. Mistral states that a `latest` alias can change without a route-name change. A major-and-minor ID is fixed. The Stage 1 control also rejects a route that contains `latest`. See the [Mistral model lifecycle policy](https://docs.mistral.ai/inference/model-lifecycle), the pinned [forbidden route parts](https://github.com/neoyipeng2018/nlp-wayfinder/blob/50447e60fce42bce925716c64247ac361f10b3ac/nlp_wayfinder/stage_run.py#L258), and the pinned [fixed-route check](https://github.com/neoyipeng2018/nlp-wayfinder/blob/50447e60fce42bce925716c64247ac361f10b3ac/nlp_wayfinder/stage_run.py#L397-L401).

This is the best current route for these reasons:

- Mistral lists `mistral-small-2603` as the exact model ID for Mistral Small 4. The model is GA, uses Apache 2.0, supports Chat Completions and Structured Outputs, and has a 256,000-token context window. Its public price is USD 0.15 per million input tokens and USD 0.60 per million output tokens. See the official [Mistral Small 4 model page](https://docs.mistral.ai/models/mistral-small-4-0-26-03).
- The current Mistral commercial terms give the customer ownership of text output. The only output-training restriction in section 3.3 applies to image output used to train a competing image product. The planned artifact is a text label used to train a narrow text classifier. The terms therefore permit this use, subject to the input-rights requirement in section 3.2. See sections 3.1 to 3.3 of the [Mistral Commercial Terms](https://legal.mistral.ai/terms/commercial-terms-of-service/).
- The existing account review found Free mode, USD 10 of included API use, USD 0 used, no payment method or credits, and pay-as-you-go off. This is account evidence for the shared Mistral organization, not evidence that the new exact model is available. See [Record current fixed-route account evidence](https://github.com/neoyipeng2018/nlp-wayfinder/issues/50#issuecomment-5716034404).
- Mistral states that Free mode uses included monthly usage and the account Limits page. The page gives per-model tokens per minute and requests per second. Pay-as-you-go is the control that extends use beyond included monthly usage. See [Usage and limits](https://docs.mistral.ai/admin/billing-usage/usage-limits). Mistral also states that pay-as-you-go is off by default and that use stops after included usage when it is off. See [API keys and profiles](https://docs.mistral.ai/vibe/code/cli/api-keys-profiles).

## Stage 1 demand

Stage 1 can inspect no more than 6,668 silver-training candidates and sends the 200 development examples to each route. It therefore needs 6,868 first attempts from each route. One malformed answer can have one identical repair attempt. The confirmed route schedule must add a repair reserve. See the pinned [silver-candidate limit](https://github.com/neoyipeng2018/nlp-wayfinder/blob/50447e60fce42bce925716c64247ac361f10b3ac/docs/stage-1-run.md#L153-L158), [development target](https://github.com/neoyipeng2018/nlp-wayfinder/blob/50447e60fce42bce925716c64247ac361f10b3ac/docs/stage-1-run.md#L209-L214), and [repair rule](https://github.com/neoyipeng2018/nlp-wayfinder/blob/50447e60fce42bce925716c64247ac361f10b3ac/docs/stage-1-run.md#L307-L317).

The strongest safe reserve is one repair for every first attempt. This gives 13,736 maximum requests. The collector limits output to 300 tokens. At the public Mistral Small 4 prices, a full-repair run fits a remaining USD 10 allowance if every request has no more than 3,653 Mistral input tokens and every response uses all 300 output tokens:

```text
floor((10,000,000 / 13,736 - 0.60 * 300) / 0.15) = 3,653 input tokens
```

This is a limit test, not current capacity evidence. The 1,024-token admission limit uses the ModernBERT tokenizer. It does not prove the Mistral token count. After the candidate set is sealed, count the exact fixed system prompt, user JSON, and schema with the Mistral tokenizer for each request. Reject the route if the largest request exceeds 3,653 Mistral input tokens or if the current included balance is less than USD 10. A smaller repair reserve can use a new calculation, but it must be set before zero-change confirmation.

The Stage 1 schedule is not yet approved. [Approve the Stage 1 route panel and schedule](https://github.com/neoyipeng2018/nlp-wayfinder/issues/52) remains open. Therefore, current public sources cannot prove a finish date. The account capture must convert the current requests-per-second and tokens-per-minute limits into a conservative daily request count:

```text
requests_per_day = min(
  floor(requests_per_second * 86,400),
  floor(tokens_per_minute * 1,440 / maximum_tokens_per_attempt)
)
```

`maximum_tokens_per_attempt` must include the complete input and the 300-token output allowance. The route has enough schedule capacity only if `ceil(current_stage_requests / requests_per_day)` is no more than `available_days` and the free-balance conversion covers `remaining_experiment_requests`.

## Exact route and OmniRoute

Mistral documents `mistral-small-2603` as a fixed provider ID. Its Models API lists all models available to the user. Use `GET /v1/models` or `GET /v1/models/mistral-small-2603` for the account-only identity check. See the [Mistral Models API](https://docs.mistral.ai/api/endpoint/models).

OmniRoute release `v3.8.51` does not advertise the fixed Small 4 ID in its static Mistral list. It advertises only `mistral-small-latest`. However, its parser treats `provider/model` as an explicit route and passes the provider-scoped model ID without alias selection. See the pinned [Mistral registry](https://github.com/diegosouzapw/OmniRoute/blob/d8ad12f22d1654be632f9d385e8ec945c674cf23/open-sse/config/providers/registry/mistral/index.ts#L3-L17) and [explicit-route parser](https://github.com/diegosouzapw/OmniRoute/blob/d8ad12f22d1654be632f9d385e8ec945c674cf23/open-sse/services/model.ts#L451-L477).

This source behavior is necessary but not sufficient. Before admission, one non-label preflight must request `mistral/mistral-small-2603` through the dedicated Mistral provider endpoint. Keep the response model, OmniRoute provider and model headers, decision strategy, fallback-attempt count, cache result, token counts, cost, request ID, and OmniRoute version. The observed provider and model must reconstruct the same exact route. Any alias, substitution, fallback attempt, cache hit, or paid response rejects the route.

## Why not use another Groq route

Groq lists `qwen/qwen3.8-27b` as a current preview model. Its public Free table gives 1,000 requests per day, 8,000 tokens per minute, and 200,000 tokens per day. See the official [Groq model catalog](https://console.groq.com/docs/models) and [rate-limit table](https://console.groq.com/docs/rate-limits). This model is not the recommended replacement:

- It would add a second Groq route and a second Qwen-family vote. Mistral Small 4 preserves the original three-provider and three-family shape.
- The public daily limits do not prove `observed_free_requests_remaining >= remaining_experiment_requests`. Account evidence can differ from the public table.
- It is a preview model, not GA.
- The current OmniRoute Groq registry does not list Qwen3.8. See the pinned [Groq registry](https://github.com/diegosouzapw/OmniRoute/blob/d8ad12f22d1654be632f9d385e8ec945c674cf23/open-sse/config/providers/registry/groq/index.ts).

Do not change the existing `groq/qwen/qwen3.6-27b` route.

## Required account record

Save one dated evidence record no more than 30 days before `starts_on`. Remove all secrets. It must contain:

1. Organization and workspace names.
2. API plan `Free`, the current included allowance, current used amount, and remaining included amount.
3. No payment method, no bought credits, and pay-as-you-go off. These facts set `account_no_paid_overflow` to `true`.
4. An account-scoped Models API response that contains the exact ID `mistral-small-2603` and shows Chat Completions support.
5. The account Limits values for `mistral-small-2603`: requests per second and tokens per minute. Keep the raw values and UTC capture time.
6. The sealed maximum Mistral input-token count, the 300-token output cap, the repair reserve, the current public prices, and the calculations for `observed_free_requests_remaining` and `observed_requests_per_day`.
7. The exact terms URL, retrieval time, reviewer, audited object `Mistral Small 4 text labels`, and sections 3.1 to 3.3 as the training-use evidence.
8. The non-label OmniRoute preflight record described above.

The manifest values `free_requests_remaining` and `requests_per_day` must equal these conservative converted values. Do not copy the USD allowance, requests per second, or tokens per minute into a request-count field.

## Result

`mistral/mistral-small-2603` is the recommended replacement candidate. It preserves a fixed non-GPT route and the current Mistral training-use permission. The existing account state can also preserve a hard no-paid-overflow rule. It is not eligible until the exact model appears in Yi Peng's account and the sealed capacity conversion proves that the approved Stage 1 schedule fits. If either check fails, do not use `latest`, another Mistral model, automatic routing, fallback, or paid overflow.

A new HITL task ticket is needed: **Record Mistral Small 4 replacement account evidence**. The task must collect the eight items above. It must get separate approval before the non-label preflight because the map requires approval before each external-service phase. **Approve the Stage 1 route panel and schedule** must wait for this task.
