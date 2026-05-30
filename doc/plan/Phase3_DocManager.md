# Phase 3 — Svelte Frontend: Document Manager

**Status:** � Complete  
**Depends on:** [Phase2_ChatUI.md](Phase2_ChatUI.md) 🟢  
**Next phase:** [Phase4_Settings.md](Phase4_Settings.md)

---

## Goal

Add a document management panel that lets users:
1. Upload documents for ingestion using a native OS file picker
2. See all ingested documents with metadata (name, type, date, chunk count)
3. Delete documents from the knowledge base
4. See upload progress while ingestion runs

The panel slides in from the right (or bottom of sidebar) when the 📄 icon is clicked. This phase also fully implements `ui/src/lib/api/documents.ts`.

---

## Backend Endpoints Used

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/ingest/upload` | Upload file for ingestion |
| GET | `/api/documents` | List all ingested documents |
| DELETE | `/api/documents/{id}` | Delete document and its chunks |

**Note:** Tauri's `dialog.open()` is used for the file picker (Phase 5 wires this). In Phase 3 development, use an HTML `<input type="file">` as a temporary fallback — replaced in Phase 5.

---

## Steps

### 3.1 — Complete `ui/src/lib/api/documents.ts`

```typescript
export interface DocumentInfo {
  document_id: string;
  document_name: string;
  doc_type: string;
  chunk_count: number;
  ingested_at: string;   // ISO datetime string
}

export async function listDocuments(): Promise<DocumentInfo[]>

export async function uploadDocument(file: File): Promise<DocumentInfo>
// POST /api/ingest/upload  (multipart/form-data, field name: "file")

export async function deleteDocument(id: string): Promise<void>
// DELETE /api/documents/{id}
```

### 3.2 — Add `documents` store (`ui/src/lib/stores/documents.svelte.ts`)

```typescript
export let documents = $state<DocumentInfo[]>([]);
export let uploadState = $state<{
  active: boolean;
  filename: string;
  progress: 'uploading' | 'processing' | 'done' | 'error';
  error?: string;
}>({ active: false, filename: '', progress: 'done' });

export async function refreshDocuments(): Promise<void>
export async function uploadAndIngest(file: File): Promise<void>
export async function removeDocument(id: string): Promise<void>
```

### 3.3 — `DocumentManager.svelte`

Slide-in panel (right side, 420px wide) triggered by `showDocManager` store.

Layout:
```
┌─────────────────────────────────────┐
│ 📄 Knowledge Base          [×close] │
├─────────────────────────────────────┤
│ [+ Add Documents]                   │
│  Supported: PDF, TXT, MD, DOCX,     │
│  code files, images (OCR)           │
├─────────────────────────────────────┤
│ ▓▓▓▓▓▓░░░░ Ingesting report.pdf... │  ← IngestionProgress (shown during upload)
├─────────────────────────────────────┤
│ 3 documents in knowledge base       │
│ ┌───────────────────────────────┐   │
│ │ 📄 annual_report.pdf   [🗑]   │   │
│ │ PDF · 142 chunks · 2d ago     │   │
│ └───────────────────────────────┘   │
│ ┌───────────────────────────────┐   │
│ │ 📝 meeting_notes.md    [🗑]   │   │
│ │ Markdown · 23 chunks · 1h ago │   │
│ └───────────────────────────────┘   │
└─────────────────────────────────────┘
```

On mount: calls `refreshDocuments()`.

### 3.4 — `UploadButton.svelte`

In Phase 3 (dev mode, no Tauri): renders `<input type="file" multiple accept=".pdf,.txt,.md,.docx,...">`.

In Phase 5: replaced with Tauri `dialog.open()` call.

On file(s) selected: calls `uploadAndIngest(file)` for each file sequentially.

Supported extensions shown in button tooltip and file picker accept filter:
`.pdf, .txt, .md, .docx, .py, .js, .ts, .java, .c, .cpp, .h, .cs, .go, .rs, .png, .jpg, .jpeg, .tiff, .bmp`

### 3.5 — `IngestionProgress.svelte`

Props: `{ filename: string, state: 'uploading' | 'processing' | 'done' | 'error', error?: string }`

- `uploading`: spinner + "Uploading filename.pdf..."
- `processing`: animated progress bar + "Processing chunks..." (indeterminate, polls list until count changes)
- `done`: green checkmark + "filename.pdf added (N chunks)"
- `error`: red X + error message

Polling strategy:
1. After upload responds, record current `documents.length`
2. Poll `GET /api/documents` every 1.5s
3. When length increases: mark `done`, stop polling
4. Timeout after 120s: mark `error`

### 3.6 — `DocumentCard.svelte`

Props: `{ doc: DocumentInfo }`

Shows:
- Icon by type: 📄 PDF, 📝 Markdown/TXT, 💻 Code, 🖼 Image
- Document name (truncated with ellipsis)
- `{doc_type} · {chunk_count} chunks · {relative_time}`
- Delete button (🗑) — shows confirmation tooltip before calling `removeDocument(id)`

---

## Files Created

| File | Purpose |
|---|---|
| `ui/src/lib/api/documents.ts` | Document upload/list/delete API (replaces stub) |
| `ui/src/lib/stores/documents.svelte.ts` | Document state + actions |
| `ui/src/lib/components/DocumentManager.svelte` | Slide-in panel |
| `ui/src/lib/components/UploadButton.svelte` | File picker (HTML input, upgraded in Phase 5) |
| `ui/src/lib/components/IngestionProgress.svelte` | Progress indicator |
| `ui/src/lib/components/DocumentCard.svelte` | Single document row |

## Files Modified

| File | Change |
|---|---|
| `ui/src/App.svelte` | Slot `<DocumentManager>` into layout, wire `showDocManager` toggle |

---

## Verification Checklist

- [x] `npm run check` — 0 errors, 0 warnings
- [ ] Click 📄 icon in sidebar → DocumentManager panel slides in *(manual)*
- [ ] Click “Add Documents” → file picker opens *(manual)*
- [ ] Select a PDF → progress shown → document appears in list *(manual — requires backend)*
- [ ] Document card shows correct name, type, chunk count, relative time *(manual)*
- [ ] Click 🗑 → confirmation shown → document removed *(manual)*
- [ ] Upload unsupported file type → backend 400 error shown in progress bar *(manual)*
- [ ] Upload large file → progress bar stays visible until ingestion completes *(manual)*

---

## Open Questions

- Sequential vs parallel uploads? **Resolved: sequential** — `for...of` loop in `UploadButton.svelte`.
- Warn when deleting doc referenced in open chat? **Resolved: no** — sources become stale naturally.

---

## Completion Notes

> - **Date completed:** 2026-05-27
> - **Test results:** `npm run check` — 0 errors, 0 warnings
> - **Deviations from plan:**
>   - Backend `DocumentInfo` fields are `name` / `chunks_count` (not `document_name` / `chunk_count` as in plan spec) — matched actual backend schema
>   - Ingestion endpoint is synchronous — no polling needed; document appears in list immediately after upload; `processing` state is shown briefly, refreshes on response, then auto-dismisses after 3s
>   - `DocumentManager` rendered as a fixed overlay outside the grid in `AppLayout.svelte` (not as a right-side panel inside the grid) for correct z-index behaviour
>   - Slide-in animation via CSS `@keyframes slide-in`
> - **New files:** `ui/src/lib/stores/documents.svelte.ts`, `ui/src/lib/components/DocumentManager.svelte`, `ui/src/lib/components/DocumentCard.svelte`, `ui/src/lib/components/UploadButton.svelte`, `ui/src/lib/components/IngestionProgress.svelte`
> - **Modified files:** `ui/src/lib/api/documents.ts` (stub replaced), `ui/src/lib/components/AppLayout.svelte`
