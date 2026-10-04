"""Absolute-path entry point for MCP clients that do not set a working directory."""
from law_harness.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
