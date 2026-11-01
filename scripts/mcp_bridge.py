"""Absolute-path entry point for MCP clients with any working directory."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.argv[1:1] = ["mcp", "--config", str(root / "config.json")]
from cyai.__main__ import main

main()
