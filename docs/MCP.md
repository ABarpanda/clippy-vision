# Clippy Vision MCP server

Query Clippy's local memory from Claude Desktop, Cursor, or any MCP client. The
server runs on your machine and reads the same database the desktop app writes to.

> Tool results are returned to whichever client you connect. If that client is a
> cloud assistant, the retrieved context leaves your machine as part of its normal
> request. Clippy itself still stores and searches everything locally.

## Prerequisites

1. Clippy Vision installed (or running from source) with some captured history.
2. Python with `requirements.txt` installed — the setup wizard does this.
3. Ollama running with `qwen3:8b` and `nomic-embed-text` pulled.

## Connect from the app (easiest)

Open **Settings → Connect other AI apps** and press **Connect** next to Claude
Desktop or Cursor. Clippy writes the config for that app with the right paths
already filled in, keeping a `.clippy-backup` copy of the previous file and
leaving any other MCP servers you had untouched. Restart that app afterwards.

**Check server** (also runs when you open Settings) spawns the same MCP entry
those apps would use and confirms tools register against your data directory.
“Server ready” means Clippy’s side can start — it does **not** mean Cursor or
Claude has loaded the session yet; reload that app after connecting.

**Copy config** puts the same JSON on your clipboard for any other MCP client.
**Disconnect** removes only Clippy's entry.

### If Connect does not work

Use **Copy config**, then add the server manually in that app. Official guides:

- [Cursor — Model Context Protocol (MCP)](https://cursor.com/docs/mcp) — Settings →
  Tools & MCP, or edit `~/.cursor/mcp.json`
- [Claude Desktop — local MCP servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [MCP docs — connect local servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers) —
  Claude Desktop Developer → Edit Config walkthrough

Paste the copied `clippy-vision` block into the client’s MCP config (keep any
other servers you already have), save, then fully quit and reopen that app.

## Generate your config manually

From the repo:

```powershell
python scripts\print_mcp_config.py
```

It prints a ready-to-paste snippet with absolute paths for the interpreter, the
server script, and your data directory. Use `--client claude` or `--client cursor`
for just one, and `--data-dir` to point at a non-default location.

## Claude Desktop

Official setup: [Getting started with local MCP servers on Claude Desktop](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
(or the [MCP connect-local walkthrough](https://modelcontextprotocol.io/docs/develop/connect-local-servers)).

If auto-connect failed, open Claude Desktop → **Settings → Developer → Edit Config**,
or edit `%APPDATA%\Claude\claude_desktop_config.json` on Windows /
`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS.
Merge in the `clippy-vision` entry (Copy config from Clippy, or the example below):

```json
{
  "mcpServers": {
    "clippy-vision": {
      "command": "C:\\Users\\YOU\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["C:\\path\\to\\clippy-vision\\mcp_server.py"],
      "env": {
        "CLIPPY_DATA_DIR": "C:\\Users\\YOU\\AppData\\Roaming\\Clippy Vision\\data",
        "PYTHONPATH": "C:\\path\\to\\clippy-vision"
      }
    }
  }
}
```

Restart Claude Desktop, then ask "what did I work on yesterday?" and confirm it
calls `query_activity`.

## Cursor

Official setup: [Cursor MCP docs](https://cursor.com/docs/mcp).

If auto-connect failed, open **Settings → Tools & MCP**, or write
`~/.cursor/mcp.json` (user-wide) / `.cursor/mcp.json` (project). Paste Clippy’s
copied config, or:

```json
{
  "mcpServers": {
    "clippy-vision": {
      "command": "python",
      "args": ["C:/path/to/clippy-vision/mcp_server.py"],
      "env": {
        "CLIPPY_DATA_DIR": "C:/Users/YOU/AppData/Roaming/Clippy Vision/data",
        "PYTHONPATH": "C:/path/to/clippy-vision"
      }
    }
  }
}
```

Reload Cursor, confirm `clippy-vision` shows as connected under Tools & MCP, then
ask about your activity.

## Packaged install paths

`mcp_server.py` ships inside the app. Point `args` and `PYTHONPATH` at:

| | Server script | Data directory |
|--|--|--|
| Windows | `...\Clippy Vision\resources\clippy\mcp_server.py` | `%APPDATA%\Clippy Vision\data` |
| macOS | `/Applications/Clippy Vision.app/Contents/Resources/clippy/mcp_server.py` | `~/Library/Application Support/Clippy Vision/data` |

`CLIPPY_DATA_DIR` is optional on a packaged install — the server falls back to
those defaults. Set it explicitly if you run Clippy from source, where the data
lives in `<repo>/core/data`.

## Tools

| Tool | Use for |
|------|---------|
| `query_activity` | **Start here.** Runs Clippy's router + prefetch and returns the right context in one call |
| `search_sessions_tool` | Fallback: day/week overviews, project recaps |
| `search_events_tool` | Fallback: exact URLs, OCR text, clipboard, fine detail |
| `recall_memory_tool` | List long-term memory clusters |
| `fetch_cluster_tool` | All facts inside one cluster |
| `save_identity_tool` | Save a personal fact |
| `save_note_tool` | Save a note or reminder |
| `delete_note_tool` | Forget a note or fact |

`query_activity` is the same path the in-app chat uses: the MiniLM router picks a
route (time window, topic, specific artifact, or memory), and only routes that
clear their confidence threshold are fetched. Casual questions retrieve nothing,
which is intentional — the client should just answer them.

`query_activity` also takes an optional `recent_turns` list — the last few messages
of your conversation, oldest first, each prefixed with the speaker:

```json
{
  "question": "what about the day before that?",
  "recent_turns": [
    "User: what did I work on yesterday?",
    "Assistant: you were packaging the macOS build"
  ]
}
```

Those turns feed time parsing, topic extraction, and the query embedding, the same
way the in-app chat uses its own history. Routing reads the bare question first,
since the classifier was trained on single turns; only when that finds nothing to
retrieve does it retry with the previous question prepended. That recovers vague
follow-ups ("what about the day before that?", "and the other one?") while leaving
acknowledgements like "thanks" and standalone questions alone. Still phrase the
question as fully as you can — routing is best when it stands on its own.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Empty or wrong answers | `CLIPPY_DATA_DIR` points at the wrong folder; confirm `events.db` is there |
| `ModuleNotFoundError` | `PYTHONPATH` must be the folder containing `core/` and `agent/` |
| Retrieval hangs or errors | Start Ollama and pull `qwen3:8b` + `nomic-embed-text` |
| First call is slow | The server warms the router at startup, but Ollama still has to load `qwen3:8b` and `nomic-embed-text`; later calls are faster |
| Server won't start | Run the same `python ...\mcp_server.py` in a terminal and read stderr |
| Connect writes config but Cursor/Claude show errors | Use **Copy config** / **Check server**. Config should use an absolute Python path; reconnect from Clippy if an old bare `python` entry is stale |
| Check server times out | Cold imports can be slow; retry once. If it still fails, run `python mcp_server.py --self-check` in a terminal |
