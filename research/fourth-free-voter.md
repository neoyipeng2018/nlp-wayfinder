# Evidence memo: a fourth free silver-label voter

**Retrieval date:** 2026-09-19 (all web sources and the local catalog)
**Scope:** Evidence for [Screen OmniRoute free providers for a fourth silver-label voter](https://github.com/neoyipeng2018/nlp-wayfinder/issues/71). It feeds [Choose a fourth free silver-label voter](https://github.com/neoyipeng2018/nlp-wayfinder/issues/72). This memo uses the installed OmniRoute package, the local catalog, official provider pages, and official model licenses. It makes no model call and changes no OmniRoute configuration.

## Answer

Only one route is a practical fourth voter now: `cf/@cf/google/gemma-4-26b-a4b-it`.

It is a Gemma model. Gemma 4 uses Apache 2.0. Cloudflare gives it the same official free allocation and the same hard stop as the GLM voter. The installed OmniRoute registry lists the exact ID. The cost is that it shares the Cloudflare daily pool with `cf/@cf/zai-org/glm-4.7-flash`. Stage 1 first attempts for both routes need about 12 daily grants. A full repair reserve needs about 23.

The next choice, `cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast`, is also valid. It is four times as expensive in Neurons, so Stage 1 needs about 31 days of the shared pool.

No other free provider in the catalog passes all rules. Most fail on the family, the free limit, or the terms.

## Short list

| Rank | Route | Family | Licence | Stage 1 days, shared CF pool (first attempts / full repair) | Main risk |
| ---: | --- | --- | --- | --- | --- |
| 1 | `cf/@cf/google/gemma-4-26b-a4b-it` | Gemma (Google) | Apache 2.0 | 11.5 / 23.0 | Shares the GLM pool. Not on Cloudflare's JSON-mode list. |
| 2 | `cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast` | Llama (Meta) | Llama 3.3 Community | 30.9 / 61.9 | Slow. Naming rule if the student is ever distributed. |
| 3 | `sealion/aisingapore/Llama-SEA-LION-v3.5-70B-R` | Llama (AI Singapore fine-tune) | Llama 3.1 Community | No daily cap published | Reasoning model under a 300-token cap. The free status is called a "trial" key. |
| 4 | `cf/@cf/moonshotai/kimi-k2.6` | Kimi (Moonshot) | Modified MIT ("other") | 72.5 / 144.9 | Too slow for a shared pool. Check the licence text. |

The day counts use the planning size of the earlier memo: 800 input and 80 output tokens for each vote. They count 6,868 first attempts for each route, or 13,736 with one repair for each. They add the GLM route's use because both routes draw on one 10,000-Neuron daily grant. At the 300-token output cap, Gemma alone rises from 9.45 to 15.45 Neurons for each vote.

### 1. `cf/@cf/google/gemma-4-26b-a4b-it`

- **Model ID.** Cloudflare lists the exact ID `@cf/google/gemma-4-26b-a4b-it`, with Google as author and a 256,000-token context. It has no beta or deprecation note. See the [Cloudflare model page](https://developers.cloudflare.com/workers-ai/models/gemma-4-26b-a4b-it/). The installed OmniRoute 3.8.50 registry lists the same ID under `cloudflare-ai` (alias `cf`) at `open-sse/config/providers/registry/cloudflare-ai/index.ts`.
- **Free limit.** Workers AI gives 10,000 Neurons each day. On the Free plan, "further operations will fail with an error" above the limit. The model uses 9,091 Neurons for 1M input tokens and 27,273 for 1M output tokens. See [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/).
- **Terms.** The customer owns the input and output. Cloudflare does not train on it without consent. Third-party model licences still apply. See [Your Data and Workers AI](https://developers.cloudflare.com/workers-ai/platform/data-usage/). Gemma 4 uses Apache 2.0, not the older Gemma Terms. See the [Gemma 4 licence page](https://ai.google.dev/gemma/docs/gemma_4_license) and the [model card](https://huggingface.co/google/gemma-4-26B-A4B-it). This removes the "Model Derivative" condition that the earlier memo noted for older Gemma models. The linked Prohibited Use Policy still applies to the model. It does not target a sentiment classifier.
- **JSON.** Cloudflare's JSON-mode list does not include this model. It does not include the GLM voter either. Cloudflare also says it "can't guarantee that the model responds according to the requested JSON Schema". See [JSON Mode](https://developers.cloudflare.com/workers-ai/features/json-mode/). The Stage 1 collector already treats a bad answer as malformed and gives one repair, so this is a quality risk, not a rule failure. Measure it in the preflight.
- **Financial evidence.** None for Gemma 4. For older Gemma models: FLaME reports FPB F1 of .884 for Gemma 2 27B and .940 for Gemma 2 9B ([Matlin et al. 2025, Table 2](https://arxiv.org/html/2506.15846v1)). On target-based Bloomberg news, zero-shot macro-F1 is 0.69 for Gemma 2 27B and 0.66 for Gemma 2 9B, against 0.77 for ChatGPT-4o and 0.81 for DeepSeek-R1 ([Muhammad et al. 2025, Table 3](https://aclanthology.org/2025.clicit-1.74.pdf)). The target-based figure is the closer match to this task.

### 2. `cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast`

- Same Cloudflare account, free limit, hard stop, and data terms as route 1. The installed registry lists the exact ID. See the [pricing page](https://developers.cloudflare.com/workers-ai/platform/pricing/).
- It is the only non-excluded family on Cloudflare's [JSON-mode list](https://developers.cloudflare.com/workers-ai/features/json-mode/).
- It costs 26,668 input and 204,805 output Neurons for each 1M tokens. That is about 37.7 Neurons for each vote, four times Gemma.
- The [Llama 3.3 licence](https://developer.meta.com/ai/llama3_3/license/) (6 December 2024) permits training on outputs. If a model trained on outputs "is distributed or made available", its name must begin with "Llama" (Section 1.b.i). An internal student is not affected.
- **Financial evidence.** None for Llama 3.3. FLaME reports FPB F1 of .902 for Llama 3 70B Instruct. Target-based macro-F1 for Llama 3 8B is 0.63 zero-shot. No published target-based figure exists for a 70B Llama.

### 3. `sealion/aisingapore/Llama-SEA-LION-v3.5-70B-R`

- AI Singapore runs the API. It is the model maker's own service. The installed registry lists the exact ID at `https://api.sea-lion.ai/v1/chat/completions`.
- The only published limit is "10 requests per minute per user" (as of 4 June 2026). The docs call the keys "trial API keys". They publish no daily cap and no paid plan. See [SEA-LION API](https://docs.sea-lion.ai/guides/inferencing/api).
- The user keeps ownership of content. AI Singapore may use content to improve its services. The terms are silent on training other models on outputs. See [Terms of Use](https://sea-lion.ai/terms-of-use/) (19 November 2024). The model uses the Llama 3.1 licence, which has the same naming rule as Llama 3.3.
- The "R" model is a reasoning model. A 300-token output cap may cut its answer. It is a Llama fine-tune, so it gives the same family as route 2.
- **Financial evidence.** None.
- **Result:** conditional. It needs written confirmation of the free quota and a preflight.

### 4. `cf/@cf/moonshotai/kimi-k2.6`

- Listed in the installed registry. Kimi is a new family. It costs 86,364 input and 363,636 output Neurons for each 1M tokens.
- The shared pool makes Stage 1 take about 72 days. That is too slow unless Stage 1 shrinks.
- The [model card](https://huggingface.co/moonshotai/Kimi-K2.6) gives the licence as "other" (a modified MIT). Read the text before use.
- **Financial evidence.** None.

## Exclusions, grouped by reason

The installed OmniRoute 3.8.50 marks 154 of 352 providers as `hasFree` (`omniroute providers available --json`). Its free-model catalog has 456 entries over 79 providers (`open-sse/config/freeModelCatalog.data.ts`, curated 2026-08-20). The local `/v1/models` list shows 580 routes. Of the first-party API-key providers, only `mistral/*` is connected in this install.

1. **Automatic routing, combos, Fusion, fallback, `latest`, or a `:free` suffix.** A route ID with `auto`, `free`, `fusion`, `fallback`, or `latest` fails `FORBIDDEN_ROUTE_PARTS` in `nlp_wayfinder/stage_run.py`. This covers all 38 `combo` routes (`auto/*`), `openrouter/auto`, `openrouter/free`, `bazaarlink/auto:free`, `kilo-auto/free`, every `:free` route on `kilo-gateway`, `routeway`, and `arcee-ai`, the `opencode*` `-free` routes, and `mistral/*-latest`.
2. **Unofficial web, cookie, keyless, OAuth-subscription, or CLI-agent proxies.** No official API account and no dated free-limit evidence. This covers all `web-cookie` providers (such as `huggingchat`, `qwen-web`, `t3-web`, `lmarena`, `zai-web`, `gemini-business`), all `noauth` providers (`duckduckgo-web`, `cloudflare-playground`, `felo-web`, `theoldllm`, `chipotle`, `veoaifree-web`, `uncloseai`, `aihorde`, `opencode`), the OAuth providers (`agy`, `kiro`, `amazon-q`, `qoder`, `openference`), and the `codex`, `devin-cli-agentic`, `auggie`, and `zcode` routes in the local list. OmniRoute itself marks many of these `tos: "avoid"`.
3. **Resellers and gateways.** They are not the first-party account for the model. This covers `agentrouter`, `api-airforce`, `bazaarlink`, `bluesminds`, `llm7`, `requesty`, `navy`, `nara`, `ainative`, `freemodel-dev`, `pollinations`, `blackbox`, `coze`, and the long tail of `api-key` routers (such as `unorouter`, `zylo-api`, `fastrouter`, `anyapi`, `electronhub`, `llmgateway`, `literouter`, `zenmux`, `openadapter`, `tokenrouter`, `void-ai`, `naga-ai`, `free-ai`, `freetheai`, `freeinference`, `chatanywhere`, `cloudcode-one`).
4. **GPT routes.** Every `gpt-*`, `openai/*`, `gpt-oss-*`, `o3`, and `o4-mini` route. This includes `gpt-oss-120b` on Groq, Cerebras, SambaNova, and Cloudflare.
5. **Family already used (GLM, Qwen, Mistral).** `glm`, `glm-cn`, Cerebras `zai-glm-4.7`, `@cf/zai-org/*`, every Qwen and QwQ route, `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` (a Qwen base), `mistral/*`, `@cf/mistral*`, and the Qwen-based SEA-LION models.
6. **No non-excluded family in the official free plan.** [Groq's Free plan](https://console.groq.com/docs/rate-limits) now covers only `gpt-oss`, `qwen/qwen3.8-27b`, and non-chat models. Its [model list](https://console.groq.com/docs/models) gives both Llama chat models "Enterprise pricing". The [Cerebras public endpoints](https://inference-docs.cerebras.ai/models/overview) serve only `gpt-oss-120b` and `qwen-3.8-27b`.
7. **Free capacity too small for Stage 1 (6,868 first attempts).** [SambaNova Free](https://docs.sambanova.ai/docs/en/models/rate-limits) allows 20 requests a day for each model: about 343 days. [Cohere trial keys](https://docs.cohere.com/docs/rate-limits) allow 1,000 calls a month: about 7 months. Hugging Face Inference gives a small monthly credit.
8. **One-time or trial credits, or no production use.** `nvidia` (the [NVIDIA API Trial Terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) limit use to "limited trial purposes only". They forbid use of Generated Content "to develop or improve products or services that compete with the API Service".), and `deepseek`, `deepinfra`, `fireworks`, `hyperbolic`, `nebius`, `nscale`, `novita`, `scaleway`, `together`, `vertex`, `baseten`, `byteplus`, `ai21`, `longcat`, `stepfun`, `baichuan`, `doubao`, `sensenova`, `predibase`, `publicai`, `monsterapi`, `nous-research`, and `bytez`.
9. **No published numeric free limit.** [Ollama Cloud Free](https://ollama.com/pricing) gives "a starter amount of usage". `siliconflow`, `tencent`, `baidu`, `sparkdesk`, `iflytek`, `agnes`, `aion`, and `liquid` publish only rates, or nothing, in the catalog. ModelScope's official [limits page](https://modelscope.ai/docs/model-service/API-Inference/limits) did not render. Secondary sources say its per-model quota changes daily and it needs Alibaba Cloud real-name binding. Its terms on output use were not found.
10. **Terms forbid the use.** Gemini API free routes, and Gemma served through the Gemini API, fall under the [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms). These forbid developing competing models and use unpaid data for training. See the [earlier memo](free-non-gpt-labeling-ensemble.md).
11. **Not a chat model, or not reachable.** Search, embedding, OCR, image, audio, and local providers (`serper-search`, `exa-search`, `jina-*`, `voyage-ai`, `nomic`, `mixedbread`, `segmind`, `magnific`, `speechmatics`, `sdwebui`, `comfyui`, `dify`) and `morph`, which only applies code edits. Cloudflare also serves `@cf/meta/llama-4-scout-17b-16e-instruct`, `@cf/deepseek-ai/deepseek-v4-flash-0731`, `@cf/nvidia/nemotron-3-120b-a12b`, and `@cf/ibm-granite/granite-4.0-h-micro`. The installed registry does not list them, and `cloudflare-ai` has `passthroughModels: false`. So they need an OmniRoute configuration change, which is outside this ticket. Of these, DeepSeek V4 Flash (MIT) is the strongest on paper, because DeepSeek-R1 has the best open result in both finance studies. It would cost about 41.6 Neurons for each vote.

## Before admission

- Record the Cloudflare account evidence for the chosen route, as for the GLM route: the exact ID, the Free plan, the 10,000-Neuron grant, and no Workers Paid plan.
- Set `observed_free_requests_remaining` and `observed_requests_per_day` from the shared pool. Give each Cloudflare route its own part of the pool. Do not count the whole grant twice.
- Make one separately approved non-label preflight. It must return exactly the declared provider and model, with no fallback, no cache, and valid schema JSON.
- A shared pool couples the two Cloudflare routes. When the grant runs out, both routes stop together. The errors are not coupled, because the families differ.
