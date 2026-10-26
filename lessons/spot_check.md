# Spot check of the LLM judge (baseline): AI-labelled, not human

> **WARNING: these labels come from Claude (Opus), not from a human.**
> This is **not** the human spot check that `scripts/spot_check.py` was built for. It is a second
> opinion from a stronger model, useful as a rough check, but it should not be reported as human agreement.
>
> `eval/results/spotcheck_baseline.jsonl` has **not been touched** (still 0 lines) and is free for your own labels:
>
> ```
> .venv/bin/python scripts/spot_check.py --tag baseline --n 30
> ```
>
> That command shows exactly the same 30 claims, in the same order (I checked that the sampled keys match).

| Measure | Value |
|---|---|
| Claims checked | 30 |
| Raw agreement | 0.90 (27/30) |
| Cohen's kappa | 0.80 |
| Judge too lenient (count) | 2 |
| Judge too strict (count) | 1 |
| Main pattern in disagreements | The llama judge passed claims that were mostly copied from the evidence but had one wrong or added piece: one merged two loss definitions (L_sec and L_far), one added "moderate to strong" when the evidence only gives a slope. Its one strict mistake was an arithmetic slip: it rejected "4 more rounds" when the evidence says 11 vs 7. |

## Setup

- **Judge under test:** llama3.1:8b verdicts in `eval/results/judged_baseline.jsonl` (262 claims, no errors).
- **Copies, so your file stays clean:** `eval/results/judged_baseline_claude.jsonl` is a byte copy of
  `judged_baseline.jsonl`. I ran the real script with `--tag baseline_claude --n 30` (seed 7, the default), and it wrote
  `eval/results/spotcheck_baseline_claude.jsonl`.
- **Sample:** stratified. 15 claims the judge called *supported* and 15 it called *partial/unsupported*, shuffled.
  The keys are identical to what `--tag baseline` gives.
- **Blind labelling:** a scratch script copied the script's sampling logic and dumped only the question, claim and
  evidence (first 1500 chars each, as the script shows them). I labelled from that dump, with a short reason for each,
  before opening any judge verdicts. I used the script's own rule: `y` only if the claim is *fully* supported by the
  shown evidence. Partly supported, inferred, garbled and non-claim lines (`Missing:`, `Note:`) all got `n`. No skips.
  Then I piped the 30 answers into the real script and checked that the written keys matched the dump order.

## Results (n = 30)

| | |
|---|---|
| Agreement (Claude vs llama judge) | **0.90** (27/30) |
| Cohen's kappa | **0.80** |
| Judge said supported, Claude said no | **2** |
| Judge said not supported, Claude said yes | **1** |
| Claude's labels | 14 y / 16 n |
| Judge's labels on the sample | 15 supported / 15 not (by design) |

### Disagreements

| key | claim (short) | Claude | llama judge | right on second look | reason |
|---|---|---|---|---|---|
| g-2609.16772#1 | "This [far-layer] loss measures total contribution of far layers **and preferentially suppresses weakly supported distant hypotheses** in HLC regions" | n | supported | Claude | The second half describes L_sec, not L_far. The answer merged two losses and the judge missed it ("directly stated"). |
| m08#1 | "This suggests a **moderate to strong** association between tree shade and surface temperature" | n | supported | Claude | The evidence gives a direction and a slope (~3.00 pp canopy per 1 °C). It never calls the strength "moderate to strong". The judge accepted an added characterisation. |
| g-2609.00814#1 | "Significant improvement, as without the Critic it **requires 4 more rounds**" | y | unsupported | Claude (mostly) | 11 - 7 = 4 is correct. The judge's reason ("11 rounds, not 4 more") is an arithmetic slip. "Significant" is loose wording, so a strict reader could still say n. |

### Comparison with the Qwen judge (qwen2.5:7b-instruct)

`judged_baseline_qwen.jsonl` has the same 262 keys with identical claim text, so I compared the same 30 claims.

- Claude vs Qwen: agreement **0.97** (29/30), kappa **0.93**. Qwen called 15/30 supported.
- The one disagreement: **g-2607.25310#2** ("AP values ... high for MF, ACE, CEM in all
  signature cases"). Qwen said supported, Claude said n. The evidence says *ROC-AUC* is high in all cases. It does not
  say that about AP. I still think n is right.
- Qwen got all three llama disagreements "right" by my labels: partial, partial, supported.
- llama vs Qwen on these 30: kappa 0.73.

## What we can see / learn

- **The llama judge is broadly usable but leans lenient where it matters most.** 2 of the 15 claims it called
  *supported* were not fully supported (about 13%). Since it calls 232/262 claims supported, that rate, if it holds,
  would mean roughly 30 of its "supported" claims are wrong. That estimate is very rough at n=15.
- **It errs in a recognisable way.** It misses claims that are *mostly* copied from the evidence but carry one wrong or
  added piece: a merged definition, or an evaluative phrase like "moderate to strong". Near-verbatim claims it gets right.
- **Its strict-side mistake was a reasoning error, not a strictness choice.** It failed simple arithmetic (11 vs 7 = 4 more).
  An 8B judge can't be trusted to check derived numbers.
- **Non-claim noise is a big part of the "not supported" bucket.** 9 of the 15 not-supported items here were `Missing:`/`Note:`
  lines or meta-statements about the sources, not facts. Across all 262 claims there are 16 such lines (3 judged
  *supported*). They distort faithfulness in both directions and should be filtered in `split_claims` rather than judged.
- **Kappa 0.80 vs llama and 0.93 vs Qwen suggest Qwen is the better judge**, at least against this labeller. It matches
  the earlier finding that the two judges disagree on some claims.
- **Agreement on this sample is not agreement on the full set.** Half the sample is the judge's "not supported" claims (15 of only 30
  in the whole set), and those are mostly easy non-claims. Raw agreement on all 262 would be driven by the 232 "supported"
  claims, where the error rate looked like ~13%.
- **Caveats:** n=30, a single labeller, and the labeller is an AI. Its strictness on judgement calls (e.g. "significant",
  meta-claims) may differ from yours. Claude and Qwen may also share biases that a human would not.

## Next steps

1. **Label the same 30 yourself** with `.venv/bin/python scripts/spot_check.py --tag baseline --n 30`. Then compare your labels with
   `spotcheck_baseline_claude.jsonl` (same keys) to see whether the AI labeller is a good stand-in for you.
2. **Drop `Missing:` / `Note:` / meta lines before judging** (in `split_claims`), then re-judge and re-run the spot check.
3. **Spot-check more of the judge's "supported" claims** (e.g. a run with larger `--n`, or a sample drawn only from the supported
   bucket). That's where the uncertain error rate is. Consider switching the default judge to Qwen if the gap holds.

## What Claude answered vs the model

All 30 labelled claims, in script order. Claude = AI labeller (Opus), not a human. "not (x)" = the judge said partial or unsupported, both of which count as not supported. "match?" compares each judge to Claude. Where they differ, the note says who is right on a second look.

| # | key | claim (short) | Claude | llama3.1:8b judge | qwen2.5:7b-instruct judge | match? (llama / qwen) |
|---|---|---|---|---|---|---|
| 0 | g-2607.25310#2 | The AP values for MF, ACE, and CEM are mentioned in as being high f... | n | not (partial) | supported | yes / NO; qwen wrong (Claude right) |
| 1 | g-2610.12517#5 | TerraAgent's strengths and weaknesses are compared to other models ... | n | not (partial) | not (unsupported) | yes / yes |
| 2 | g-2607.13192#2 | However, in the case of SimCLR, it is stated that it exhibits parti... | y | supported | supported | yes / yes |
| 3 | m02#0 | The 2-qubit QCNN model achieved an F1-score of 0.97, and the 4-qubi... | y | supported | supported | yes / yes |
| 4 | g-2609.16772#1 | This loss measures the total contribution of all far secondary laye... | n | supported | not (partial) | NO / yes; llama wrong (Claude right) |
| 5 | g-2610.01710#1 | This is shown in Figure 5, which displays the reward curves for the... | y | supported | supported | yes / yes |
| 6 | g-2607.22380#4 | Missing: A detailed explanation of how these challenges affect the ... | n | not (partial) | not (partial) | yes / yes |
| 7 | g-2608.03407#2 | RoadTracer and Sat2Graph are examples of graph-based methods that a... | y | supported | supported | yes / yes |
| 8 | m11#4 | Note: The question is partially answered, as the sources do not pro... | n | not (partial) | not (partial) | yes / yes |
| 9 | g-2607.18051#0 | According to, the SAR-specific morphological processing technique a... | n | not (partial) | not (partial) | yes / yes |
| 10 | g-2607.19787#3 | Missing: The specific details of the CV-SSM module and its implemen... | n | not (partial) | not (unsupported) | yes / yes |
| 11 | g-2608.11064#3 | Missing: Specific examples of images showing these failure cases. | n | not (unsupported) | not (partial) | yes / yes |
| 12 | m08#1 | This suggests a moderate to strong association between tree shade a... | n | supported | not (partial) | NO / yes; llama wrong (Claude right) |
| 13 | g-2610.21238#7 | 50.4 80.6 77.0 45.1 59.9 | n | not (unsupported) | not (unsupported) | yes / yes |
| 14 | m17#2 | Missing: Information about the other metrics reported in for SCD da... | n | not (partial) | not (partial) | yes / yes |
| 15 | g-2607.28401#3 | Therefore, it is likely that the self-supervised learning model can... | n | not (partial) | not (partial) | yes / yes |
| 16 | g-2607.26973#1 | The dataset consists of 30 Omaha areas of interest (AOIs) and 11 Ja... | y | supported | supported | yes / yes |
| 17 | g-2608.30633#3 | The averaging process is described in the Hybrid Quantum Machine Le... | y | supported | supported | yes / yes |
| 18 | m16#2 | Missing: Information on which specific deep learning approaches map... | n | not (partial) | not (unsupported) | yes / yes |
| 19 | g-2610.27018#0 | The proposed method increases precision by 0.072 from 0.510 to 0.58... | y | supported | supported | yes / yes |
| 20 | m09#0 | According to, the pretrained model matches or exceeds ImageNet-pret... | y | supported | supported | yes / yes |
| 21 | g-2609.00814#1 | This is a significant improvement, as the framework without the Cri... | y | not (unsupported) | supported | NO / yes; llama wrong (Claude right, mostly) |
| 22 | g-2607.13371#0 | Yes, the model accurately reproduces the spatial continuity of the ... | y | supported | supported | yes / yes |
| 23 | g-2608.15054#2 | The FE-SAM's improvements are attributed to its frequency adaptatio... | y | supported | supported | yes / yes |
| 24 | m01#2 | Missing: Comparison of other spectral configurations, such as Dual-... | n | not (unsupported) | not (partial) | yes / yes |
| 25 | g-2607.26973#2 | The WorldView-3 satellite imagery is used for the benchmarking expe... | y | supported | supported | yes / yes |
| 26 | g-2607.25524#0 | The consistency loss in ReLATE is a symmetric mixture-to-view Kullb... | y | supported | supported | yes / yes |
| 27 | m11#3 | Missing: Specific details on how the generative noise-removal model... | n | not (partial) | not (unsupported) | yes / yes |
| 28 | g-2608.04106#1 | It also matches RoMa's saturated performance on the > 800 mm focal-... | y | supported | supported | yes / yes |
| 29 | g-2610.04300#2 | The use of Mean Fusion instead of OAMR's selective feature repair l... | n | not (unsupported) | not (unsupported) | yes / yes |
