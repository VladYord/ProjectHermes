.PHONY: run run-mcp test lint clean dev dev-stub prebuild-stop build-ui build-app bundle-backend bundle-app

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

## Stop stale local dev/bundle processes that can lock sidecar binaries on Windows.
prebuild-stop:
ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File packaging\scripts\stop-dev-processes.ps1
else
	@echo "prebuild-stop: no-op on non-Windows"
endif

## Build Svelte frontend only
build-ui:
	cd ui && npm run build

## Build full Tauri installer (beforeBuildCommand in tauri.conf.json builds the frontend)
## Ensures backend resources exist (creates dev-stub if real bundle not present).
build-app: prebuild-stop dev-stub
	set RUST_MIN_STACK=67108864 && cargo tauri build

## Run PyInstaller to produce hermes-server binary (outputs to backend/dist/)
bundle-backend: prebuild-stop
ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File packaging\scripts\build-backend.ps1
else
	bash packaging/scripts/build-backend.sh
endif

## Copy backend binary from backend/dist/ to src-tauri/resources/
## Runs after PyInstaller completes to avoid Windows file-locking issues.
copy-backend-resources: bundle-backend
ifeq ($(OS),Windows_NT)
	powershell -ExecutionPolicy Bypass -File packaging\scripts\copy-backend-to-resources.ps1
else
	bash packaging/scripts/copy-backend-to-resources.sh
endif

## Full production bundle: backend binary + copy to resources + Tauri installer
bundle-app: copy-backend-resources build-app

## Tag and push a new release  (usage: make release VERSION=0.2.0)
release:
	@echo Releasing version $(VERSION)
	git add -A
	git commit -m "chore: release v$(VERSION)"
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin main
	git push origin v$(VERSION)
