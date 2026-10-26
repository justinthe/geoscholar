# Unanswerable questions u06–u08

Appended to `eval/questions_manual.jsonl` (now 26 lines). `paper_ids` is empty on purpose: the correct behavior is "I could not find this in the indexed papers." Checked by a subagent against the 399 PDFs in `data/pdfs` (PyMuPDF text, whitespace-normalised, lowercased) and Qdrant `papers_c300`.

| id | Question | Kind (tag) |
|---|---|---|
| u06 | What are the ingredients of a classic margherita pizza? | off-topic |
| u07 | How is coral reef bleaching detected from satellite imagery? | in-domain |
| u08 | What F1-score did the 8-qubit QCNN reach on the SEVIRI Ash RGB volcanic cloud images? | false-premise |

## What was checked

**u06 (off-topic)**
- "margherita": 1 hit (2609.33687, an author name in a reference).
- "pizza": 1 hit (2608.11142, the author "Pizzati" in a reference). "mozzarella": 0 hits.
- Dense top 5 are irrelevant, with scores of about 0.51–0.53: a hyperspectral-XRF minerals dataset (2608.30537), a visual grounding paper (2610.01710), a Swiss crop benchmark (2608.09497).

**u07 (in-domain)**
- "bleaching": 0 hits in any paper.
- "coral": 30 hits across 7 papers, none about reefs. They are CORAL (correlation alignment / ordinal regression) or colour names; "playa los corales" in 2607.11838 is a place name.
- "reef": appears only as the label "reefs and invertebrates" in the SUIM segmentation dataset table of 2609.34528.
- Dense top 10 are marine pollution, methane, anomaly detection and cashew papers (2609.04906, 2609.15676, 2610.03649, 2608.11996). None mention coral or bleaching.
- Rejected candidate: oil spill detection in SAR (96 hits in 6 papers, mostly 2609.15676). Mangrove (15 hits) and lightning (6 hits) have some mentions and were not tested.

**u08 (false-premise)**
- In 2608.00072, every QCNN mention is of 2 or 4 qubits. The only results are 2-qubit and 4-qubit F1 scores (volcanic cloud: 0.97 and 1.00; multi-class: 0.85 and 0.90).
- "qcnn" appears only in 2608.00072 (31 hits); "ash rgb" appears only there too.
- "8-qubit" appears only in 2607.14160 (10 hits), a different paper (QUFEX on Sen2Fire), not a QCNN or SEVIRI result. SEVIRI is otherwise only in 2608.24715, which has no QCNN.
- Dense top 5 are all 2608.00072 chunks describing the 2- and 4-qubit models; none give an 8-qubit result.

## Caveats

- u08: the paper mentions Ash RGB 4 times, but I did not confirm that the QCNN images are specifically Ash RGB. The false premise is the 8-qubit claim.
- u08 is a good trap, since 2607.14160 has a real 8-qubit model and a retriever could mix up the two papers. A system might also cite the wrong paper's result.
- u06 and u07 were checked with dense search only, not hybrid.
- u07 candidates mangrove and lightning were never tested; only coral reef and oil spill were.
- u01–u05 have no `tags` field. Only u06–u08 are tagged.
