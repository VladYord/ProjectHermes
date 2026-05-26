"""
render_diagrams.py
==================
Extracts every Mermaid diagram from a Markdown file and renders each one
to a PNG image using the mermaid.ink public API — no Node.js or npm needed.

Usage
-----
    python tools/render_diagrams.py                          # uses defaults
    python tools/render_diagrams.py --input doc/Architecture.md --out doc/diagrams
    python tools/render_diagrams.py --filter startup         # render one matching name
    python tools/render_diagrams.py --help

Requirements (all already in pyproject.toml / .venv)
-----------------------------------------------------
    httpx    — HTTP client (already a project dependency)

No Node.js, no npm, no Chromium download required.
"""

from __future__ import annotations

import argparse
import base64
import sys
import re
import time
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_INPUT = Path(__file__).parent.parent / "doc" / "Architecture.md"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "doc" / "diagrams"

# mermaid.ink public rendering API
MERMAID_INK_BASE = "https://mermaid.ink"

# Request settings
TIMEOUT_SECONDS = 30
RETRY_COUNT     = 2
RETRY_DELAY     = 3   # seconds between retries


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert a heading string to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "_", text)
    text = re.sub(r"-+", "_", text)
    return text.strip("_")[:80]


def _encode(mermaid_code: str) -> str:
    """Base64-encode a Mermaid diagram for the mermaid.ink URL."""
    return base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")


def _extract_diagrams(md_path: Path) -> list[tuple[str, str]]:
    """
    Parse the Markdown file and return a list of (label, mermaid_code) tuples.
    Label is derived from the last heading seen before each code block.
    """
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    diagrams: list[tuple[str, str]] = []
    current_heading = "diagram"
    in_block = False
    block_lines: list[str] = []
    heading_count: dict[str, int] = {}

    for line in lines:
        heading_match = re.match(r"^#{1,4}\s+(.+)", line)
        if heading_match and not in_block:
            current_heading = heading_match.group(1).strip()
            continue

        if line.strip() == "```mermaid":
            in_block = True
            block_lines = []
            continue

        if in_block:
            if line.strip() == "```":
                code = "\n".join(block_lines).strip()
                slug = _slugify(current_heading)
                count = heading_count.get(slug, 0) + 1
                heading_count[slug] = count
                label = slug if count == 1 else f"{slug}_{count}"
                diagrams.append((label, code))
                in_block = False
                block_lines = []
            else:
                block_lines.append(line)

    return diagrams


def _render_one(client, label: str, code: str, out_dir: Path) -> Path | None:
    """Render a single diagram via mermaid.ink. Returns output path or None."""
    encoded = _encode(code)
    url = f"{MERMAID_INK_BASE}/img/{encoded}?bgColor=white"
    out_path = out_dir / f"{label}.png"

    last_err = ""
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            response = client.get(url, timeout=TIMEOUT_SECONDS)
            if response.status_code == 200:
                out_path.write_bytes(response.content)
                return out_path
            last_err = f"HTTP {response.status_code}"
        except Exception as exc:
            last_err = str(exc)

        if attempt < RETRY_COUNT:
            time.sleep(RETRY_DELAY)

    print(f"  ❌  FAILED — {last_err}")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render Mermaid diagrams from a Markdown file to PNG images.",
    )
    parser.add_argument("--input",  "-i", type=Path, default=DEFAULT_INPUT,
                        help=f"Input Markdown file (default: {DEFAULT_INPUT.name})")
    parser.add_argument("--out",    "-o", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Output directory (default: doc/diagrams/)")
    parser.add_argument("--filter", "-f", default=None,
                        help="Only render diagrams whose slug contains this string")
    parser.add_argument("--no-verify", action="store_true",
                        help="Disable SSL verification (for corporate proxies)")
    args = parser.parse_args()

    md_path: Path = args.input.resolve()
    out_dir: Path = args.out.resolve()

    if not md_path.is_file():
        sys.exit(f"❌  Input file not found: {md_path}")

    try:
        import httpx
    except ImportError:
        sys.exit(
            "❌  httpx not found. Activate the virtual environment first:\n"
            "        .venv\\Scripts\\Activate.ps1\n"
            "    then re-run the script."
        )

    print(f"\n🔍  Reading: {md_path}")
    diagrams = _extract_diagrams(md_path)

    if not diagrams:
        sys.exit("❌  No Mermaid code blocks found in the file.")

    print(f"📊  Found {len(diagrams)} Mermaid diagram(s)")

    if args.filter:
        diagrams = [(l, c) for l, c in diagrams if args.filter.lower() in l.lower()]
        if not diagrams:
            sys.exit(f"❌  No diagrams matching '{args.filter}'")
        print(f"🔎  Filtered to {len(diagrams)} diagram(s) matching '{args.filter}'")

    out_dir.mkdir(parents=True, exist_ok=True)

    ssl_verify = not args.no_verify
    if not ssl_verify:
        print("⚠️   SSL verification disabled (--no-verify)")

    print(f"\n🌐  Rendering via mermaid.ink → {out_dir}\n")

    ok = 0
    fail = 0

    with httpx.Client(verify=ssl_verify, follow_redirects=True) as client:
        for i, (label, code) in enumerate(diagrams, 1):
            print(f"  [{i:02d}/{len(diagrams)}] {label} … ", end="", flush=True)
            out = _render_one(client, label, code, out_dir)
            if out:
                size_kb = out.stat().st_size // 1024
                print(f"✅  {out.name}  ({size_kb} KB)")
                ok += 1
            else:
                fail += 1

    print(f"\n{'─'*60}")
    print(f"  ✅  {ok} rendered successfully")
    if fail:
        print(f"  ❌  {fail} failed")
        print(f"\n  💡  If you see SSL errors try:  python tools/render_diagrams.py --no-verify")
    print(f"  📁  Output: {out_dir}")
    print(f"{'─'*60}\n")

    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()

