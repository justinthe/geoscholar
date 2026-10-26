# Retrieval evaluation (Week 3)

## Setup

- Collection: `papers_c300` (300-token chunks, 50 overlap), embeddings `BAAI/bge-small-en-v1.5`, reranker `BAAI/bge-reranker-base`, candidates 30, RRF k=60.
- Questions: **91 answerable** = 73 generated (71 `generated` + 2 `generated-edited`) + 18 manual (m01-m18). The 5 unanswerable manual questions (u01-u05) are excluded (week 4).
- Date: 2026-10-25. Latency is p50 after a warm-up query, on this machine's GPU.
- Command (repo root):
  `.venv/bin/python scripts/run_eval.py --questions eval/questions.jsonl eval/questions_manual.jsonl`
  Raw output: `/tmp/claude-1000/-home-jthe-Dev-tutes-geoscholar/3779ddea-a2c2-43e9-91f2-6acdc4a86475/scratchpad/eval_stdout.txt`
- **Filename note:** I was told the manual file is `eval/questions_manual.json` and that the default would skip it. In this checkout the file is actually `eval/questions_manual.jsonl`, which matches the script default, so no mismatch exists here and the defaults work. Passing `...manual.json` would have been the thing that silently skipped it (script prints "skipping missing file"). If you do have a `.json`-named copy elsewhere, fix it or rename it; nothing was renamed or edited.

## Results

| Config | R@1 | R@5 (95% CI) | R@10 | MRR | p50 latency |
|---|---|---|---|---|---|
| dense | 0.772 | 0.878 [0.81-0.94] | 0.908 | 0.844 | 6 ms |
| bm25 | 0.879 | 0.945 [0.90-0.98] | 0.966 | 0.929 | 26 ms |
| hybrid | 0.818 | 0.952 [0.91-0.98] | 0.993 | 0.901 | 37 ms |
| dense+rerank | 0.888 | 0.936 [0.88-0.97] | 0.949 | 0.931 | 374 ms |
| hybrid+rerank | 0.912 | 0.972 [0.95-0.99] | 0.984 | 0.954 | 413 ms |

Recall is paper-level and fractional for multi-paper questions (found papers / relevant papers).

### R@5 by question type

Manual questions are split by their first tag (the m15-m18 week1-failure ones also carry a second tag). "manual (all)" is the 18 together.

| Type | n | dense | bm25 | hybrid | dense+rerank | hybrid+rerank |
|---|---|---|---|---|---|---|
| generated | 71 | 0.901 | 1.000 | 0.972 | 0.958 | 1.000 |
| generated-edited | 2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| manual: exact-term | 7 | 0.690 | 0.952 | 0.881 | 0.810 | 0.881 |
| manual: paraphrase | 7 | 1.000 | 0.571 | 1.000 | 1.000 | 1.000 |
| manual: week1-failure | 4 | 0.525 | 0.575 | 0.625 | 0.625 | 0.575 |
| manual (all) | 18 | 0.774 | 0.720 | 0.870 | 0.843 | 0.859 |

Subgroups of 2-7 questions: treat as anecdotes, not measurements.

## What we can see / learn

Paired bootstrap on per-question differences (2000-4000 resamples, same questions for both configs) is used below, because overlapping marginal CIs are a weak test with n=91.

1. **Best overall: hybrid+rerank** (R@5 0.972, MRR 0.954, best R@1 0.912), at ~413 ms vs 37 ms for plain hybrid. Against hybrid the R@5 gain (+0.020, paired CI -0.004 to +0.055) is within noise; the R@1 gain (+0.094, CI +0.037 to +0.162) is real. Against dense, hybrid+rerank is clearly better on both (R@5 +0.094, CI +0.041 to +0.158).
2. **Hybrid beats dense, but not bm25 on R@5.** Hybrid vs dense R@5: +0.074 (CI +0.026 to +0.131), outside noise even though the marginal CIs overlap. Hybrid vs bm25 R@5: +0.008 (CI -0.040 to +0.060), indistinguishable. Hybrid does win on R@10 (0.993 vs 0.966 bm25, 0.908 dense) and is the only config (with hybrid+rerank) that never misses a relevant paper in the top 10 on a single-paper question (see 5), but nothing here proves it beats bm25 on R@5.
3. **BM25 vs dense depends on the question type.** On exact-term questions bm25 gets 0.952 and dense 0.690; on paraphrase questions it flips (dense 1.000, bm25 0.571). That is the case for hybrid: it gets 0.881 and 1.000 on these two. BM25 also beat dense on the generated questions (1.000 vs 0.901), which I read as circularity (point 8). Overall bm25-dense R@5 is +0.066 (CI -0.005 to +0.140), borderline; bm25-dense R@1 is +0.107 (CI +0.030 to +0.187), real.
4. **Reranking helps the top of the list, costs ~10x latency.** dense+rerank vs dense: R@1 +0.115 (CI +0.038 to +0.203), R@5 +0.058 (CI +0.014 to +0.110). Cost: 6 ms to 374 ms (hybrid: 37 to 413 ms). The reranker adds ~340-380 ms, fine for a chat answer, heavy for autocomplete. It cannot add candidates, and it can hurt: dense+rerank dropped m05 from rank 1 to rank 6 (point 7).
5. **R@1 vs R@10 gap: mostly ranking, with a candidate-recall problem for dense.** Hybrid goes 0.818 R@1 to 0.993 R@10, and every hybrid single-paper question has a relevant chunk in the top 10, so its gap is ranking, and the reranker closes about half of it (R@1 0.912). Dense is different: 6 of 91 questions have no relevant paper in the top 10 at all (bm25: 2, hybrid: 0, dense+rerank: 3, hybrid+rerank: 0), so reranking dense cannot recover them. Reranking is only as good as the candidate pool, which is why hybrid candidates matter.
6. **Multi-paper questions (m05, m07, m15, m16, m17) are never fully answered; top-10 recall tops out around 0.4-1.0.** Top-k chunks from the same paper crowd out other relevant papers. Best case R@10 per question: m05 1.0 (bm25, hybrid, hybrid+rerank), m07 1.0 (all but dense), m15 0.75 (hybrid), m16 0.8 (hybrid, dense+rerank), m17 0.8 (bm25, hybrid). R@1 is capped at 1/n_relevant by construction (e.g. 0.2 for m16), so R@1 on these is not a quality signal. For "list the studies" questions, retrieve by paper (dedupe to one chunk per paper) rather than top chunks.
7. **Worst failing questions** (top-1 text checked against the retrieved chunks):
   - **g-2610.27874** "two benchmark datasets used for hyperspectral image reconstruction": dense and dense+rerank miss the paper entirely (no relevant paper in top 10); bm25 rank 5, hybrid rank 10, hybrid+rerank rank 1. Dense top-1 was 2609.37340 (HyperSAM, "High-Fidelity Hyperspectral Dataset Construction"). Generic phrasing; the topic words match many hyperspectral papers.
   - **g-2608.01910** "main limitations of recent hyperspectral classification methods": dense and dense+rerank miss; bm25 rank 1, others 4-5. Dense top-1 was 2607.21050 (HyperImageNet related work, "current datasets primarily face..."), a limitations passage about datasets, from a different paper. Topic-level question with many near-duplicate papers.
   - **g-2609.20150** "number of parameters in the CAM ... under the detection setting": dense and dense+rerank miss; bm25 and hybrid+rerank rank 1. Dense top-1 was 2609.26064 (SPEANet "Design and Implementation Details", mentions parameter overhead). The acronym CAM carries the question, dense embeddings blur it.
   - **m17** LEVIR-CD metrics (5 relevant papers): dense rank 3 and R@5 0.2; others R@5 0.4. Top-1 for dense (2608.07982, AdaDINO) actually says "we report F1 score and IoU on ... LEVIR-CD", a correct answer that is not in the gold list. This is a label-coverage gap, not a retrieval failure: the gold set looks incomplete.
   - **m05** EMIT hyperspectral: dense+rerank rank 6, R@5 0.0 (hybrid+rerank rank 1). Reranker top-1 was 2608.26812 (HyDiff-EI, Chikusei/Botswana datasets, no EMIT); the real EMIT paper's chunk (2609.35410, "The EMIT Imaging Spectrometer's L1B ...") was at rank 6. The cross-encoder preferred a generic hyperspectral dataset passage over a rare token. Candidates were fine; the rerank hurt.
   Common pattern: dense loses specific tokens (CAM, EMIT), bm25 loses paraphrases, so each fails where the other works.
8. **Circularity risk.** The 73 generated questions were written from chunks of the indexed text, so they share vocabulary with the source chunk. That favours keyword matching: bm25 and hybrid+rerank score 1.000 on them, dense 0.901. The manual questions are the more honest signal (bm25 0.720 there, hybrid 0.870), but there are only 18 of them. Absolute numbers on the generated set are probably optimistic for real user queries.
9. **Caveats.**
   - n=91; the CI is for R@5 only (bootstrap over questions); R@1, R@10 and MRR have no interval here. Subgroup tables have n=2-7.
   - Paired differences above were computed ad hoc (not saved by the script).
   - p50 latency is after warm-up on this GPU, single query at a time; the bm25 index is in memory, so its 26 ms excludes index build and will not scale unchanged to a larger corpus.
   - Paper-level relevance: a hit on the right paper's wrong chunk counts as a success; it says nothing about whether the answer text was retrieved.
   - Labels may be incomplete (m17). Unanswerable questions are excluded; abstention is a week-4 topic.

## Next steps

1. Fix the multi-paper case: dedupe retrieved chunks to one per paper (or MMR) before top-k, and report paper-level recall for m05/m07/m15/m16/m17; audit the m17 gold list for the other LEVIR-CD papers.
2. Grow the manual set to 50+ questions (more paraphrase and exact-term, written without looking at chunks) so subgroup differences and R@1/MRR CIs are meaningful; save per-question paired-bootstrap CIs in `evaluation.py`/`run_eval.py`.
3. Make hybrid+rerank the default for the Week 4 answer pipeline, but try reranking the top 10-15 instead of 30 (or a smaller reranker) to see whether latency drops without losing R@1; add the unanswerable questions and measure abstention.
