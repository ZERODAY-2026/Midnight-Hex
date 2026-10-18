"""DataMind: Gemma LLM client for Ollama with structured JSON output."""

import json
import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "gemma3n:e4b"


def clean_json_text(raw_text: str) -> str:
    """Strip markdown code fences and extraneous leading/trailing whitespace."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    # If still not valid, try finding the outermost {...}
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def ask_json(
    system: str,
    user: str,
    timeout: int = 120,
    demo_mode: bool | None = None,
) -> dict:
    """
    Send system and user prompts to Gemma via Ollama and parse JSON response.
    Temperature is set to 0 for deterministic, factual outputs.
    """
    ollama_url = os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    if demo_mode is None:
        demo_mode = os.environ.get("DATAMIND_DEMO_MODE", "false").lower() in ("true", "1", "yes")

    if demo_mode:
        return _mock_gemma_response(system, user)

    try:
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        resp = requests.post(ollama_url, json=payload, timeout=timeout)
        resp.raise_for_status()

        content = resp.json().get("message", {}).get("content", "{}")
        cleaned = clean_json_text(content)
        return json.loads(cleaned)

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Could not connect to Ollama at {ollama_url}. "
            "Please ensure Ollama is running (`ollama serve`) and model is downloaded (`ollama pull gemma3n:e4b`), "
            "or set DATAMIND_DEMO_MODE=true in .env for simulated testing."
        )
    except Exception as e:
        # Re-raise or provide detailed context
        raise RuntimeError(f"Gemma inference error via Ollama: {e}")


def _mock_gemma_response(system: str, user: str) -> dict:
    """Simulated responses for testing or demo without active local Ollama instance."""
    u_lower = user.lower()

    if "explain" in system.lower():
        return {
            "answer": "This is a simulated summary; no Snowflake data was queried.",
            "how": "The displayed rows are placeholders from demo execution."
        }

    tables = re.findall(r"(?m)^Table:\s*([A-Z0-9_]+)\s*$", system)
    mentioned_table = next(
        (
            table
            for table in tables
            if re.search(rf"\b{re.escape(table.lower())}\b", u_lower)
            or (
                table.lower().endswith("s")
                and re.search(rf"\b{re.escape(table[:-1].lower())}\b", u_lower)
            )
        ),
        None,
    )
    target_table = mentioned_table or (tables[0] if len(tables) == 1 else None)
    if target_table:
        return {
            "status": "ok",
            "sql": f"SELECT * FROM {target_table} LIMIT 10",
            "assumptions": [],
        }

    if "weather" in u_lower or "unsupported" in u_lower:
        return {
            "status": "unsupported",
            "message": "This request is not supported by the available data."
        }

    return {
        "status": "clarify",
        "clarification": "Please specify which table in the selected dataset you want to query.",
    }
