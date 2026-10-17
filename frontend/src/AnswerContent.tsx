import { useEffect, useMemo, useRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";

import type { Citation } from "./api";

export interface OpenCitation {
  documentId: string;
  page: number;
  n: number;
}

interface Props {
  answer: string;
  citations: Citation[];
  openN: number | null;
  onOpen: (citation: Citation) => void;
}

/** Citations are rewritten to markdown links with a `cite:` scheme, so the
 *  renderer can stay a pure function of props. */
const CITE_LINK = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

function toMarkdown(answer: string, known: Set<number>): string {
  return answer.replace(CITE_LINK, (whole, group: string) => {
    const ns = group.split(",").map((s) => parseInt(s.trim(), 10)).filter((n) => known.has(n));
    if (!ns.length) return whole;
    return ns.map((n) => `[${n}](cite:${n})`).join("");
  });
}

export default function AnswerContent({ answer, citations, openN, onOpen }: Props) {
  const byN = useMemo(() => new Map(citations.map((c) => [c.n, c])), [citations]);
  const markdown = useMemo(() => toMarkdown(answer, new Set(byN.keys())), [answer, byN]);

  const components: Components = useMemo(
    () => ({
      a: ({ href, children }) => {
        const n = href?.startsWith("cite:") ? parseInt(href.slice(5), 10) : NaN;
        const citation = byN.get(n);
        if (!citation) {
          return (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          );
        }
        return (
          <button
            type="button"
            className={`cite${openN === n ? " active" : ""}`}
            title={`${citation.title ?? citation.filename} — page ${citation.page}`}
            onClick={() => onOpen(citation)}
          >
            {n}
          </button>
        );
      },
      p: ({ children }) => <p>{children}</p>,
    }),
    [byN, openN, onOpen],
  );

  return (
    <>
      <div className="answer">
        <ReactMarkdown components={components} urlTransform={(url) => url}>
          {markdown}
        </ReactMarkdown>
      </div>
      <SourceList citations={citations} openN={openN} onOpen={onOpen} />
    </>
  );
}

export function SourceList({
  citations,
  openN,
  onOpen,
  label = "cited passages",
}: {
  citations: Citation[];
  openN: number | null;
  onOpen: (c: Citation) => void;
  label?: string;
}) {
  const activeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [openN]);

  if (!citations.length) return null;

  return (
    <div className="sources">
      <div className="sources-head">
        {citations.length} {citations.length === 1 ? label.replace(/s$/, "") : label}
      </div>
      {citations.map((c) => {
        const active = openN === c.n;
        return (
          <button
            key={`${c.document_id}-${c.page}-${c.n}`}
            ref={active ? activeRef : undefined}
            type="button"
            className={`src${active ? " active" : ""}`}
            onClick={() => onOpen(c)}
          >
            <span className="src-n">[{c.n}]</span>
            <span className="src-body">
              <span className="src-file">
                <b>{c.title ?? c.filename}</b>
                <span>p.{c.page}</span>
              </span>
              <span className="src-quote">{c.snippet}</span>
            </span>
            <span className="src-score">
              {c.score != null ? c.score.toFixed(1) : ""}
            </span>
          </button>
        );
      })}
    </div>
  );
}
