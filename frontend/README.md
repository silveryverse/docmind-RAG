# DocMind frontend

React + TypeScript + Vite. Plain CSS in `src/styles.css` — no UI framework, no
utility-class soup.

## Run

```powershell
npm install
npm run dev     # http://localhost:5173, proxies /api to 127.0.0.1:8000
```

The dev server proxies `/api` to the backend, so start the backend first.

## Build

```powershell
npm run build   # tsc -b && vite build → dist/
```

If `dist/` exists, the FastAPI app serves it, so the whole app can run from one
process on port 8000.

Point the UI at a different backend with `VITE_API_BASE=https://api.example.com`.
In that case add the UI origin to the backend's `CORS_ORIGINS`.

## Structure

| File | Role |
|---|---|
| `App.tsx` | Owns documents, question turns, scope, and which page the viewer shows |
| `Library.tsx` | Upload, ingestion status, per-document scope toggles |
| `Composer.tsx` | Question input (`/` focuses it, Enter asks, Shift+Enter newlines) |
| `AnswerContent.tsx` | Renders answers and turns `[n]` markers into clickable citations |
| `Viewer.tsx` | Rendered source page with the cited regions highlighted, plus the excerpt |
| `api.ts` | Typed API client |

Typography is deliberately mixed: a serif for answers and document prose,
the sans for interface chrome, and a monospace for identifiers, page numbers and
retrieval scores.
