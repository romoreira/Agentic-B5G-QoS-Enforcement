#!/usr/bin/env python3
import json
import re
import time
import urllib.request
import urllib.error

VLLM_BASE_URL = "http://127.0.0.1:18000/v1"
MODEL = "Qwen/Qwen2.5-7B-Instruct"

def extract_json(text: str):
    text = text.strip()

    # Accept markdown fenced JSON.
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()

    # Accept extra text around a JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": (
                "You are a network QoS controller. "
                "Return only a JSON object. "
                "Do not use markdown. "
                "Do not wrap the response in code fences."
            ),
        },
        {
            "role": "user",
            "content": (
                "Given a stable network state, return this schema exactly, "
                "{\"action\":\"keep\",\"mbr_kbps\":[200000,200000,150000,150000,100000],"
                "\"reason\":\"short reason\"}"
            ),
        },
    ],
    "temperature": 0,
    "max_tokens": 120,
}

req = urllib.request.Request(
    f"{VLLM_BASE_URL}/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

t0 = time.time()

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
except urllib.error.URLError as e:
    raise SystemExit(f"LLM request failed: {e}")

latency_ms = (time.time() - t0) * 1000.0

data = json.loads(raw)
content = data["choices"][0]["message"]["content"]
parsed = extract_json(content)

required = ["action", "mbr_kbps", "reason"]
missing = [k for k in required if k not in parsed]
if missing:
    raise SystemExit(f"Missing keys: {missing}. Parsed: {parsed}")

if len(parsed["mbr_kbps"]) != 5:
    raise SystemExit(f"mbr_kbps must have 5 values. Parsed: {parsed}")

if sum(parsed["mbr_kbps"]) > 800000:
    raise SystemExit(f"capacity constraint violated. Parsed: {parsed}")

print("LLM ping OK")
print(f"latency_ms={latency_ms:.2f}")
print(f"raw_content={content}")
print(f"parsed_json={json.dumps(parsed, indent=2)}")

usage = data.get("usage", {})
print(f"prompt_tokens={usage.get('prompt_tokens')}")
print(f"completion_tokens={usage.get('completion_tokens')}")
print(f"total_tokens={usage.get('total_tokens')}")
