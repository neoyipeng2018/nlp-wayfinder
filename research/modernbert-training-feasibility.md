# ModernBERT training feasibility

Research date: 2026-09-05

## Decision

Do not reduce the common input limit because of the local computer.

Use one evidence-preserving input with a total limit of 1,024 tokens. Give the exact same input to each system. Use the Apple M3 MacBook Air only for a no-spend compatibility check. Rent one NVIDIA GPU for the 1,024-token pilot and the full three-seed run.

A 24 GB NVIDIA Ampere-or-newer GPU is the minimum practical class. A 48 GB NVIDIA A40 is the recommended first choice when it is available at the current stated price. It gives more memory margin for full fine-tuning, and it supports BF16 Tensor Core work. Use Flash Attention 2 on CUDA.

Set these cash limits:

- Pilot limit: USD 5.
- Normal full-run limit: USD 20.
- Absolute limit: USD 25.

Stop the rented instance when work stops. Do not start the full run until the pilot passes the gates in this report.

## Scope and method

This report examines full parameter fine-tuning of this fixed artifact:

`answerdotai/ModernBERT-base@8949b909ec900327062f0ebf497f51aef5e6f0c8`

The target computer is the current Apple MacBook Air. A local hardware query found:

- Apple M3 chip.
- 10-core integrated GPU.
- 8 GB unified memory.
- macOS 14.3.

No model was loaded or run. No account was created. No hardware was rented. No money was spent. Thus, the local and rental runtime statements below are engineering estimates. They are not benchmark results.

## Fixed model facts

The pinned Hugging Face API record gives an exact total of 149,655,232 FP32 parameters. The pinned configuration has 22 layers, hidden size 768, 12 attention heads, a local attention window of 128 tokens, and a maximum position count of 8,192. The model card says that the base model has 149 million parameters. It also says that Transformers 4.48.0 or later can load the model. It recommends Flash Attention 2 on a supported GPU. [Pinned configuration](https://huggingface.co/answerdotai/ModernBERT-base/blob/8949b909ec900327062f0ebf497f51aef5e6f0c8/config.json), [pinned model card](https://huggingface.co/answerdotai/ModernBERT-base/blob/8949b909ec900327062f0ebf497f51aef5e6f0c8/README.md), [pinned model API](https://huggingface.co/api/models/answerdotai/ModernBERT-base/revision/8949b909ec900327062f0ebf497f51aef5e6f0c8)

The ModernBERT paper says that global attention occurs every third layer. The other layers use a local window of 128 tokens. The authors first trained at 1,024 tokens and then extended the model to 8,192 tokens. This proves model support for 1,024 tokens. It does not prove that an 8 GB Mac can do full fine-tuning. The paper's efficiency tests used an NVIDIA RTX 4090. They did not use Apple MPS. [ModernBERT paper](https://arxiv.org/html/2412.13663v2)

## Local Mac assessment

Apple lists 8 GB unified memory as an M3 MacBook Air option. Apple also lists 100 GB/s memory bandwidth for the M3 MacBook Air. The CPU and integrated GPU use the same unified memory. Thus, the GPU does not have a separate 8 GB memory pool. [Apple MacBook Air specifications](https://support.apple.com/en-euro/118551), [Apple unified-memory property](https://developer.apple.com/documentation/metal/mtldevice/hasunifiedmemory)

PyTorch supports GPU training through its MPS backend. The current MPS requirements include Apple silicon and macOS 14.0 or later. The local macOS version meets this operating-system condition. However, MPS support alone does not show that this full job will fit. [Apple PyTorch guidance](https://developer.apple.com/metal/pytorch/), [PyTorch MPS notes](https://docs.pytorch.org/docs/stable/notes/mps.html)

Hugging Face documents these MPS limits:

- The complete model must fit in unified memory.
- Some operations do not have MPS support.
- A CPU fallback can reduce speed.
- Variable input shapes can grow the MPS graph cache until memory is exhausted.
- BF16 mixed precision needs macOS 14.0 or later.

The same guidance says that `device_map="auto"` cannot move layers from MPS to the CPU. [Hugging Face MPS training guidance](https://github.com/huggingface/transformers/blob/main/docs/source/en/perf_train_special.md)

Flash Attention 2 does not give the Mac the same path as a CUDA GPU. Its official requirements specify CUDA or ROCm, and its CUDA implementation supports Ampere, Ada, and Hopper GPUs. Hugging Face says that SDPA chooses its fastest kernels on CUDA but uses the C++ implementation on other backends. [Flash Attention requirements](https://github.com/Dao-AILab/flash-attention), [Hugging Face attention backends](https://huggingface.co/docs/transformers/en/attention_interface)

### Lower-bound training-state estimate

This estimate uses 149,655,232 parameters:

| Item | Calculation | Approximate size |
| --- | ---: | ---: |
| FP32 weights | parameters x 4 bytes | 0.599 GB |
| FP32 gradients | parameters x 4 bytes | 0.599 GB |
| Two FP32 Adam moments | parameters x 8 bytes | 1.197 GB |
| Total before other data | parameters x 16 bytes | 2.394 GB |

A separate BF16 working copy can add about 0.299 GB. The total becomes about 2.7 GB before activations, attention work areas, optimizer temporary data, MPS caches, input batches, Python, and macOS.

Doubling the input from 512 to 1,024 tokens doubles many activations. A full attention matrix grows by four times. Efficient attention can avoid full matrix materialization, but the best ModernBERT path is the CUDA Flash Attention 2 path, not the Mac path.

### Local result

- **512 tokens:** Technically plausible for a small compatibility check. Use microbatch 1, BF16, gradient checkpointing, fixed-size padded batches, and gradient accumulation. This configuration is not confirmed until a measured check succeeds.
- **1,024 tokens:** Model support is confirmed, but reliable full fine-tuning on this 8 GB Mac is not confirmed. The small memory margin, shared memory, MPS cache behavior, and slower attention path make it fragile.
- **Full Stage 1 run:** Do not use the Mac as the planned training computer. A local failure, system memory pressure, or very low speed can waste more time than a low-cost GPU rental.

## Rented GPU assessment

NVIDIA lists the A40 as an Ampere GPU with 48 GB GDDR6 ECC memory, 696 GB/s memory bandwidth, and BF16 Tensor Core support. This gives a large margin above the lower-bound model state and allows useful microbatch tests at 1,024 tokens. [NVIDIA A40 specifications](https://www.nvidia.com/en-us/data-center/a40/), [NVIDIA A40 data sheet](https://images.nvidia.com/content/Solutions/data-center/a40/nvidia-a40-datasheet.pdf)

A 24 GB NVIDIA GPU is also a reasonable minimum. NVIDIA lists 24 GB GDDR6 for the A10. Flash Attention 2 supports Ampere and later CUDA GPUs with FP16 and BF16. [NVIDIA A10 specifications](https://www.nvidia.com/en-us/data-center/products/a10-gpu/), [Flash Attention requirements](https://github.com/Dao-AILab/flash-attention)

The selection rule is:

1. Prefer one 48 GB A40 at the listed Runpod Pod price when it is available.
2. A 24 GB A5000, A10, L4, RTX 3090, or RTX 4090 can run the pilot.
3. Use a 40 GB A100 only if the lower-cost class fails the memory or time gate.
4. Do not change the GPU class between seeds after the pilot freezes the run configuration.

## Current first-party price evidence

These prices were checked on 2026-09-05. They can change. Check them again before a rental.

Runpod lists these Pod prices:

- RTX A5000, 24 GB: USD 0.27 per hour.
- A40, 48 GB: USD 0.44 per hour.
- L4, 24 GB: USD 0.49 per hour.
- RTX 4090, 24 GB: USD 0.74 per hour.

Storage can add cost. [Runpod pricing](https://www.runpod.io/pricing)

Lambda lists an A40 at USD 1.09 per GPU-hour, an A10 at USD 1.29 per GPU-hour, and an A100 40 GB at USD 1.99 per GPU-hour. Lambda bills on-demand instances by the minute while they run. Tax can apply. [Lambda instance prices](https://lambda.ai/instances), [Lambda billing](https://docs.lambda.ai/public-cloud/billing/)

Modal lists GPU work by the second. Its listed rates give these hourly amounts before separate CPU and memory charges:

- L4: USD 0.7992 per hour.
- A10: USD 1.1016 per hour.
- A100 40 GB: USD 2.0988 per hour.

[Modal pricing](https://modal.com/pricing)

## Work and budget estimate

The estimate uses these assumptions:

- 4,000 Stage 1 training examples.
- 3 epochs.
- 3 seeds.
- One fixed configuration.
- A maximum of 1,024 tokens for each example.

This is 36,000 example-passes. It is at most 36,864,000 token-passes. With effective batch 8, it is 4,500 optimizer steps across all seeds. No primary source gives a runtime for this exact task. Therefore, the estimates below use time allowances, not a promised runtime.

### Pilot

Use 200 to 500 examples, one seed, 100 to 200 optimizer steps, and the 1,024-token limit. Allow two GPU-hours.

At current listed rates, two hours cost:

- Runpod A40: USD 0.88.
- Runpod RTX 4090: USD 1.48.
- Lambda A10: USD 2.58, plus possible tax.
- Modal A10: about USD 2.20, plus CPU and memory.

The USD 5 pilot limit gives margin for startup, package installation, and one repeat.

### Full run

Reserve 24 A40 GPU-hours for the three seeds, checkpoints, evaluation, and one repeat. At the listed Runpod A40 rate, this is USD 10.56 before storage. Set a normal limit of USD 20 and an absolute limit of USD 25.

If only an A100 40 GB is available at Lambda, a 12-hour allowance costs USD 23.88 before tax. Do not use this fallback unless the user accepts that the total can exceed USD 25 after tax.

The expected run can be much shorter than these allowances. The pilot must supply the measured step time and projected cost.

## Pilot gates

Freeze these items before the full run:

- Model revision.
- Transformers version.
- PyTorch version.
- CUDA version.
- Flash Attention version.
- GPU type.
- Total token limit.
- Padding and batch method.
- Microbatch size.
- Gradient accumulation count.
- Seed method.
- Epoch count.

Continue only if all these conditions are true:

- The pilot has no out-of-memory error.
- The pilot has no NaN loss.
- Peak allocated GPU memory is not more than 80% of available GPU memory. For a 24 GB GPU, the gate is 19.2 GB. For a 48 GB GPU, the gate is 38.4 GB.
- The measured speed projects the full three-seed run below the USD 20 normal limit.
- A stopped instance does not continue to create charges.

If the pilot fails, reduce microbatch size and use gradient accumulation. Do not reduce the 1,024-token input rule only to fit the training computer. If a 24 GB GPU still fails, move to the 48 GB A40. If the A40 fails, use an A100 40 GB and get a new cost approval.

