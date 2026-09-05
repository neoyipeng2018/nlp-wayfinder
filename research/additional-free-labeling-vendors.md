# Additional free labeling vendors

**Research date:** 2026-09-05  
**Scope:** Evidence for [Find more free labeling vendors for the staged experiment](https://github.com/neoyipeng2018/nlp-wayfinder/issues/21). This report uses official provider documents, official model terms, and pinned OmniRoute source. No account was created. No model call was made. No money was spent.

## Decision

Do not add a new labeling vendor now.

No new vendor passes all required checks. Cerebras is the closest standby option. It has a fixed OmniRoute route, a published free limit, a hard quota error, and JSON-schema output. However, its terms prohibit use of the service or output to develop competing products or services. The experiment uses model output to train a specialist. Do not assume that this use is permitted. Get written approval from Cerebras before use.

Check vendors as each stage needs them. Do not require all future vendor accounts to pass before Stage 1 starts. Before a route gives its first vote in a stage, record an account-specific check for the exact route, the current free limit, a hard USD 0 spend limit, data use, output use, and model-training use. Freeze the route before collection for that stage. Do not replace a route during a stage.

## Test volume

The ticket asks about 21,000 votes. The estimate uses 800 input tokens and 80 output tokens for each vote. Thus, the full load is about 18.48 million tokens. This is a planning estimate. The collector must record actual input and output tokens.

## Closest standby: Cerebras

**Candidate route:** `cerebras/zai-glm-4.7`

The current Cerebras free-tier table gives this model 60,000 tokens per minute, 1 million tokens per day, 10 requests per minute, and 100 requests per day. A quota error returns HTTP 429. The account page is the source of truth when account limits differ. At 100 requests each day, 21,000 votes need at least 210 days. The request limit, not the token limit, controls this estimate. See [Cerebras rate limits](https://inference-docs.cerebras.ai/support/rate-limits).

Cerebras supports strict JSON-schema output. See [Cerebras structured outputs](https://inference-docs.cerebras.ai/capabilities/structured-outputs). The model owner publishes GLM-4.7 under the MIT license. See the official [GLM-4.7 repository](https://github.com/zai-org/GLM-4.7).

Cerebras states that it claims no ownership of API input or output. It also states that service content is not granted for model training or fine-tuning. However, its terms prohibit use of the service or output to develop competing products or services, and they prohibit benchmarking or competitive analysis. The planned specialist learns from the labels. This creates a material permission risk. See the [Cerebras terms](https://www.cerebras.ai/terms-of-service).

The pinned OmniRoute registry maps `cerebras` to the official API and lists `zai-glm-4.7`. See the [Cerebras registry at revision `c0b2253`](https://github.com/diegosouzapw/OmniRoute/blob/c0b2253f21c2e70c5d73581ae1be6f60a4ac5647/open-sse/config/providers/registry/cerebras/index.ts). The route is compatible with OmniRoute at that revision.

**Verdict:** Standby only. Use it only after written provider approval and an account-specific free-limit check. Its 210-day minimum also makes it a poor full-run route.

## Vendors that do not pass

| Vendor | Current fact | Result |
| --- | --- | --- |
| Zhipu BigModel | `GLM-4.7-Flash` is free and supports structured output. However, the user agreement prohibits use of model output for development, training, labeling, fine-tuning, or improvement of another model. | Reject for silver-label training. See the official [model page](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash), [price page](https://bigmodel.cn/pricing), and [user agreement](https://docs.bigmodel.cn/cn/terms/user-agreement). |
| NVIDIA API Catalog | The developer API is a limited trial. NVIDIA does not publish a fixed account quota. Its trial terms permit use of input and output to improve NVIDIA models. They also prohibit use of output to develop or improve a competing product or service. | Reject. The cost, data-use, and training-use gates fail. See the [NVIDIA API trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) and [API quick start](https://docs.api.nvidia.com/nim/re/docs/api-quickstart). |
| Cohere | A free evaluation key permits 1,000 API calls each month. Thus, 21,000 votes need at least 21 months. Cohere also prohibits benchmarking and competitive use. | Reject for this experiment. See [Cohere rate limits](https://docs.cohere.com/docs/rate-limits) and [Cohere terms](https://cohere.com/terms-of-use). |
| OpenRouter | An account with no purchased credits gets 50 free-model requests each day. Thus, 21,000 votes need at least 420 days. Free model requests can go to different upstream providers, and each provider has its own data policy. | Reject. The schedule and fixed-provenance gates fail. See the [OpenRouter FAQ](https://openrouter.ai/docs/faq), [provider logging rules](https://openrouter.ai/docs/guides/privacy/provider-logging), and [zero-retention rules](https://openrouter.ai/docs/guides/features/zdr). |
| Hugging Face Inference Providers | A free account gets USD 0.10 of monthly inference credits. Extra use needs purchased credits. | Reject. The published free grant is not sufficient for 18.48 million tokens. See [Hugging Face pricing](https://huggingface.co/docs/inference-providers/pricing). |
| SambaNova Cloud | The current Free plan says that the user must add a payment method and buy credits before the first request. An earlier USD 5 credit expired after three months. | Reject. There is no current recurring zero-cost quota. See [SambaNova plans](https://cloud.sambanova.ai/plans) and the official [developer-tier notice](https://sambanova.ai/blog/sambanova-cloud-developer-tier-is-live). |
| Ollama Cloud | The free plan has an unspecified starter amount. Extra credits can be used after the included amount ends. The terms prohibit use to develop competing products. | Reject until Ollama publishes enough free capacity and confirms training use. See [Ollama pricing](https://ollama.com/pricing), [Ollama terms](https://ollama.com/terms), and [Ollama privacy](https://ollama.com/privacy). |
| Requesty | Requesty says that every model that permits training on prompts is free. Its public pages do not prove a sufficient fixed free limit for one acceptable model. | Reject for rights-limited passages and for missing capacity evidence. See [Requesty privacy](https://www.requesty.ai/privacy), [provider data rules](https://www.requesty.ai/privacy/subprocessors), and [security controls](https://www.requesty.ai/security). |
| GitHub Models | GitHub Models was retired on 2026-07-30. | Reject. See the [GitHub retirement notice](https://docs.github.com/en/github-models). |

OmniRoute contains connectors for Cerebras, NVIDIA, Cohere, Hugging Face, OpenRouter, and SambaNova. Connector presence proves transport support only. It does not prove free access or permitted use. See the pinned [provider registry](https://github.com/diegosouzapw/OmniRoute/tree/c0b2253f21c2e70c5d73581ae1be6f60a4ac5647/open-sse/config/providers/registry) and [free-model catalog](https://github.com/diegosouzapw/OmniRoute/blob/c0b2253f21c2e70c5d73581ae1be6f60a4ac5647/open-sse/config/freeModelCatalog.data.ts).

## Stage-by-stage vendor gate

Use this gate before a new vendor gives its first vote in a stage:

1. Confirm the exact model in the provider console and in the pinned OmniRoute registry.
2. Record the account limit and reset time. Public limits are not sufficient when the provider says that account limits can differ.
3. Set the account and API key to a hard USD 0 limit. Do not add a payment method if the service can use it automatically.
4. Confirm that the provider does not train on the passage or the output.
5. Confirm that the provider permits use of output as training labels for the specialist.
6. Confirm that the passage source permits transfer to that provider.
7. Run one non-blind structured-output test only after the human permits a model call.
8. Record provider, exact model, OmniRoute revision, request ID, token use, quota use, and returned model for each vote.
9. Stop on a quota error. Do not retry through a paid route, fallback route, or different model.

## Final answer

The present three-vendor ensemble remains the only planned ensemble. Additional connectors exist, but none is approved now. Cerebras can become a slow fourth vendor only if it gives written permission for this training use and its account shows a hard free limit. This result supports a stage-by-stage account gate. It does not support silent vendor changes during collection.
