
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ASSISTANT_NAME = "VAYU"
IST = ZoneInfo("Asia/Kolkata")

# PC proxy URL and secret are configured in Render environment variables.
OLLAMA_PROXY_URL = os.getenv("OLLAMA_PROXY_URL", "").strip().rstrip("/")
OLLAMA_PROXY_TOKEN = os.getenv("OLLAMA_PROXY_TOKEN", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b").strip()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "instagram": "https://www.instagram.com",
    "spotify": "https://open.spotify.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "poki": "https://poki.com",
}


def normalize(text):
    return " ".join(str(text or "").lower().strip().split())


def ask_ollama(question, user_name):
    if not OLLAMA_PROXY_URL or not OLLAMA_PROXY_TOKEN:
        raise RuntimeError("Ollama proxy is not configured.")

    prompt = (
        f"You are {ASSISTANT_NAME}, a helpful personal voice assistant. "
        f"The user's name is {user_name}. "
        "Answer naturally and concisely in 1 to 3 short sentences. "
        "Do not show internal reasoning. "
        "Reply in the language used by the user.\n\n"
        f"User: {question}"
    )

    response = requests.post(
        OLLAMA_PROXY_URL,
        headers={"Authorization": f"Bearer {OLLAMA_PROXY_TOKEN}"},
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "num_predict": 120,
                "temperature": 0.5,
            },
        },
        timeout=(8, 180),
    )
    response.raise_for_status()
    data = response.json()
    answer = str(data.get("response", "")).strip()

    if not answer:
        raise RuntimeError("Ollama returned an empty answer.")

    return answer


def ask_gemini(question, user_name):
    if not GEMINI_API_KEY:
        return (
            "VAYU AI is not connected yet. "
            "Configure the Ollama proxy on Render first."
        )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )

    prompt = (
        f"You are {ASSISTANT_NAME}, a concise personal assistant. "
        f"The user's name is {user_name}. "
        "Answer in 1 to 3 short sentences.\n\n"
        f"User: {question}"
    )

    response = requests.post(
        url,
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.5,
                "maxOutputTokens": 160,
            },
        },
        timeout=(8, 30),
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []

    if not candidates:
        return "I couldn't create an answer just now."

    parts = candidates[0].get("content", {}).get("parts", [])
    return " ".join(
        part.get("text", "")
        for part in parts
        if part.get("text")
    ).strip() or "I couldn't create an answer just now."


@app.get("/")
def home():
    configured = bool(
        (OLLAMA_PROXY_URL and OLLAMA_PROXY_TOKEN)
        or GEMINI_API_KEY
    )
    provider = (
        "ollama"
        if OLLAMA_PROXY_URL and OLLAMA_PROXY_TOKEN
        else "gemini" if GEMINI_API_KEY else None
    )

    return jsonify({
        "assistant": ASSISTANT_NAME,
        "status": "online",
        "ai_configured": configured,
        "ai_provider": provider,
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "assistant": ASSISTANT_NAME})


@app.post("/command")
def command():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "Send a valid JSON object."
        }), 400

    user_command = str(data.get("command", "")).strip()
    user_name = str(data.get("name", "")).strip() or "User"

    if not user_command:
        return jsonify({
            "success": False,
            "error": "No command received."
        }), 400

    text = normalize(user_command)
    if text.startswith("please "):
        text = text[7:].strip()

    action = "none"
    target = ""
    response_text = ""

    time_phrases = {
        "time", "what time is it", "what is the time",
        "what's the time", "tell me the time",
        "current time", "tell me current time",
    }
    date_phrases = {
        "date", "what is the date", "what's the date",
        "what is today's date", "tell me today's date",
        "today's date",
    }

    if text in time_phrases:
        response_text = (
            "The time is "
            + datetime.now(IST).strftime("%I:%M %p").lstrip("0")
        )

    elif text in date_phrases:
        response_text = (
            "Today's date is "
            + datetime.now(IST).strftime("%d %B %Y")
        )

    elif text.startswith("search "):
        query = user_command.strip()[7:].strip()
        if query:
            action = "open_url"
            target = "https://www.google.com/search?q=" + quote_plus(query)
            response_text = f"Searching for {query}"
        else:
            response_text = "What should I search for?"

    elif text.startswith("open "):
        target_name = text[5:].strip()
        if target_name in WEBSITES:
            action = "open_url"
            target = WEBSITES[target_name]
            response_text = f"Opening {target_name.title()}"
        elif target_name.startswith(("http://", "https://")):
            action = "open_url"
            target = target_name
            response_text = f"Opening {target_name}"
        else:
            action = "open_url"
            target = (
                "https://www.google.com/search?q="
                + quote_plus(target_name)
            )
            response_text = f"Searching for {target_name}"

    else:
        try:
            if OLLAMA_PROXY_URL and OLLAMA_PROXY_TOKEN:
                response_text = ask_ollama(user_command, user_name)
            else:
                response_text = ask_gemini(user_command, user_name)

        except requests.exceptions.Timeout:
            response_text = "The AI took too long to respond. Try again."

        except requests.exceptions.RequestException:
            app.logger.exception("AI request failed")
            response_text = "I couldn't connect to the AI. Check the PC and tunnel."

        except (ValueError, KeyError, TypeError, RuntimeError):
            app.logger.exception("AI response failed")
            response_text = "I couldn't process that AI response."

    return jsonify({
        "success": True,
        "assistant": ASSISTANT_NAME,
        "user": user_name,
        "command": user_command,
        "response": response_text,
        "action": action,
        "target": target,
        "running": True,
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
