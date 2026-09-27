"""
Sends the already-detected pattern + confirmation context to Gemini for a
plain-English explanation. The LLM never decides the pattern itself —
it only explains what the rule-based engine already found.
"""
import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)


def explain_pattern(symbol: str, pattern: str, bias: str, confidence_note: str) -> str:
    # Read API key inside the function so it picks up mid-session changes
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "(Set GEMINI_API_KEY in your environment to get an AI explanation here.)"

    prompt = (
        f"You are teaching a beginner Indian retail trader about candlestick patterns.\n"
        f"Stock: {symbol}\n"
        f"Detected pattern: {pattern} ({bias})\n"
        f"Rule-based confirmation notes: {confidence_note}\n\n"
        f"In 3-4 short sentences, explain what this pattern usually means and why the "
        f"confirmation notes make it stronger or weaker. Do not give a buy/sell instruction. "
        f"End with a one-line educational disclaimer."
    )

    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(
            GEMINI_URL.format(model=GEMINI_MODEL, key=api_key),
            headers={"Content-Type": "application/json"},
            data=json.dumps(body),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        # Guard against blocked / empty responses from Gemini safety filters
        candidates = data.get("candidates", [])
        if not candidates:
            block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
            logger.warning("Gemini blocked the response: %s", block_reason)
            return f"(Gemini blocked this request — reason: {block_reason})"

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or "text" not in parts[0]:
            return "(Gemini returned an empty response. Try again.)"

        return parts[0]["text"]

    except requests.exceptions.Timeout:
        return "(Gemini request timed out. Try again.)"
    except requests.exceptions.HTTPError as e:
        logger.error("Gemini API error: %s", e)
        return f"(Gemini API error: {e.response.status_code})"
    except Exception as e:
        logger.error("Unexpected error calling Gemini: %s", e)
        return f"(Error getting AI explanation: {e})"
