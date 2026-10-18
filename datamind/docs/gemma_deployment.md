# Google Gemma Deployment & Configuration Guide

DataMind utilizes **Google Gemma** as its reasoning engine for SQL generation, query auto-repair, and factual explanation synthesis. This guide details how to install, configure, and serve Gemma locally using **Ollama**.

---

## 1. Supported Gemma Models

| Model Name | Ollama Identifier | Memory Requirements | Primary Use Case |
|---|---|---|---|
| **Gemma 3n E4B** *(Default)* | `gemma3n:e4b` | ~4.5 GB RAM / VRAM | High-accuracy SQL generation & multi-table joins |
| **Gemma 3n E2B** | `gemma3n:e2b` | ~2.5 GB RAM / VRAM | Ultra-lightweight edge execution |
| **Gemma 2 2B** | `gemma2:2b` | ~2.0 GB RAM / VRAM | Rapid local testing on low-resource machines |
| **Gemma 2 9B** | `gemma2:9b` | ~8.0 GB RAM / VRAM | Enhanced reasoning for complex nested CTEs |

---

## 2. Installation & Setup

### Step 1: Install Ollama
Download and install Ollama for your operating system:
- **Windows**: Download installer from [ollama.com/download/windows](https://ollama.com/download/windows)
- **macOS**: Download `.dmg` from [ollama.com/download/mac](https://ollama.com/download/mac)
- **Linux**: Run the one-line install script:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

### Step 2: Download the Gemma Model
Open your terminal / PowerShell and pull the desired Gemma checkpoint:
```bash
ollama pull gemma3n:e4b
```
*(If your system has limited RAM, you can pull `ollama pull gemma2:2b` instead).*

### Step 3: Verify the Ollama Service
Ensure Ollama is running and accessible on `http://localhost:11434`:
```bash
# In terminal / command prompt
ollama list
```
You should see `gemma3n:e4b` listed under installed models.

---

## 3. DataMind Configuration

DataMind automatically connects to the Ollama endpoint via environment variables in `.env`:

```env
# Ollama / Gemma Endpoint
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=gemma3n:e4b
```

If you pull an alternative variant like `gemma2:2b`, simply update `OLLAMA_MODEL=gemma2:2b` in your `.env` file. No code changes are required.

---

## 4. Testing Gemma Connectivity

You can test model inference using a simple PowerShell / curl call:

```powershell
# PowerShell Test
Invoke-RestMethod -Uri "http://localhost:11434/api/chat" -Method Post -ContentType "application/json" -Body '{"model": "gemma3n:e4b", "stream": false, "messages": [{"role": "user", "content": "Return JSON: {\"test\": \"ok\"}"}]}'
```

Or using Python:
```python
from datamind.gemma_client import ask_json

response = ask_json("You are an assistant.", "Return JSON with status: ok")
print(response)
```

---

## 5. Offline Simulation / Demo Mode

If you are developing or evaluating DataMind in an environment where Ollama cannot be installed immediately, enable simulation mode:
```env
DATAMIND_DEMO_MODE=true
```
When enabled, DataMind activates a built-in mock inference provider that allows the full Streamlit UI, tabs, query flow, and validation pipeline to be demonstrated without live inference.

When Snowflake credentials are absent, database execution also switches to simulation. The UI labels these responses and rows as simulated; they are placeholders, not Snowflake results, and numeric checks against them are not evidence about the real dataset. The demo SQL generator uses the selected dataset's configured table whitelist, and the same AST validator still runs before any execution.
