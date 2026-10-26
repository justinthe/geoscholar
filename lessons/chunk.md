# Chunk size comparison: 150 vs 300 vs 500 tokens

## Setup

- Paper: 2610.24075, "OrTeN: Neural Inverse Graphics for Joint Terrain and Line-scan Camera Trajectory Reconstruction".
- Parsing: GROBID TEI (cached) -> `sections_from_tei`. 16 sections, 5,064 source tokens (sum of per-section token counts).
- Chunker: `chunk_paper(p, sections, max_tokens=size, overlap=50, count=count)`.
- Tokenizer: the `BAAI/bge-small-en-v1.5` tokenizer, no special tokens.
- Only `max_tokens` changed between runs. Overlap stayed at 50.
- Chunks never cross section boundaries, so every section produces at least one chunk.

`embed_text` format (title, section line, blank line, body):

```
OrTeN: Neural Inverse Graphics for Joint Terrain and Line-scan Camera Trajectory Reconstruction
Section: 2. Related Work DTM creation with MVS.

<chunk text>
```

The header costs about 30 tokens per chunk, and it is not counted in `n_tokens`.

## Results

| Metric | 150 | 300 | 500 |
|---|---|---|---|
| Chunks | 49 | 27 | 18 |
| Avg tokens | 114 | 188 | 281 |
| Min / max tokens | 18 / 150 | 40 / 290 | 92 / 469 |
| Total chunk tokens | 5,581 | 5,074 | 5,064 |
| Duplication vs source (5,064) | +10.2% | +0.2% | 0.0% |
| Tiny chunks (<50 tokens) | 4 | 1 | 0 |
| Adjacent same-section pairs | 33 | 11 | 2 |
| ...of which share overlap text | 15 (45%) | 1 (9%) | 0 |
| Overlap length when present (tokens) | 6 to 50 | 10 | n/a |
| Chunks starting mid-sentence | 1 | 1 | 0 |
| Chunks ending mid-sentence | 7 | 2 | 0 |

"Mid-sentence" is a regex check: the chunk starts with something other than a capital, digit or bracket, or it ends without `. ! ? ) ]`. Every hit was traced back to the source text (see the findings below). None came from the chunker cutting a normal sentence.

### Chunks per section

| Section | Tokens | 150 | 300 | 500 |
|---|---|---|---|---|
| Abstract (polluted) | 137 | 1 | 1 | 1 |
| 1. Introduction | 692 | 7 | 3 | 2 |
| 2. Related Work DTM creation with MVS. | 689 | 6 | 4 | 2 |
| 3. Methodology | 124 | 1 | 1 | 1 |
| 3.1. Rendering a height field | 242 | 2 | 1 | 1 |
| 3.2. Calibrated I/F image formation | 167 | 2 | 1 | 1 |
| Geometric shadows. | 303 | 3 | 2 | 1 |
| 3.3. Linescan bundle adjustment | 175 | 2 | 1 | 1 |
| 3.4. Surface-guided patch consistency | 163 | 2 | 1 | 1 |
| 3.5. Architecture and losses | 445 | 4 | 2 | 1 |
| Sigmoid (bogus) | 92 | 1 | 1 | 1 |
| 4.1. Datasets | 402 | 3 | 2 | 1 |
| 4.2. Evaluation protocol and metrics | 332 | 3 | 2 | 1 |
| 4.3. Training details | 364 | 4 | 2 | 1 |
| 4.4. Results and ablations | 469 | 5 | 2 | 1 |
| 5. Conclusion | 268 | 3 | 1 | 1 |
| Total | 5,064 | 49 | 27 | 18 |

### Tiny chunks (<50 tokens)

- 150 (4 chunks):
  - 3.2: 18 tokens, "This interpolates between Lambert and Lommel-Seeliger responses [28]." It is a one-sentence remainder, cut off from the equation it describes.
  - 3.3: 48 tokens, an equation-adjacent leftover.
  - 3.5: 27 tokens, the tail of the architecture-diagram text: `-ū), b i Sun-only ambient network s -> SH 4 (s) 32 32 1 a amb (s)`.
  - 4.3: 47 tokens, a short hyperparameter sentence.
- 300 (1 chunk): "Geometric shadows.", 40 tokens, starting `where z p = 1 marks a detected core...`. It is a prose fragment that comes right after a lost equation.
- 500: none.

## Examples

Same passage at each size: the start of 4.4. Results and ablations (about 330 characters shown).

**150** (chunk 41, 141 tokens, the first of 5 chunks in the section)
> Tab. 2 gives the results of the baseline OrTeN configuration on each scene. OrTeN attains sub-GSD height RMSE a in Jezero, Gale, and McGetchin scenes. On the Olympus Mons scene, the RMSE a remains at 2.91 x GSD. Its large relief (almost 3 km) and substantial cast shadows make reconstruction challeng...
> ... It falls short of OrTeN both visually and in structural accuracy.

The next chunk (42) opens with that last sentence: "Depth-supervised EO-NeRF fails ... It falls short of OrTeN ..."

**300** (chunk 24, 290 tokens, 1 of 2 chunks)
> Tab. 2 gives the results of the baseline OrTeN configuration on each scene. OrTeN attains sub-GSD height RMSE a in Jezero, Gale, and McGetchin scenes. ...
> ... the reconstruction visibly degrading, especially in the fine detail around the central crater region.

The next chunk (25) starts at "Disabling NCC has an even more pronounced effect...". There is no overlap, because the last sentence of chunk 24 is longer than 50 tokens.

**500** (chunk 16, 469 tokens, the whole section in one chunk)
> Tab. 2 gives the results of the baseline OrTeN configuration on each scene. ... (all of 4.4) ... The baseline is able to reconstruct the large shadow cast by the cliff face while the ablated scene cannot.

Same passage at each size: the start of 3.5. Architecture and losses.

- 150: 4 chunks. Chunk 26 holds the prose ("Fig. 3 shows the overall network architecture. Training progresses ...", 149 tokens). Chunks 28 and 29 hold the diagram text. Chunk 29 is a 27-token word-cut fragment: `-ū), b i Sun-only ambient network s -> SH 4 (s) 32 32 1 a amb (s)`.
- 300: 2 chunks. Chunk 15 holds the prose and equation text (269 tokens, ending `...Its second derivative`). Chunk 16 holds the diagram text (176 tokens). The split falls where the paper moves from prose to figure text.
- 500: 1 chunk (445 tokens), prose and diagram text together.

## Findings

- **Larger size means fewer chunks, roughly inversely.** 49 -> 27 -> 18 chunks. From 300 to 500 the saving is less than proportional, because each section is capped at one chunk minimum and most sections are already small.
- **Overlap cost is only real at 150.** It adds 517 tokens (+10.2%), against +10 (+0.2%) at 300 and 0 at 500.
  - The chunker carries over whole trailing sentences only if they total 50 tokens or fewer. Sentences here average 30 to 60 tokens, so at 300 and 500 the last sentence is usually too long to carry.
  - Overlap was actually present in 45% of 150-size boundaries (15 of 33), 9% at 300 (1 of 11) and 0 at 500. The configured overlap=50 effectively switches off as chunks grow.
- **Small-section floor.** The median section is about 285 tokens, and 7 of 16 sections are under 250. Each section gets one chunk at any size, so those sections show the same chunk count at 300 and 500. Size only matters for the 5 or so sections over 400 tokens. The floor also produces uneven chunks: 500 has a minimum of 92 tokens and 300 has 40.
- **Retrieval tradeoff.**
  - 150 is the most precise (one idea per chunk, e.g. 4.4 splits into RMSE results, EO-NeRF, ASP, and NCC ablation). It also loses context: "Disabling NCC..." is cut off from the sentence introducing the ablation. It adds 31 more vectors than 500 for one paper, which is about 2.7x.
  - 500 puts a whole subsection in one chunk. The embedding then averages several topics, such as 4.4's results, baselines and three ablations. A query about a single ablation competes with the rest of the text. It is also close to bge-small's 512-token limit once the ~25-token header is added (469 + 25 = ~494). A longer section would risk truncation.
  - 300 is in the middle: 2 chunks for most long subsections, split on paragraph/sentence boundaries.
- **The chunker does not cut normal sentences.** Sentence-boundary breaking works at every size. All 1 + 7 (150), 1 + 2 (300) and 0 (500) flagged hits are caused by GROBID, not by the size setting.
  - 5 of the 7 flagged ends at 150 and 1 of 2 at 300 stop right before an equation (`...is`, `...penalties are`, `...loss is`, `...derivative`). GROBID dropped the equation, so the sentence is left hanging.
  - The one genuine word-level cut is at 150 (chunk 29, the 3.5 diagram text): a monster "sentence" with no punctuation, split by words as designed.
  - The one start flag at 300 (`where z p = 1 marks ...`) is a sentence that follows a dropped equation.
- **GROBID errors, effect on chunks.**
  - The **Abstract** is polluted: it holds the Figure 1 caption and RMSE numbers (`DTM RMSE a : 2.35 m ...`), and the abstract prose is missing from it. One chunk at every size, with the header "Section: Abstract". It will match queries about the paper's main claims poorly and may match on numbers.
  - The bogus **Sigmoid** section is a 92-token orphan holding the tail of 3.5's equations ("No activation penalizes trajectory curvature: ... The complete objective is"). It is 1 chunk at every size, labeled with the wrong section, and its content is mostly fragments with no equations. That is likely never useful in retrieval, and it dilutes metadata filtering by section.
  - **Equation gaps** leave sentences ending in `:` or `is` and following sentences starting with "where" or "Here". These are the main source of the odd chunk edges at 150 and 300. Larger chunks hide them because the neighbouring text stays in the same chunk, but they do not fix them.
  - **Diagram text in 3.5** (the architecture figure labels) becomes a number-heavy chunk with a few useful phrases. It is 2 chunks at 150 (one of them the 27-token fragment), 1 at 300, and merged with prose at 500.
  - Section headings like "Geometric shadows." (a paragraph title) and "2. Related Work DTM creation with MVS." (heading merged with the first paragraph title) are wrong heading boundaries, so they end up in the `Section:` line of the embed text.

## Recommendation

Use **300 tokens, overlap 50** (the current default) for this corpus.

- It splits long subsections into 2 to 4 topical chunks, with no meaningful duplication (+0.2%) and few tiny chunks (1 vs 4 at 150).
- 150 gives 2.7x the vectors of 500 and 4 tiny fragments, and its +10% overlap duplication only partly repairs the equation-gap breaks.
- 500 leaves large chunks (up to 469 tokens, near the 512 limit with the header), so queries about one specific result compete with the rest of the section.
- Fix GROBID first, whatever size you choose: drop or merge the Sigmoid section, drop the Abstract caption (or rebuild the Abstract from the arXiv metadata), and flag chunks that end on a dropped equation. The size choice changes chunk edges by a few sentences, while those errors change which sections exist.

This is one paper. The conclusions about overlap and the small-section floor depend on this paper's average sentence length (30 to 60 tokens) and section length, and they should be confirmed on 5 to 10 more papers, ideally with retrieval tests on a few real questions (not just chunk statistics), before changing anything.
