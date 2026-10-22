import os
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ASSISTANT_NAME = "VAYU"
IST = ZoneInfo("Asia/Kolkata")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

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


def ask_cloud_ai(question, user_name):
    if not GEMINI_API_KEY:
        return "Cloud AI is not configured yet. Add GEMINI_API_KEY in the hosting environment settings."

    prompt = (
        f"You are {ASSISTANT_NAME}, a concise, friendly personal voice assistant. "
        f"The user's name is {user_name}. Answer naturally in 1 to 3 short sentences "
        "unless the user asks for more detail. Do not repeat the question.\n\n"
        f"User: {question}"
    )
    response = requests.post(
        GEMINI_URL.format(model=GEMINI_MODEL),
        params={"key": GEMINI_API_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 160},
        },
        timeout=(8, 25),
    )
    if response.status_code == 429:
        return "The cloud AI is busy right now. Please try again shortly."
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return "I couldn't create an answer just now. Please try again."
    parts = candidates[0].get("content", {}).get("parts", [])
    answer = " ".join(p.get("text", "") for p in parts if p.get("text")).strip()
    return answer or "I couldn't create an answer just now. Please try again."


@app.get("/")
def home():
    return jsonify({"assistant": ASSISTANT_NAME, "status": "online", "ai_configured": bool(GEMINI_API_KEY)})


@app.get("/health")
def health():
    return jsonify({"status": "ok", "assistant": ASSISTANT_NAME})


@app.post("/command")
def command():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Send a valid JSON object."}), 400

    user_command = str(data.get("command", "")).strip()
    user_name = str(data.get("name", "")).strip() or "User"
    if not user_command:
        return jsonify({"success": False, "error": "No command received."}), 400

    text = normalize(user_command)
    if text.startswith("please "):
        text = text[7:].strip()

    action, target = "none", ""
    response_text = ""

    # Fast commands don't call the AI model.
    time_phrases = {
        "time", "what time is it", "what is the time", "what's the time",
        "tell me the time", "what is current time", "what's the current time",
        "current time", "tell me current time"
    }
    date_phrases = {
        "date", "what is the date", "what's the date", "what is today's date",
        "what's today's date", "tell me the date", "tell me today's date",
        "what is today date", "what's the date today", "today's date"
    }

    if text in time_phrases:
        response_text = "The time is " + datetime.now(IST).strftime("%I:%M %p").lstrip("0")
    elif text in date_phrases:
        response_text = "Today's date is " + datetime.now(IST).strftime("%d %B %Y")
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
            target = "https://www.google.com/search?q=" + quote_plus(target_name)
            response_text = f"Searching for {target_name}"
    else:
        try:
            response_text = ask_cloud_ai(user_command, user_name)
        except requests.exceptions.Timeout:
            response_text = "The cloud AI took too long to respond. Please try again."
        except requests.exceptions.RequestException:
            app.logger.exception("Cloud AI request failed")
            response_text = "I couldn't connect to the cloud AI. Please try again."
        except (ValueError, KeyError, TypeError):
            app.logger.exception("Invalid cloud AI response")
            response_text = "I received an unexpected response. Please try again."

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
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
