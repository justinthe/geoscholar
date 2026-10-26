# GPU footprint: embedder + reranker + 8B LLM

Date: 2026-10-25 (about 21:15-21:25 WIB). Snapshot, not a continuous measurement.

## Commands

```
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv
ollama ps
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
nvidia-smi                      # per-process table
ps -eo pid,args | grep -E 'ollama|python'   # map PIDs to processes
```

## Raw output (trimmed)

```
name, memory.used [MiB], memory.total [MiB]
NVIDIA GeForce RTX 3060, 9060 MiB, 12288 MiB

NAME           ID              SIZE      PROCESSOR          CONTEXT    RUNNER      UNTIL
llama3.1:8b    46e0c10c039e    4.6 GB    12%/88% CPU/GPU    8192       llamacpp    3 minutes from now

pid, process_name, used_gpu_memory [MiB]
44253,  .venv/bin/python (jupyter kernel), 766 MiB
361465, .venv/bin/python (jupyter kernel), 1806 MiB
471452, .venv/bin/python (jupyter kernel), 1662 MiB
548362, /usr/local/lib/ollama/llama-server, 4012 MiB
(+ Xorg 347, gnome-shell 146, code 77, browser ~127, nautilus 9 = ~700 MiB desktop)
```

Python probe (scratch script, own process, exited afterwards). It built `Embedder()` (bge-small-en-v1.5)
and `Retriever(Index(embedder), reranker=Reranker())` (bge-reranker-base), as in notebook 03, and ran one
hybrid+rerank search:

```
torch allocated 1198 MiB, reserved 1624 MiB, peak allocated 1422 MiB
nvidia-smi for that PID: 1754 MiB   (reserved + CUDA context)
nvidia-smi total while it was loaded: 10830 / 12288 MiB
```

Ollama's own timing, two tiny prompts (num_ctx 8192, 200 token cap): 123 tok / 4.05 s = 30.4 tok/s, 126 tok / 4.15 s = 30.4 tok/s.

## Table

| Measure | Value |
|---|---|
| GPU model and total memory | NVIDIA GeForce RTX 3060, 12288 MiB (12 GB) |
| Ollama process (LLM, num_ctx 8192) | 4012 MiB (llama-server, PID 548362; llama3.1:8b, 4.6 GB loaded size, CONTEXT 8192) |
| Python process (embedder + reranker) | 1754 MiB (live probe: 1198 MiB tensors, 1624 MiB reserved, rest CUDA context). Not present in the snapshot itself. |
| Total used | 9060 MiB at snapshot (measured, no embedder/reranker process of ours running). 10830 MiB measured with the probe loaded alongside (9060 + 1754 = 10814, close). Free then: about 1.4 GB. |
| Model fully on GPU? (from ollama ps) | No: 12%/88% CPU/GPU (about 12% of the model sits in system RAM) |
| Generation speed (tokens/s, from summary) | baseline 27.8, k3 29.4, k8 26.1, sandwich 27.0 (mean_tokens_per_s); ollama direct check 30.4 |

Generation speed per tag (answer_summary.csv, last column `mean_tokens_per_s`):

| tag | k | mean tok/s | p50 generate ms | p50 retrieve+rerank ms | p50 total ms | mean prompt tokens |
|---|---|---|---|---|---|---|
| baseline | 5 | 27.75 | 4069 | 426 | 4454 | 1455 |
| k3 | 3 | 29.38 | 4083 | 410 | 4490 | 942 |
| k8 | 8 | 26.08 | 4762 | 418 | 5206 | 2212 |
| sandwich | 5 | 26.98 | 4341 | 428 | 4775 | 1455 |

How it is computed: `llm.chat_full` takes Ollama's `eval_count / (eval_duration / 1e9)` per request (output tokens divided by decode time only,
prompt processing excluded), stores it as `tokens_per_s` in each answer record, and `answer_eval` takes the mean over records.
The `gpu_mb_models_loaded` column (10743-10814) is the whole-GPU `memory.used` from nvidia-smi, read by `run_answers.py` right after a
warm-up question. It is not per process: it includes Ollama, the run_answers process, the open Jupyter kernels and the desktop.

## What was running at the time

No `run_answers.py` or `judge_answers.py` process was alive (sandwich answers and judging had both finished; judged_sandwich.jsonl has 99 rows).
The only Ollama model loaded was the generator, llama3.1:8b, idle with a keep-alive timer (not the Qwen judge). The Python entries on the GPU were
three open Jupyter kernels (PIDs 44253, 361465, 471452, started 08:34, 16:42, 19:17) holding 0.8 to 1.8 GB each. They are notebook sessions,
and I could not tell which one holds which models, so the embedder + reranker row comes from the separate probe, not from them.

## What we can see / learn

- The pipeline fits, but not comfortably. LLM (4.0 GB) + embedder/reranker (1.75 GB) + desktop (0.7 GB) is about 6.5 GB. The rest of the 10.8 GB seen during runs is idle Jupyter kernels (about 4.2 GB). Closing them would free more than the embedder + reranker cost.
- Ollama reports 12% CPU / 88% GPU for llama3.1:8b at num_ctx 8192. The model is not fully on GPU, because the kernels and desktop were holding VRAM when it loaded. Freeing the kernels and reloading would probably put it fully on GPU. I did not try it.
- Headroom is about 3.2 GB at the snapshot (12288 - 9060), and about 1.4 GB with the embedder/reranker loaded as well. That is enough for a larger k (k8 still ran fine) but not for a second 7-8B model: the Qwen judge is about 4.7 GB on disk, so generator + Qwen together would be roughly 9.3 GB before the 1.75 GB of Python models, which would spill more of both onto the CPU.
- Speed is about 26-30 tok/s, stable across runs. Latency is dominated by generation (about 4.1-4.8 s of 4.5-5.2 s total); retrieval + rerank is only about 0.4 s. More context (k8, 2212 prompt tokens) costs about 0.7 s and about 1.7 tok/s, while k3 is fastest. Ollama's direct check (30.4 tok/s, short prompt) agrees within about 10% of the run means.
- What limits scaling is VRAM for a second resident model or a larger num_ctx (KV cache grows with context), not retrieval cost. The partial CPU offload is the likely cause of tok/s staying below what a fully GPU-resident 8B on this card usually gives.
- Caveats: this is a point-in-time snapshot. The embedder/reranker number is a live probe (measured), the 10814 total in the meta files is a recorded whole-GPU value from the answer runs, and the 10830 figure was measured with the probe loaded while the 9060 + 1754 sum agrees with it. The Qwen + llama figure is an estimate from disk sizes, not measured. The probe loaded with only about 2.7 GB free, below the 3 GB I had planned for, and it fit.
