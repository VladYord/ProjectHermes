# Phase 4 — Svelte Frontend: Settings

**Status:** � Complete  
**Depends on:** [Phase3_DocManager.md](Phase3_DocManager.md) 🟢  
**Next phase:** [Phase5_TauriIntegration.md](Phase5_TauriIntegration.md)

---

## Goal

Build the settings panel where users can configure all LLM providers, store API keys (encrypted via backend), and access guides to obtain API keys. After this phase:
- Users can enter and save API keys for OpenAI, Gemini
- Users can configure Ollama URL and model
- Ollama connectivity shows live green/red status
- Embedding provider and model are configurable
- A links section points to external blog/docs for getting API keys
- All sensitive fields saved to `config.enc` via `PATCH /api/config`

---

## UI Layout

```
┌──────────────────────────────────────────────┐
│ ⚙ Settings                         [×close]  │
├──────────────────────────────────────────────┤
│ [LLM Providers] [Embedding] [About]           │  ← Tab bar
├──────────────────────────────────────────────┤
│ LLM Providers tab:                            │
│                                               │
│ ┌──────────────────────────────────────────┐ │
│ │ 🟢 OpenAI                    [configured] │ │
│ │ API Key  [••••••••••••] [👁]              │ │
│ │ Model    [gpt-4o         ▼]               │ │
│ │                    [Test Connection]       │ │
│ └──────────────────────────────────────────┘ │
│                                               │
│ ┌──────────────────────────────────────────┐ │
│ │ 🔴 Google Gemini          [not configured]│ │
│ │ API Key  [Enter key...  ] [👁]            │ │
│ │ Model    [gemini-2.5-pro ▼]               │ │
│ └──────────────────────────────────────────┘ │
│                                               │
│ ┌──────────────────────────────────────────┐ │
│ │ 🟡 Ollama (local)         [checking...]   │ │
│ │ URL      [http://localhost:11434]         │ │
│ │ Model    [llama3.1       ▼]               │ │
│ │ Not running? → Setup Guide ↗              │ │
│ └──────────────────────────────────────────┘ │
│                                               │
│ Default Provider: [OpenAI ▼]                  │
├──────────────────────────────────────────────┤
│ 🔑 How to get API keys                        │
│ [OpenAI] [Google Gemini] [Ollama (free)]      │
└──────────────────────────────────────────────┘
```

---

## Steps

### 4.1 — Complete `ui/src/lib/api/config.ts`

```typescript
export interface ProviderConfig {
  model: string;
  api_key?: string;          // only for sending to PATCH (never returned)
  api_key_set: boolean;      // returned by GET
  base_url?: string;
  reachable: boolean;
}

export interface AppConfig {
  default_provider: string;
  embedding_provider: string;
  embedding_model: string;
  providers: Record<string, ProviderConfig>;
}

export async function getConfig(): Promise<AppConfig>
export async function patchConfig(patch: Partial<AppConfig>): Promise<AppConfig>
export async function testProvider(provider: string): Promise<{ reachable: boolean; latency_ms: number | null }>
```

### 4.2 — Config store (`ui/src/lib/stores/config.svelte.ts`)

```typescript
export let config = $state<AppConfig | null>(null);
export let isSaving = $state(false);
export let saveError = $state<string | null>(null);

export async function loadConfig(): Promise<void>
export async function saveProviderConfig(
  provider: string,
  patch: Partial<ProviderConfig>
): Promise<void>
export async function setDefaultProvider(provider: string): Promise<void>
```

### 4.3 — `SettingsPanel.svelte`

Slide-in panel (right side, 480px wide) triggered by `showSettings` store.
Contains a tab bar: **LLM Providers** | **Embedding** | **About**

On mount: calls `loadConfig()`.
On close: saves any pending changes.

### 4.4 — `ProviderCard.svelte`

Props: `{ provider: string, config: ProviderConfig }`

- **Status indicator:** 🟢 reachable, 🔴 not reachable, 🟡 unknown/checking
- **API key field:**
  - Type `password` by default — shows `••••••••`
  - Eye icon toggles to `text`
  - Placeholder: `Enter API key...` (if not set) or `••••••••••••` (if set but not shown)
  - On blur: calls `saveProviderConfig(provider, { api_key: value })` if changed
- **Model field:** text input or dropdown (see model lists below)
- **URL field:** shown only for Ollama and custom endpoints
- **Test Connection button:** calls `testProvider(provider)`, shows spinner then green/red result

Model dropdowns per provider:
- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `o3`, `o4-mini`
- Gemini: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.0-flash`
- Ollama: free text input (user types model name, e.g. `llama3.1`, `mistral`)

### 4.5 — `OllamaStatus.svelte`

Standalone component within the Ollama ProviderCard:
- Shows "🟢 Running" / "🔴 Not running"
- When not running: link to Ollama setup guide `https://ollama.com/download`
- Auto-checks every 30s when settings panel is open

### 4.6 — Embedding tab (`EmbeddingConfig.svelte`)

- Embedding provider selector: dropdown (same providers as LLM: openai, ollama, etc.)
- Embedding model field: text input (pre-filled with current model)
- Warning banner: "⚠ Changing the embedding model requires re-ingesting all documents. Your existing knowledge base will need to be rebuilt." (shown when embedding provider/model changes)
- On save: calls `patchConfig({ embedding_provider, embedding_model })`

### 4.7 — `ApiKeyGuides.svelte`

Shown at bottom of LLM Providers tab.

Cards with external links:

| Service | Link | Description |
|---|---|---|
| OpenAI | https://platform.openai.com/api-keys | Create an OpenAI API key |
| Google Gemini | https://aistudio.google.com/app/apikey | Get a free Gemini API key |
| Ollama | https://ollama.com/download | Run models locally for free |

Each card: service logo/icon, name, one-line description, "Get Key →" button (opens in external browser via `window.open` in dev, Tauri `shell.open` in Phase 5).

### 4.8 — About tab

- App name, version (read from `package.json` via `import.meta.env`)
- Backend version (from `GET /api/health`)
- Short description and GitHub link
- License: Apache 2.0

---

## Files Created

| File | Purpose |
|---|---|
| `ui/src/lib/api/config.ts` | Config GET/PATCH/test API (replaces stub) |
| `ui/src/lib/stores/config.svelte.ts` | App config state + save actions |
| `ui/src/lib/components/SettingsPanel.svelte` | Settings slide-in drawer |
| `ui/src/lib/components/ProviderCard.svelte` | Per-provider config block |
| `ui/src/lib/components/OllamaStatus.svelte` | Ollama live status indicator |
| `ui/src/lib/components/EmbeddingConfig.svelte` | Embedding config tab |
| `ui/src/lib/components/ApiKeyGuides.svelte` | External links to API key docs |

## Files Modified

| File | Change |
|---|---|
| `ui/src/App.svelte` | Slot `<SettingsPanel>`, wire `showSettings` toggle |

---

## Verification Checklist

- [x] `npm run check` — 0 errors, 0 warnings
- [ ] Click ⚙ in sidebar → SettingsPanel slides in with 3 tabs *(manual)*
- [ ] Enter OpenAI API key → blur → key saved, GET /api/config shows `api_key_set: true` *(manual)*
- [ ] Key is NOT visible in `config.enc` (binary/encrypted) *(manual)*
- [ ] “Test Connection” for OpenAI with valid key → green result *(manual)*
- [ ] Ollama card shows 🔴 if not running, 🟢 if running *(manual)*
- [ ] Ollama setup guide link opens in browser *(manual)*
- [ ] Change embedding model → warning banner shown *(manual)*
- [ ] API Key Guides cards show correct links *(manual)*
- [ ] About tab shows app version *(manual)*

---

## Open Questions

- Should the settings panel block the UI (modal) or be non-blocking? **Resolved: non-blocking overlay** — backdrop closes on click, chat remains behind.
- Should API keys be shown partially? **Resolved: no partial reveal** — just `api_key_set: true` visually (🟢 status dot + “configured” label).

---

## Completion Notes

> - **Date completed:** 2026-05-27
> - **Test results:** `npm run check` — 0 errors, 0 warnings
> - **Deviations from plan:**
>   - `const` boolean flags (`hasApiKey` etc.) in ProviderCard required `$derived()` per Svelte 5 rune rules; input initialisations required `untrack()` to silence state_referenced_locally warnings
>   - `testProvider()` endpoint does not exist in backend; “Test Connection” calls `GET /api/providers` instead (live Ollama ping for Ollama, key-set check for cloud providers)
>   - App version hardcoded to `0.1.0` (Phase 6 build pipeline will inject from `tauri.conf.json`)
>   - GitHub link uses placeholder URL — update when repo is public
>   - Azure OpenAI included as a 4th provider card (not shown in plan wireframe but supported by backend)
> - **New files:** `ui/src/lib/api/config.ts` (stub replaced), `ui/src/lib/stores/config.svelte.ts`, `ui/src/lib/components/SettingsPanel.svelte`, `ui/src/lib/components/ProviderCard.svelte`, `ui/src/lib/components/OllamaStatus.svelte`, `ui/src/lib/components/EmbeddingConfig.svelte`, `ui/src/lib/components/ApiKeyGuides.svelte`
> - **Modified files:** `ui/src/lib/components/AppLayout.svelte`
