"""
file2image MCP Server — convert any document to page images.

Tools exposed:
  • convert_document   — convert a file to images (returns base64 + optional save)
  • list_supported_formats — list every file extension that can be converted
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastmcp import FastMCP

from file2image.converter import (
    ALL_SUPPORTED,
    convert_to_images,
    get_supported_formats,
    validate_file,
)

logger = logging.getLogger("file2image")

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="file2image",
    instructions=(
        "An MCP server that converts documents into images — like 'Print to Image'. "
        "Give it any document (PDF, DOCX, PPTX, HTML, TXT, source code, …) and it "
        "will return one image per page. Useful for visual previews, thumbnailing, "
        "or feeding document pages as images to vision models."
    ),
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def convert_document(
    file_path: str,
    dpi: int = 200,
    image_format: str = "png",
    output_dir: str | None = None,
    max_pages: int = 0,
) -> list[dict]:
    """Convert a document file into one image per page.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the document to convert.
        Supported formats include PDF, DOCX, PPTX, XLSX, HTML, TXT,
        EPUB, SVG, source code files, and many more.
    dpi : int, optional
        Rendering resolution in dots-per-inch (default: 200).
        Higher values produce sharper but larger images.
    image_format : str, optional
        Output image format — "png" (default) or "jpeg".
    output_dir : str, optional
        If provided, each page image will also be saved to this directory.
        The directory is created if it doesn't exist.
    max_pages : int, optional
        Maximum number of pages to convert (0 = all pages, default).
        Useful for previewing just the first page of long documents.

    Returns
    -------
    list[dict]
        A list of dicts, one per page, each containing:
        - page: page number (1-based)
        - total_pages: total page count in the document
        - width / height: image dimensions in pixels
        - format: image format ("png" or "jpeg")
        - mime_type: MIME type of the image
        - base64_data: base64-encoded image bytes
        - saved_path: (only if output_dir was given) path where image was saved
    """
    path = Path(file_path).expanduser().resolve()
    validate_file(path)

    results = convert_to_images(
        path,
        dpi=dpi,
        image_format=image_format,
        output_dir=output_dir,
    )

    # Trim to max_pages if requested
    if max_pages > 0:
        results = results[:max_pages]

    return results


@mcp.tool()
def list_supported_formats() -> dict:
    """Return a structured summary of all supported document formats.

    The response groups formats by category:
    - native_document_formats: PDF, XPS, EPUB, SVG, etc. (rendered natively)
    - office_formats: DOCX, PPTX, XLSX, etc. (requires LibreOffice)
    - text_and_code_formats: .py, .js, .md, .json, etc. (rendered as styled text)
    - image_formats: PNG, JPEG, etc. (returned as-is)

    Also indicates whether LibreOffice is available for Office conversions.
    """
    return get_supported_formats()


# ---------------------------------------------------------------------------
# Entry point (for running directly)
# ---------------------------------------------------------------------------


def run(verbose: bool = False) -> None:
    """Start the MCP server."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Starting file2image MCP server v0.1.0")
    logger.info("Supported extensions: %d formats", len(ALL_SUPPORTED))
    mcp.run()
