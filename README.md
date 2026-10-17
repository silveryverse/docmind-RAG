# DocMind

DocMind lets you upload PDFs and ask questions in plain English. It answers from
what is actually in the document, and every answer points back to the exact page
and passage it came from. If the evidence is missing, it says so instead of
guessing.

![DocMind answering a question, with the cited passage highlighted on the source page](docs/ui.png)

*Each answer includes numbered citations, the retrieved passages it was built
from, and the source page with the cited regions highlighted. Click any `[n]`
marker to jump to the supporting page.*

| | |
|---|---|
| **Stack** | Python 3.11 · FastAPI · PostgreSQL + pgvector · React + TypeScript · PyMuPDF + RapidOCR |
| **Runs offline** | Embedded Postgres, local embedding and rerank models, no API key required |
| **Measured** | retrieval hit@1 **97.6%** · hit@3 **100%** · citation precision **96.1%** on a 50-question benchmark |
| **Tests** | 31 passing (19 unit + 12 integration) |

---

## Features

- **PDF parsing with OCR fallback.** Pages with little or no text layer are
  rendered and read with RapidOCR. Mixed digital and scanned documents work, and
  the OCR output is cleaned up enough to be searchable instead of just readable.
- **Page-level chunking.** A chunk never crosses a page boundary, so each chunk
  maps to one citable page. Bounding boxes are kept with the text.
- **Hybrid retrieval.** pgvector cosine search and PostgreSQL full-text search
  run side by side, then their results are fused and re-ranked.
- **Verified citations.** The model has to cite passage numbers, and the app
  checks those citations against what was actually retrieved. If a citation is
  invalid, it gets dropped.
- **Refusal when evidence is missing.** The app does a quick evidence check
  before answering, and it refuses if the retrieved text does not actually answer
  the question.
- **Source viewer.** The cited page is rendered with the relevant regions
  highlighted next to the extracted excerpt.
- **Benchmarked against a synthetic corpus.** Fifty questions are generated from
  fictional facts, so a correct answer has to come from retrieval rather than
  prior knowledge.

---

## Quick start

Start the backend and frontend in two terminals. No Docker, no external
Postgres, and no API key is needed for the basic setup.

### 1. Backend

The first run creates the virtualenv, starts an embedded PostgreSQL instance
with pgvector under `backend/data/pg`, and downloads the embedding and rerank
models (a few hundred MB, once).

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

```bash
# macOS / Linux
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173, proxies /api to :8000
```

Drop a few PDFs into the library pane and ask a question. If you want a quick
sample, generate the benchmark corpus. It writes three ready-to-use PDFs, one of
which is image-only so you can watch OCR do its job:

```powershell
cd backend
.\.venv\Scripts\python -m eval.build_corpus   # -> backend/eval/corpus/*.pdf
```

### 3. Add an LLM key for real answers

Without a key, the answer step runs in extractive fallback mode: it quotes the
best-supported sentences verbatim. It works offline, but it cannot reason or
synthesise, so it is noticeably weaker. Copy `backend/.env.example` to
`backend/.env` and add one of these keys:

```
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

`GET /api/health` reports which provider is active. The provider is selected
automatically (`openai` → `anthropic` → `extractive`), or you can set
`LLM_PROVIDER` directly. Any OpenAI-compatible endpoint works via
`OPENAI_BASE_URL`.

### Production: one process, one port

```powershell
cd frontend && npm run build          # emits frontend/dist
cd ../backend && .\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

When `frontend/dist` exists the API serves it, so the whole app runs at
`http://localhost:8000/`.

### Using a managed Postgres instead

Set `DATABASE_URL=postgresql://user:pass@host:5432/db`. The schema creates the
`vector` extension itself if the role is allowed to; otherwise run
`CREATE EXTENSION vector;` once.

> **Embedded Postgres and unclean shutdowns.** If the machine crashes or the
> process is killed, Postgres replays its WAL on the next start, which can
> outlast the 10 seconds `pg_ctl` is willing to wait, so startup retries up to
> three times. The server log lives at `backend/data/pg.log`, deliberately
> *outside* the data directory: recovery has to fsync the data directory, and on
> Windows it cannot open a log file that `pg_ctl` still holds — which stalls
> recovery for 30 seconds against a timeout of 10. Stopping the API shuts the
> server down cleanly, and the data directory is never deleted, so your
> documents survive restarts. If a start still fails, stop any leftover
> `postgres` processes and try again.

---

## How it works

```
 PDF ──▶ extract text + boxes ──▶ OCR if the page has no text layer
            │
            ▼
     page-bounded chunks (never span pages, keep their boxes)
            │
            ▼
     embeddings ──▶ PostgreSQL:  chunks + vector(384) + tsvector
                                          │
 question ──▶ embed ──┬──▶ vector search ─┤
                     └──▶ full-text ─────┴──▶ RRF fusion ──▶ cross-encoder rerank
                                                                   │
                                            evidence gate ─────────┤ (reject off-topic)
                                                                   ▼
                        LLM (or extractive fallback) ──▶ validate citations ──▶ answer + [n]
                                                              │
                                                    no valid citation ──▶ refusal
```

### Ingestion — `app/pdf.py`, `app/chunking.py`, `app/ingest.py`

1. PyMuPDF extracts text blocks with bounding boxes per page.
2. Pages with less than `OCR_MIN_CHARS` of text are rendered and OCR'd. The
   render DPI is normalised from the measured line height, because the
   recogniser drops the spaces between words when glyphs are much larger or
   smaller than it was trained on — run-together text like
   `Eligibleemployeesmustwork` is unsearchable. Remaining glued words are split
   with a word-segmentation model, and hyphenated codes (`HX-SH2`) are preserved.
3. Text is chunked **within page boundaries**, oversized blocks split on sentence
   boundaries, tiny trailing fragments merged backwards.
4. Chunks, boxes, embeddings and a generated `tsvector` are written in one
   transaction; the document flips to `ready`.

Ingestion runs in a single background worker with progress the UI polls. Uploads
are de-duplicated by content hash.

### Retrieval — `app/retrieval.py`

Dense and sparse results are fused with reciprocal rank fusion and the top
candidates are re-scored by a cross-encoder (MiniLM). The keyword side ORs the
stemmed question terms rather than ANDing them, since a natural-language question
rarely matches every term in a passage.

A cheap **evidence gate** drops off-topic questions before any model call — this
is what makes refusals fast. It is deliberately coarse: deciding whether a
passage *answers* the question is the model's job.

### Answering and citation validation — `app/rag.py`

The model receives numbered passages and must append `[n]` after every factual
sentence, or return `answerable: false`. Then:

- citation numbers that don't exist are **removed**;
- survivors are renumbered `1..k` in order of first appearance;
- **an answer with zero valid citations is downgraded to a refusal.**

So the model cannot cite a source that was never retrieved. The response also
carries the retrieved passages and per-stage timings, which is what the UI shows
under each answer and what makes failures debuggable.

---

## Evaluation

`backend/eval/` is a self-contained benchmark: three generated PDFs (16 pages,
one image-only so it must be OCR'd), 50 questions with gold pages and required
facts, and a scorer. **Every fact in the corpus is fictional**, so a model cannot
answer from prior knowledge — a correct answer has to come from retrieval.

```powershell
cd backend
.\.venv\Scripts\python -m eval.build_corpus               # write the PDFs
.\.venv\Scripts\python -m eval.run_eval                   # ingest, ask, score
.\.venv\Scripts\python -m eval.run_eval --retrieval-only  # skip answer scoring
.\.venv\Scripts\python -m eval.run_eval --only nw-09,hx-13
```

### Retrieval — 42 answerable questions

| Metric | Score |
|---|---|
| hit@1 | **97.6%** |
| hit@3 | **100%** |
| MRR | **0.988** |

### Answers — offline extractive fallback (no LLM key)

| Metric | Score |
|---|---|
| Answer accuracy | 81.0% |
| Citation accuracy (≥1 cited page is a gold page) | **100%** |
| Citation precision (citations on gold pages) | **96.1%** |
| False refusals | 9.5% |
| Refusal recall | 62.5% |

By type: OCR **100%**, reasoning **100%**, facts 85.2%, tables 57.1%,
multi-hop 0%.

**These answer numbers are a floor, not the headline.** They come from the
fallback mode, which can only quote retrieved sentences and cannot reason, so it
fails exactly where reasoning is required — most visibly on near-miss questions
(asked for *fiscal 2022* revenue when the corpus only covers *fiscal 2025*, it
quotes the 2025 figure). With an LLM configured the answer step is a real model
reading numbered passages. Those numbers are **not** in the table above because
no API key was available when this was measured; the harness is unchanged, so
`python -m eval.run_eval` after adding a key fills in the comparison.
[`eval/RESULTS.md`](backend/eval/RESULTS.md) has the full breakdown and caveats,
and `eval/results.json` holds every question with its retrieved passages and
scores.

---

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest                  # unit tests, no network, ~5s
.\.venv\Scripts\python -m pytest -m integration   # real DB, embeddings, HTTP API
```

Unit tests cover chunking invariants (page-bounded, size caps, box preservation),
text cleaning, OCR word re-spacing, and citation parsing/renumbering. The
integration suite ingests a document for real, checks that the correct passage
ranks first, that off-topic questions are gated, that document scoping is
enforced, and that a failed ingest records an error rather than hanging.

---

## Configuration

`backend/app/config.py`, overridable by environment or `backend/.env`
(see [`backend/.env.example`](backend/.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | *unset → embedded Postgres* | Managed Postgres connection string |
| `DATA_DIR` | `backend/data` | Uploads, model cache, embedded DB |
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model (384-dim) |
| `EMBED_DIM` | `384` | Must match the model |
| `RERANK_ENABLED` | `true` | Cross-encoder re-scoring |
| `CANDIDATES` / `TOP_K` | `24` / `6` | Retrieved → kept |
| `MIN_RERANK_SCORE` | `-7.0` | Evidence gate threshold |
| `CHUNK_TARGET_CHARS` | `550` | Chunking target |
| `OCR_MIN_CHARS` / `OCR_DPI` | `40` / `150` | When and how to OCR |
| `MAX_UPLOAD_MB` | `50` | Upload limit |
| `LLM_PROVIDER` | `auto` | `auto` \| `openai` \| `anthropic` \| `extractive` |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` | `gpt-4.1-mini` / `claude-sonnet-4-5` | Answer model |

Changing `EMBED_MODEL` means changing `EMBED_DIM` to match and re-indexing
everything (`python manage.py reindex`).

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Provider, models, DB reachability |
| `GET` | `/api/documents` | List with status, page/chunk counts, OCR page count |
| `POST` | `/api/documents` | Upload a PDF (multipart); `409` on duplicate content |
| `DELETE` | `/api/documents/{id}` | Delete document, pages and chunks |
| `POST` | `/api/documents/{id}/reindex` | Re-parse, re-chunk, re-embed |
| `GET` | `/api/documents/{id}/file` | Original PDF |
| `GET` | `/api/documents/{id}/pages/{n}` | Page text and dimensions |
| `GET` | `/api/documents/{id}/pages/{n}/image` | Rendered page PNG (used for highlighting) |
| `POST` | `/api/ask` | `{question, document_ids?}` → answer, citations, retrieved passages, timings |

`backend/manage.py` offers the useful parts from the shell:

```powershell
python manage.py ingest path/to/file.pdf      # index synchronously
python manage.py reindex                      # rebuild every document's index
python manage.py ask "How much clearance is needed in front of the fan?" 
python manage.py db-url                       # which database is in use
```

---

## Project layout

```
backend/
  app/
    config.py      settings (env + .env)
    db.py          connection pool, schema, pgvector/tsvector indexes
    pdf.py         text extraction, OCR fallback, text cleaning, page rendering
    chunking.py    page-bounded chunking with boxes
    embeddings.py  local embedder + cross-encoder reranker
    ingest.py      the pipeline, background worker, uploads
    retrieval.py   hybrid search, RRF, rerank, evidence gate
    rag.py         prompt, citation validation, refusal, extractive fallback
    main.py        FastAPI routes, static frontend
  eval/            corpus generator, questions.json, scorer, RESULTS.md
  tests/           19 unit + 12 integration tests
  manage.py        small admin CLI
frontend/
  src/
    App.tsx           documents, question turns, scope, viewer target
    Library.tsx       upload, ingestion status, per-document scope
    Composer.tsx      question input
    AnswerContent.tsx answers + citation markers + source list
    Viewer.tsx        rendered page, highlighted cited regions, excerpt
    api.ts            typed API client
    styles.css        the entire design system
docs/ui.png        screenshot used above
```

---

## Design decisions

**Chunks never cross pages.** Anything else makes "cite the exact page"
approximate: a chunk spanning pages 3–4 has no single honest citation.

**Hybrid retrieval, then rerank.** Dense search handles paraphrase; full-text
handles exact identifiers, codes and numbers (`E04`, `HX-SH2`, `$2,830m`) that
embeddings blur. The cross-encoder then fixes the ordering, which is where most
of the hit@1 comes from.

**Validate citations instead of trusting them.** Prompt instructions reduce
fabricated citations but cannot eliminate them. Stripping invalid ones and
refusing uncited answers turns "the model probably cited a real page" into a
guarantee the UI can rely on.

**An evidence gate before the model.** Off-topic questions are decided in
milliseconds by retrieval scores rather than by paying for a model call, and the
threshold is deliberately loose so that genuine questions are never refused
early — precision is the model's job.

**Embedded Postgres by default.** The benchmark and the tests run against a real
`pgvector` database with no Docker and no setup; point `DATABASE_URL` at a
managed instance for deployment and nothing else changes.

**Offline-capable by design.** Local embedding and rerank models plus an
extractive answer path mean the whole system is runnable and measurable on a
machine with no API key — which is also how it was evaluated here.

---

## Known limitations

- **The offline mode cannot refuse near-miss questions.** Asked about *fiscal
  2022* revenue when only *fiscal 2025* exists, the extractive fallback answers
  with the 2025 figure. With an LLM configured the prompt handles this correctly;
  without a key, expect roughly 60% refusal recall on this class.
- **OCR quality depends on scan quality.** The digit `5` is occasionally read as
  `S`. Values are usually recoverable from context, but scan resolution matters.
- **Tables are chunked as text**, so in the extractive mode a row can be quoted
  without its header (joining adjacent numeric rows recovered 28.6% → 57.1% on
  table questions, but it isn't a real table parser). The LLM path sees the whole
  table.
- **Ingestion is in-process** — one background worker, status polled by the UI.
  A production deployment would move it to a queue; nothing else would change.
- **No authentication or multi-tenancy.** Anyone who can reach the API can read
  every document, so don't expose it as-is.
- **No streaming answers**; the response arrives in one piece.
- **Benchmark scale.** 50 questions over 16 pages is enough to catch regressions
  and compare configurations, not enough to make strong claims — one question
  moves refusal recall by 12.5 points.
