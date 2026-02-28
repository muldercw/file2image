# file2image

An MCP (Model Context Protocol) server that converts **any document into page images** — like *Print to Image* for AI agents.

Hand it a PDF, Word doc, PowerPoint, spreadsheet, HTML page, source code file, or plain text and it will render each page as a high-quality image. Perfect for feeding document pages to vision models, generating thumbnails, or creating visual previews.

## ✨ Features

- **Wide format support** — PDF, DOCX, PPTX, XLSX, HTML, EPUB, SVG, TXT, source code, and 50+ more
- **Multi-page** — returns one image per page / slide / sheet
- **Configurable DPI** — control resolution from thumbnails to print quality
- **Save to disk** — optionally write images to a directory
- **Two MCP tools** — `convert_document` and `list_supported_formats`
- **Cross-platform** — Windows, macOS, Linux
- **Zero config** — works out of the box for PDFs and text; add LibreOffice for Office docs

## 📁 Supported Formats

| Category | Extensions | Engine |
|---|---|---|
| **Documents** | `.pdf` `.xps` `.epub` `.mobi` `.fb2` `.cbz` | PyMuPDF (native) |
| **Web / Markup** | `.html` `.htm` `.svg` `.xml` | PyMuPDF (native) |
| **Office** | `.docx` `.doc` `.pptx` `.ppt` `.xlsx` `.xls` `.odt` `.odp` `.ods` `.rtf` `.csv` | LibreOffice → PDF → PyMuPDF |
| **Text / Code** | `.py` `.js` `.ts` `.md` `.json` `.yaml` `.toml` `.go` `.rs` `.java` `.c` `.cpp` + many more | Pillow text renderer |
| **Images** | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` `.tiff` `.ico` | Returned directly |

## 🚀 Quick Start

### Run directly from GitHub

```bash
uvx --from git+https://github.com/muldercw/file2image.git file2image
```

### Local development

```bash
git clone https://github.com/muldercw/file2image.git
cd file2image
uv pip install -e .
file2image              # start the MCP server
file2image --info       # print supported formats
file2image --verbose    # debug logging
```

## 🔌 Integration

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "file2image": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/muldercw/file2image.git",
        "file2image"
      ]
    }
  }
}
```

### VS Code / Copilot

Add to your `.vscode/mcp.json`:

```json
{
  "servers": {
    "file2image": {
      "command": "uvx",
      "args": [
        "--from", "git+https://github.com/muldercw/file2image.git",
        "file2image"
      ]
    }
  }
}
```

## 🛠 Tool Reference

### `convert_document`

Convert a document file into one image per page.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file_path` | `string` | *(required)* | Path to the document |
| `dpi` | `int` | `200` | Rendering resolution |
| `image_format` | `string` | `"png"` | `"png"` or `"jpeg"` |
| `output_dir` | `string` | `null` | Save images to this directory |
| `max_pages` | `int` | `0` | Limit pages (0 = all) |

**Returns** a list of objects per page:

```json
{
  "page": 1,
  "total_pages": 5,
  "width": 1700,
  "height": 2200,
  "format": "png",
  "mime_type": "image/png",
  "base64_data": "iVBORw0KGgo…",
  "saved_path": "/tmp/out/doc_page1.png"
}
```

### `list_supported_formats`

Returns a structured summary of all supported formats, grouped by category, and indicates whether LibreOffice is available.

## 📋 Requirements

- **Python** ≥ 3.10
- **PyMuPDF** — renders PDFs, EPUB, XPS, SVG, HTML natively
- **Pillow** — renders text/code files as images
- **FastMCP** ≥ 2.0 — serves the MCP protocol
- **LibreOffice** *(optional)* — needed only for Office formats (DOCX, PPTX, XLSX, etc.)

## 🔐 Security

- File size limit: **50 MB**
- Format validation before processing
- Detailed error messages for unsupported or corrupt files

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

Built for the MCP ecosystem. Contributions welcome!
