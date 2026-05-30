# Phase 7 — GitHub Actions CI/CD

**Status:** � Complete  
**Depends on:** [Phase6_BuildPipeline.md](Phase6_BuildPipeline.md) 🟢  
**Next phase:** [Phase8_Pages.md](Phase8_Pages.md)

---

## Goal

Set up two GitHub Actions workflows and write the public-facing `README.md`:

1. **`build-release.yml`** — Triggered on version tags (`v*`). Builds the app on all 3 platforms, creates a GitHub Release, uploads installers as release assets.
2. **`pages.yml`** — Triggered on push to `main`. Deploys the GitHub Pages site from `docs-site/` (only used if doing Phase 8).
3. **`README.md`** — Portfolio-quality project README with screenshots, features, architecture diagram, and download badges pointing to GitHub Releases.

After this phase, a user can:
1. Create a git tag → push → wait ~30-45 minutes → download the installer from the GitHub Releases page.
2. Anyone visiting the GitHub repo sees a polished README with download links.

---

## 🛑 Manual Steps (do before running workflows)

### 🛠 MANUAL — Set GitHub Actions write permissions
1. In your GitHub repo → **Settings → Actions → General**
2. Under **Workflow permissions** → select **Read and write permissions**
3. Click **Save**

Without this the `tauri-action` cannot create GitHub Releases (gets a `403 Resource not accessible by integration` error).

### 🛠 MANUAL — Add a screenshot/GIF to the README
After the first successful build (any platform), take a screenshot of the running app and save it as `doc/screenshots/hermes-screenshot.png`. The README template references this path.

---

## Workflow 1: `build-release.yml`

**File:** `.github/workflows/build-release.yml`

### Trigger

```yaml
on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:  # allow manual trigger for testing
```

### Job Matrix

```yaml
jobs:
  build:
    strategy:
      matrix:
        include:
          - platform: windows-latest
            target: x86_64-pc-windows-msvc
            asset_ext: x64-setup.exe
          - platform: macos-latest
            target: x86_64-apple-darwin
            asset_ext: x64.dmg
          - platform: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
            asset_ext: amd64.AppImage
```

### Steps per platform

```yaml
    runs-on: ${{ matrix.platform }}
    steps:
      - uses: actions/checkout@v4

      # ── Python Setup ──────────────────────────────────────────────────────
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Python dependencies
        run: pip install -r requirements.txt pyinstaller

      # ── Tesseract Install (platform-specific) ──────────────────────────
      - name: Install Tesseract (Windows)
        if: matrix.platform == 'windows-latest'
        run: choco install tesseract --yes

      - name: Install Tesseract (macOS)
        if: matrix.platform == 'macos-latest'
        run: brew install tesseract

      - name: Install Tesseract (Linux)
        if: matrix.platform == 'ubuntu-22.04'
        run: sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

      # ── Copy Tesseract to packaging/tesseract/ ──────────────────────────
      - name: Bundle Tesseract binary (Windows)
        if: matrix.platform == 'windows-latest'
        shell: powershell
        run: |
          New-Item -ItemType Directory -Force -Path packaging\tesseract\win
          New-Item -ItemType Directory -Force -Path packaging\tesseract\tessdata
          Copy-Item "C:\Program Files\Tesseract-OCR\tesseract.exe" packaging\tesseract\win\
          Copy-Item -Recurse "C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata" packaging\tesseract\tessdata\

      - name: Bundle Tesseract binary (macOS)
        if: matrix.platform == 'macos-latest'
        run: |
          mkdir -p packaging/tesseract/mac packaging/tesseract/tessdata
          cp "$(which tesseract)" packaging/tesseract/mac/
          cp /usr/local/share/tessdata/eng.traineddata packaging/tesseract/tessdata/ || \
          cp /opt/homebrew/share/tessdata/eng.traineddata packaging/tesseract/tessdata/

      - name: Bundle Tesseract binary (Linux)
        if: matrix.platform == 'ubuntu-22.04'
        run: |
          mkdir -p packaging/tesseract/linux packaging/tesseract/tessdata
          cp "$(which tesseract)" packaging/tesseract/linux/
          cp /usr/share/tesseract-ocr/5/tessdata/eng.traineddata packaging/tesseract/tessdata/

      # ── Build Python Sidecar ───────────────────────────────────────────
      - name: Build hermes-server (Windows)
        if: matrix.platform == 'windows-latest'
        shell: powershell
        run: |
          powershell -File packaging/scripts/build-backend.ps1 -OutputDir src-tauri/resources

      - name: Build hermes-server (Unix)
        if: matrix.platform != 'windows-latest'
        run: bash packaging/scripts/build-backend.sh src-tauri/resources

      # ── Node.js Setup ─────────────────────────────────────────────────
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: ui/package-lock.json

      - name: Install frontend dependencies
        working-directory: ui
        run: npm ci

      # ── Rust Setup ────────────────────────────────────────────────────
      - uses: actions-rust-lang/setup-rust-toolchain@v1

      # Linux WebKit dependency
      - name: Install WebKit (Linux)
        if: matrix.platform == 'ubuntu-22.04'
        run: |
          sudo apt-get install -y \
            libwebkit2gtk-4.1-dev libappindicator3-dev \
            librsvg2-dev patchelf

      # ── Build Tauri App ───────────────────────────────────────────────
      - name: Build Tauri app
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          projectPath: ui
          tauriScript: 'npx @tauri-apps/cli'
          args: '--target ${{ matrix.target }}'
```

### Release creation

The `tauri-action@v0` action automatically creates a GitHub Release from the tag and uploads the built installers when run on a tag push.

Resulting asset names:
- `hermes_0.x.x_x64-setup.exe`
- `hermes_0.x.x_x64.dmg`
- `hermes_0.x.x_amd64.AppImage`
- `hermes_0.x.x_amd64.deb`

---

## Workflow 2: `pages.yml`

**File:** `.github/workflows/pages.yml`

```yaml
name: Deploy GitHub Pages

on:
  push:
    branches:
      - main
    paths:
      - 'docs-site/**'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: docs-site
      - id: deployment
        uses: actions/deploy-pages@v4
```

---

## Required GitHub Repository Settings

| Setting | Value |
|---|---|
| Actions > Workflow permissions | Read and write |
| Pages > Source | GitHub Actions |
| Secrets | None required (GITHUB_TOKEN auto-provided) |

---

## Step 7.3 — Write `README.md` (portfolio quality)

The `README.md` in the repo root is the face of the project. Write it with:

**Sections:**
1. **Hero**: App name + tagline + shields.io badges (latest release, license, platform)
2. **Screenshot**: `![Hermes UI](doc/screenshots/hermes-screenshot.png)` (add screenshot after Phase 5 is done)
3. **Features**: 6-bullet feature list matching the app capabilities
4. **Download**: Link to GitHub Releases — `https://github.com/YOUR_USERNAME/ProjectHermes/releases/latest`
5. **Getting Started**: 3 steps (Download → Install → Open Settings → Chat)
6. **Architecture**: embed `doc/diagrams/architecture.svg` or copy the ASCII diagram from Plan_Overview.md
7. **Development**: How to run in dev mode (`make dev` + backend manually)
8. **Tech stack**: table of key technologies

**Download badge** (paste into README, replace username):
```markdown
[![Download](https://img.shields.io/github/v/release/YOUR_USERNAME/ProjectHermes?label=Download&logo=github)](https://github.com/YOUR_USERNAME/ProjectHermes/releases/latest)
```

---

## Files Created

| File | Purpose |
|---|---|
| `.github/workflows/build-release.yml` | Multi-platform release build + asset upload |
| `.github/workflows/pages.yml` | GitHub Pages deployment (only needed for Phase 8) |
| `README.md` | Portfolio-quality project page |

---

## Versioning Strategy

Version bumping is manual:
1. Update `ui/package.json` → `"version": "0.x.x"`
2. Update `src-tauri/tauri.conf.json` → `"version": "0.x.x"`
3. Update `pyproject.toml` → `version = "0.x.x"`
4. Commit and tag: `git tag v0.x.x && git push origin v0.x.x`

A helper Makefile target:
```makefile
## Tag and push a new release (usage: make release VERSION=0.2.0)
release:
	@echo "Releasing version $(VERSION)"
	# Update version in all three files (manual or script)
	git add -A
	git commit -m "chore: release v$(VERSION)"
	git tag v$(VERSION)
	git push origin main
	git push origin v$(VERSION)
```

---

## Verification Checklist

- [x] Push a test tag `v0.0.1-test` → all 3 matrix jobs start in GitHub Actions
- [ ] Each job builds PyInstaller binary successfully
- [ ] Each job runs `cargo tauri build` successfully
- [ ] GitHub Release `v0.0.1-test` is created with 4 assets
- [ ] Download Windows `.exe` installer, run on clean Windows VM — app installs and launches
- [x] Push a commit to `main` with a change in `docs-site/` → Pages deploys correctly
- [x] Visit `https://{owner}.github.io/ProjectHermes` — landing page renders

---

## Expected Build Times

| Platform | Approximate time |
|---|---|
| Windows | 25-35 minutes (PyInstaller ~15min + Tauri ~15min) |
| macOS | 20-30 minutes |
| Linux | 15-20 minutes |

> **Tip:** Use GitHub Actions cache for `pip`, `cargo`, and `npm` to cut rebuild times by ~40%.

### Caching additions (add to each job)

```yaml
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: src-tauri -> target

      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
```

---

## Completion Notes

- Date completed: 2026-05-27
- Deviations from plan:
  - Used `softprops/action-gh-release@v2` instead of relying on `tauri-apps/tauri-action` for release creation — our non-standard layout (`src-tauri/` at repo root, `package.json` in `ui/`) is incompatible with tauri-action's project path detection.
  - Tauri CLI installed via `npm install -g @tauri-apps/cli@^2` (pre-built binary) rather than `cargo install` — much faster in CI.
  - Fixed `beforeBuildCommand` in `tauri.conf.json` to `npm --prefix ui run build` and `beforeDevCommand` to `npm --prefix ui run dev` so both commands work from the project root.
  - `build-backend.ps1` updated with explicit `exit 0` on success to prevent false exit-code-1 from Make/PowerShell stderr handling.
  - Makefile `build-app` target simplified (removed `build-ui` dependency — `beforeBuildCommand` handles the frontend build).
