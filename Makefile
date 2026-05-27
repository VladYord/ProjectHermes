.PHONY: run run-mcp test lint clean dev build-ui build-app bundle-backend bundle-app

run:
	python -m hermes

run-mcp:
	python -m hermes --mcp

test:
	python -m pytest tests/ -v

lint:
	python -m ruff check hermes/ tests/

format:
	python -m ruff format hermes/ tests/

clean:
	@if exist data\chromadb rmdir /s /q data\chromadb
	@if exist __pycache__ rmdir /s /q __pycache__
	@echo Cleaned.

# ── Desktop App Targets ──────────────────────────────────────────────────────

## Start Tauri dev window (Svelte HMR + Tauri shell)
test:
	.venv\Scripts\python.exe -m pytest tests/ -q

dev:
	cargo tauri dev

## Build Svelte frontend only
build-ui:
	cd ui && npm run build

## Build full Tauri installer (run bundle-backend first for production)
build-app: build-ui
	cargo tauri build

## Run PyInstaller to produce hermes-server binary (Phase 6)
bundle-backend:
	python -m PyInstaller packaging/pyinstaller/hermes.spec --distpath src-tauri/resources --workpath build/pyinstaller --noconfirm

## Full production bundle: backend binary + Tauri installer
bundle-app: bundle-backend build-app

## Tag and push a new release  (usage: make release VERSION=0.2.0)
release:
	@echo Releasing version $(VERSION)
	git add -A
	git commit -m "chore: release v$(VERSION)"
	git tag v$(VERSION)
	git push origin main
	git push origin v$(VERSION)
