<!-- Soft Suave · The AI Engineering League -->

# Week 3 Practical — Task Set D

## Ingest the new endorsement pack and prove your chunking finds the answer

|        |                                                |
| ------ | ---------------------------------------------- |
| Domain | Insurance claims                               |
| Week   | 3 — Retrieval-Augmented Generation, From Parts |
| Module | M2 — Retrieval & RAG                           |
| Sat on | Week 4 · Monday                                |
| Marks  | 100                                            |

> **This is an extension of the app you already built in Week 3.** It is not a build from scratch, and it tests only this week's concepts. Bring your numbers written down.

---

## 1. Problem statement

Underwriting has issued 6 new endorsements to the homeowners wording, each one a form-numbered document (HO-0304 ed. 03-24 and friends) with an exclusions table and an effective date in the header. Your claims-assistant RAG app already indexes the base wording, but nobody has checked whether your current chunker keeps exclusion code E-17 attached to the endorsement that scopes it. Work against your existing pipeline: ingest the drop, measure two chunking strategies on questions you already know the answers to, and make the app refuse what it cannot source.

---

## 2. Requirements

1. Ingest the 6 supplied endorsements into your existing index with metadata on every chunk: source_file, form_number, policy_line, edition_date. A chunk with no source_file is a failed ingest.
2. Write 8 questions whose answers you already know and can point to by form_number and clause (at least 3 must depend on a row inside an exclusions table, e.g. whether exclusion E-17 applies to water damage from a burst supply line under HO-0304 ed. 03-24).
3. Index the same 6 endorsements under TWO chunking strategies — your current one, and a structure-aware one that splits on form/clause headers and never separates an exclusion row from its table header or form number. Run all 8 questions search-only against both and report hit-in-top-5 as a number out of 8 for each. Two strategies, two numbers, same 8 questions.
4. Add a metadata filter on policy_line and show one query where filtering changes the top-1 result. Paste both result lists (unfiltered and filtered) with scores.
5. Run 3 answerable questions through generation with a citation per claim that resolves to a real chunk_id and form_number + clause, and 3 questions your corpus cannot answer (e.g. the reserve-setting threshold for claim CLM-2024-88431, which lives in an adjuster system you never indexed) that must be refused rather than invented.
6. Time reality: do NOT re-index the whole policy wording library. Index the 6 new endorsements only, and say so in your write-up.

---

## 3. Expected output

A results.md containing: the 8 questions with their known-correct form_number/clause, a table of hit-in-top-5 for both chunking strategies (X/8 each), the unfiltered vs filtered result lists for one query, 3 cited answers with clickable/resolvable chunk_ids, 3 refusal transcripts, and one paragraph naming which chunking strategy you are keeping and why. Plus the code diff and the search-only dump for all 8 questions under both strategies.

---

## 4. Evaluation rubric

| Criterion                                                                                                       | Points  |
| --------------------------------------------------------------------------------------------------------------- | ------- |
| Two hit-in-top-5 numbers over the SAME 8 known-answer questions, per-question record shown, not a summary claim | 30      |
| Metadata filter demonstrably changing retrieval, with both result lists and scores pasted                       | 20      |
| Citations resolve to real chunk_ids and the cited chunk actually contains the claim (grader will check one)     | 20      |
| All 3 out-of-corpus questions honestly refused, with the refusal transcripts pasted                             | 20      |
| Written defended chunking choice plus one documented retrieval that embarrassed you, with its diagnosis         | 10      |
| **Total**                                                                                                       | **100** |

_Zero points for polish, UI, or "it works". This mirrors the House rubric: failure-finding and a number that moved are what score._

---

## 5. Bonus challenge

Find a question where the structure-aware chunker WINS on retrieval but LOSES on the final answer, because the tight exclusion-row chunk retrieves precisely and then strands the model without the definitions clause that says what 'sudden and accidental' means. Show both answers side by side and write two sentences on the precision/completeness tension.

---

## 6. Submission checklist

- [ ] results.md with all 8 questions and their known-correct form_number + clause
- [ ] The two hit-in-top-5 numbers (X/8 and Y/8) in one table
- [ ] Unfiltered vs filtered result lists for one policy_line query, with scores
- [ ] 3 cited answers + 3 refusal transcripts pasted verbatim
- [ ] Code diff showing the second chunker and the metadata fields
- [ ] One paragraph: which chunker ships, and why

---

## 7. Common mistakes

- **Writing the 8 questions AFTER looking at what retrieval returns — then your hit-rate measures your question-writing, not your chunker. Write the questions from the endorsements first, then run search.**
- **Changing the chunker AND swapping the embedding model in the same run, then reporting one number — two changes means you learn nothing about which one moved it.**
- **Judging chunking by eyeballing the retrieved text and saying it 'looks better'. Looks-better is not a number and scores zero here.**
- **Letting the grounding prompt say 'if the context is insufficient, use your best judgement' — an invented coverage answer read out to a policyholder is a bad-faith exposure. The refusal must be forced, not suggested.**
- **Re-indexing the entire wording library and running out of time at minute 45 with no measurement at all. The measurement is the deliverable; the ingest is plumbing.**

---

_Set D of 6. Sets A–F are equivalent in difficulty and objectives; only the domain differs._
