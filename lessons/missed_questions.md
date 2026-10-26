# Missed questions: why do the retrievers fail?

## 1. Setup, definitions, counts

- Collection `papers_c300`, 91 answerable questions (73 in `eval/questions.jsonl` + 18 manual `m01-m18`). I rebuilt the same `Retriever` (Embedder, `Index`, `Reranker`) in a scratch script and called `retriever.search(q, k=10, mode, rerank)` exactly as `scripts/run_eval.py` does, then scored with `geoscholar.evaluation` (`recall_at_k`, `first_relevant_rank`). Nothing in the repo, DB or Qdrant was changed and `run_eval.py` was not run. The scratch script and raw hits are in the session scratchpad (`run.py`, `res.pkl`).
- **Miss** = recall@5 < 1 (not every gold paper has a chunk in the top 5). **Hard miss** = no gold paper at all in the top 10. Relevance is judged at paper level.
- **Candidate pool @30** = fraction of gold papers among the 30 candidates (dense top 30, bm25 top 30, hybrid = RRF of both cut to 30) that reranking sees.
- **Cross-check vs `lessons/eval.md`: all numbers reproduce exactly** (R@5 .878 / .945 / .952 / .936 / .972; R@10 .908 / .966 / .993 / .949 / .984; hard-miss counts 6 / 2 / 0 / 3 / 0 match the "6, 2, 0, 3, 0" in point 5). No discrepancies. One factual correction to `eval.md` point 7: it says the reranker's top-1 for m05 (HyDiff-EI, 2608.26812) has "no EMIT". That paper does validate on EMIT data (see m05 below).

| Config | questions missed (R@5<1) | hard misses (none in top 10) |
|---|---|---|
| dense | 13 | 6 |
| bm25 | 7 | 2 |
| hybrid | 7 | 0 |
| dense+rerank | 8 | 3 |
| hybrid+rerank | 5 | 0 |

16 of 91 questions are missed by at least one config. **Missed by all 5: 4** (m07, m15, m16, m17; all multi-paper). Missed by 4 of 5: m05 (only bm25 gets it). Missed by 3: g-2610.27874. Every other miss is a single-paper question missed by 1-2 configs.

Matrix (only the 16 questions with at least one miss; the other 75 are R@5 = 1 in every config). Cell = R@5 and rank of the first gold paper.

| qid | n gold | dense | bm25 | hybrid | dense+rerank | hybrid+rerank | #missed | pool@30 d/b/h |
|---|---|---|---|---|---|---|---|---|
| g-2609.35848 | 1 | **MISS** (0, r10) | ok (r1) | ok (r1) | ok (r1) | ok (r1) | 1 | 1/1/1 |
| g-2609.20150 | 1 | **MISS** (0, none) | ok (r1) | ok (r4) | **MISS** (0, none) | ok (r1) | 2 | 0/1/1 |
| g-2608.01910 | 1 | **MISS** (0, none) | ok (r1) | ok (r4) | **MISS** (0, none) | ok (r5) | 2 | 0/1/1 |
| g-2610.04836 | 1 | **MISS** (0, none) | ok (r1) | **MISS** (0, r7) | ok (r1) | ok (r1) | 2 | 1/1/1 |
| g-2610.27874 | 1 | **MISS** (0, none) | ok (r5) | **MISS** (0, r10) | **MISS** (0, none) | ok (r1) | 3 | 0/1/1 |
| g-2610.07698 | 1 | **MISS** (0, none) | ok (r1) | ok (r4) | ok (r1) | ok (r1) | 1 | 1/1/1 |
| g-2607.20116 | 1 | **MISS** (0, none) | ok (r1) | ok (r5) | ok (r5) | ok (r1) | 1 | 1/1/1 |
| m03 | 1 | **MISS** (0, r10) | ok (r1) | ok (r1) | ok (r1) | ok (r1) | 1 | 1/1/1 |
| m05 | 2 | **MISS** (.5, r1) | ok (1, r1) | **MISS** (.5, r1) | **MISS** (0, r6) | **MISS** (.5, r1) | 4 | .5/1/1 |
| m07 | 3 | **MISS** (.33, r1) | **MISS** (.67, r1) | **MISS** (.67, r1) | **MISS** (.67, r1) | **MISS** (.67, r1) | 5 | 1/1/1 |
| m09 | 1 | ok (r1) | **MISS** (0, none) | ok (r3) | ok (r2) | ok (r5) | 1 | 1/0/1 |
| m11 | 1 | ok (r1) | **MISS** (0, r7) | ok (r3) | ok (r3) | ok (r4) | 1 | 1/1/1 |
| m12 | 1 | ok (r3) | **MISS** (0, none) | ok (r3) | ok (r1) | ok (r5) | 1 | 1/1/1 |
| m15 | 4 | **MISS** (.5, r1) | **MISS** (.5, r2) | **MISS** (.5, r1) | **MISS** (.5, r1) | **MISS** (.5, r2) | 5 | .75/1/.75 |
| m16 | 5 | **MISS** (.4, r1) | **MISS** (.4, r2) | **MISS** (.6, r1) | **MISS** (.6, r1) | **MISS** (.4, r1) | 5 | 1/.8/1 |
| m17 | 5 | **MISS** (.2, r3) | **MISS** (.4, r1) | **MISS** (.4, r1) | **MISS** (.4, r2) | **MISS** (.4, r2) | 5 | 1/.8/1 |

"none" = no gold paper in top 10. Note g-2610.04836 (hybrid, r7) and g-2610.27874 (hybrid, r10) are in the top 10 but not the top 5.

## 2. Taxonomy

Each question gets exactly one primary cause (16 questions in total).

| Cause | What it means | Possible fix (later |
|---|---|---|
| Bad label | Another paper (not in gold) genuinely answers it too, or the question is vague/generic. (6 questions: g-2608.01910, g-2610.04836, g-2610.27874, m05, m15, m17) | Fix or drop the question (propose corrected paper_ids or rewrite) |
| Parsing loss | The answer was in a table, figure or a section GROBID dropped or garbled. (0 questions) | Better parsing (stretch goal) |
| Vocabulary gap | User words differ from the paper's words, even for BM25. (3 questions: m09, m11, m12) | Query rewriting (HyDE) |
| Needs several papers | Multi-paper gold or "which papers compare..." style, where top-k chunks are filled by few papers or the set is incomplete. (2 questions: m07, m16) | Agentic or multi-query retrieval |
| Other: dense embedding fails on rare names, acronyms, numbers | Query terms are in the gold chunk and the PDF text is intact, bm25 finds it at rank 1, but the dense model (bge-small) ranks it low or out of the top 30. (5 questions: g-2609.35848, g-2609.20150, g-2607.20116, g-2610.07698, m03) | Keep bm25 in the mix (hybrid already fixes 4 of 5 in top 5); larger embedder or fine-tuning is optional |

## 3. Per-question table

Confidence is for the primary cause. "Pool" = gold in the 30 candidates (d/b/h = dense/bm25/hybrid).

| qid | question (short) | gold papers | configs that missed (rank) | cause | evidence | conf. |
|---|---|---|---|---|---|---|
| g-2609.35848 | Classical optimum transform for compressing Gaussian sources under MSE | 2609.35848 | dense (r10) | Other: dense rare-term/ranking failure | Gold chunk 4 has "Gaussian", "optimum", "KLT"; dense top-3 are generic compression/denoising papers; pool 1.0 | med |
| g-2609.20150 | Number of parameters in the CAM, detection setting | 2609.20150 | dense (none), dense+rerank (none) | Other: dense fails on acronym "CAM"; secondary: underspecified question | Chunk 21 says "CAM uses 633.24K parameters" (PDF identical); dense pool 0, so reranker cannot rescue | high |
| g-2608.01910 | Main limitations of recent hyperspectral classification methods in complex scenes | 2608.01910 | dense (none), dense+rerank (none) | Bad label (generic) | Question reuses gold wording; MSCM-net intro and HyperImageNet related work list "However/limitations" too; they take ranks 1-3 | high |
| g-2610.04836 | Remote sensing tools using past trajectories/experience to improve later task solving | 2610.04836 | dense (none), hybrid (r7) | Bad label (vague; distractors are on-topic) | Gold is a related-work citation list (RSMeM, GeoEvolver, GeoForge); RS-Claw-Evolution and RingMoClaw are themselves experience-driven agents and fill hybrid top 3 | med |
| g-2610.27874 | Two benchmark datasets used for hyperspectral image reconstruction | 2610.27874 | dense, hybrid (r10), dense+rerank | Bad label (generic, no paper anchor); secondary: dense ranking | Many HSI-reconstruction papers use CAVE/other datasets (2609.05303 uses CAVE, Pavia Centre, ICVL); bm25 only r5, dense pool 0 | med |
| g-2610.07698 | EMA decay rate for per-class confidence on unlabeled stream | 2610.07698 | dense (none) | Other: dense confuses it with other EMA hyperparameters | Chunk text matches the query almost verbatim ("tracks per-class confidence on the unlabeled stream by EMA ... 0.999"); dense returns other papers' EMA decay 0.9999 | med |
| g-2607.20116 | DINOv3-B/16 frozen retrieval values on MSLS-val and Pitts30k | 2607.20116 | dense (none) | Other: dense fails on identifiers in a number-heavy table chunk | Chunk has "DINOv3-B/16, frozen backbone 77.97 89.32 ..."; table intact in PDF and chunk; dense returns unrelated DINOv3 tables | high |
| m03 | How many modalities and which two scales does SomBench cover | 2609.13283 | dense (r10) | Other: dense fails on rare name "SomBench" | Abstract and chunk 19 contain "SomBench ... 11 modalities ... 1 m and 100 m"; dense top-3 are CoordBench/MIND chunks | high |
| m05 | Which studies use hyperspectral data from the EMIT spectrometer | 2609.04906, 2609.35410 | dense (.5), hybrid (.5), dense+rerank (0, r6), hybrid+rerank (.5) | Bad label (incomplete gold) | 2608.26812 (HyDiff-EI) validates on "real-time EMIT data" and 2609.09762 (MethaneFuse) uses EMIT observations; both outrank a gold paper | high |
| m07 | Which studies insert a variational quantum circuit into a classical NN for satellite images | 2608.00072, 2607.14160, 2608.30633 | all 5 | Needs several papers (chunk crowding) | Top 10 is all gold, but 2608.00072 fills 4 of top 5 slots; 2608.30633 sits at ranks 8-10; pool 1.0 | high |
| m09 | Is low-rank adaptation as good as full updating of a lunar model for craters | 2609.13283 | bm25 (none) | Vocabulary gap | "updating", "good", "find" absent from the gold paper; paper says LoRA/lunar/fine-tuning; bm25 top-3 are generic PEFT papers | high |
| m11 | Rebuild radar images from far fewer measurements with generative denoiser plus sparse-recovery steps | 2610.06107 | bm25 (r7) | Vocabulary gap | "rebuilt", "noise-removal", "sparse-recovery", "style" never occur in the gold paper; bm25 top-1 matches "rebuilt" in an editing benchmark | high |
| m12 | Adapt a classifier to a new many-band scene when source data cannot be shared | 2608.05964 | bm25 (none) | Vocabulary gap | Paper says "source-free", "cross-scene", "domain adaptation"; "cannot be shared", "narrow", "adapted" absent; bm25 returns generic hyperspectral intros | high |
| m15 | "Sentinel-1 SAR imagery" (bare keyword) | 2608.14366, 2608.04915, 2610.21993, 2610.06704 | all 5 | Bad label (bare keyword, gold covers a handful); secondary: crowding | 20+ other papers mention Sentinel-1 heavily (e.g. 2610.17680: 21, 2608.01963: 20); 2608.14366 fills up to 5 of the top-10 slots | high |
| m16 | Deep learning approaches for mapping flooded areas/surface water from SAR | 2607.28401, 2608.17398, 2610.06704, 2610.23377, 2607.14743 | all 5 | Needs several papers; secondary: label/ranking | 2610.23377 (FloodVLM-Pix) never in any top 10 (pool 1.0 for dense/hybrid); 2607.28401 takes 2-4 of top-10 slots; non-gold 2610.21993 plausible | med |
| m17 | Metrics (F1, IoU) reported on LEVIR-CD | 2608.24263, 2608.21754, 2610.15813, 2608.28247, 2608.30817 | all 5 | Bad label (incomplete gold) | AdaDINO, GAAT, Zero-OVCD, Freq-RemoteVAR, 2609.02171 all report F1/IoU on LEVIR-CD and rank high; gold 2610.15813 shows LEVIR-CD+ | high |

Proposed label fixes:
- m05: add 2608.26812 and 2609.09762 (EMIT data used in both). Optionally check 2609.31234 and 2609.09876, which mention EMIT but whose usage I did not verify.
- m17: add 2608.07982, 2608.27971, 2608.11663, 2607.25815, 2609.02171 (each seen reporting F1/IoU on LEVIR-CD in a retrieved chunk). Re-check 2610.15813 (the chunk I saw is LEVIR-CD+) and 2608.28247, 2608.30817 (only 1-2 chunks mention both LEVIR and F1/IoU).
- m15: drop, or rewrite as a concrete question that one paper answers; as a keyword it matches 20+ papers.
- m16: consider adding 2610.21993 (flood segmentation on Sentinel-1) after reading it; check that FloodVLM-Pix (a VLM paper using SAR 19 times, "deep learning" 0 times) counts as a "deep learning approach".
- g-2608.01910, g-2610.04836, g-2610.27874: add a paper anchor to the wording, for example "What limitation of prototype and uncertainty-based methods does PNEC-Mamba note?", or drop them.

## 4. What we learn

- **Label problems are the biggest single cause: 6 of 16 misses**, including 3 of the 4 questions missed by every config (m15, m17; m16 partly) and m05. These are not retrieval failures. In m17 and m05 the retrievers return papers that really do answer the question, so the real recall ceiling is higher than the reported numbers. Clean these before drawing conclusions about the multi-paper rows.
- **Dense misses are mostly rare names, acronyms and numbers** (5 questions: SomBench, CAM, DINOv3-B/16 MSLS, the EMA decay, one generic Gaussian/KLT case). The answer text is in the chunk and intact in the PDF; the small embedder just does not rank it. BM25 finds all five at rank 1, and hybrid brings four of them into the top 5 (the fifth, g-2607.20116, is at rank 5). This supports keeping hybrid as the default.
- **BM25's 3 unique misses are all vocabulary gaps** (m09, m11, m12): the user words (updating, rebuilt, cannot be shared) never occur in the paper, and the tokenizer has no stemming. Dense, hybrid and reranked configs recover all three, so these are what hybrid is for. HyDE or query rewriting would help bm25 itself but is not needed if hybrid stays.
- **I found no parsing loss.** For the six single-paper questions where I compared PyMuPDF text with the chunks (tables and numbers: 77.97, 633.24K, 0.999, SomBench, KLT, CAVE/KAIST), the answer strings were present in the chunks. Caveat: I only compared these six, and the answers sit in prose or simple tables. Because bm25 and hybrid find the gold paper anyway, a figure-only or badly garbled table could still be hidden; this eval cannot see it, since it only checks whether a chunk from the right paper was retrieved.
- **Chunk crowding is real for multi-paper questions** (m07: one paper takes 4 of the top 5 slots; m15: one paper fills up to 5 of the top 10; m16: 2-4 of the top 10). In all of them the missing gold paper is in the 30-candidate pool, so a "one best chunk per paper" step (dedupe or MMR before taking top-k) should lift paper-level recall. This is the same fix `eval.md` suggested; here it is supported by m07, where all top-10 chunks are gold and the problem is purely which papers fill them.
- **Reranking does not fix candidate-pool misses and can hurt.** dense+rerank still misses g-2609.20150, g-2608.01910 and g-2610.27874 because dense never put the gold paper in its top 30 (pool 0.00); on m05 it pushed a gold paper from rank 1 to rank 6 by promoting HyDiff-EI, which is itself a valid answer. Hybrid+rerank has the fewest misses (5), all of them multi-paper.
- **Hybrid candidate pool is good**: 15 of the 16 questions have the full gold set in the hybrid 30 (pool = 1.0); only m15 (0.75) does not, so single-paper misses in hybrid (g-2610.04836 r7, g-2610.27874 r10) are ranking issues, and both look like the generic-question label problem.
- **Next steps:** (1) fix the labels above and re-run; (2) add per-paper dedupe before top-k; (3) keep hybrid+rerank as the default; (4) write the few remaining generic questions with a paper-specific anchor, and add more manual questions of the kinds that showed gaps here (paraphrases, rare names).

### What I could not verify

- Whether PDF figures or images hold answers that no parser could extract; this eval cannot detect that.
- Bad-label calls for g-2610.27874 and g-2610.04836 are judgement on retrieved chunks, not a full read of the competing papers (confidence "med"). For m16 I did not read 2610.21993 or FloodVLM-Pix in full.
- m05's extra EMIT papers (2609.09762, 2608.26812) were checked via the retrieved text snippets around "EMIT", not full papers. 2609.31234 and 2609.09876 were not checked.
- For the dense-only "Other" cases I identified what the dense model returned instead, but did not test why bge-small fails (for example whether a different embedder or query prefix would fix them).
