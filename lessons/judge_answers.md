# Judging the baseline answers with two judges

## 1. Setup

- Date: 2026-10-25
- Answers judged: `eval/results/answers_baseline.jsonl`, 99 questions: 91 answerable, 8 unanswerable. 9 were refused (all 8 unanswerable plus 1 answerable). 90 answers were judged, giving 262 claims. (An answer that is not a refusal gets claims; all 90 had at least one.)
- Answer generator (from meta): `llama3.1:8b` (Q4_K_M), hybrid search, rerank on, k=5, order=relevance, collection `papers_c300`, num_ctx 8192.
- Judge 1 (default, `config.JUDGE_MODEL`): `llama3.1:8b`. This is the SAME model that wrote the answers, so there is a self-judging bias risk.
- Judge 2: `qwen2.5:7b-instruct` (7.6B, Q4_K_M, 4.7 GB, Ollama digest 845dbda0ea48). Chosen as a non-thinking Qwen so `format=json` output parses cleanly. No JSON/parse errors from either judge (0 "error" verdicts).
- Commands:
  - `.venv/bin/python scripts/judge_answers.py --tag baseline` was NOT re-run to completion: `judged_baseline.jsonl` already had 99 rows judged by `llama3.1:8b` (recorded in `answer_summary.csv`, run 2026-10-25 19:51), so a re-run would skip all rows. The llama column below comes from `aggregate()` on that existing file (same numbers as the CSV row).
  - `ollama pull qwen2.5:7b-instruct`
  - `cp answers_baseline.jsonl answers_baseline_qwen.jsonl` and `cp answers_baseline.meta.json answers_baseline_qwen.meta.json` (copy trick: judgments are keyed by tag, so the Qwen run writes `judged_baseline_qwen.jsonl` and leaves `judged_baseline.jsonl` untouched).
  - `.venv/bin/python scripts/judge_answers.py --tag baseline_qwen --judge qwen2.5:7b-instruct` (about 7 minutes). This appended a row to `answer_summary.csv` with judge = qwen2.5:7b-instruct.

## 2. Results

| Metric | Baseline (judge: llama3.1:8b) | Baseline (judge: qwen2.5:7b-instruct) |
|---|---|---|
| Retrieval hit rate | 1.000 | 1.000 |
| Refusal on unanswerable | 1.000 | 1.000 |
| False refusal | 0.011 | 0.011 |
| Answered without evidence | n/a (nan: no retrieval misses) | n/a (nan: no retrieval misses) |
| Faithfulness (claims) | 0.885 | 0.855 |
| Citation coverage | 0.802 | 0.802 |
| Invalid citations | 0.011 | 0.011 |
| Cites relevant paper | 0.978 | 0.978 |
| Relevance (full) | 0.778 | 0.600 |
| p50 total latency | 4453.8 ms | 4453.8 ms |

p50 latency comes from the answers file, so it is identical across judges. Most rows do not use the judge at all (see below).

Glossary (row -> `aggregate()` key):

- Retrieval hit rate -> `retrieval_hit_rate`: share of answerable questions where a labelled paper is among the 5 sources. Judge-free.
- Refusal on unanswerable -> `refusal_rate_unanswerable`: share of unanswerable questions the system refused. Should be high. Judge-free.
- False refusal -> `false_refusal_rate`: refused although the right paper was retrieved. Should be low. Judge-free.
- Answered without evidence -> `answered_without_evidence`: answered although the right paper was NOT retrieved. nan here because there were zero misses (denominator empty).
- Faithfulness (claims) -> `faithfulness`: share of claims the judge calls "supported" (partial counts as not supported; `partial_rate` was 0.061 llama / 0.073 qwen). Judge-dependent.
- Citation coverage -> `citation_coverage`: share of claims with at least one `[S#]` citation. Judge-free (regex).
- Invalid citations -> `invalid_citation_rate`: share of answered questions citing a source number that does not exist. Note this is per answer, not per claim. Judge-free.
- Cites relevant paper -> `cites_relevant`: among answered questions where the labelled paper was retrieved, share whose cited sources include it. Judge-free.
- Relevance (full) -> `relevance_full`: share of answered answerable questions the judge scores 3 ("directly and completely answers"). Judge-dependent.
- p50 total latency -> `p50_total_ms`: median end-to-end time per question.

All labels map cleanly to one key each.

## 3. Judge agreement

Claim extraction (`split_claims`) is deterministic, so both judges saw the same 262 claims and they match one-to-one by index (verified).

- Verdict agreement (3 classes): 235/262 = 89.7%.
- Cohen's kappa, supported vs not-supported: 0.70 (substantial but not near-perfect).
- Verdict counts, llama / qwen: supported 232 / 224, partial 16 / 19, unsupported 14 / 19.
- Main disagreement pattern: llama says supported, qwen says partial (10 claims); partial->unsupported 7; supported<->unsupported 3 each way.
- Per question, Qwen's supported share is lower for 11 of 90 answers, higher for 3, equal for the rest (mean difference -0.03).
- Relevance: both judges scored 90 answers; exact agreement 77.8%; kappa on "score = 3" is 0.50. In 18 cases llama gave 3 and qwen 2; only 2 went the other way. Qwen is the stricter judge on relevance.
- Refusal flags come from the answers file, so they are identical for both judges.

Biggest disagreements (all read against the cited evidence):

1. `g-2609.00814` (Critic mechanism, convergence rounds). Claim 0 "reduces rounds from 11 to 7": llama supported, qwen partial. The evidence states 7 vs 11 rounds, so llama is right. Claim 1 "requires 4 more rounds": llama unsupported, qwen supported. 11 - 7 = 4, so qwen is right. One question, each judge wrong once.
2. `g-2607.25310` (AP values for ground SVC). Claim "the specific values are not provided": llama partial, qwen supported. The evidence has no AP values, so partial is the more sensible reading; llama is closer. The trailing "Missing: ..." line: llama partial, qwen unsupported. These are meta-statements about absence, and neither verdict is really meaningful.
3. `g-2610.21238` (domain adaptation tables). Lead-in claims "results ... are as follows:" with no citation: llama unsupported ("no evidence"), qwen supported. The passages do contain these tables of numbers, so qwen is closer, but the claim carries no content to check.
4. `m11` (SAR reconstruction). Claim attributing the diffusion-plus-unrolling idea to the cited paper, but the cited passage [4] is a generic compressed-sensing background paragraph: llama supported, qwen unsupported. Qwen is right; llama looks to be accepting the title string as proof.
5. `m16` (flood mapping). Claim mentions "U-Net based flood mapping" with AEF: llama supported, qwen partial because U-Net is not in the passage. Qwen is right. Also `g-2609.19010`: a "Note: sources do not provide..." claim, llama supported, qwen partial; unclear, and it is again a meta-statement.

Overall: Qwen caught 2 of 3 clear llama errors (m11, m16); llama caught one clear Qwen error (00814 claim 0); one arithmetic case went to Qwen. Roughly a wash on accuracy, but Qwen is stricter and a more independent check.

## 4. What we can see / learn

- The judge-free metrics look strong and cannot be argued with: top-5 hit rate 1.00, 8/8 refusals on unanswerable questions, 1 false refusal in 91 (`g-2609.03804`), 0.978 cites the labelled paper, only 1 answer with an invalid citation number.
- Faithfulness is judge-sensitive but in a narrow band: 0.885 (llama) vs 0.855 (qwen). Both say roughly 86-89% of claims are fully supported and about 6-7% are only partial. The ranking-level story (mostly grounded) is robust; the third decimal is not.
- Relevance (full) is the most judge-sensitive number: 0.778 vs 0.600. Strictness differs more than quality does. Treat it as a relative metric only.
- Citation coverage is 0.802: about 20% of claims (52 of 262) have no citation. These are often connective or "Missing: ..." sentences, which also confuse the judges. This is the real weakness to fix, not unsupported content.
- Some "unsupported" flags come from non-claims (lead-ins like "as follows:", "Note: ...", "Missing: ..."). `split_claims` keeps them as claims, which adds noise to both judges and probably understates faithfulness slightly.
- Latency: p50 about 4.5 s per question, of which about 4.1 s is generation and only about 0.4 s is retrieval plus rerank. Generation speed is the lever.
- Threats to validity: n is small (99 questions; 8 unanswerable; 262 claims). Retrieval hit rate 1.0 and zero "answered without evidence" cases means the retrieval-failure path was never exercised. Judge 1 is the generator itself (self-preference risk), and Qwen is a similar 7-8B size, so neither judge is a strong reference; no human labels exist. Single run, temperature 0 judges.

Next steps:

1. Hand-label about 30 claims (mix of all disagreements) and report each judge's accuracy against them, to decide which judge to trust.
2. Filter or tag non-claims (lead-ins, "Missing:", "Note:") in `split_claims`, and tighten the prompt to cite every factual sentence; re-measure citation coverage and faithfulness.
3. Make the eval harder: add questions whose paper is outside the top-5 (to exercise "answered without evidence") and try a larger or different-family judge; consider speeding up generation (shorter answers, smaller k) to cut the 4 s latency.
