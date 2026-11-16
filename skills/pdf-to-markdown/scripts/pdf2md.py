#!/usr/bin/env python3
"""Minimal CLI wrapper around pdf-inspector (pip package)."""

import argparse
import json
import sys
from pathlib import Path

try:
    import pdf_inspector
except ImportError:
    sys.exit(
        "pdf-inspector is not installed.\n"
        "Install it with: python -m pip install pdf-inspector"
    )

FIELDS = (
    "pdf_type", "confidence", "page_count", "markdown",
    "pages_needing_ocr", "pages_with_tables", "pages_with_columns",
    "has_encoding_issues", "is_complex_layout", "processing_time_ms",
    "title", "author", "subject", "keywords", "creator", "producer",
    "creation_date", "mod_date", "cmap_gaps",
)


def parse_pages(spec: str) -> list[int]:
    # process_pdf and process_pdf_with_ocr both use 1-indexed pages
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            a, b = int(start), int(end)
            if a > b:
                a, b = b, a
            pages.extend(range(a, b + 1))
        else:
            pages.append(int(part))
    if any(p < 1 for p in pages):
        raise ValueError("page numbers start at 1")
    return pages


def to_dict(result) -> dict:
    return {f: getattr(result, f, None) for f in FIELDS}


def run_one(path: Path, args) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    if args.ocr:
        result = pdf_inspector.process_pdf_with_ocr(
            str(path), mode="auto", page_numbers=args.pages_parsed
        )
    else:
        result = pdf_inspector.process_pdf(str(path), pages=args.pages_parsed)
    data = to_dict(result)
    data["file"] = str(path)
    if args.ocr:
        data["pages_routed_to_ocr"] = getattr(result, "pages_routed_to_ocr", None)
    return data


def render_markdown(data: dict) -> str:
    if data["markdown"]:
        return data["markdown"]
    pages = data.get("pages_needing_ocr") or []
    hint = f" pages needing OCR (1-based): {pages}" if pages else ""
    print(
        f"warning: no extractable text in {data['file']} "
        f"(type={data['pdf_type']}).{hint}",
        file=sys.stderr,
    )
    return ""


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        prog="pdf2md.py",
        description="PDF -> Markdown using pdf-inspector (local, no OCR by default).",
    )
    ap.add_argument("inputs", nargs="+", type=Path, help="PDF file(s) or directories")
    ap.add_argument("-r", "--recursive", action="store_true", help="search directories recursively")
    ap.add_argument("-o", "--output", type=Path, help="output file, or directory for multiple inputs")
    ap.add_argument("--json", action="store_true", help="emit JSON with metadata + markdown")
    ap.add_argument("--meta", action="store_true", help="print classification metadata only")
    ap.add_argument("--pages", help="1-indexed page selection, e.g. 1,3,5-10")
    ap.add_argument(
        "--ocr",
        action="store_true",
        help="selective OCR (requires PDFium + ONNX Runtime installed)",
    )
    args = ap.parse_args()

    try:
        args.pages_parsed = parse_pages(args.pages) if args.pages else None
    except ValueError as e:
        ap.error(f"invalid --pages: {e}")

    inputs: list[Path] = []
    for path in args.inputs:
        if path.is_dir():
            pattern = "**/*.pdf" if args.recursive else "*.pdf"
            found = sorted(p for p in path.glob(pattern) if p.is_file())
            if not found:
                print(f"warning: no PDF files in {path}", file=sys.stderr)
            inputs.extend(found)
        else:
            inputs.append(path)
    args.inputs = inputs
    if not args.inputs:
        print("error: no input PDF files", file=sys.stderr)
        return 1

    if len(args.inputs) > 1 and args.output and args.output.exists() and not args.output.is_dir():
        ap.error("-o must be a directory when passing multiple inputs")

    results, failed = [], 0
    for path in args.inputs:
        try:
            results.append(run_one(path, args))
        except FileNotFoundError:
            print(f"error: not found: {path}", file=sys.stderr)
            failed += 1
        except Exception as e:
            print(f"error: {path}: {type(e).__name__}: {e}", file=sys.stderr)
            failed += 1

    def build_text(docs: list[dict]) -> str:
        if args.json:
            payload = docs[0] if len(docs) == 1 else docs
            return json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        if args.meta:
            return "\n".join(
                f"{d['file']}\n"
                f"  type={d['pdf_type']} confidence={round(d['confidence'], 3)} "
                f"pages={d['page_count']} time={d['processing_time_ms']}ms\n"
                f"  tables={d.get('pages_with_tables')} "
                f"columns={d.get('pages_with_columns')} "
                f"encoding_issues={d.get('has_encoding_issues')} "
                f"complex_layout={d.get('is_complex_layout')}\n"
                f"  ocr_pages(1-based)={d.get('pages_needing_ocr')}"
                for d in docs
            )
        return "\n\n".join(c for c in (render_markdown(d) for d in docs) if c)

    text = ""
    if args.output and (len(results) > 1 or args.output.is_dir()):
        args.output.mkdir(parents=True, exist_ok=True)
        suffix = ".json" if args.json else ".md"
        for d in results:
            target = args.output / (Path(d["file"]).stem + suffix)
            target.write_text(build_text([d]), encoding="utf-8")
            print(f"wrote {target}", file=sys.stderr)
    else:
        text = build_text(results)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            print(text)

    if failed:
        return 1
    return 2 if not args.meta and not args.json and not text else 0


if __name__ == "__main__":
    raise SystemExit(main())
