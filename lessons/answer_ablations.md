# Answer pipeline ablations: sandwich ordering, k=3, k=8 (all four runs complete)

## 1. Setup

- Date: 2026-10-25.
- Generator: `llama3.1:8b` (Ollama, num_ctx 8192, temperature 0.1, one run per config).
- Judge: `llama3.1:8b` (default `config.JUDGE_MODEL`, same for every run, `--judge` not passed). Judge == generator, so the scores are self-judged and probably lenient (same bias as the baseline; the earlier spot check found this judge too lenient and qwen2.5:7b-instruct stricter).
- Baseline config: hybrid retrieval, bge reranker on, k=5, order=relevance, collection `papers_c300`, context budget 3000 approx. tokens.
- Questions: 99 total, 91 answerable, 8 unanswerable.
- Commands (from repo root, strictly one at a time, GPU idle checked before each):
  - `run_answers.py --tag k3 --k 3`, then `judge_answers.py --tag k3`
  - `run_answers.py --tag k8 --k 8`, then `judge_answers.py --tag k8`
  - `run_answers.py --tag sandwich --order sandwich`, then `judge_answers.py --tag sandwich` (added later, see below).
  - **Sandwich was rerun from scratch.** A first attempt had left `answers_sandwich.jsonl` with 11 of 99 answers (no judged file, nothing running). The script is resumable and the partial meta matched the intended config (hybrid, rerank on, k=5, order sandwich, llama3.1:8b, num_ctx 8192; temperature is not in the meta, it comes from `config`, same as baseline). I still did not resume, because (a) the GPU state in the partial meta (6.4 GB used before warm-up, vs 10.4 GB for baseline) shows it ran under different load, (b) its 11 latencies (median about 6.1 s) were mostly slower than baseline's on the same questions (about 4.9 s), and p50 latency is a reported metric, and (c) `config.py` and `llm.py` have uncommitted changes, so I could not verify the partial run used the same code. Mixing two sessions in one latency number is worse than 5 extra minutes of compute. The partial files were renamed, not deleted: `eval/results/answers_sandwich.jsonl.bak` and `eval/results/answers_sandwich.meta.json.bak` (the `.bak` suffix keeps them out of the `answers_*.jsonl` glob). They can be deleted.
  - The fresh sandwich run has 99/99 answers, the same 99 questions, and the same set of 5 chunks per question as baseline in all 99 (checked by chunk text). Other GPU processes (about 4 GB, not mine) were present during the run, as for the baseline.
- What each ablation changes (one variable each):
  - sandwich: only the order of the same 5 chunks in the prompt (1,3,5,4,2 instead of 1,2,3,4,5), so the best chunk is first, the second best is last, and the weakest is in the middle. The aim is to counter models paying less attention to the middle of a long prompt. The citation numbers [S1]..[S5] follow the position in the prompt, not the relevance rank.
  - k3: 3 chunks instead of 5 (the same top-3 as the baseline's first three).
  - k8: 8 chunks instead of 5 (baseline's 5 plus 3 more).

## 2. Results

The sandwich column comes from the fresh run (`judged_sandwich.jsonl`). Baseline numbers come from `aggregate()` over `judged_baseline.jsonl` and match the expected values (faithfulness 0.885, coverage 0.802, relevance 0.778, p50 4453.8 ms).

| Metric | baseline (k5) | sandwich | k3 | k8 |
|---|---|---|---|---|
| Retrieval hit rate | 1.000 | 1.000 | 0.956 | 1.000 |
| Refusal on unanswerable | 1.000 (8/8) | 1.000 (8/8) | 1.000 (8/8) | 1.000 (8/8) |
| False refusal (hit but refused) | 0.011 | 0.022 | 0.023 | 0.022 |
| Answered without evidence | n/a (no misses) | n/a (no misses) | 0.500 (2 of 4 misses) | n/a (no misses) |
| Faithfulness (claims) | 0.885 | 0.895 | 0.888 | 0.906 |
| Citation coverage | 0.802 | 0.818 | 0.789 | 0.800 |
| Invalid citations (answers) | 0.011 | 0.011 | 0.011 | 0.011 |
| Cites relevant paper | 0.978 | 1.000 | 1.000 | 0.978 |
| Relevance (full) | 0.778 | 0.775 | 0.805 | 0.764 |
| p50 total latency (ms) | 4453.8 | 4774.6 | 4490.3 | 5205.9 |
| Claims judged | 262 | 258 | 313 | 235 |
| Refusals (all 99) | 9 | 10 | 12 | 10 |
| Mean prompt tokens | 1455 | 1455 | 942 | 2212 |

Glossary caveat: "retrieval hit rate" is measured over the k chunks given to the LLM, so k3 (0.956) vs k5/k8 (1.000) is a real effect of k, but the rows are not on equal footing. Also "answered without evidence" is only defined when the right paper is missing, which happens only for k3. Faithfulness and coverage are per-claim, and the claim counts differ a lot between runs (k3 writes more, shorter claims; k8 fewer), so the denominators are not the same.

## 3. Per-question analysis (vs baseline, same question ids)

Retrieved sets are nested in all 99 questions (k3 chunks are a subset of the baseline's, baseline chunks a subset of k8's), so every change comes from a different amount of context, not different search results. Paired bootstrap, 2000 resamples, seed 0, over questions answered in both runs.

| | k3 | k8 |
|---|---|---|
| Answered -> refused / refused -> answered | 3 / 0 | 2 / 1 |
| Supported-claim share, better / worse / same | 9 / 21 / 57 | 15 / 12 / 61 |
| Mean diff in supported share (95% CI) | -0.036 (-0.078, +0.003), n=87 | -0.002 (-0.047, +0.038), n=88 |
| Relevance, better / worse / same | 10 / 11 / 66 | 8 / 10 / 70 |
| Mean diff in relevance score (95% CI) | -0.011 (-0.103, +0.081), n=87 | -0.023 (-0.125, +0.068), n=88 |
| Cites relevant paper, gained / lost | 1 / 1 | 1 / 1 |

Both supported-share intervals and both relevance intervals include 0, so none of these differences can be told apart from noise. k3's supported-share drop is the closest to something (upper bound +0.003) but still not clear at n~87.

Largest changes, k3:
1. m11 (radar image reconstruction): baseline answered (rel 2), k3 refused. The paper's evidence was in the baseline's chunks 4-5, dropped at k=3.
2. m09 (low-rank adaptation): same pattern, baseline answered from chunk 5, k3 refused.
3. g-2607.25310 (AP values for MF/ACE/CEM): baseline answered from [1] with low support (0.25), k3 refused. The refusal is arguably the more honest result.
Also m12: supported share fell 1.0 -> 0.2 and the answer lost its citations.

Largest changes, k8:
1. g-2610.13636 (GeoChat/VRSBench): baseline answered with full support, k8 refused (extra chunks apparently distracted the model).
2. g-2609.03804 (MCGC vs CLIP): baseline refused, k8 answered with full support and relevance 3 (the only refused->answered flip).
3. g-2607.18051 (SAR vessel morphology): baseline answered with support 0.0, k8 refused. Again arguably better.
Also m16 and m17 (multi-paper): support 0.67 -> 1.0 and relevance 2 -> 3, with more papers cited.

Multi-paper questions (retrieved relevant papers, baseline -> k3 / k8): m05 1 of 2 in all; m07 2 of 3 in all (k3 support 1.0 -> 0.67); m15 2 of 4 in all; m16 2 of 5 -> 2 / 3 (k8 gains one paper); m17 2 of 5 -> 1 / 2 (k3 loses one). So k3 does not help coverage and slightly hurts it; k8 helps on m16 only.

### Sandwich vs baseline

Same 5 chunks in all 99 questions, only the order differs. So any change is ordering plus sampling noise at temperature 0.1 (one run each). Paired bootstrap, 2000 resamples, seed 0.

| | sandwich vs baseline |
|---|---|
| Answered -> refused / refused -> answered | 1 / 0 (m11, the same question k3 also lost) |
| Supported-claim share, better / worse / same | 7 / 8 / 74 |
| Mean diff in supported share (95% CI) | +0.002 (-0.016, +0.021), n=89 |
| Relevance, better / worse / same | 5 / 7 / 77 |
| Mean diff in relevance score (95% CI) | -0.022 (-0.101, +0.056), n=89 |
| Cites relevant paper, gained / lost | 2 / 0 |
| Refusals (all 99) | 10 vs 9 |
| p50 total latency | 4775 vs 4454 ms; mean paired diff +191 ms (95% CI -55, +437), n=99 |
| Median generate time | 4341 vs 4069 ms (output tokens 89 vs 88, tokens/s 27.0 vs 27.8) |

Both intervals include 0 and are narrow around 0: ordering made no measurable difference to faithfulness or relevance. 74 of 89 questions have the identical supported share. The latency difference is not significant; nothing about sandwich should make generation slower (same prompt length, 1455 tokens), so it is most likely run-to-run and load noise (other GPU processes were present).

Largest changes: g-2610.04300 and m17 improved (support 0.67 -> 1.0), g-2609.00814 improved (0.5 -> 0.8); g-2608.04915 and g-2610.13636 dropped (1.0 -> 0.75). These are 1-claim flips on short answers. m17 (multi-paper) got better support but cited 1 of the 2 relevant papers it cited before; the other multi-paper questions (m05, m07, m15, m16) are unchanged.

Where the cited sources sit. Share of all citations by position in the prompt (baseline: 159 citations, sandwich: 157), and by relevance rank (1 = best chunk):

| | 1st | 2nd | 3rd | 4th | 5th |
|---|---|---|---|---|---|
| Baseline, prompt position (= rank) | 47.2% | 22.0% | 11.3% | 10.1% | 9.4% |
| Sandwich, prompt position | 48.4% | 12.1% | 11.5% | 10.2% | 17.8% |
| Baseline, relevance rank | 48.4% | 20.8% | 13.8% | 8.2% | 8.8% |
| Sandwich, relevance rank | 49.7% | 16.6% | 13.4% | 8.9% | 11.5% |

Reading: the first slot gets about half the citations in both runs. The model follows position: under sandwich the 2nd slot (now the rank-3 chunk) drops from 22% to 12% and the last slot (now the rank-2 chunk) rises from 9% to 18%. By relevance rank, the rank-2 chunk is cited a bit less (20.8% -> 16.6%) and rank-5 a bit more (8.8% -> 11.5%), small shifts. So sandwich moves some citations to the end of the prompt, but the best chunk still gets the same share, and the answers are not better or worse for it. I did not run a significance test on the position shift (citations within one answer are not independent); treat the last-slot rise (15 -> 28 citations) as suggestive only. Answers cite 1.78 sources on average in both runs.

## 4. Findings

- Sandwich ordering: no measurable effect. Faithfulness 0.895 vs 0.885, relevance 0.775 vs 0.778, citation coverage 0.818 vs 0.802, all within noise; paired supported-share diff +0.002 (CI -0.016, +0.021). One extra refusal (m11). Citations shift toward the last slot (9% -> 18% of citations) and away from the 2nd slot, i.e. the model follows prompt position more than relevance, but this does not change answer quality here. p50 latency is +321 ms (4775 vs 4454), paired CI includes 0, same prompt length, so likely noise.
- k3 does not reduce noise in any measurable way: faithfulness 0.888 vs 0.885 (same), relevance 0.805 vs 0.778 (within noise), but retrieval hit rate falls from 1.000 to 0.956 and refusals rise from 9 to 12. The paired supported-share change is -0.036 (CI just touching 0), so there is a hint of a small loss, not proof.
- k3 hurts questions where the key evidence sits in ranks 4-5 (m09, m11) and loses a relevant paper on multi-paper m17. It saves prompt tokens (942 vs 1455) but not latency (4490 vs 4454 ms p50), because generation dominates.
- k8 adds evidence without a visible hallucination cost: faithfulness 0.906 (+0.02, within noise; paired CI -0.047 to +0.038), invalid-citation rate unchanged at 0.011, relevance 0.764 (within noise).
- k8 costs latency: p50 total 5206 ms vs 4454 ms (+17%), prompt tokens +52%, tokens/s 26.1 vs 27.8. This is the only clear difference in the table (single run, but the shift is large and consistent with the extra prompt tokens).
- k8 helps multi-paper questions a bit (m16 and m17 cite more relevant papers and get higher support/relevance), but it also flipped one answerable question to a refusal. Net refusals 10 vs 9.
- Refusal behaviour on the 8 unanswerable questions is perfect (8/8) in baseline, k3 and k8, so k does not affect it here. False refusals are 1-2 of 91 in every run.
- Citation behaviour is stable: coverage 0.79-0.80 in all runs, invalid citations 1 of ~90 answers in all runs.
- Most of the "better/worse" movement is small flips in a claim or two on 3-6-claim answers, so per-question differences are noisy.

Threats to validity:
- One run per configuration at temperature 0.1, so some of the per-question flips are just sampling variation. Rerunning the baseline would show this noise floor.
- The judge is the generator model (self-judging), lenient per the earlier spot check; absolute scores are inflated and differences may be understated.
- n=99 (91 answerable, 8 unanswerable): CIs are wide (about +/-0.04 on supported share, +/-0.09 on relevance).
- Claim splitting changes with k (k3 313 claims, k8 235), so faithfulness is not computed over the same claims.
- Sandwich is one run versus one baseline run; the sandwich-vs-baseline differences are the same size as the sampling noise at temperature 0.1, and nothing was done to measure that noise floor. Latency in particular depends on other GPU processes present during both runs, and GPU memory before warm-up differed between runs (10.4 GB baseline, 6.4 GB sandwich), which can affect p50.
- The first partial sandwich run is kept only as `.bak` and was not used.

Tentative recommendation: keep k=5 relevance order. Sandwich gives no gain and adds one refusal, so there is no reason to switch (it is also free, so it does no harm; only worth revisiting with a longer context where lost-in-the-middle matters more). k3 gives no clear gain and loses some evidence, k8 costs about 17% latency for a gain that is within noise.

Next steps:
1. Delete the `.bak` sandwich files once nobody needs them.
2. Re-judge baseline, k3, k8 and sandwich with `qwen2.5:7b-instruct`: copy `answers_<tag>.jsonl` and `.meta.json` to `answers_<tag>_qwen.*` and run `judge_answers.py --tag <tag>_qwen --judge qwen2.5:7b-instruct`.
3. Repeat the baseline 2-3 times to measure run-to-run noise (or set temperature 0), then only trust differences larger than that. Consider k=6/7 and a multi-paper-focused subset, since only the multi-paper questions showed any benefit from more context.
