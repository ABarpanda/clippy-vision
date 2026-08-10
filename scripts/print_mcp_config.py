"""Print an MCP client config for this Clippy Vision install.

MCP clients spawn the server with no shell context, so every path has to be
absolute. This resolves them from the running interpreter and prints a snippet
that can be pasted straight into Claude Desktop or Cursor.

    python scripts/print_mcp_config.py
    python scripts/print_mcp_config.py --client cursor
    python scripts/print_mcp_config.py --data-dir "D:/clippy/data"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp_server.py"

CONFIG_LOCATIONS = {
    "claude": {
        "win32": r"%APPDATA%\Claude\claude_desktop_config.json",
        "darwin": "~/Library/Application Support/Claude/claude_desktop_config.json",
        "linux": "~/.config/Claude/claude_desktop_config.json",
    },
    "cursor": {
        "win32": r"%USERPROFILE%\.cursor\mcp.json  (or Settings -> MCP -> Add new MCP server)",
        "darwin": "~/.cursor/mcp.json  (or Settings -> MCP -> Add new MCP server)",
        "linux": "~/.cursor/mcp.json  (or Settings -> MCP -> Add new MCP server)",
    },
}


def default_data_dir() -> Path:
    env = (os.environ.get("CLIPPY_DATA_DIR") or "").strip()
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Clippy Vision" / "data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Clippy Vision" / "data"
    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / "clippy-vision" / "data"


def server_entry(data_dir: Path) -> dict:
    return {
        "command": sys.executable,
        "args": [str(SERVER)],
        "env": {
            "CLIPPY_DATA_DIR": str(data_dir),
            "PYTHONPATH": str(ROOT),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("claude", "cursor", "both"), default="both")
    parser.add_argument("--data-dir", help="Override the Clippy data directory.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    snippet = json.dumps({"mcpServers": {"clippy-vision": server_entry(data_dir)}}, indent=2)
    clients = ("claude", "cursor") if args.client == "both" else (args.client,)
    platform_key = sys.platform if sys.platform in ("win32", "darwin") else "linux"

    if not SERVER.exists():
        print(f"WARNING: {SERVER} not found — run this from the Clippy Vision repo.\n")
    if not (data_dir / "events.db").exists():
        print(f"WARNING: no events.db in {data_dir} — Clippy has not captured anything there yet.\n")

    for client in clients:
        print(f"=== {client.capitalize()} ===")
        print(f"Config file: {CONFIG_LOCATIONS[client][platform_key]}")
        print(snippet)
        print()

    print("Ollama must be running (qwen3:8b + nomic-embed-text) for retrieval tools to work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
