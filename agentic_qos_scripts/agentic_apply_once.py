#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

VLLM_BASE_URL = "http://127.0.0.1:18000/v1"
VLLM_MODEL = "Qwen/Qwen2.5-7B-Instruct"

CAPACITY_LIMIT_KBPS = 800000
INITIAL_MBR_KBPS = [200000, 200000, 150000, 150000, 100000]

LOG_DIR = Path.home() / "agentic_qos_results" / "agentic_smoke"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DECISIONS_FILE = LOG_DIR / "decisions.jsonl"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def extract_json(text):
    text = text.strip()

    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return json.loads(text)


def validate_mbr_vector(mbr):
    if not isinstance(mbr, list):
        raise ValueError("mbr_kbps must be a list")

    if len(mbr) != 5:
        raise ValueError("mbr_kbps must have exactly five values")

    if not all(isinstance(x, int) for x in mbr):
        raise ValueError("all MBR values must be integers")

    if not all(x > 0 for x in mbr):
        raise ValueError("all MBR values must be positive")

    if not all(x % 10000 == 0 for x in mbr):
        raise ValueError("all MBR values must be multiples of 10000 kbps")

    if sum(mbr) > CAPACITY_LIMIT_KBPS:
        raise ValueError(f"capacity violated, sum={sum(mbr)} > {CAPACITY_LIMIT_KBPS}")

    return True


def call_llm(phase):
    if phase == "B":
        violated_slices = ["S5"]
        allowed_change_slices = ["S5"]
        candidate_mbr_vectors = [
            INITIAL_MBR_KBPS,
            [200000, 200000, 150000, 150000, 70000],
            [200000, 200000, 150000, 150000, 60000],
            [200000, 200000, 150000, 150000, 50000]
        ]
    elif phase == "C":
        violated_slices = ["S3", "S4"]
        allowed_change_slices = ["S3", "S4"]
        candidate_mbr_vectors = [
            INITIAL_MBR_KBPS,
            [200000, 200000, 120000, 120000, 100000],
            [200000, 200000, 110000, 110000, 100000],
            [200000, 200000, 100000, 100000, 100000]
        ]
    else:
        violated_slices = []
        allowed_change_slices = []
        candidate_mbr_vectors = [INITIAL_MBR_KBPS]

    telemetry = {
        "phase": phase,
        "capacity_limit_kbps": CAPACITY_LIMIT_KBPS,
        "current_mbr_kbps": INITIAL_MBR_KBPS,
        "slice_order": ["S1", "S2", "S3", "S4", "S5"],
        "violated_slices": violated_slices,
        "allowed_change_slices": allowed_change_slices,
        "candidate_mbr_vectors": candidate_mbr_vectors,
        "slices": [
            {
                "slice": "S1",
                "tier": "Gold",
                "teid": 1,
                "loss_rate": 0.000,
                "delivered_mbps": 160,
                "sla_loss_max": 0.001
            },
            {
                "slice": "S2",
                "tier": "Gold",
                "teid": 11,
                "loss_rate": 0.000,
                "delivered_mbps": 160,
                "sla_loss_max": 0.001
            },
            {
                "slice": "S3",
                "tier": "Silver",
                "teid": 21,
                "loss_rate": 0.002,
                "delivered_mbps": 120,
                "sla_loss_max": 0.010
            },
            {
                "slice": "S4",
                "tier": "Silver",
                "teid": 31,
                "loss_rate": 0.002,
                "delivered_mbps": 120,
                "sla_loss_max": 0.010
            },
            {
                "slice": "S5",
                "tier": "Bronze",
                "teid": 41,
                "loss_rate": 0.220,
                "delivered_mbps": 80,
                "sla_loss_max": 0.050
            }
        ]
    }

    payload = {
        "model": VLLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a B5G UPF QoS controller. "
                    "Protect Gold slices first, then Silver, then Bronze. "
                    "A slice violates its SLA when loss_rate is greater than sla_loss_max. "
                    "Never say that SLA is met when any slice has loss_rate greater than sla_loss_max. "
                    "If phase is B and S5 violates its SLA, reduce only S5 MBR by at least 30000 kbps. "
                    "In phase B, never reduce S1, S2, S3, or S4. "
                    "If phase is C and S3 or S4 violates SLA, adjust Silver slices while preserving Gold. "
                    "If the proposed mbr_kbps is identical to current_mbr_kbps, action must be keep. "
                    "If action is modify_mbr, the proposed mbr_kbps must differ from current_mbr_kbps. "
                    "The sum of mbr_kbps must be less than or equal to 800000. "
                    "Use five integers ordered as S1, S2, S3, S4, S5. "
                    "Use multiples of 10000 kbps only. "
                    "Return only valid JSON, no markdown."
                )
            },
            {
                "role": "user",
                "content": (
                    "Given the telemetry, decide the next QoS action. "
                    "Use violated_slices as the authoritative list of SLA violations. "
                    "Do not infer additional SLA violations. "
                    "You must choose mbr_kbps from candidate_mbr_vectors exactly. "
                    "Do not invent another vector. "
                    "If you choose the current_mbr_kbps, action must be keep. "
                    "If you choose a different vector, action must be modify_mbr. "
                    "Return exactly this JSON schema. "
                    "{\"action\":\"keep or modify_mbr\","
                    "\"mbr_kbps\":[int,int,int,int,int],"
                    "\"reason\":\"short reason\","
                    "\"expected_effect\":\"short expected effect\"}. "
                    f"Telemetry is {json.dumps(telemetry)}"
                )
            }
        ],
        "temperature": 0,
        "max_tokens": 300
    }

    t0 = time.time()
    response = requests.post(
        f"{VLLM_BASE_URL}/chat/completions",
        json=payload,
        timeout=60
    )
    latency_ms = (time.time() - t0) * 1000.0
    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]
    parsed = extract_json(content)
    usage = data.get("usage", {})

    return parsed, content, latency_ms, usage


def apply_mbr(mbr):
    mbr_csv = ",".join(str(x) for x in mbr)

    cmd = [
        "sudo", "docker", "exec", "pfcpsim",
        "pfcpctl", "-s", "localhost:12345",
        "session", "modify",
        "--count", "5",
        "--baseID", "1",
        "--app-filter", "udp:any:any:allow:100",
        "--app-mbr-uplink", mbr_csv,
        "--app-mbr-downlink", mbr_csv
    ]

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False
    )

    return {
        "cmd": " ".join(cmd),
        "returncode": result.returncode,
        "output": result.stdout
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="B")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset:
        mbr = INITIAL_MBR_KBPS
        validate_mbr_vector(mbr)
        apply_result = apply_mbr(mbr)
        print(json.dumps(apply_result, indent=2))
        if apply_result["returncode"] != 0:
            raise SystemExit(1)
        print("Reset applied")
        return

    parsed, raw_content, latency_ms, usage = call_llm(args.phase)

    action = parsed.get("action")
    mbr = parsed.get("mbr_kbps")

    if action not in ["keep", "modify_mbr"]:
        raise SystemExit(f"Invalid action: {parsed}")

    validate_mbr_vector(mbr)

    if action == "modify_mbr" and mbr == INITIAL_MBR_KBPS:
        raise SystemExit(
            f"Invalid decision: action is modify_mbr but mbr_kbps equals current vector. Parsed={parsed}"
        )

    # Policy guard for the synthetic smoke test.
    # In phase B, only S5 is overloaded, so Gold and Silver caps must be preserved.
    if args.phase == "B":
        expected_prefix = INITIAL_MBR_KBPS[:4]
        valid_candidates = [
            INITIAL_MBR_KBPS,
            [200000, 200000, 150000, 150000, 70000],
            [200000, 200000, 150000, 150000, 60000],
            [200000, 200000, 150000, 150000, 50000]
        ]
        if mbr[:4] != expected_prefix:
            raise SystemExit(
                "Invalid phase B decision: only S5 may be changed. "
                f"Expected S1-S4={expected_prefix}, got={mbr[:4]}. Parsed={parsed}"
            )
        if mbr not in valid_candidates:
            raise SystemExit(
                f"Invalid phase B decision: MBR vector is not a valid candidate. Parsed={parsed}"
            )

    # In phase C, Silver may be adjusted, but Gold must be preserved.
    if args.phase == "C":
        expected_gold = INITIAL_MBR_KBPS[:2]
        if mbr[:2] != expected_gold:
            raise SystemExit(
                "Invalid phase C decision: Gold slices must be preserved. "
                f"Expected S1-S2={expected_gold}, got={mbr[:2]}. Parsed={parsed}"
            )

    apply_result = None
    if not args.dry_run:
        apply_result = apply_mbr(mbr)
        if apply_result["returncode"] != 0:
            raise SystemExit(f"pfcpsim modify failed: {apply_result}")

    record = {
        "timestamp_utc": now_utc(),
        "phase": args.phase,
        "model": VLLM_MODEL,
        "raw_content": raw_content,
        "parsed": parsed,
        "decision_latency_ms": latency_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "dry_run": args.dry_run,
        "apply_result": apply_result
    }

    with DECISIONS_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")

    print("Agentic decision OK")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
