# Phase 2 — Svelte Frontend: Chat UI

**Status:** � Complete  
**Depends on:** [Phase1_Backend.md](Phase1_Backend.md) 🟢  
**Next phase:** [Phase3_DocManager.md](Phase3_DocManager.md)

---

## Goal

Build a fully functional ChatGPT-style chat interface in Svelte 5 that:
- Connects to the Python backend via HTTP and SSE streaming
- Displays conversation sessions in a sidebar (create, switch, delete)
- Renders AI responses with inline collapsible source citations
- Shows a typing indicator while streaming
- Has the final dark UI layout that all other panels will slot into

The backend port is **hardcoded to `http://localhost:8000`** in this phase and made dynamic in Phase 5.

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ ┌────────────┐  ┌────────────────────────────────────────────────┐  │
│ │  Sidebar   │  │                  ChatWindow                     │  │
│ │            │  │  ┌──────────────────────────────────────────┐  │  │
│ │ + New Chat │  │  │  [AI] Hello! How can I help you today?   │  │  │
│ │            │  │  │  ▶ Source: report.pdf (score: 0.92)     │  │  │
│ │ > Chat 1   │  │  │                                           │  │  │
│ │   Chat 2   │  │  │  [You] What is the Q3 revenue?            │  │  │
│ │            │  │  │                                           │  │  │
│ │ ─────────  │  │  │  [AI] ●●● (streaming...)                  │  │  │
│ │ 📄 Docs    │  │  └──────────────────────────────────────────┘  │  │
│ │ ⚙ Settings │  │  ┌──────────────────────────────────────────┐  │  │
│ │            │  │  │  Ask Hermes anything...          [Send]   │  │  │
│ └────────────┘  │  └──────────────────────────────────────────┘  │  │
│                  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Steps

### 2.1 — TypeScript API client layer (`ui/src/lib/api/`)

**`client.ts`** — base fetch wrapper:
```typescript
// Base URL — will be made dynamic in Phase 5
export const BASE_URL = 'http://localhost:8000';

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T>
```
- Throws typed `ApiError` on non-2xx responses
- Sets `Content-Type: application/json` by default

**`chat.ts`** — SSE streaming client:
```typescript
export async function* streamChat(
  message: string,
  sessionId: string,
  provider?: string
): AsyncGenerator<ChatChunk>
```
- Uses `EventSource`-compatible SSE parsing via `fetch` + `ReadableStream`
- Yields `{ type: 'text' | 'sources' | 'done' | 'error', data: string }`

**`sessions.ts`**:
```typescript
export function listSessions(): Promise<SessionInfo[]>
export function getSessionHistory(id: string): Promise<Message[]>
export function deleteSession(id: string): Promise<void>
```

**`documents.ts`** (stubs — full implementation in Phase 3):
```typescript
export function listDocuments(): Promise<DocumentInfo[]>
```

**`config.ts`** (stubs — full implementation in Phase 4):
```typescript
export function getConfig(): Promise<AppConfig>
```

### 2.2 — Svelte 5 state stores (`ui/src/lib/stores/`)

Use Svelte 5 runes (`$state`, `$derived`):

**`sessions.svelte.ts`**:
```typescript
export let sessions = $state<SessionInfo[]>([]);
export let activeSessionId = $state<string | null>(null);
export let messages = $state<Message[]>([]);
export let isStreaming = $state(false);
```

**`ui.svelte.ts`**:
```typescript
export let showDocManager = $state(false);
export let showSettings = $state(false);
export let sidebarCollapsed = $state(false);
```

### 2.3 — App shell components

**`ui/src/App.svelte`** — root component:
- Imports `AppLayout`, `ChatSidebar`, `ChatWindow`, `DocumentManager` (Phase 3 slot), `SettingsPanel` (Phase 4 slot)
- No routing — single-page, panels toggled via `ui.svelte.ts` stores

**`ui/src/lib/components/AppLayout.svelte`**:
- CSS Grid: `250px sidebar | 1fr main`
- Dark theme: background `#1a1a2e`, sidebar `#16213e`, chat `#0f3460`
- Responsive: sidebar collapses to icon strip below 800px

### 2.4 — `ChatSidebar.svelte`

- Hermes logo / app name at top
- "＋ New Chat" button — creates new session ID (UUID), sets `activeSessionId`
- Session list — renders `sessions` store, highlights active
- Click session → `setActiveSession(id)` → loads history via API
- Delete session button (trash icon on hover) → calls `deleteSession(id)`
- Bottom icons: 📄 (DocManager toggle), ⚙ (Settings toggle)

### 2.5 — `ChatWindow.svelte`

- Scrollable message list (auto-scroll to bottom on new message)
- Renders `messages` from store via `{#each messages as msg}`
- `<MessageBubble>` for each message
- `<StreamingDots>` shown when `isStreaming === true`
- Bottom composer: `<textarea>` (auto-resize, max 5 lines) + Send button
- Send: calls `streamChat()`, appends chunks to active session's messages in real-time
- Enter sends (Shift+Enter = newline)

### 2.6 — `MessageBubble.svelte`

Props: `{ role: 'user' | 'assistant', content: string, sources?: SourceRef[] }`

- User messages: right-aligned, accent colour
- AI messages: left-aligned, neutral dark
- If `sources` present: collapsed `▶ Sources (3)` toggle → expands to list of `<SourceCard>`

### 2.7 — `SourceCard.svelte`

Props: `{ name: string, score: number, excerpt: string }`

- Shows: document name, relevance score as percentage bar, excerpt text (truncated to 3 lines)
- Click to expand full excerpt

### 2.8 — `StreamingDots.svelte`

Animated CSS three-dot ellipsis to show AI is typing:
```css
.dot { animation: bounce 1.2s infinite; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
```

### 2.9 — CSS design tokens (`ui/src/lib/styles/tokens.css`)

```css
:root {
  --bg-primary:    #1a1a2e;
  --bg-secondary:  #16213e;
  --bg-chat:       #0f1b2d;
  --accent:        #4f8ef7;
  --text-primary:  #e8eaf6;
  --text-muted:    #8892b0;
  --border:        #2d3561;
  --user-bubble:   #1e3a5f;
  --ai-bubble:     #1a2744;
  --success:       #4caf50;
  --warning:       #ff9800;
  --error:         #f44336;
}
```

---

## Files Created

| File | Purpose |
|---|---|
| `ui/src/lib/api/client.ts` | Base HTTP client |
| `ui/src/lib/api/chat.ts` | SSE streaming chat client |
| `ui/src/lib/api/sessions.ts` | Session management API calls |
| `ui/src/lib/api/documents.ts` | Document API stubs |
| `ui/src/lib/api/config.ts` | Config API stubs |
| `ui/src/lib/stores/sessions.svelte.ts` | Chat session state |
| `ui/src/lib/stores/ui.svelte.ts` | UI panel visibility state |
| `ui/src/lib/styles/tokens.css` | Design tokens |
| `ui/src/App.svelte` | Root component (replaces scaffold) |
| `ui/src/lib/components/AppLayout.svelte` | Shell layout |
| `ui/src/lib/components/ChatSidebar.svelte` | Left nav |
| `ui/src/lib/components/ChatWindow.svelte` | Main chat area |
| `ui/src/lib/components/MessageBubble.svelte` | Single message |
| `ui/src/lib/components/SourceCard.svelte` | Source reference |
| `ui/src/lib/components/StreamingDots.svelte` | Typing indicator |

---

## Verification Checklist

- [x] `cd ui && npm run check` — 0 errors, 0 warnings
- [ ] App renders with dark theme sidebar and main chat area *(manual — run `npm run dev`)*
- [ ] “New Chat” creates a new session entry in sidebar *(manual)*
- [ ] Typing a message and pressing Send triggers API call to backend *(manual — requires backend on :8000)*
- [ ] AI response streams character-by-character into the chat bubble *(manual)*
- [ ] After response: sources are shown collapsed under AI message *(manual — requires ingest + RAG)*
- [ ] Clicking source expands excerpt *(manual)*
- [ ] Clicking different session in sidebar loads its history *(manual)*
- [ ] Delete session removes it from sidebar *(manual)*

---

## Open Questions

- Should sessions be named automatically (e.g., first N chars of first message) or always “Chat 1”, “Chat 2”? **Resolved: auto-title from first user message, truncated to 40 chars** — implemented in `SessionsStore.sendMessage()`.
- Should the streaming abort if the user clicks Send again? **Resolved: yes** — implemented via `AbortController` stored in store; cancelled before each new send.

---

## Completion Notes

> - **Date completed:** 2026-05-27
> - **Test results:** `npm run check` — 0 errors, 0 warnings
> - **Deviations from plan:**
>   - `$lib` alias configured manually (plain Vite project, not SvelteKit) via `vite.config.ts` `resolve.alias` + `tsconfig.app.json` `paths`
>   - Sources always empty for now (backend `chat_stream` does not emit source events); `MessageBubble` renders source section only when `sources.length > 0` — ready for future Phase
>   - Outer session item uses `<div role="button">` instead of `<button>` to avoid nested-button HTML validity issue (delete button is a `<button>` inside)
>   - `pct` in `SourceCard` uses `$derived` (not `const`) to stay reactive to prop changes
> - **New files:** `ui/src/lib/api/` (5 files), `ui/src/lib/stores/` (2 files), `ui/src/lib/components/` (6 files), `ui/src/lib/styles/tokens.css`
> - **Modified files:** `ui/src/App.svelte`, `ui/src/app.css`, `ui/vite.config.ts`, `ui/tsconfig.app.json`
