# Clippy Vision's Vision
The aim of this project is to build a complete screen watcher tool, one that sees what's on your screen (windows, clipboard, typing activity, screenshots), stores it in memory, remembers it, and retrieves or acts on it when needed.
To build trust with users, this project is kept 100% local and open source.

This doc exists so contributors know what we're optimizing for, where we stand today, and where we're headed, use it as the reference point when deciding what to build or how to build it.

# Principles it's built on
- **Privacy First:** No data should leave the user's machine. We're actively working toward zero sensitive-data capture (passwords, card numbers, etc.); this isn't fully solved yet, see Current Limitations below.
- **Performance & Efficiency:** It should not be a performance blocker and should be efficient enough. This comes before accuracy.
- **Transparency:** Openly share the current limitations of the system rather than hiding them.

# Current Limitations
- Sensitive info like passwords or card numbers can still be captured today. Manual pause/resume of capture is the current workaround while automatic redaction for this is being built.
- Per-app redaction is not usable yet. The backend rules exist in `core/privacy_settings.py`, but reliable window matching only works for Clippy Vision's own window; other apps match inconsistently. That is why Settings shows "Access control" as coming soon. Stopping capture is the dependable privacy switch until this is fixed.
- Running the vision model on screenshots is the main reason for the 16 GB RAM / 6 GB VRAM floor, which rules out most laptops. Reducing that floor is a priority, see the capture cascade item below.

# Roadmap
No fixed timeline, ordered by priority rather than by date.

**Version 1.0.1 (Shipped)**
- [x] Screen capture for Windows
- [x] Context building using qwen3:8b and qwen3-vl:4b
- [x] Hierarchical memory handling
- [x] Intent detection and query routing
- [x] ReAct agent for data retrieval and answering

**Version 1.1.0 (Shipped)**
- [x] Delete option for conversations (chats with agent)
- [ ] Screen redaction for WhatsApp, incognito tabs/private windows, Gmail, Outlook, etc. (still open, window matching is unreliable outside Clippy's own window, see Current Limitations)
- [x] Markdown rendering for agent responses in UI
- [x] Other bug fixes

**Version 1.2.0 (Current)**
- [x] Screen capture support for macOS along with a macOS release

**Version 1.3.0 (Next in pipeline)**
- Skills layer, making the agent proactive instead of purely reactive
- Planned skill 1: A reading/watching mode that quizzes you on material afterward, and a timed study mode that builds a quiz/test plus analytics once a session ends
- Planned skill 2: "when you see XYZ, do ABC"
- MCP server integration. `mcp_server.py` already exposes the retrieval and memory tools over stdio, so what is left is shipping it with the packaged app (it is currently missing from the electron-builder `extraResources` filter), making paths resolve when a client like Claude Desktop or Cursor spawns it with no Clippy environment, and writing per-client setup docs. This lets any MCP client query Clippy's memory directly instead of the user copy-pasting context out of the chat.

**Planned next, ordered by priority**

*Capture cascade: accessibility APIs, then OCR, then vision model*
Today every screenshot that needs text goes to `qwen3-vl:4b`, which is what forces the GPU requirement. The plan is to try platform accessibility APIs first (UI Automation on Windows, AXUIElement on macOS), fall back to OCR when that returns nothing useful, and only reach for the vision model when text extraction is still too thin to classify the activity. Each step needs a measurable threshold for "not enough text" and a benchmark run in `bench/`, otherwise the cascade quietly degrades to always-vision and saves nothing. This is tracked as the single biggest lever on the hardware floor, and it needs to land per platform behind one shared interface.

*Timeline and capture audit view*
A browsable view of what Clippy actually captured, session by session, with the matching screenshots, plus the ability to delete individual entries from memory. This serves recall (scroll back to find something) and trust equally: a user should be able to see exactly what is stored about them and remove it. Needs listing endpoints on the API first, since `api_server.py` has no events or sessions listing today.

*Audio capture and speaker attribution for meetings*
Local transcription with faster-whisper or whisper.cpp, pinned to CPU so it does not compete with the reasoning model for VRAM. First version attributes speech by audio source rather than by voice: microphone is the user, system output loopback is everyone else, which needs no enrollment and no extra model. Voiceprint matching (a one-time voice sample, then embedding similarity per segment) is a later addition for in-person conversations where every voice arrives through the mic. No meeting-platform APIs or bots, loopback capture works the same across Zoom, Meet and Teams. macOS system audio is the hard part and will need ScreenCaptureKit audio or a virtual device.

*Mouse and idle signals*
Mouse activity is intended as an idle detector that gates capture, not as stored events. Storing raw clicks and scrolls adds volume without meaning and works against the bounded-storage design.

# Licensing
Core stays free and open source for individuals, always, latest version, no delay, source is visible for every version we release. Leaning toward AGPL (or similar) for the core, with a separate commercial license for companies that want to use it without AGPL's obligations. Still being finalized.

# Future Vision
The ultimate plan for monetizing Clippy Vision is an enterprise version, where an employee could hand off their work context to another employee, using what Clippy already captured, instead of calling and disturbing someone on vacation. There are other use cases beyond this one too. Individual versions stay completely free, regardless of what the enterprise version looks like.

# Contributing
Want to help build this? See [CONTRIBUTING.md](https://github.com/protocorn/clippy-vision?tab=contributing-ov-file) for setup, and join the Discord server for ongoing discussion, skills architecture, and what's currently being worked on.
