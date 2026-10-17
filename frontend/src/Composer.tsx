import { useEffect, useRef } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  scopeLabel: string;
  disabled: boolean;
}

export default function Composer({ value, onChange, onSubmit, busy, scopeLabel, disabled }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 190)}px`;
  }, [value]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const typing = /INPUT|TEXTAREA/.test(target.tagName);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="composer">
      <div className="composer-inner">
        <div className="composer-box">
          <textarea
            ref={ref}
            value={value}
            rows={1}
            placeholder="Ask a question about the documents…"
            disabled={disabled}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit();
              }
            }}
          />
          <div className="composer-foot">
            <span className="scope-note">
              <b>Scope</b>
              <span title={scopeLabel}>{scopeLabel}</span>
            </span>
            <div className="composer-actions">
              <span className="hint">↵ to ask · ⇧↵ newline</span>
              <button
                className="btn primary"
                onClick={onSubmit}
                disabled={busy || disabled || value.trim().length < 2}
              >
                {busy ? "Searching…" : "Ask"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
