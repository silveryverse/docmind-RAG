import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import AnswerContent, { type OpenCitation } from "./AnswerContent";
import Composer from "./Composer";
import Library from "./Library";
import Viewer from "./Viewer";
import { api, isPending, type AskResponse, type Citation, type Doc } from "./api";

interface Turn {
  id: number;
  question: string;
  scope: string[];
  response: AskResponse | null;
  error: string | null;
}

const SAMPLES = [
  "What was the group revenue for fiscal 2025?",
  "How do I reset the unit after an E04 lockout?",
  "How many days must staff work from a council building?",
  "What is the extended warranty on the compressor?",
];

export default function App() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploadNames, setUploadNames] = useState<File[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [viewer, setViewer] = useState<{ docId: string; page: number } | null>(null);
  const [openCitation, setOpenCitation] = useState<OpenCitation | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const turnId = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  const ready = useMemo(() => docs.filter((d) => d.status === "ready"), [docs]);
  const inScope = useMemo(() => ready.filter((d) => !hidden.has(d.id)), [ready, hidden]);
  const processing = docs.some(isPending);

  const scopeLabel = inScope.length === 0
    ? "nothing selected"
    : inScope.length === ready.length
      ? `all ${ready.length} document${ready.length === 1 ? "" : "s"}`
      : inScope.length === 1
        ? inScope[0].title ?? inScope[0].filename
        : `${inScope.length} of ${ready.length} documents`;

  const loadDocs = useCallback(async () => {
    try {
      setDocs(await api.documents());
      setApiError(null);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Cannot reach the API");
    }
  }, []);

  useEffect(() => {
    void loadDocs();
  }, [loadDocs]);

  // Poll only while something is being ingested.
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(() => void loadDocs(), 1500);
    return () => clearInterval(t);
  }, [processing, loadDocs]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && busy) el.scrollTop = el.scrollHeight;
  }, [busy, turns.length]);

  const upload = async (files: File[]) => {
    const pdfs = files.filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) {
      setNotice("Only PDF files can be uploaded.");
      return;
    }
    setUploadNames(pdfs);
    setNotice(null);
    for (const file of pdfs) {
      try {
        await api.upload(file);
      } catch (e) {
        setNotice(e instanceof Error ? e.message : "Upload failed");
      }
    }
    setUploadNames([]);
    await loadDocs();
  };

  const ask = async (question: string) => {
    const q = question.trim();
    if (q.length < 2 || busy) return;
    if (!inScope.length) {
      setNotice("Select at least one document to search.");
      return;
    }
    const id = ++turnId.current;
    const scopeIds = inScope.map((d) => d.id);
    setTurns((t) => [...t, { id, question: q, scope: scopeIds, response: null, error: null }]);
    setInput("");
    setBusy(true);
    setNotice(null);
    try {
      const response = await api.ask(q, scopeIds);
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, response } : turn)));
      if (response.citations.length) {
        openSource(response.citations[0], response);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "Request failed";
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, error: message } : turn)));
    } finally {
      setBusy(false);
    }
  };

  const openSource = (citation: Citation, response: AskResponse) => {
    setViewer({ docId: citation.document_id, page: citation.page });
    setOpenCitation({ documentId: citation.document_id, page: citation.page, n: citation.n });
    setCollapsed(false);
    void response;
  };

  const openPage = (doc: Doc, page: number) => {
    setViewer({ docId: doc.id, page });
    setOpenCitation(null);
    setCollapsed(false);
  };

  const viewerDoc = viewer ? docs.find((d) => d.id === viewer.docId) ?? null : null;

  // All citations that land on the page currently shown in the viewer.
  const highlights = useMemo(() => {
    if (!viewer || !openCitation) return [];
    const onPage = new Map<number, { boxes: [number, number, number, number][]; n: number }>();
    for (const turn of turns) {
      for (const c of turn.response?.citations ?? []) {
        if (c.document_id === viewer.docId && c.page === viewer.page && c.boxes?.length) {
          onPage.set(c.n, { boxes: c.boxes, n: c.n });
        }
      }
    }
    return [...onPage.values()];
  }, [turns, viewer, openCitation]);

  const excerpt = useMemo(() => {
    if (!openCitation) return null;
    const hit = turns
      .flatMap((turn) => turn.response?.citations ?? [])
      .find(
        (c) =>
          c.n === openCitation.n &&
          c.document_id === openCitation.documentId &&
          c.page === openCitation.page,
      );
    return hit ? { n: hit.n, text: hit.snippet } : null;
  }, [turns, openCitation]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="wordmark">
          <strong>DocMind</strong>
          <span>document intelligence</span>
        </div>
        <div className="topbar-stats">
          <dl className="stat">
            <dt>corpus</dt>
            <dd>{ready.reduce((a, d) => a + d.page_count, 0)} pages</dd>
          </dl>
          <dl className="stat">
            <dt>passages</dt>
            <dd>{ready.reduce((a, d) => a + d.chunk_count, 0)}</dd>
          </dl>
          <dl className="stat">
            <dt>ocr</dt>
            <dd>{ready.reduce((a, d) => a + d.ocr_pages, 0)} pages</dd>
          </dl>
        </div>
      </header>

      <div className="body">
        <Library
          docs={docs}
          hidden={hidden}
          onToggle={(id) =>
            setHidden((h) => {
              const next = new Set(h);
              if (next.has(id)) next.delete(id);
              else next.add(id);
              return next;
            })
          }
          onScopeAll={() => setHidden(new Set())}
          onScopeNone={() => setHidden(new Set(ready.map((d) => d.id)))}
          onUpload={upload}
          onRemove={async (doc) => {
            if (!confirm(`Delete “${doc.title ?? doc.filename}” and its index?`)) return;
            await api.remove(doc.id);
            await loadDocs();
          }}
          onReindex={async (doc) => {
            setBusyId(doc.id);
            try {
              await api.reindex(doc.id);
              await loadDocs();
            } finally {
              setBusyId(null);
            }
          }}
          onPreview={(doc) => openPage(doc, 1)}
          uploading={uploadNames}
          busyId={busyId}
        />

        <main className="thread">
          <div className="thread-scroll" ref={scrollRef}>
            <div className="thread-inner">
              {apiError && (
                <div className="error-box" style={{ marginBottom: 18 }}>
                  {apiError} — is the API running on port 8000?
                </div>
              )}

              {turns.length === 0 && (
                <div className="intro">
                  <h1>Answers with page-level citations</h1>
                  <p>
                    Every claim in an answer is traceable to the page it came from. If the documents do not
                    support an answer, DocMind says so instead of guessing.
                  </p>
                  <ul>
                    <li>
                      <b>1</b>
                      <span>
                        Upload PDFs. Scanned pages are detected and read with OCR, so image-only reports are
                        searchable too.
                      </span>
                    </li>
                    <li>
                      <b>2</b>
                      <span>
                        Ask in plain language. Retrieval combines vector search with keyword matching, then
                        re-scores the candidates.
                      </span>
                    </li>
                    <li>
                      <b>3</b>
                      <span>
                        Click any <span className="cite">1</span> marker to read the highlighted passage on the
                        original page.
                      </span>
                    </li>
                  </ul>
                </div>
              )}

              {turns.map((turn) => (
                <article className="turn" key={turn.id}>
                  <div className="q">
                    <span className="q-mark">Q</span>
                    <div>
                      <div className="q-text">{turn.question}</div>
                      <div className="q-note">
                        {turn.response
                          ? `${turn.response.passages.length} passages retrieved · ` +
                            `${(turn.response.timings_ms.retrieval ?? 0) + (turn.response.timings_ms.generation ?? 0)} ms · ` +
                            `${turn.response.mode === "llm" ? "model answer" : "extractive fallback"}`
                          : "searching the corpus…"}
                      </div>
                    </div>
                  </div>

                  <div className="a">
                    {turn.error && (
                      <div className="error-box">
                        {turn.error}
                        <div style={{ marginTop: 6 }}>
                          <button className="btn" onClick={() => ask(turn.question)}>
                            Retry
                          </button>
                        </div>
                      </div>
                    )}

                    {!turn.response && !turn.error && (
                      <div className="thinking">
                        <span>retrieving and re-scoring passages</span>
                        <span className="bar">
                          <i />
                        </span>
                      </div>
                    )}

                    {turn.response && !turn.response.answerable && (
                      <>
                        <div className="refusal">
                          {turn.response.answer}
                          <div className="refusal-reason">
                            reason: {turn.response.refusal_reason ?? "insufficient evidence"}
                            {turn.response.passages.length > 0 &&
                              ` · closest passage: ${turn.response.passages[0].filename}, page ${turn.response.passages[0].page}`}
                          </div>
                        </div>
                        {turn.response.passages.length > 0 && (
                          <>
                            <div className="sources-head" style={{ marginTop: 16 }}>
                              nearest passages (not used)
                            </div>
                            {turn.response.passages.slice(0, 3).map((p) => (
                              <button
                                key={`${p.document_id}-${p.page}-${p.similarity}`}
                                type="button"
                                className="src"
                                onClick={() => {
                                  setViewer({ docId: p.document_id, page: p.page });
                                  setOpenCitation(null);
                                  setCollapsed(false);
                                }}
                              >
                                <span className="src-n">–</span>
                                <span className="src-body">
                                  <span className="src-file">
                                    <b>{p.filename}</b>
                                    <span>p.{p.page}</span>
                                  </span>
                                  <span className="src-quote">{p.text}</span>
                                </span>
                                <span className="src-score">sim {p.similarity.toFixed(2)}</span>
                              </button>
                            ))}
                          </>
                        )}
                      </>
                    )}

                    {turn.response && turn.response.answerable && (
                      <AnswerContent
                        answer={turn.response.answer}
                        citations={turn.response.citations}
                        openN={openCitation?.n ?? null}
                        onOpen={(c) => openSource(c, turn.response!)}
                      />
                    )}
                  </div>
                </article>
              ))}
            </div>
          </div>

          {notice && (
            <div style={{ padding: "0 32px 8px" }}>
              <div className="error-box">{notice}</div>
            </div>
          )}

          {turns.length === 0 && ready.length > 0 && (
            <div className="samples">
              {SAMPLES.map((s) => (
                <button key={s} onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          <Composer
            value={input}
            onChange={setInput}
            onSubmit={() => void ask(input)}
            busy={busy}
            scopeLabel={scopeLabel}
            disabled={!ready.length}
          />
        </main>

        <Viewer
          doc={viewerDoc}
          page={viewer?.page ?? 1}
          openCitation={openCitation}
          highlights={highlights}
          excerpt={excerpt}
          collapsed={collapsed}
          onToggleCollapsed={() => setCollapsed((c) => !c)}
          onPage={(p) => setViewer((v) => (v ? { ...v, page: p } : v))}
        />
      </div>
    </div>
  );
}
