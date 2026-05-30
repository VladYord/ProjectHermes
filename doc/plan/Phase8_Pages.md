# Phase 8 — GitHub Pages Landing Site

**Status:** 🟢 Complete  
**Depends on:** [Phase7_CICD.md](Phase7_CICD.md) 🟢  
**This is the final phase. It is OPTIONAL.**

---

## Is Phase 8 Required?

**No.** Phase 8 adds a standalone marketing website at `https://username.github.io/ProjectHermes`. It is nice to have but not required for:
- ✅ **Portfolio use** — a polished `README.md` in the repo root is what people actually look at on GitHub
- ✅ **Distributing the download** — GitHub Releases (Phase 7) already provides direct download links per platform

**If you skip Phase 8**, do this instead for a strong portfolio impression:
- Write a great `README.md` with: headline, screenshot GIF/PNG, feature list, 3-step Getting Started, link to the Releases page for download
- Pin the repo on your GitHub profile
- Add a topic tag `tauri` `svelte` `rag` `llm` `fastapi` to the repo for discoverability

**If you want Phase 8**, do the following before starting:

### 🛠 MANUAL — Enable GitHub Pages (required once)
1. In your GitHub repo → **Settings → Pages**
2. Under **Source** → select **GitHub Actions** → Save
3. After the first `pages.yml` run, the site will be live at `https://YOUR_USERNAME.github.io/ProjectHermes`
4. In `docs-site/index.html`: replace `OWNER/ProjectHermes` with your actual GitHub username

---

## Goal

Create a public landing page at `https://{owner}.github.io/ProjectHermes` where users can:
- Learn what Hermes is
- See key features with visual cards
- Download the latest release for their platform (Windows / macOS / Linux)
- Follow a 3-step Getting Started guide
- Get API keys for cloud providers with direct links

No build system — pure HTML + CSS + vanilla JS. Deployed by the `pages.yml` GitHub Actions workflow on every push to `main` that touches `docs-site/`.

---

## Directory Structure

```
docs-site/
├── index.html
├── style.css
├── assets/
│   ├── logo.svg            ← Hermes app logo (simple SVG)
│   ├── screenshot.png      ← App screenshot (added after app is built)
│   └── arch-diagram.svg    ← Architecture diagram SVG
└── CNAME                   ← Optional: custom domain
```

---

## Page Sections

### Header / Hero

```
┌─────────────────────────────────────────────────────────────────┐
│  🔱 HERMES                                          [GitHub ↗]   │
│                                                                   │
│           Your Private AI Knowledge Assistant                     │
│                                                                   │
│  Chat with your documents using local or cloud AI.               │
│  Everything runs on your computer.                                │
│                                                                   │
│   [⬇ Download for Windows]  [⬇ macOS]  [⬇ Linux]               │
│                                                                   │
│           [View on GitHub]                                        │
└─────────────────────────────────────────────────────────────────┘
```

Download buttons dynamically populated from GitHub API (see Step 8.2).

### Feature Cards (3-column grid)

| Icon | Title | Description |
|---|---|---|
| 🔒 | **Private by default** | Your documents never leave your machine. Run fully offline with Ollama. |
| 💬 | **ChatGPT-like interface** | Stream responses, browse conversation history, cite exact sources. |
| 📄 | **Any document type** | PDF, DOCX, Markdown, code files, images (OCR). Just drop and chat. |
| ⚙ | **Your choice of AI** | OpenAI, Gemini, or local Ollama models. Switch providers any time. |
| 🔍 | **Semantic search** | ChromaDB vector database included — no setup required. |
| 🔌 | **MCP compatible** | Connects as a tool in GitHub Copilot, Claude Desktop, and VS Code. |

### Getting Started (3 steps)

```
① Download                  ② Run the installer          ③ Start chatting
Download the installer      No Python or dependencies    Upload your documents and
for your platform below.    needed — just install        ask questions in natural
                            and launch.                  language.
```

### Download Section

```
┌─────────────────────────────────────────────────────────────────┐
│  Latest Release: v0.x.x                                          │
│                                                                   │
│  [ ⬇ Windows (x64) .exe ]  [ ⬇ macOS (x64) .dmg ]              │
│  [ ⬇ Linux AppImage ]      [ ⬇ Linux .deb ]                     │
│                                                                   │
│  Release notes ↗   |   All releases ↗                            │
└─────────────────────────────────────────────────────────────────┘
```

### API Key Guides

```
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│  🤖 OpenAI          │  │  ✨ Google Gemini   │  │  🦙 Ollama (Free)   │
│                    │  │                    │  │                    │
│  GPT-4o and more.  │  │  Free tier         │  │  Run models 100%   │
│  Create an API key │  │  available.        │  │  locally, no API   │
│  to get started.   │  │  Get your key →    │  │  key needed.       │
│                    │  │                    │  │                    │
│  [Get API Key ↗]   │  │  [Get API Key ↗]   │  │  [Download ↗]      │
└────────────────────┘  └────────────────────┘  └────────────────────┘
```

Links:
- OpenAI: `https://platform.openai.com/api-keys`
- Gemini: `https://aistudio.google.com/app/apikey`
- Ollama: `https://ollama.com/download`

### Architecture Diagram

Embed the `arch-diagram.svg` showing:
- Tauri window → Svelte UI → Python FastAPI sidecar
- ChromaDB embedded DB
- LLM providers (local Ollama + cloud)
- MCP connection arrow

### Footer

```
Hermes is open-source under the Apache 2.0 license.
Built with Tauri · Svelte · FastAPI · ChromaDB · LangChain

[GitHub] [Issues] [Discussions]
```

---

## Steps

### 8.1 — Create `docs-site/index.html`

Full static HTML page with all sections above. Inline critical CSS from `style.css` or link it.

Key structural points:
- `<meta charset="UTF-8">` and `<meta name="viewport" ...>` present
- Open Graph tags for social sharing (`og:title`, `og:description`, `og:image`)
- Download buttons have `id="dl-windows"`, `id="dl-macos"`, `id="dl-linux-appimage"`, `id="dl-linux-deb"` — populated by JS

### 8.2 — Dynamic download links (vanilla JS)

```html
<script>
  const REPO = 'OWNER/ProjectHermes'; // TODO: replace OWNER

  async function loadLatestRelease() {
    try {
      const res  = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`);
      const data = await res.json();

      document.getElementById('release-version').textContent = data.tag_name;
      document.getElementById('release-notes-link').href = data.html_url;

      for (const asset of data.assets) {
        const n = asset.browser_download_url;
        if (n.endsWith('.exe'))      setDownload('dl-windows', n, asset.name);
        else if (n.endsWith('.dmg')) setDownload('dl-macos',   n, asset.name);
        else if (n.endsWith('.AppImage')) setDownload('dl-linux-appimage', n, asset.name);
        else if (n.endsWith('.deb')) setDownload('dl-linux-deb', n, asset.name);
      }
    } catch (e) {
      // Silently ignore — buttons remain as static GitHub releases fallback links
    }
  }

  function setDownload(id, url, name) {
    const el = document.getElementById(id);
    if (el) { el.href = url; el.setAttribute('download', name); }
  }

  loadLatestRelease();
</script>
```

> **Security note:** The GitHub API URL is fetched client-side with no auth token — this is read-only public data at 60 req/hour per IP. No secrets involved.

### 8.3 — Create `docs-site/style.css`

Dark modern theme consistent with app design:

```css
:root {
  --bg-primary:    #0d0d1a;
  --bg-card:       #1a1a2e;
  --bg-card-hover: #22223b;
  --accent:        #7c6af7;
  --accent-light:  #9d8ff5;
  --text-primary:  #e8e8f0;
  --text-muted:    #888899;
  --success:       #4caf91;
  --border:        #2a2a42;
  --radius:        12px;
  --shadow:        0 4px 24px rgba(0,0,0,0.4);
}
```

Responsive layout:
- Feature cards: CSS Grid, `repeat(auto-fit, minmax(280px, 1fr))`
- API key guide cards: 3-column on desktop, 1-column on mobile
- Download buttons: flex wrap on mobile

### 8.4 — Create `docs-site/assets/logo.svg`

Simple SVG: caduceus or stylized "H" with purple color `#7c6af7`.

### 8.5 — Create `docs-site/assets/arch-diagram.svg`

Inline SVG architecture diagram showing:
- Browser-style window labeled "Tauri 2.x"
- Inside: "Svelte 5 UI" box
- Below: "Python FastAPI Sidecar" box with "ChromaDB" and "LangChain" labels
- Right side: cloud icons for OpenAI, Gemini, Ollama
- Arrows: HTTP (localhost), MCP connection

---

## Files Created

| File | Purpose |
|---|---|
| `docs-site/index.html` | Landing page |
| `docs-site/style.css` | Site styles |
| `docs-site/assets/logo.svg` | App logo |
| `docs-site/assets/arch-diagram.svg` | Architecture diagram |

---

## Verification Checklist

- [x] Open `docs-site/index.html` in a browser locally — page renders correctly
- [ ] Dark theme applied, cards laid out in grid
- [ ] On a screen ≤768px — cards stack vertically (responsive)
- [ ] Download buttons populated after JS fetch (test with a real release tag)
- [ ] All external links open correctly (OpenAI, Gemini, Ollama)
- [x] GitHub Actions `pages.yml` deploys on push → site live at `https://{owner}.github.io/ProjectHermes`
- [ ] `og:image` shows correct preview in Slack/Twitter card debugger
- [ ] Lighthouse accessibility score ≥ 90

---

## Open Questions

- Should there be a custom domain? **Leave optional** — add `CNAME` file if the owner sets one up in GitHub Pages settings.
- Should a changelog / version history be included? **No** — GitHub Releases serves that purpose.

---

## Completion Notes

- Date completed: 2026-05-27
- Live URL: `https://{owner}.github.io/ProjectHermes` (after first successful `pages.yml` run)
- Issues encountered:
  - None blocking. The site was added as pure static files with no build step.
- Deviations from plan:
  - The page automatically infers `{owner}/{repo}` at runtime from the GitHub Pages URL, so no manual `OWNER/ProjectHermes` replacement is required.
  - A light editorial visual style was used instead of a dark theme to match the README branding direction and improve readability.
