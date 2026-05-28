.PHONY: run run-mcp test lint clean dev dev-stub build-ui build-app bundle-backend bundle-app

run:
	.venv\Scripts\python.exe -m hermes

run-mcp:
	.venv\Scripts\python.exe -m hermes --mcp

test:
	.venv\Scripts\python.exe -m pytest tests/ -q

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
dev: dev-stub
	cargo tauri dev

## Create a minimal stub binary so `cargo tauri dev` can compile.
## Skips if a real/stub binary already exists in src-tauri/resources/.
dev-stub:
ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File packaging\scripts\create-dev-stub.ps1
else
	bash packaging/scripts/create-dev-stub.sh
endif

## Build Svelte frontend only
build-ui:
	cd ui && npm run build

## Build full Tauri installer (beforeBuildCommand in tauri.conf.json builds the frontend)
build-app:
	cargo tauri build

## Run PyInstaller to produce hermes-server binary (renames to include target triple)
bundle-backend:
ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File packaging\scripts\build-backend.ps1
else
	bash packaging/scripts/build-backend.sh
endif

## Full production bundle: backend binary + Tauri installer
bundle-app: bundle-backend build-app

## Tag and push a new release  (usage: make release VERSION=0.2.0)
release:
	@echo Releasing version $(VERSION)
	git add -A
	git commit -m "chore: release v$(VERSION)"
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin main
	git push origin v$(VERSION)
