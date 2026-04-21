import json
import os
import re
import urllib.error
import urllib.request


OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
SITE_URL = os.getenv("YOUR_SITE_URL")
SITE_NAME = os.getenv("YOUR_SITE_NAME")

MODELS = [
    "openchat/openchat-7b",
    "mistralai/mistral-7b-instruct",
    "gryphe/mythomax-l2-13b",
]


def _headers():
    headers = {
        "Content-Type": "application/json",
    }
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
    if SITE_URL:
        headers["HTTP-Referer"] = SITE_URL
    if SITE_NAME:
        headers["X-OpenRouter-Title"] = SITE_NAME
    return headers


def call_ai(prompt, max_tokens=250):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("Missing OpenRouter API key.")

    last_error = None
    for model in MODELS:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=_headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(f"All models failed: {last_error}")


def generate_question(role, previous_questions=None):
    previous_questions = previous_questions or []
    previous_block = "\n".join(f"- {question}" for question in previous_questions[-5:])
    return f"""
Ask ONE realistic technical interview question for a {role}.
Keep it short. Do not include the answer.
Avoid repeating these previous questions:
{previous_block or '- None'}
"""


def evaluate_answer(role, question, answer):
    return f"""
Evaluate this answer for a {role} interview.

Question: {question}
Answer: {answer}

Return ONLY in this format:
Score: X/10
Feedback: short explanation
"""


def extract_score(text):
    match = re.search(r"(\d+)/10", text)
    if match:
        return int(match.group(1))
    return 0
