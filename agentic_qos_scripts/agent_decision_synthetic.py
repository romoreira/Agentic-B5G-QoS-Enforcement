#!/usr/bin/env python3
import json
import re
import time
import urllib.request

VLLM_BASE_URL = "http://127.0.0.1:18000/v1"
MODEL = "Qwen/Qwen2.5-7B-Instruct"

INITIAL_MBR = [200000, 200000, 150000, 150000, 100000]
CAPACITY_LIMIT = 800000

def extract_json(text: str):
    text = text.strip()
    m = re.search(r"```(?:json)?\\s*(.*?)\\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)

telemetry = {
    "phase": "B",
    "description": "Bronze slice S5 is overloaded. Gold and Silver slices are stable.",
    "capacity_limit_kbps": CAPACITY_LIMIT,
    "current_mbr_kbps": INITIAL_MBR,
    "slices": [
        {"slice": "S1", "tier": "Gold", "teid": 1, "loss_rate": 0.000, "delivered_mbps": 160, "sla_loss_max": 0.001},
        {"slice": "S2", "tier": "Gold", "teid": 11, "loss_rate": 0.000, "delivered_mbps": 160, "sla_loss_max": 0.001},
        {"slice": "S3", "tier": "Silver", "teid": 21, "loss_rate": 0.002, "delivered_mbps": 120, "sla_loss_max": 0.010},
        {"slice": "S4", "tier": "Silver", "teid": 31, "loss_rate": 0.002, "delivered_mbps": 120, "sla_loss_max": 0.010},
        {"slice": "S5", "tier": "Bronze", "teid": 41, "loss_rate": 0.220, "delivered_mbps": 80, "sla_loss_max": 0.050}
    ]
}

schema = {
    "action": "keep or modify_mbr",
    "mbr_kbps": "array of exactly five integers ordered as S1,S2,S3,S4,S5",
    "reason": "short explanation",
    "expected_effect": "short explanation"
}

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": (
                "You are a B5G UPF QoS controller. "
                "You must protect Gold slices first, then Silver, then Bronze. "
                "The sum of mbr_kbps must be <= 800000. "
                "Use only these MBR values per slice step: multiples of 10000 kbps. "
                "Return only valid JSON. Do not use markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                "Decide the next MBR vector based on the telemetry. "
                f"Required schema: {json.dumps(schema)}. "
                f"Telemetry: {json.dumps(telemetry)}"
            ),
        },
    ],
    "temperature": 0,
    "max_tokens": 220,
}

req = urllib.request.Request(
    f"{VLLM_BASE_URL}/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

t0 = time.time()
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))
latency_ms = (time.time() - t0) * 1000

content = data["choices"][0]["message"]["content"]
parsed = extract_json(content)

if parsed.get("action") not in ["keep", "modify_mbr"]:
    raise SystemExit(f"Invalid action: {parsed}")

mbr = parsed.get("mbr_kbps")
if not isinstance(mbr, list) or len(mbr) != 5:
    raise SystemExit(f"Invalid mbr_kbps: {parsed}")

if not all(isinstance(x, int) for x in mbr):
    raise SystemExit(f"MBR values must be integers: {parsed}")

if sum(mbr) > CAPACITY_LIMIT:
    raise SystemExit(f"Capacity violation: sum={sum(mbr)} parsed={parsed}")

if any(x % 10000 != 0 for x in mbr):
    raise SystemExit(f"MBR values must be multiples of 10000: {parsed}")

print("Synthetic decision OK")
print(f"latency_ms={latency_ms:.2f}")
print(f"raw_content={content}")
print(f"parsed_json={json.dumps(parsed, indent=2)}")
print(f"sum_mbr_kbps={sum(mbr)}")

usage = data.get("usage", {})
print(f"prompt_tokens={usage.get('prompt_tokens')}")
print(f"completion_tokens={usage.get('completion_tokens')}")
print(f"total_tokens={usage.get('total_tokens')}")
