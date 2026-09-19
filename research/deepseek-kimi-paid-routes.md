# Evidence memo: capped paid routes for DeepSeek and Kimi voters

**Retrieval date:** 2026-09-19 (all web sources, the installed OmniRoute package, and this repository at `50447e6`)
**Scope:** Evidence for [Find capped paid routes for DeepSeek and Kimi voters](https://github.com/neoyipeng2018/nlp-wayfinder/issues/73). It feeds [Choose the Chinese-model voter panel and paid cap](https://github.com/neoyipeng2018/nlp-wayfinder/issues/72). It builds on the [fourth free voter memo](https://github.com/neoyipeng2018/nlp-wayfinder/blob/84ec49a78a66b56cee73f2481b0f6533874fea23/research/fourth-free-voter.md). No model call was made. No OmniRoute configuration was changed. No account action was taken.

## Answer

- **Kimi:** use the official Moonshot API with `moonshot/kimi-k2.6`, thinking disabled. It has a prepaid balance and a project daily budget. The worst-case cost for 13,736 requests is **USD 37.36** before tax. The installed OmniRoute registry lists the exact ID.
- **DeepSeek:** the official DeepSeek API is the only route with a true prepaid hard stop. Its current name `deepseek-flash` is a moving name, not a fixed ID. DeepSeek says so in its own change log. The worst-case cost is **USD 11.54** at peak prices. It is admissible only if issue 72 accepts a named, time-boxed exception to the fixed-ID rule. Without that exception, no DeepSeek route passes both the fixed-ID rule and the hard-stop rule.
- **Cloudflare paid routes** (`@cf/deepseek-ai/deepseek-v4-flash-0731` and `@cf/moonshotai/kimi-k2.6`) have fixed IDs. They fail the hard stop. Workers Paid is billed after use, with no cap. It would also end the hard stop of the free GLM route on the same account. Prepaid AI Gateway credits need a request header that OmniRoute 3.8.50 cannot send to Cloudflare.
- **Total worst case for both recommended routes:** USD 48.90 at full repair reserve (USD 24.45 for first attempts only). The run rules now allow USD 0.00 for paid silver labels, and the other categories already add up to the USD 100 total. Issue 72 must find this money.

## Request size

The cost uses a worst case for each request.

- Passage: up to 1,024 ModernBERT tokens. Add 10% for a different tokenizer and JSON escaping: about 1,126 tokens.
- System prompt (`LABELING_SYSTEM_PROMPT`): 183 ModernBERT tokens.
- Vote schema (`_vote_request` in `nlp_wayfinder/stage_run.py`): 182 ModernBERT tokens, if the provider adds it to the prompt.
- User wrapper, company, aspect, and chat template: about 60 tokens.
- **Input: 1,600 tokens.** **Output: 300 tokens** (`VOTE_MAX_OUTPUT_TOKENS`).

The token counts come from the pinned ModernBERT tokenizer in this repository. A typical case uses the earlier memo's 800 input and 80 output tokens. Every figure below uses cache-miss input prices. A cache hit on the fixed system prompt would lower the real cost.

## Cost table

Prices are USD per 1M tokens. The cost is `requests × (1,600 × input + 300 × output) / 1,000,000`.

| Route | Input | Output | Worst case, 6,868 | Worst case, 13,736 | Typical, 13,736 | Hard stop |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| DeepSeek API `deepseek-flash`, peak | 0.30 | 1.20 | 5.77 | **11.54** | 4.62 | Yes, prepaid |
| DeepSeek API `deepseek-flash`, off-peak | 0.15 | 0.60 | 2.88 | 5.77 | 2.31 | Yes, prepaid |
| DeepSeek API `deepseek-v4-pro`, peak | 1.32 | 3.96 | 22.66 | 45.33 | 18.86 | Yes, prepaid |
| Cloudflare `@cf/deepseek-ai/deepseek-v4-flash-0731` | 0.44 | 1.32 | 7.55 | 15.11 | 6.29 | No |
| Kimi API `kimi-k2.6` | 0.95 | 4.00 | 18.68 | **37.36** | 14.83 | Yes, prepaid, if no card is stored |
| Cloudflare `@cf/moonshotai/kimi-k2.6` | 0.95 | 4.00 | 18.68 | 37.36 | 14.83 | No |
| Kimi API `kimi-k3` | 3.00 | 15.00 | 63.87 | 127.74 | 49.45 | Yes, but always reasons |

Add these to the Cloudflare rows: USD 5 a month for Workers Paid, or a 5% fee on AI Gateway credits. Kimi prices exclude tax.

Set the cap from the peak DeepSeek price. DeepSeek peak hours cover 35 hours of each week, and the collector cannot choose the hour of each call.

## DeepSeek

### Official DeepSeek API (first party)

- **Model and access.** The [Models & Pricing page](https://api-docs.deepseek.com/quick_start/pricing/) lists `deepseek-flash` (model version "DeepSeek-V4.1-Flash") and `deepseek-v4-pro` (model version "DeepSeek-V4-Pro-0813"). It says: "The legacy names `deepseek-v4-flash` and `deepseek-v4-flash-vision-exp` are still accepted, but the corresponding models have been retired, their requests are served by the DeepSeek-V4.1-Flash model and billed at the Flash price."
- **Not a fixed ID.** The [change log](https://api-docs.deepseek.com/updates) (2026-09-10) says: "Change the model name to deepseek-flash to call the latest V4.1 Flash model." For V4 Pro (2026-08-13) it says: "simply set the model name to deepseek-v4-pro to use the latest version." DeepSeek offers no dated snapshot name. So both names work like a `latest` alias, although neither contains a word in `FORBIDDEN_ROUTE_PARTS`.
- **Reasoning.** Thinking is on by default. `reasoning_effort: "none"` or `{"thinking": {"type": "disabled"}}` turns it off ([Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode), [Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion)). With thinking on, the reasoning would use the 300-token cap.
- **JSON.** Chat Completions accepts only `text` or `json_object` for `response_format` ([reference](https://api-docs.deepseek.com/api/create-chat-completion)). The [JSON Output guide](https://api-docs.deepseek.com/guides/json_mode) warns that "the API may occasionally return empty content." The [Responses API guide](https://api-docs.deepseek.com/guides/responses_api) says `text.format` is "fully supported". OmniRoute sends DeepSeek requests to that Responses endpoint (see below). Whether the strict schema reaches the model must be checked in the preflight.
- **Hard stop.** "The corresponding fees will be directly deducted from your topped-up balance or granted balance" ([pricing](https://api-docs.deepseek.com/quick_start/pricing/)). The [Open Platform Terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html) (effective 29 April 2026), section 6.1: "you may need to prepay for the Services ... we reserve the right to suspend or terminate Services if your balance is insufficient." An empty balance returns "402 - Insufficient Balance" ([Error Codes](https://api-docs.deepseek.com/quick_start/error_codes)). The docs describe no auto-recharge. Confirm in the console that none is set. Load only the cap amount. Refunds of an unspent balance are possible, less fees (section 6.3).
- **Rate limits.** No RPM or TPM limit. The concurrency limit is 2,500 for `deepseek-flash` and 500 for `deepseek-v4-pro`. Above it, the API returns 429 ([Rate Limit](https://api-docs.deepseek.com/quick_start/rate_limit)). Stage 1 can finish in hours.
- **Training use.** Terms section 4.2(3): "You may apply the Inputs and Outputs of the Services to a wide range of use cases, including personal use, academic research, derivative product development, training other models (such as model distillation), etc." Section 4.2(2) assigns output rights to the user. This clearly permits a narrow text classifier.
- **Data location and retention.** The [Privacy Policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html) (last update 10 February 2026): "we directly collect, process and store your Personal Data in People's Republic of China." Input is kept "for as long as you have an account." DeepSeek uses data "to train and improve our technology". The passages are published news text, so this is a disclosure point, not a blocker.
- **OmniRoute 3.8.50.** The `deepseek` provider (alias `ds`) lists only `deepseek-v4-pro` and `deepseek-v4-flash` (`open-sse/config/providers/registry/deepseek/index.ts`). It sends requests to `https://api.deepseek.com/responses`. `deepseek-flash` is not in the registry. Add it as a custom model in the dashboard, as was done for Mistral. `src/sse/services/model.ts` treats a custom model as available, even when the live catalog is authoritative. Do not use `ds/deepseek-v4-flash`: it is a retired name that DeepSeek now routes to another model. Do not use an effort suffix such as `deepseek-flash-none`: OmniRoute rewrites it to the base model, so the returned route would not match. No DeepSeek family fallback exists in `open-sse/services/modelFamilyFallback.ts`.

### Cloudflare Workers AI `@cf/deepseek-ai/deepseek-v4-flash-0731`

- **Model.** A dated ID. The [model page](https://developers.cloudflare.com/workers-ai/models/deepseek-v4-flash-0731/) calls it "the official release of DeepSeek-V4-Flash". It is a reasoning model. `reasoning_effort` accepts `low`, `medium`, or `high`, with no `none` value. Turning thinking off would need `chat_template_kwargs`. The weights use the MIT licence ([Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731)).
- **Paid access only.** "This model is not available through standard Workers Free billing. To use it, upgrade to the Workers Paid plan or use prepaid AI Gateway credits" ([pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)). So the earlier memo's free-pool figure for this model no longer applies.
- **Hard stop: fails.** Workers Paid charges USD 0.011 per 1,000 Neurons above the free grant, billed after use. No spend cap is documented. AI Gateway credits are prepaid, but "In rare instances, your credit balance may go negative. If this happens, Cloudflare will charge the payment method on file" ([Unified Billing](https://developers.cloudflare.com/ai-gateway/features/unified-billing/)). AI Gateway [spend limits](https://developers.cloudflare.com/ai-gateway/features/spend-limits/) "are eventually consistent" and "best-effort". Auto top-up exists and must stay off.
- **Side effect on GLM.** The GLM route's evidence in [issue 50](https://github.com/neoyipeng2018/nlp-wayfinder/issues/50) depends on "Workers Paid was not active" and no credits. Adding Workers Paid to that account would end GLM's hard stop. Any paid Cloudflare route needs a separate Cloudflare account.
- **Rate limits.** 20 requests per minute on Workers Paid, 50 with prepaid credits ([Limits](https://developers.cloudflare.com/workers-ai/platform/limits/)). 13,736 requests take about 11.4 hours at 20 per minute.
- **Terms and data.** Cloudflare does not train on Customer Content without consent. Content is stored only if a storage service is used ([Data usage](https://developers.cloudflare.com/workers-ai/platform/data-usage/), updated 21 April 2026). Processing is on Cloudflare's network, with no fixed region. MIT weights permit the use.
- **OmniRoute 3.8.50.** The `cloudflare-ai` registry does not list the ID and has `passthroughModels: false`. It needs a custom model. The credits path needs the `cf-aig-gateway-id` header. `open-sse/executors/cloudflare-ai.ts` sends only `Content-Type`, `Authorization`, and `Accept`, and it does not apply `customHeaders`. So OmniRoute cannot use prepaid credits without a code change.

## Kimi

### Official Kimi (Moonshot) API (first party)

- **Model and access.** The [model list](https://platform.kimi.ai/docs/models.md) has `kimi-k3`, `kimi-k2.7-code`, `kimi-k2.7-code-highspeed`, and `kimi-k2.6`. `kimi-k2.6` "Supports both visual and text input, thinking and non-thinking modes". It is a versioned name. The docs do not say it is updated in place. Old names were retired with a date (for example `kimi-latest` on 28 January 2026 and `kimi-k2.5` on 31 August 2026). Check the model list again before freezing.
- **Reasoning.** `kimi-k2.6` accepts `{"type": "enabled"}` (the default) and `{"type": "disabled"}`. `temperature` is fixed at 0.6 without thinking, and "other values return an error" ([Model Parameter Reference](https://platform.kimi.ai/docs/api/models-overview.md)). Thinking tokens count against `max_tokens` ([Thinking Models](https://platform.kimi.ai/docs/guide/use-thinking-models.md)), so thinking must be off under a 300-token cap. `kimi-k3` and `kimi-k2.7-code` always think, so they do not fit.
- **JSON.** `json_schema` Structured Output is supported. The guide warns that `kimi-k2.6` "occasionally behaves unstably with complex schemas" ([response_format](https://platform.kimi.ai/docs/guide/response_format.md)). The vote schema is flat, with no `$ref` or `oneOf`, so the risk is small. The collector already validates each answer.
- **Prices.** `kimi-k2.6`: USD 0.16 (cache hit), 0.95 (cache miss) input, 4.00 output per 1M tokens. Prices exclude tax ([pricing](https://platform.kimi.ai/docs/pricing/chat.md)).
- **Hard stop.** The account must be topped up to be used. Individual top-ups use WeChat Pay or Alipay QR payments ([Account and Billing](https://platform.kimi.ai/docs/guide/account-and-payments.md)). A project daily spending budget rejects all requests after the limit, "may take about 10 minutes to take effect". An empty balance returns `exceeded_current_quota_error`, and "Requests interrupted by a 429 error are not charged" ([Troubleshooting](https://platform.kimi.ai/docs/guide/troubleshooting.md)). **Caution:** the [Terms of Service](https://platform.kimi.ai/docs/agreement/modeluse) (last updated 30 July 2026), section 5.1, say that with a stored card "Moonshot AI may automatically charge the designated payment method for applicable fees, including usage-based charges". So the account must hold no stored card. Record that in the route evidence, with the daily budget set.
- **Rate limits.** Limits depend on the total amount topped up ([Recharge and Rate Limiting](https://platform.kimi.ai/docs/pricing/limits.md)). Tier 0 (USD 1) allows 3 RPM and 1.5M tokens a day, about 790 requests a day, or about 17 days for Stage 1. Tier 1 (USD 10) allows 100 RPM, 2M TPM, and no daily token limit. A cap above USD 10 reaches Tier 1, so 13,736 requests take about 2.3 hours.
- **Training use.** There is no clause that grants output use for training. Terms section 4: "You are solely responsible for content and we do not claim ownership of it." Section 3.2(5) forbids use "For developing, serving, or creating applications, products, Services, or models that have potential competitive possibilities with the Services without authorization." A narrow financial-sentiment classifier does not serve general chat or coding. It is a weaker grant than DeepSeek's. The reviewer must record a judgment, as for the Groq clause in [issue 48](https://github.com/neoyipeng2018/nlp-wayfinder/issues/48). Moonshot "may use Content to provide, maintain, develop, support, and improve the Services", unless an enterprise agreement says otherwise.
- **Data location and retention.** The [Open Platform Privacy Policy](https://platform.kimi.ai/docs/agreement/userprivacy) (last update 30 April 2025) is from Moonshot AI Pte. Ltd.: "We store the information we collect in secure servers located in Singapore." Input "is retained while your account is active." Singapore law governs the terms.
- **OmniRoute 3.8.50.** The `moonshot` provider lists `kimi-k2.6` and sends requests to `https://api.moonshot.ai/v1/chat/completions` (`open-sse/config/providers/registry/moonshot/index.ts`). No configuration change is needed. Use `moonshot/kimi-k2.6`, not `kimi/kimi-k2.6`, because the `kimi` provider forces upstream streaming. `open-sse/executors/moonshot.ts` removes `temperature` for `kimi-k2.6`. It sets `thinking: {"type": "disabled"}` only when the request carries `reasoning_effort: "none"`, `enable_thinking: false`, or that `thinking` value. Without one, the model thinks by default.
- **Licence of the open weights.** A modified MIT licence. Its only added condition applies to products with more than 100 million monthly users or USD 20 million monthly revenue ([LICENSE](https://huggingface.co/moonshotai/Kimi-K2.6/raw/main/LICENSE)). This matters only for the Cloudflare route, where the model licence governs.

### Cloudflare Workers AI `@cf/moonshotai/kimi-k2.6`

- The same ID and prices as the official API. It is now on the paid-only list ([pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)), so the earlier memo's free-pool figure no longer applies.
- It has the same hard-stop failure, GLM side effect, rate limits, and OmniRoute credits gap as the DeepSeek Cloudflare route. It is already in the installed registry.
- `reasoning_effort` accepts only `low`, `medium`, or `high` ([model page](https://developers.cloudflare.com/workers-ai/models/kimi-k2.6/)). OmniRoute does not remove `temperature` for Cloudflare.
- It has no advantage over the official API.

### Other first-party hosts

DeepSeek and Moonshot have no other first-party API for these models. Moonshot's China platform is the same company in another region. It was not reviewed.

## OmniRoute cost header

`x-omniroute-response-cost` is OmniRoute's own estimate. `open-sse/handlers/chatCore.ts` calls `calculateCost` (`src/lib/usage/costCalculator.ts`), which reads OmniRoute's pricing table. It returns 0 when no price is found, for example for a new custom model. The static pricing tables in the package (`src/shared/constants/pricing/`) have no `deepseek-flash` or `kimi-k2.6` entry. Synced prices in the local database were not checked. Its DeepSeek comment says it uses off-peak prices, "a deliberate, documented undercount". The header is not a billing record. It cannot enforce a cap.

## Required rule and code changes

1. **Budget.** `BUDGET_LIMITS["paid-silver-labels"]` is `0.00`, and the categories already add up to `TOTAL_BUDGET_LIMIT` (USD 100). Issue 72 must set a cap for each route and find the money. The map's out-of-scope rule on paid silver-label calls must change. Record a `record-cost` commitment equal to each route's cap before collection.
2. **Route kind.** Add a capped-paid route kind. `_route_evidence_reason` now requires `account_no_paid_overflow` to be true and integer `observed_free_requests_remaining` and `observed_requests_per_day` that match the route. `ROUTE_ELIGIBILITY_FIELDS` requires `account_free_limit_verified` and `no_paid_overflow`. A capped route needs other evidence: prepaid balance, no auto-recharge, no stored card (Kimi), daily budget (Kimi), cap in USD, frozen input and output prices with URL and retrieval date, and the worst-case request size.
3. **Capacity gate.** The `route-demand-exceeds-free-capacity` check compares free requests with demand. For a capped route, compare `floor(cap / worst-case cost of one request)` with `remaining_experiment_requests` instead.
4. **Paid response check.** `_vote_attempt` turns any nonzero `x-omniroute-response-cost` into `paid-overflow` and stops. For a capped route, accept a paid response. Keep a running cost from `usage` tokens × the frozen peak prices. Do not trust the header. Stop before the next request could pass the cap.
5. **Balance exhaustion.** DeepSeek returns HTTP 402 "Insufficient Balance". `_is_free_limit` does not match it, so the vote becomes a `transport-error` abstention. That abstention is kept, so the vote is never collected again, and the loop moves on to the next item. Add a stop reason, such as `prepaid-balance-exhausted`, for 402 and balance errors. Kimi's `exceeded_current_quota_error` contains "quota", so it already stops as `free-limit-failure`. Give it the same new reason.
6. **Fixed request fields for each route.** `_vote_request` is the same for all routes. A capped route needs frozen extra fields: `reasoning_effort: "none"` for DeepSeek, and `thinking: {"type": "disabled"}` (or `reasoning_effort: "none"`) for Kimi. It may need `response_format: {"type": "json_object"}` for DeepSeek, if the preflight shows the strict schema is dropped. Freeze these fields in the route record and in the request hash.
7. **Fixed-ID exception (DeepSeek only).** If issue 72 admits `ds/deepseek-flash`, record the model version from the pricing page (DeepSeek-V4.1-Flash) and the change-log date (2026-09-10) in the route evidence. Run all DeepSeek votes in one short window. Check the change log again at the end, and void the route if a new Flash version appeared.
8. **OmniRoute.** Add `deepseek-flash` as a custom model on the `deepseek` provider. Kimi needs no change. A Cloudflare paid route would also need a custom model for DeepSeek and a code change for the credits header.
9. **Docs.** Update `docs/stage-1-run.md` (route evidence, about lines 244–260; repair and stop rules, about lines 313–323) to match items 2 to 6.
10. **Preflight.** One separately approved non-label call for each route. It must show the exact returned provider and model, `strategy=single`, no fallback, no cache, no reasoning tokens, and valid schema JSON under 300 tokens.

## Schedule effect of paid GLM or Qwen

- **Qwen (Groq free)** allows 500,000 requests a day ([issue 50](https://github.com/neoyipeng2018/nlp-wayfinder/issues/50)). Stage 1 fits in one day. A paid route would not help.
- **GLM (Cloudflare free)** is the bottleneck. At the worst-case size, `@cf/zai-org/glm-4.7-flash` uses 19.7 Neurons for each request (5,500 input and 36,400 output Neurons per 1M tokens, [pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)). That is about 507 requests a day: 13.5 days for first attempts and 27.1 days with the full reserve. At the typical size it is 5.0 and 10.0 days. Adding Gemma to the same pool roughly doubles these figures.
- A paid GLM route would cost only about USD 3 at full reserve. But on Cloudflare it needs Workers Paid, which has no hard stop, or credits, which OmniRoute cannot use. So it does not meet the cap rule now.
- DeepSeek and Kimi on their official APIs finish in hours. They do not slow the schedule. GLM's free pool still sets the Stage 1 finish date.
