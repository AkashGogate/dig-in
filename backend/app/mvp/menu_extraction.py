"""Document-to-editable-draft boundary. No activation or provider/stock mutation.

Adapters return OCR lines, never operational facts. All file bytes live only in
an automatically removed temporary directory. Linux needs Poppler + Tesseract;
macOS uses the checked-in Apple Vision/PDFKit bridge and installed Swift tools.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_UPLOAD = 8 * 1024 * 1024
MEDIA = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}


class ExtractionUnavailable(RuntimeError):
    pass


def extraction_status():
    native = sys.platform == "darwin" and bool(shutil.which("swift"))
    portable = all(shutil.which(tool) for tool in ("pdfinfo", "pdftoppm", "tesseract"))
    return {
        "available": native or portable,
        "provider": "apple_vision"
        if native
        else "poppler_tesseract"
        if portable
        else "unavailable",
        "max_bytes": MAX_UPLOAD,
        "max_pages": 10,
        "media_types": list(MEDIA),
        "requires_human_review": True,
    }


def _run(args, timeout=60):
    try:
        return subprocess.run(
            args, check=True, capture_output=True, timeout=timeout
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(
            "Could not read the document. Use an unlocked PDF of at most 10 pages or a clear PNG/JPEG photo."
        ) from exc


def ocr_pages(content, media_type):
    status = extraction_status()
    if not status["available"]:
        raise ExtractionUnavailable(
            "Install Swift tools on macOS, or Poppler and Tesseract on Linux, then restart. Structured menu upload remains available."
        )
    with tempfile.TemporaryDirectory(prefix="dig-in-menu-") as directory:
        path = Path(directory) / "upload"
        path.write_bytes(content)
        if status["provider"] == "apple_vision":
            result = json.loads(
                _run(
                    [
                        shutil.which("swift"),
                        str(Path(__file__).parent / "adapters/menu_ocr.swift"),
                        str(path),
                        media_type,
                    ],
                    90,
                )
            )
            return result["pages"]
        if media_type == "application/pdf":
            info = _run(["pdfinfo", str(path)]).decode()
            count = re.search(r"Pages:\s+(\d+)", info)
            if not count or not 1 <= int(count[1]) <= 10:
                raise ValueError("PDF must have 1–10 pages")
            _run(
                [
                    "pdftoppm",
                    "-r",
                    "120",
                    "-png",
                    str(path),
                    str(Path(directory) / "page"),
                ],
                90,
            )
            images = sorted(Path(directory).glob("page-*.png"))
        else:
            images = [path]
        return [
            _run(["tesseract", str(image), "stdout"], 30).decode().splitlines()
            for image in images
        ]


HEADINGS = {
    "menu",
    "appetizers",
    "mains",
    "desserts",
    "starters",
    "drinks",
    "sides",
    "salads",
    "entrees",
    "groundwork",
    "heavy lifting",
    "finishing touches",
    "dig in",
    "the construction kitchen",
    "built for big appetites",
}


def propose_items(pages):
    """Conservative line grouping, not guaranteed layout/food understanding.

    Uppercase/short title lines and price-ending lines propose dish names;
    sentence lines attach as descriptions. OCR evidence remains editable below.
    No kitchen metadata, modifiers or allergy guarantees are inferred.
    """
    items = []
    for page in pages:
        for line in page:
            line = " ".join(line.split()).replace("|", " ")
            if not line or len(line) > 1200:
                continue
            label = re.sub(r"[^a-z ]", "", line.lower()).strip()
            if (
                label in HEADINGS
                or re.fullmatch(r"[\d\W]+", line)
                or "/" in line
                and line.upper() == line
            ):
                continue
            price = re.search(r"\s+\$?(\d{1,3}[.,]\d{2})\s*$", line)
            title = line[: price.start()].strip(" .-–") if price else line
            is_name = (
                bool(price)
                or title.isupper()
                or (
                    len(title.split()) <= 8
                    and not title.endswith(".")
                    and title.istitle()
                )
            )
            if is_name or not items:
                item = {"name": title[:200], "description": ""}
                if price:
                    item["price_cents"] = int(
                        price[1].replace(",", "").replace(".", "")
                    )
                items.append(item)
            elif items:
                items[-1]["description"] = (
                    items[-1]["description"] + " " + line
                ).strip()[:1000]
    return items[:500]


def extract_menu(content, media_type):
    if media_type not in MEDIA or not content.startswith(MEDIA[media_type]):
        raise ValueError("File signature does not match a supported PDF, PNG or JPEG")
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError("Upload must be 1 byte to 8 MiB")
    pages = ocr_pages(content, media_type)
    if (
        not 1 <= len(pages) <= 10
        or sum(len(line) for page in pages for line in page) > 100_000
    ):
        raise ValueError("Document contains too many pages or too much text")
    items = propose_items(pages)
    if not items:
        raise ValueError(
            "No readable dishes found. Try a clearer photo or paste the menu text"
        )
    return {
        "items": items,
        "source_text": "\n\n".join("\n".join(page) for page in pages),
        "page_count": len(pages),
        "requires_human_review": True,
        "warnings": [
            "OCR and line grouping can miss, split or merge dishes. Compare with the original and correct the editable items before encoding. Prices assume decimal cents; verify the source currency."
        ],
    }
