# Evaluation results

Corpus: 3 generated PDFs, 16 pages, one image-only document (must be OCR'd).
Questions: 50 — 42 answerable, 8 unanswerable. All corpus facts are fictional,
so a correct answer must come from retrieval rather than model knowledge.

Run with:

```powershell
python -m eval.build_corpus
python -m eval.run_eval
```

## Retrieval (answerable questions)

| Metric | Score |
|---|---|
| hit@1 | **97.6%** |
| hit@3 | **100%** |
| hit@6 | **100%** |
| MRR | **0.988** |
| Evidence gate passes answerable questions | 100% |
| Evidence gate rejects unanswerable questions | 12.5% |

The gate is deliberately a cheap coarse filter for off-topic questions; it is not
the refusal mechanism. Deciding whether a passage *actually answers* the question
is the model's job, which is why the last row is low by design.

## Answers — extractive fallback (no LLM key)

| Metric | Score |
|---|---|
| Answer accuracy | 81.0% |
| Citation accuracy (≥1 cited page is a gold page) | 100% |
| Citation precision (citations on gold pages) | 96.1% |
| False refusals (answerable but refused) | 9.5% |
| Refusal recall (unanswerable correctly refused) | 62.5% |

By question type: OCR 100%, reasoning 100%, facts 85.2%, tables 57.1%,
multi-hop 0%.

## What these numbers mean

**Retrieval is the strong part.** The correct page is ranked first for 41 of 42
answerable questions, and the gold page is always in the top 3.

**Citation precision is the point of the project** and it holds up even in the
weakest answer mode: 96% of citations point at a page that supports the claim,
and invalid citations cannot survive at all — they are stripped and an
uncited answer is downgraded to a refusal.

**These answer metrics are a floor, not the headline.** They come from the
fallback mode, which can only quote retrieved sentences and cannot reason:

- It cannot refuse a near-miss question. Asked for *fiscal 2022* revenue when
  the corpus only covers *fiscal 2025*, it quotes the 2025 figure. This single
  class of failure is most of the 62.5% refusal recall.
- Multi-hop questions ("Who are the CEO and the Board Chair?") fail because it
  returns sentences rather than a synthesis.
- Table accuracy improved from 28.6% to 57.1% by keeping adjacent numeric rows
  together as one quotable unit, so a figure keeps its header.

With `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` set, the answer step is a real model
reading numbered passages, which addresses all three. Those figures are **not**
included here because no key was available when this was measured — the harness
is the same, so re-running after adding a key fills in the comparison:

```powershell
python -m eval.run_eval      # writes results.json next to this file
```

## Honest notes

- 8 unanswerable questions is a small sample: one question is 12.5 percentage
  points of refusal recall.
- The measured 12.5% gate rejection is expected — 7 of the 8 unanswerable
  questions are topically on-target (e.g. "How much does the HX-200 cost?"), so
  passing the coarse gate is correct behaviour.
- `results.json` holds every question with retrieved passages, scores and the
  full answer text, which is what to inspect when a number looks wrong.
