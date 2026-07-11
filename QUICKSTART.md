# Quick Start Guide - Clippy Vision

## Installation (Windows)

### Method 1: Automated Setup (Recommended)

1. **Clone the repository:**
   ```powershell
   git clone https://github.com/yourusername/clippy-vision.git
   cd clippy-vision
   ```

2. **Run the setup script:**
   
   **Option A - PowerShell (recommended):**
   ```powershell
   .\setup.ps1
   ```
   
   **Option B - If PowerShell fails (execution policy issues):**
   ```cmd
   setup.bat
   ```

The script will automatically:
- Verify Python 3.8+ installation
- Install/check Ollama
- Install Python dependencies
- Download required AI models (qwen2.5:3b, qwen2-vl:2b, nomic-embed-text)
- Create necessary directories
- Run connectivity tests

**Note:** Model downloads are large (~8 GB total) and may take 15-45 minutes depending on your connection.

### Method 2: Manual Setup

If the automated script fails, follow these steps:

#### 1. Install Python 3.8+
Download from [python.org](https://www.python.org/downloads/) and ensure "Add Python to PATH" is checked.

#### 2. Install Ollama
Download and install from [ollama.com/download](https://ollama.com/download)

#### 3. Start Ollama service
```powershell
ollama serve
```

#### 4. Pull required models
```powershell
ollama pull qwen3:8b
ollama pull qwen3-vl:4b
ollama pull nomic-embed-text
```

#### 5. Install Python dependencies
```powershell
pip install -r requirements.txt
```

#### 6. Create directories
```powershell
mkdir -p core/data core/screenshots logs
```

---

## Running Clippy Vision

### 1. Start the Capture Daemon
This runs in the background and captures your screen activity:

```powershell
python core\screen_capture.py
```

**What it does:**
- Monitors active windows, clipboard, and typing patterns
- Takes adaptive screenshots during activity
- Classifies events through the 3-tier pipeline
- Stores interesting events in the SQLite database

Leave this running in the background.

### 2. Chat with Clippy (New Terminal)
In a **new terminal window**, start the interactive agent:

```powershell
python agent\react_agent.py
```

**Example queries:**
- "What have I been working on today?"
- "What articles did I read in the last 2 hours?"
- "Summarize my activity from 2 PM to 4 PM"
- "What bugs was I debugging yesterday?"
- "Remember that I prefer Python over JavaScript"

### 3. (Optional) Run the MCP Server
For integration with Cursor or other MCP clients:

```powershell
python mcp_server.py
```

---

## Verify It's Working

### Check the database
```powershell
python -c "from core.storage import conn; print(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0], 'events captured')"
```

### Check screenshots folder
```powershell
dir core\screenshots
```

### Check Ollama models
```powershell
ollama list
```

You should see:
- qwen3:8b
- qwen3-vl:4b
- nomic-embed-text

---

## Troubleshooting

### "Ollama not found" or connection errors
- Make sure Ollama is running: `ollama serve`
- Restart your terminal after installing Ollama
- Check if Ollama is in PATH: `ollama --version`

### "Python not found"
- Reinstall Python and check "Add Python to PATH"
- Restart terminal after installation
- Verify: `python --version`

### Models downloading slowly
- Models are large (qwen3:8b is ~4.7GB, qwen3-vl:4b is ~2.9GB)
- This is normal on slower connections
- You can continue using Clippy while models download in the background

### Import errors (pywin32, etc.)
```powershell
pip install --force-reinstall -r requirements.txt
```

### Database locked errors
- Close all Python processes using the database
- Delete `core\data\events.db-wal` and `core\data\events.db-shm` if they exist
- Restart the capture daemon

### Screenshots not being captured
- Ensure `core\screenshots` directory exists
- Check if you have sufficient disk space
- Verify the capture daemon is running

---

## File Locations

| Item | Location |
|------|----------|
| Database | `core\data\events.db` |
| Screenshots | `core\screenshots\` |
| Ollama models | `C:\Users\<YourUsername>\.ollama\models` |
| Logs | `logs\` |

---

## Performance Tips

1. **Disk space:** Screenshots accumulate over time. Clean old ones periodically.
2. **CPU usage:** The vision model is compute-intensive. It processes screenshots in batches every 10 seconds.
3. **Battery:** On laptops, consider pausing the capture daemon when on battery to save power.

---

## Next Steps

- Read the [full README](README.md) for architecture details
- Customize classification thresholds in `classifier/tier_one_classifier.py`
- Adjust typing baseline sensitivity in `core/baseline.py`
- Explore the database schema in `core/storage.py`

---

## Stopping Clippy Vision

1. Press `Ctrl+C` in the terminal running `screen_capture.py`
2. Press `Ctrl+C` in the terminal running `react_agent.py` (if active)
3. (Optional) Stop Ollama: `taskkill /IM ollama.exe /F`

---

## Uninstall

1. Delete the project folder
2. (Optional) Uninstall Ollama from Windows Settings > Apps
3. (Optional) Remove models: Delete `C:\Users\<YourUsername>\.ollama\`

---

## Need Help?

- Open an issue on GitHub
- Check the [README](README.md) for architecture details
- Review the troubleshooting section above
