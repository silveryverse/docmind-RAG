import { useEffect, useRef, useState } from "react";

import { api, type Doc } from "./api";
import type { OpenCitation } from "./AnswerContent";

interface Props {
  doc: Doc | null;
  page: number;
  openCitation: OpenCitation | null;
  highlights: { boxes: [number, number, number, number][]; n: number }[];
  excerpt: { n: number; text: string } | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onPage: (page: number) => void;
}

export default function Viewer(props: Props) {
  const { doc, page, openCitation, highlights, excerpt, collapsed } = props;
  const stageRef = useRef<HTMLDivElement>(null);
  const imageKey = doc ? `${doc.id}-${page}` : null;
  // Tracks which image has finished loading, so highlights only appear once the
  // page underneath them is painted. Reset by the image key, not by an effect.
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const loaded = loadedKey === imageKey;

  useEffect(() => {
    if (stageRef.current) stageRef.current.scrollTop = 0;
  }, [doc?.id, page]);

  if (collapsed) {
    return (
      <aside className="viewer collapsed">
        <button className="viewer-toggle" onClick={props.onToggleCollapsed} title="Show source pages">
          <span aria-hidden>&laquo;</span>
          <span className="vlabel">Sources</span>
        </button>
      </aside>
    );
  }

  const focused = highlights.find((h) => h.n === openCitation?.n) ?? highlights[0];

  return (
    <aside className="viewer">
      <div className="viewer-head">
        <button className="btn quiet" onClick={props.onToggleCollapsed} title="Hide panel" aria-label="Hide panel">
          &raquo;
        </button>
        <div className="viewer-title">
          {doc ? (
            <>
              <b>{doc.title ?? doc.filename}</b>
              <span>
                page {page} of {doc.page_count}
                {doc.ocr_pages > 0 && " · searchable OCR"}
              </span>
            </>
          ) : (
            <>
              <b>No page selected</b>
              <span>open a citation to inspect its source</span>
            </>
          )}
        </div>
        {doc && (
          <div className="pager">
            <button className="btn" disabled={page <= 1} onClick={() => props.onPage(page - 1)} aria-label="Previous page">
              &larr;
            </button>
            <span className="page-num">
              {page}/{doc.page_count}
            </span>
            <button
              className="btn"
              disabled={page >= doc.page_count}
              onClick={() => props.onPage(page + 1)}
              aria-label="Next page"
            >
              &rarr;
            </button>
          </div>
        )}
      </div>

      {doc ? (
        <>
          <div className="page-stage" ref={stageRef}>
            <div className="page-canvas">
              <img
                key={imageKey}
                src={api.pageImage(doc.id, page, 1000)}
                alt={`${doc.filename} page ${page}`}
                onLoad={() => setLoadedKey(imageKey)}
              />
              {loaded &&
                highlights.map((h, i) =>
                  h.boxes.map(([x0, y0, x1, y1], j) => (
                    <span
                      key={`${i}-${j}`}
                      className={`hl${focused && h.n !== focused.n ? " dim" : ""}${focused?.n === h.n ? " focus" : ""}`}
                      style={{
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${Math.max(x1 - x0, 0.004) * 100}%`,
                        height: `${Math.max(y1 - y0, 0.004) * 100}%`,
                      }}
                    />
                  )),
                )}
            </div>
          </div>

          <div className="viewer-excerpt">
            <div className="excerpt-label">
              {excerpt ? `Cited excerpt [${excerpt.n}]` : "Cited excerpt"}
              <span style={{ marginLeft: "auto", letterSpacing: 0, textTransform: "none" }}>
                {highlights.length > 1 ? `${highlights.length} cited passages on this page` : ""}
              </span>
            </div>
            {excerpt ? (
              <div className="excerpt-text">{excerpt.text}</div>
            ) : (
              <div className="excerpt-text" style={{ color: "var(--ink-4)" }}>
                Nothing cited on this page yet.
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="viewer-empty">
          <div>
            Click a citation marker in an answer, or “View pages” on a document, to read the source here.
          </div>
        </div>
      )}
    </aside>
  );
}
