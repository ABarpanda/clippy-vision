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

# Roadmap
No fixed timeline, ordered by priority rather than by date.

**Version 1.0.1 (Current)**
- Screen capture for Windows
- Context building using qwen3:8b and qwen3-vl:4b
- Hierarchical memory handling
- Intent detection and query routing
- ReAct agent for data retrieval and answering

**Version 1.1.0 (Next in pipeline)**
- Delete option for conversations (chats with agent)
- Screen redaction for WhatsApp, incognito tabs/private windows, Gmail, Outlook, etc.
- Markdown rendering for agent responses in UI
- Other bug fixes

**Version 1.2.0 (Next in pipeline)**
- Screen capture support for macOS along with a macOS release

**Version 1.3.0 (Next in pipeline)**
- Skills layer, making the agent proactive instead of purely reactive
- First skills in progress: a reading/watching mode that quizzes you on material afterward, and a timed study mode that builds a quiz/test plus analytics once a session ends (in collaboration with contributor Sohan_Ananthula)
- General pattern: "when you see XYZ, do ABC"

# Licensing
Core stays free and open source for individuals, always, latest version, no delay, source is visible for every version we release. Leaning toward AGPL (or similar) for the core, with a separate commercial license for companies that want to use it without AGPL's obligations. Still being finalized.

# Future Vision
The ultimate plan for monetizing Clippy Vision is an enterprise version, where an employee could hand off their work context to another employee, using what Clippy already captured, instead of calling and disturbing someone on vacation. There are other use cases beyond this one too. Individual versions stay completely free, regardless of what the enterprise version looks like.

# Contributing
Want to help build this? See [CONTRIBUTING.md](https://github.com/protocorn/clippy-vision?tab=contributing-ov-file) for setup, and join the Discord server for ongoing discussion, skills architecture, and what's currently being worked on.
