import { useMemo, useRef, useState } from "react";

import { isPending, type Doc } from "./api";

interface Props {
  docs: Doc[];
  /** Documents the user has excluded from search. */
  hidden: Set<string>;
  onToggle: (id: string) => void;
  onScopeAll: () => void;
  onScopeNone: () => void;
  onUpload: (files: File[]) => void;
  onRemove: (doc: Doc) => void;
  onReindex: (doc: Doc) => void;
  onPreview: (doc: Doc) => void;
  uploading: File[];
  busyId: string | null;
}

function bytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export default function Library(props: Props) {
  const { docs, hidden } = props;
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const ready = docs.filter((d) => d.status === "ready");

  const totals = useMemo(
    () => ({
      pages: ready.reduce((a, d) => a + d.page_count, 0),
      chunks: ready.reduce((a, d) => a + d.chunk_count, 0),
      ocr: ready.reduce((a, d) => a + d.ocr_pages, 0),
    }),
    [ready],
  );

  return (
    <aside className="library">
      <div className="pane-head">
        <span className="pane-title">Library</span>
        <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>
          {ready.length} ready
        </span>
      </div>

      <div
        className={`drop${over ? " over" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          props.onUpload(Array.from(e.dataTransfer.files));
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
      >
        <strong>Drop PDFs here</strong>
        <span>or click to browse &middot; max 50 MB each</span>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          onChange={(e) => {
            props.onUpload(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
      </div>

      {props.uploading.length > 0 && (
        <div className="empty-note">
          Uploading {props.uploading.map((f) => f.name).join(", ")}&hellip;
        </div>
      )}

      {ready.length > 1 && (
        <div style={{ display: "flex", gap: 6, padding: "0 12px 10px" }}>
          <button className="btn" style={{ flex: 1, fontSize: 11 }} onClick={props.onScopeAll}>
            Search all
          </button>
          <button className="btn" style={{ flex: 1, fontSize: 11 }} onClick={props.onScopeNone}>
            Clear scope
          </button>
        </div>
      )}

      <div className="doclist">
        {docs.map((doc) => {
          const inScope = !hidden.has(doc.id);
          const pending = isPending(doc);
          const failed = doc.status === "failed";
          return (
            <div
              key={doc.id}
              className={`doc ${inScope ? "in-scope" : "all-scope"}`}
              onClick={() => !failed && !pending && props.onToggle(doc.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter") props.onToggle(doc.id);
              }}
            >
              <span className="doc-check" aria-hidden>
                {inScope ? "✓" : ""}
              </span>
              <div className="doc-name">{doc.title ?? doc.filename}</div>
              <div className="doc-meta">
                {pending && (
                  <span className="tag warn">
                    <span className="dot" />
                    {doc.status}
                  </span>
                )}
                {failed && <span className="tag err">failed</span>}
                {doc.status === "ready" && (
                  <>
                    <span>{doc.page_count}p</span>
                    <span>{doc.chunk_count} chunks</span>
                    {doc.ocr_pages > 0 && <span className="tag">OCR {doc.ocr_pages}p</span>}
                  </>
                )}
                {!pending && !failed && <span>{bytes(doc.size_bytes)}</span>}
              </div>

              {pending && (
                <>
                  <div className="progress-line">
                    <i />
                  </div>
                  <div className="doc-meta" style={{ marginTop: 4 }}>
                    {doc.progress ?? "queued"}
                  </div>
                </>
              )}

              {failed && <div className="doc-meta" style={{ color: "var(--danger)" }}>{doc.error}</div>}

              <div className="doc-actions" onClick={(e) => e.stopPropagation()}>
                {doc.status === "ready" && (
                  <button className="btn quiet" onClick={() => props.onPreview(doc)}>
                    View pages
                  </button>
                )}
                <button
                  className="btn quiet"
                  disabled={props.busyId === doc.id || pending}
                  onClick={() => props.onReindex(doc)}
                >
                  {failed ? "Retry" : "Reindex"}
                </button>
                <button className="btn quiet danger" onClick={() => props.onRemove(doc)}>
                  Delete
                </button>
              </div>
            </div>
          );
        })}

        {!docs.length && (
          <div className="empty-note">
            No documents yet. Upload PDFs to build a searchable corpus. Scanned pages are read with OCR.
          </div>
        )}
      </div>

      {ready.length > 0 && (
        <div className="pane-head" style={{ borderTop: "1px solid var(--rule)", borderBottom: "none" }}>
          <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>
            {totals.pages} pages &middot; {totals.chunks} chunks
            {totals.ocr > 0 ? ` · ${totals.ocr} via OCR` : ""}
          </span>
        </div>
      )}
    </aside>
  );
}
