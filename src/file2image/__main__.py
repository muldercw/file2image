"""CLI entry point for file2image MCP server."""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="file2image",
        description="MCP server that converts documents into page images.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print server info and supported formats, then exit.",
    )
    args = parser.parse_args()

    if args.info:
        from file2image.converter import get_supported_formats
        import json

        info = {
            "name": "file2image",
            "version": "0.1.0",
            "description": "MCP server — convert any document to page images.",
            "supported_formats": get_supported_formats(),
        }
        print(json.dumps(info, indent=2))
        sys.exit(0)

    from file2image.server import run
    run(verbose=args.verbose)


if __name__ == "__main__":
    main()
