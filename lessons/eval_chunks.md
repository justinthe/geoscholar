# Chunk size vs retrieval quality

## 1. Setup

- Command: `for c in 150 300 450; do .venv/bin/python scripts/run_eval.py --collection papers_c$c --configs dense hybrid+rerank; done`
- Date: 2026-10-25
- Questions: **91 answerable at all three sizes** (identical n, so the comparison is valid). 71 generated + 2 generated-edited + 18 manual. Unanswerable questions are excluded.
- Chunk overlap: 50 tokens at all sizes.
- Chunks never cross section boundaries, so actual chunk sizes sit well below the cap. Token counts below are from the Qdrant `n_tokens` payload.

| Collection | Points | Papers | Avg chunks / paper | Avg tokens | Median tokens | Max |
|---|---|---|---|---|---|---|
| papers_c150 | 38,317 | 399 | 96.0 | 117.2 | 125 | 150 |
| papers_c300 | 19,650 | 399 | 49.2 | 208.1 | 224 | 300 |
| papers_c450 | 14,489 | 399 | 36.3 | 277.6 | 289 | 450 |

The real size ratio is about 117 : 208 : 278 tokens (1 : 1.8 : 2.4), not 1 : 2 : 3. The 450 setting is mostly "300 with fewer splits".

## 2. Results

best-config = hybrid+rerank. Brackets are 95% bootstrap CIs on R@5 (2000 resamples).

| Chunk size | Chunks in collection | dense R@5 | dense MRR | best-config R@5 | best-config MRR | best-config p50 |
|---|---|---|---|---|---|---|
| 150 | 38,317 | 0.889 [0.82-0.95] | 0.894 | 0.952 [0.91-0.99] | 0.947 | 277 ms |
| 300 | 19,650 | 0.878 [0.81-0.94] | 0.844 | 0.972 [0.95-0.99] | 0.954 | 401 ms |
| 450 | 14,489 | 0.878 [0.81-0.94] | 0.845 | 0.952 [0.91-0.99] | 0.957 | 498 ms |

Dense p50: 7 ms (150), 6 ms (300), 6 ms (450).

## 3. R@5 by question type

Generated = 71 generated + 2 generated-edited (n=73). Exact-term and paraphrase are the manual-question tags (n=7 each). Multi-paper = m05, m07, m15, m16, m17 (n=5).

| Type (n) | dense 150 | dense 300 | dense 450 | hybrid+rerank 150 | hybrid+rerank 300 | hybrid+rerank 450 |
|---|---|---|---|---|---|---|
| generated (73) | 0.918 | 0.904 | 0.904 | 0.986 | 1.000 | 0.986 |
| manual (18) | 0.774 | 0.774 | 0.774 | 0.815 | 0.859 | 0.812 |
| exact-term (7) | 0.690 | 0.690 | 0.690 | 0.881 | 0.881 | 0.881 |
| paraphrase (7) | 1.000 | 1.000 | 1.000 | 0.857 | 1.000 | 0.857 |
| multi-paper (5) | 0.387 | 0.387 | 0.387 | 0.533 | 0.493 | 0.523 |

Subgroups of 5-18 questions are anecdotes, not measurements.

## 4. What we can see / learn

Paired bootstrap (2000 resamples, seed 0) on per-question differences vs 300. "Outside noise" means the 95% CI excludes 0.

| Config | Size vs 300 | R@5 diff | RR diff |
|---|---|---|---|
| dense | 150 | +0.011 [0.000, +0.033] | +0.050 [+0.016, +0.090] |
| dense | 450 | 0.000 [0.000, 0.000] | +0.001 [-0.009, +0.012] |
| hybrid+rerank | 150 | -0.020 [-0.055, +0.007] | -0.008 [-0.035, +0.017] |
| hybrid+rerank | 450 | -0.020 [-0.055, +0.006] | +0.003 [-0.016, +0.023] |

- **Dense, 150 vs 300: smaller chunks put the right paper higher, but do not find it more often.** MRR is +0.05 (CI excludes 0; 8 questions better, 2 worse). R@5 is +0.011, which is one question (CI touches 0). So 150 improves rank, not coverage. This is the only quality difference that is outside noise.
- **Dense, 450 vs 300: no difference at all.** R@5 is identical on every question and MRR differs by 0.001. 450 and 300 are effectively the same index for dense search, which fits their actual sizes (278 vs 208 tokens).
- **Hybrid+rerank: 300 is nominally best on R@5 (0.972 vs 0.952), but this is noise.** Both CIs for the difference include 0 (-0.020 is 3 questions worse vs 1 better, at both 150 and 450). We cannot say 300 beats the others once reranking is on. MRR is flat across sizes (0.947 / 0.954 / 0.957).
- **Reranking helps at every size, and the size gap mostly disappears.** Hybrid+rerank minus dense R@5 is +0.063 (150), +0.094 (300), +0.073 (450); all CIs exclude 0. Dense's MRR edge for 150 shrinks to nothing after reranking (-0.008). The test that the gap narrowed is not significant (150: +0.031 [-0.004, +0.073]; 450: +0.020 [-0.006, +0.055]). Reading: the reranker removes most of what chunk size changes, but we cannot prove it.
- **Latency grows clearly with chunk size, and this is solid.** Hybrid+rerank p50 is 277 ms (150), 401 ms (300), 498 ms (450). Reranking dominates (dense is 6-7 ms at all sizes), and the reranker reads longer text at 450. Only 150 is not slower even though it has 2x the chunks, because the reranker scores a fixed number of candidates. Single run per size, so treat exact ms as approximate, but the ordering is large and consistent.
- **Index size and embedding cost.** Points: 38.3k / 19.7k / 14.5k, so 150 stores 2x the vectors of 300 (more Qdrant memory and a bigger BM25 index). Total tokens embedded are nearly the same (about 4.5M / 4.1M / 4.0M by n_tokens x count, ignoring overlap), so embedding compute does not change much; the extra cost at 150 is storage and per-chunk overhead. Build wall-clock was about 2 minutes each for 150 and 450, but that run mixed in other work, so it is not a clean benchmark.
- **Which question types move.** Almost none. Dense is identical on manual, exact-term, paraphrase and multi-paper at all sizes. The movement is in generated questions (dense +1 at 150) and in hybrid+rerank manual/paraphrase, where the 300 advantage comes from one paraphrase question (0.857 vs 1.000) that 150 and 450 both miss. One question is not evidence. Multi-paper R@5 is low everywhere (0.39 dense, ~0.5 hybrid+rerank), and size does not fix it; that is a recall-of-all-papers problem, not a chunking one.
- **Dense never finds 6 questions at c300 (nothing in top 10); 8 miss the top 5.** Dense misses all 6 at 150 and 5 of 6 at 450; the exception (g-2610.04836) appears at rank 9 with 450. Of the two extra top-5 misses, g-2609.35848 is found at rank 1 with 150 and rank 6 with 450, and m03 at rank 6 with 450. Hybrid+rerank finds all of them at every size (rank 1 for most; worst is rank 8). So these failures are about the retriever (exact numbers and terms, such as parameter counts or EMA decay values, where lexical match matters), not chunk size.
- **Possible bias toward 300 is small and mostly checkable.** `make_questions.pick_chunks` samples source chunks from the default (c300) collection, and the questions were written from those passages (mean source chunk 231 tokens, median 241). The source section also exists in c150 and c450 for all 73 generated questions, so the answer text is in every index. Bias could still favor 300 slightly by matching wording to 300-token spans, but the results do not show a 300 advantage in dense (150 is slightly better), and the manual questions (not sampled this way) show the same pattern as generated ones. Only the hybrid+rerank 300 lead could be bias, and it is inside noise. Not fully ruled out.
- **Relevance is paper-level.** Any chunk from the right paper counts, so larger chunks are not penalized for including surrounding irrelevant text, and small chunks get no credit for precision. Chunk size effects on answer quality (what the generator sees) are not measured here and could differ.
- **Tentative recommendation: keep 300.** It is never meaningfully worse, has the best nominal hybrid+rerank R@5, and sits mid-range for index size and latency. 150 is a reasonable alternative if you want a faster reranker (about 30% lower p50) and better dense MRR, at the cost of 2x vectors; nothing here supports 450 (slowest, no quality gain).

Statistical limits: n=91 and R@5 near ceiling (0.95-0.97) means differences under about 5 points are not detectable. The questions and one run each mean latencies carry some run-to-run variance.

## 5. Next steps

1. Measure answer quality, not just retrieval: run the generator on top-5 chunks at 150 and 300 and judge faithfulness/completeness. Paper-level relevance cannot show what bigger chunks cost or give the LLM.
2. Add questions written from 150 and 450 chunks, or more manual questions (target 50+, including multi-paper), to remove the c300 sampling bias and give enough power to separate 300 from 150.
3. Look at the 6 dense-miss questions and the multi-paper questions: try larger retrieval depth, query rewriting, or per-paper deduplication before the rerank step, since size does not fix these.
