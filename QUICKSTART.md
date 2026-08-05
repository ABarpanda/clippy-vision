# Quick Start — Clippy Vision

## Recommended: Use the Installer

Download the Windows installer or matching Apple Silicon / Intel macOS DMG from the [latest release](https://github.com/rusetiq/clippy-vision/releases/latest).

The installer's built-in setup wizard will:
- Check for Python (install via winget if missing)
- Check for Ollama (install via winget if missing)
- Start the Ollama service
- Install all Python packages from `requirements.txt`
- Download the required AI models (`qwen3:8b`, `qwen3-vl:4b`, `nomic-embed-text`)
- Warm the models into memory

After setup completes, click **Launch**. Clippy Vision will start automatically on future reboots via the system tray.

**Requirements:** Windows 10/11 (64-bit) or macOS 12+; **16 GB RAM / 6 GB VRAM or unified memory / 12 GB free disk** minimum. Internet is needed on first run for model downloads.

On macOS, grant Clippy Vision Screen Recording and Accessibility permission in System Settings → Privacy & Security.

---

## Running from Source

```powershell
git clone https://github.com/protocorn/clippy-vision.git
cd clippy-vision\electron-ui
npm install
npm start
```

The setup wizard runs automatically on first launch.

---

## Models

| Model | Size | Purpose |
|-------|------|---------|
| `qwen3:8b` | ~4.7 GB | Reasoning, summarization, SQL, QA |
| `qwen3-vl:4b` | ~2.9 GB | Vision OCR and screen activity |
| `nomic-embed-text` | ~274 MB | Vector embeddings |

---

## Troubleshooting

### Setup wizard fails at a step
Click **Retry** on the failed step. If it keeps failing, check the log panel in the wizard for the specific error.

### App stuck on loading screen
The API server takes 30–60s on first launch while models load into RAM. Wait for the spinner to clear. If it stays stuck, close the app, reopen it — it will re-run preflight checks and redirect to setup if anything is broken.

### "Windows protected your PC" on install
The installer is currently unsigned. Click **More info → Run anyway**. This warning appears on unsigned executables and will be resolved in a future release with a code-signing certificate.

### Ollama not found after install
Open a new terminal and run `ollama --version`. If not found, re-run the installer or install manually from [ollama.com](https://ollama.com/download).

### Reset setup / reinstall
Delete `%APPDATA%\Clippy Vision\setup_complete.json` — the setup wizard will run again on next launch.

### Check if everything is working
```powershell
# API health
curl http://localhost:8000/health

# Events captured
python -c "import sqlite3, os; db=os.path.join(os.environ['APPDATA'],'Clippy Vision','data','events.db'); print(sqlite3.connect(db).execute('SELECT COUNT(*) FROM events').fetchone()[0], 'events')"
```

---

## File Locations (installed)

| Item | Location |
|------|----------|
| App data (DB, screenshots) | `%APPDATA%\Clippy Vision\data\` |
| Setup flag | `%APPDATA%\Clippy Vision\setup_complete.json` |
| Ollama models | `%USERPROFILE%\.ollama\models\` |
| App install | `%LOCALAPPDATA%\Programs\Clippy Vision\` |

---

## Uninstall

- **Settings → Apps → Clippy Vision → Uninstall**, or
- Run the uninstaller from `%LOCALAPPDATA%\Programs\Clippy Vision\`

To remove all data: delete `%APPDATA%\Clippy Vision\`  
To remove Ollama models: delete `%USERPROFILE%\.ollama\`
