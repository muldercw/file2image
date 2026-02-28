"""
Document-to-image conversion engine.

Supports:
  - PDF, XPS, EPUB, MOBI, FB2, CBZ, SVG, TXT  (via PyMuPDF)
  - Plain text / source code                    (via Pillow)
  - Office formats (DOCX, PPTX, XLSX, ODP …)   (via LibreOffice headless → PDF → PyMuPDF)
"""

from __future__ import annotations

import base64
import io
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("file2image")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # 50 MB

# Formats PyMuPDF can open directly
PYMUPDF_EXTENSIONS: set[str] = {
    ".pdf", ".xps", ".epub", ".mobi", ".fb2",
    ".cbz", ".svg", ".txt", ".xml", ".html", ".htm",
}

# Office formats we'll convert via LibreOffice
OFFICE_EXTENSIONS: set[str] = {
    ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".odt", ".odp", ".ods", ".odg", ".rtf", ".csv",
}

# Plain-text-like extensions we can render ourselves
TEXT_EXTENSIONS: set[str] = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c",
    ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
    ".php", ".sh", ".bash", ".zsh", ".bat", ".ps1",
    ".sql", ".r", ".m", ".swift", ".kt", ".scala",
    ".lua", ".pl", ".pm", ".ex", ".exs", ".hs",
    ".css", ".scss", ".less", ".xml", ".html", ".htm",
    ".env", ".gitignore", ".dockerignore", ".editorconfig",
}

# Image formats that are already images — we just return them directly
IMAGE_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".tiff", ".tif", ".ico",
}

ALL_SUPPORTED = PYMUPDF_EXTENSIONS | OFFICE_EXTENSIONS | TEXT_EXTENSIONS | IMAGE_EXTENSIONS

DEFAULT_DPI = 200
DEFAULT_IMAGE_FORMAT = "png"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_libreoffice() -> str | None:
    """Return the path to the LibreOffice executable, or None."""
    candidates: list[str] = []
    system = platform.system()
    if system == "Windows":
        for base in [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        ]:
            if base:
                candidates.append(os.path.join(base, "LibreOffice", "program", "soffice.exe"))
    elif system == "Darwin":
        candidates.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    else:
        candidates.append("soffice")
        candidates.append("libreoffice")

    for c in candidates:
        if shutil.which(c) or os.path.isfile(c):
            return c
    return None


def _convert_office_to_pdf(file_path: Path) -> Path:
    """Convert an Office document to PDF via LibreOffice headless."""
    soffice = _find_libreoffice()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice is required to convert Office documents (DOCX, PPTX, XLSX, etc.) "
            "but was not found. Install LibreOffice and make sure 'soffice' is on your PATH."
        )

    tmp_dir = tempfile.mkdtemp(prefix="file2image_")
    try:
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", tmp_dir,
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (exit {result.returncode}): {result.stderr}"
            )

        # The output PDF has the same stem as the input
        pdf_path = Path(tmp_dir) / (file_path.stem + ".pdf")
        if not pdf_path.exists():
            # Sometimes LibreOffice changes the name; find any PDF in the dir
            pdfs = list(Path(tmp_dir).glob("*.pdf"))
            if pdfs:
                pdf_path = pdfs[0]
            else:
                raise RuntimeError(
                    f"LibreOffice did not produce a PDF. stdout={result.stdout}, stderr={result.stderr}"
                )
        return pdf_path
    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice conversion timed out (120s limit).")


def _render_text_to_images(
    text: str,
    dpi: int = DEFAULT_DPI,
    image_format: str = DEFAULT_IMAGE_FORMAT,
) -> list[dict]:
    """Render plain text into images (one per 'page') using Pillow."""
    # Page dimensions at given DPI (approximate US Letter)
    page_w = int(8.5 * dpi)
    page_h = int(11 * dpi)
    margin = int(0.6 * dpi)
    usable_w = page_w - 2 * margin
    usable_h = page_h - 2 * margin

    # Try to load a monospace font
    font_size = max(12, dpi // 12)
    try:
        font = ImageFont.truetype("consola.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", font_size)
        except OSError:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

    # Estimate chars per line and lines per page
    # Use a test draw to measure
    test_img = Image.new("RGB", (1, 1))
    test_draw = ImageDraw.Draw(test_img)
    char_bbox = test_draw.textbbox((0, 0), "M", font=font)
    char_w = char_bbox[2] - char_bbox[0]
    char_h = char_bbox[3] - char_bbox[1]
    line_height = int(char_h * 1.4)

    chars_per_line = max(1, usable_w // max(1, char_w))
    lines_per_page = max(1, usable_h // max(1, line_height))

    # Word-wrap and paginate
    lines: list[str] = []
    for raw_line in text.splitlines():
        if not raw_line:
            lines.append("")
            continue
        # Expand tabs
        raw_line = raw_line.expandtabs(4)
        while len(raw_line) > chars_per_line:
            lines.append(raw_line[:chars_per_line])
            raw_line = raw_line[chars_per_line:]
        lines.append(raw_line)

    pages: list[list[str]] = []
    for i in range(0, len(lines), lines_per_page):
        pages.append(lines[i : i + lines_per_page])
    if not pages:
        pages = [[""]]

    results: list[dict] = []
    for page_num, page_lines in enumerate(pages, 1):
        img = Image.new("RGB", (page_w, page_h), color="white")
        draw = ImageDraw.Draw(img)

        y = margin
        for line_text in page_lines:
            draw.text((margin, y), line_text, fill="black", font=font)
            y += line_height

        buf = io.BytesIO()
        pil_fmt = "PNG" if image_format.lower() == "png" else image_format.upper()
        img.save(buf, format=pil_fmt)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        results.append({
            "page": page_num,
            "total_pages": len(pages),
            "width": page_w,
            "height": page_h,
            "format": image_format.lower(),
            "mime_type": f"image/{image_format.lower()}",
            "base64_data": b64,
        })

    return results


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------


def validate_file(file_path: Path) -> None:
    """Validate a file path for conversion."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Not a file: {file_path}")
    size = file_path.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size / (1024*1024):.1f} MB "
            f"(limit is {MAX_FILE_SIZE_MB} MB)"
        )
    ext = file_path.suffix.lower()
    if ext not in ALL_SUPPORTED:
        raise ValueError(
            f"Unsupported file format: '{ext}'. "
            f"Supported extensions: {sorted(ALL_SUPPORTED)}"
        )


def convert_to_images(
    file_path: str | Path,
    *,
    dpi: int = DEFAULT_DPI,
    image_format: str = DEFAULT_IMAGE_FORMAT,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """
    Convert a document to a list of page images.

    Parameters
    ----------
    file_path : path to the document
    dpi : rendering resolution (default 200)
    image_format : output image format — "png" or "jpeg" (default "png")
    output_dir : if provided, images are also saved to this directory

    Returns
    -------
    list of dicts, each containing:
        page, total_pages, width, height, format, mime_type, base64_data,
        and optionally saved_path
    """
    file_path = Path(file_path).resolve()
    validate_file(file_path)

    ext = file_path.suffix.lower()
    image_format = image_format.lower().strip()
    if image_format not in ("png", "jpeg", "jpg"):
        image_format = "png"
    if image_format == "jpg":
        image_format = "jpeg"

    results: list[dict] = []

    # --- Already an image file → return as-is ---
    if ext in IMAGE_EXTENSIONS:
        with Image.open(file_path) as img:
            # Handle animated GIFs — each frame becomes a page
            frames = getattr(img, "n_frames", 1)
            for frame_idx in range(frames):
                img.seek(frame_idx)
                frame = img.convert("RGB") if img.mode != "RGB" else img.copy()
                buf = io.BytesIO()
                pil_fmt = "PNG" if image_format == "png" else "JPEG"
                frame.save(buf, format=pil_fmt)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                results.append({
                    "page": frame_idx + 1,
                    "total_pages": frames,
                    "width": frame.width,
                    "height": frame.height,
                    "format": image_format,
                    "mime_type": f"image/{image_format}",
                    "base64_data": b64,
                })
        _maybe_save(results, file_path, output_dir, image_format)
        return results

    # --- Plain-text / source code fallback (if not openable by PyMuPDF) ---
    if ext in TEXT_EXTENSIONS and ext not in PYMUPDF_EXTENSIONS:
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = file_path.read_text(encoding="latin-1", errors="replace")
        results = _render_text_to_images(text, dpi=dpi, image_format=image_format)
        _maybe_save(results, file_path, output_dir, image_format)
        return results

    # --- Office documents → convert to PDF first ---
    tmp_pdf: Path | None = None
    render_path = file_path
    if ext in OFFICE_EXTENSIONS:
        tmp_pdf = _convert_office_to_pdf(file_path)
        render_path = tmp_pdf

    # --- Render with PyMuPDF ---
    try:
        doc = fitz.open(str(render_path))
        total_pages = len(doc)
        for page_num in range(total_pages):
            page = doc[page_num]
            # Render page to pixmap
            zoom = dpi / 72  # PyMuPDF default is 72 DPI
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            if image_format == "png":
                img_bytes = pix.tobytes("png")
            else:
                # Convert to JPEG via Pillow
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=90)
                img_bytes = buf.getvalue()

            b64 = base64.b64encode(img_bytes).decode("ascii")
            results.append({
                "page": page_num + 1,
                "total_pages": total_pages,
                "width": pix.width,
                "height": pix.height,
                "format": image_format,
                "mime_type": f"image/{image_format}",
                "base64_data": b64,
            })
        doc.close()
    except Exception as exc:
        # If PyMuPDF can't open it, try text rendering as last resort
        if ext in TEXT_EXTENSIONS:
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                text = file_path.read_text(encoding="latin-1", errors="replace")
            results = _render_text_to_images(text, dpi=dpi, image_format=image_format)
        else:
            raise RuntimeError(f"Failed to convert '{file_path.name}': {exc}") from exc
    finally:
        # Clean up temp PDF
        if tmp_pdf and tmp_pdf.exists():
            try:
                tmp_pdf.unlink()
                tmp_pdf.parent.rmdir()
            except OSError:
                pass

    _maybe_save(results, file_path, output_dir, image_format)
    return results


def _maybe_save(
    results: list[dict],
    source_path: Path,
    output_dir: str | Path | None,
    image_format: str,
) -> None:
    """Optionally save images to disk and add 'saved_path' to each result."""
    if output_dir is None:
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ext = "png" if image_format == "png" else "jpg"
    stem = source_path.stem

    for item in results:
        filename = f"{stem}_page{item['page']}.{ext}"
        save_path = out / filename
        raw = base64.b64decode(item["base64_data"])
        save_path.write_bytes(raw)
        item["saved_path"] = str(save_path)
        logger.info("Saved %s", save_path)


def get_supported_formats() -> dict:
    """Return a summary of all supported formats."""
    return {
        "native_document_formats": {
            "description": "Opened directly by the rendering engine (PyMuPDF)",
            "extensions": sorted(PYMUPDF_EXTENSIONS),
        },
        "office_formats": {
            "description": "Converted via LibreOffice headless, then rendered (requires LibreOffice)",
            "extensions": sorted(OFFICE_EXTENSIONS),
            "libreoffice_available": _find_libreoffice() is not None,
        },
        "text_and_code_formats": {
            "description": "Rendered as styled text pages via Pillow",
            "extensions": sorted(TEXT_EXTENSIONS - PYMUPDF_EXTENSIONS),
        },
        "image_formats": {
            "description": "Already images — returned directly (optionally re-encoded)",
            "extensions": sorted(IMAGE_EXTENSIONS),
        },
    }
