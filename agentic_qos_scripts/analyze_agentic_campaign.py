#!/usr/bin/env python3
import csv
import json
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev

EXP_DIR = Path.home() / "agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime"
OUT_DIR = EXP_DIR / "analysis_ready_campaign"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return 0.0

def safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return 0

def summarize_values(values):
    values = [float(v) for v in values]
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "mean": mean(values),
        "std": stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }

def count_oscillations(decisions):
    by_phase = defaultdict(list)
    for d in decisions:
        by_phase[d["phase"]].append(d)

    out = {}
    for phase, rows in by_phase.items():
        seq = [tuple(d.get("new_mbr_kbps", [])) for d in rows]
        osc = 0
        for i in range(2, len(seq)):
            if seq[i] == seq[i - 2] and seq[i] != seq[i - 1]:
                osc += 1
        out[phase] = osc
    return out

run_rows = []
phase_rows_all = []

for run_dir in sorted(EXP_DIR.glob("run_*")):
    if not run_dir.is_dir():
        continue

    run_name = run_dir.name
    decisions = read_jsonl(run_dir / "controller" / "decisions.jsonl")
    telemetry = read_jsonl(run_dir / "controller" / "telemetry_windows.jsonl")
    phase_rows = read_csv(run_dir / "analysis_ready" / "agentic_phase_summary.csv")

    if not decisions or not telemetry or not phase_rows:
        run_rows.append({
            "run": run_name,
            "status": "INCOMPLETE",
            "windows": len(telemetry),
            "decisions": len(decisions),
            "actions": "",
            "fallbacks": "",
            "tool_failures": "",
            "oscillations_total": "",
            "mean_llm_latency_ms": "",
            "notes": "missing decisions, telemetry, or phase summary",
        })
        continue

    actions = sum(1 for d in decisions if d.get("old_mbr_kbps") != d.get("new_mbr_kbps"))
    fallbacks = sum(1 for d in decisions if d.get("fallback_used"))
    tool_failures = sum(
        1 for d in decisions
        if d.get("apply_result") and d["apply_result"].get("returncode") != 0
    )
    latencies = [d.get("decision_latency_ms") for d in decisions if d.get("decision_latency_ms") is not None]
    tokens = [d.get("total_tokens") for d in decisions if d.get("total_tokens") is not None]

    osc_by_phase = count_oscillations(decisions)
    osc_total = sum(osc_by_phase.values())

    pdr_fail = sum(safe_int(r.get("pdr_fail", 0)) for r in phase_rows)
    far_fail = sum(safe_int(r.get("far_fail", 0)) for r in phase_rows)
    bad_route = sum(safe_int(r.get("bad_route", 0)) for r in phase_rows)

    status = "OK"
    notes = []
    if tool_failures:
        status = "FAIL"
        notes.append("tool failures")
    if pdr_fail or far_fail or bad_route:
        status = "FAIL"
        notes.append("datapath failures")
    if fallbacks:
        status = "WARN" if status == "OK" else status
        notes.append(f"fallbacks={fallbacks}")
    if osc_total:
        status = "WARN" if status == "OK" else status
        notes.append(f"oscillations={osc_total}")

    run_rows.append({
        "run": run_name,
        "status": status,
        "windows": len(telemetry),
        "decisions": len(decisions),
        "actions": actions,
        "fallbacks": fallbacks,
        "tool_failures": tool_failures,
        "oscillations_total": osc_total,
        "oscillations_A": osc_by_phase.get("A", 0),
        "oscillations_B": osc_by_phase.get("B", 0),
        "oscillations_C": osc_by_phase.get("C", 0),
        "oscillations_D": osc_by_phase.get("D", 0),
        "mean_llm_latency_ms": mean(latencies) if latencies else 0.0,
        "mean_total_tokens": mean(tokens) if tokens else 0.0,
        "pdr_fail": pdr_fail,
        "far_fail": far_fail,
        "bad_route": bad_route,
        "notes": "; ".join(notes) if notes else "clean",
    })

    for r in phase_rows:
        rr = dict(r)
        rr["run"] = run_name
        phase_rows_all.append(rr)

run_csv = OUT_DIR / "agentic_runs_summary.csv"
with run_csv.open("w", newline="", encoding="utf-8") as f:
    fieldnames = list(run_rows[0].keys()) if run_rows else []
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(run_rows)

phase_csv = OUT_DIR / "agentic_phase_rows_all.csv"
with phase_csv.open("w", newline="", encoding="utf-8") as f:
    fieldnames = list(phase_rows_all[0].keys()) if phase_rows_all else []
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(phase_rows_all)

by_phase = defaultdict(list)
for r in phase_rows_all:
    by_phase[r["phase"]].append(r)

phase_agg_rows = []
for phase in ["A", "B", "C", "D"]:
    rows = by_phase.get(phase, [])
    if not rows:
        continue

    delivered = [safe_float(r.get("mean_delivered_mbps")) for r in rows]
    app_red = [safe_float(r.get("app_qer_meter_red_packets")) for r in rows]
    actions = [safe_float(r.get("action_count")) for r in rows]
    fallbacks = [safe_float(r.get("fallback_count")) for r in rows]
    lat = [safe_float(r.get("mean_decision_latency_ms")) for r in rows]

    phase_agg_rows.append({
        "phase": phase,
        "runs": len(rows),
        "delivered_mbps_mean": summarize_values(delivered)["mean"],
        "delivered_mbps_std": summarize_values(delivered)["std"],
        "app_qer_red_mean": summarize_values(app_red)["mean"],
        "app_qer_red_std": summarize_values(app_red)["std"],
        "actions_mean": summarize_values(actions)["mean"],
        "fallbacks_mean": summarize_values(fallbacks)["mean"],
        "llm_latency_ms_mean": summarize_values(lat)["mean"],
        "llm_latency_ms_std": summarize_values(lat)["std"],
        "pdr_fail_total": sum(safe_int(r.get("pdr_fail")) for r in rows),
        "far_fail_total": sum(safe_int(r.get("far_fail")) for r in rows),
        "bad_route_total": sum(safe_int(r.get("bad_route")) for r in rows),
    })

phase_agg_csv = OUT_DIR / "agentic_phase_aggregate.csv"
with phase_agg_csv.open("w", newline="", encoding="utf-8") as f:
    fieldnames = list(phase_agg_rows[0].keys()) if phase_agg_rows else []
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(phase_agg_rows)

ok = sum(1 for r in run_rows if r["status"] == "OK")
warn = sum(1 for r in run_rows if r["status"] == "WARN")
fail = sum(1 for r in run_rows if r["status"] == "FAIL")
incomplete = sum(1 for r in run_rows if r["status"] == "INCOMPLETE")

md = []
md.append("# Agentic RTX6000 campaign summary")
md.append("")
md.append(f"Experiment directory `{EXP_DIR}`")
md.append("")
md.append(f"Runs found `{len(run_rows)}`")
md.append(f"OK `{ok}`")
md.append(f"WARN `{warn}`")
md.append(f"FAIL `{fail}`")
md.append(f"INCOMPLETE `{incomplete}`")
md.append("")
md.append("## Run summary")
md.append("")
md.append("| run | status | windows | decisions | actions | fallbacks | tool failures | oscillations | mean LLM latency ms | notes |")
md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
for r in run_rows:
    md.append(
        f"| {r['run']} | {r['status']} | {r['windows']} | {r['decisions']} | "
        f"{r['actions']} | {r['fallbacks']} | {r['tool_failures']} | "
        f"{r['oscillations_total']} | {float(r['mean_llm_latency_ms']):.2f} | {r['notes']} |"
    )

md.append("")
md.append("## Phase aggregate")
md.append("")
md.append("| phase | runs | delivered Mbps mean | delivered Mbps std | app QER red mean | actions mean | fallbacks mean | LLM latency mean ms |")
md.append("|---|---:|---:|---:|---:|---:|---:|---:|")
for r in phase_agg_rows:
    md.append(
        f"| {r['phase']} | {r['runs']} | {r['delivered_mbps_mean']:.2f} | "
        f"{r['delivered_mbps_std']:.2f} | {r['app_qer_red_mean']:.2f} | "
        f"{r['actions_mean']:.2f} | {r['fallbacks_mean']:.2f} | "
        f"{r['llm_latency_ms_mean']:.2f} |"
    )

report = OUT_DIR / "agentic_campaign_report.md"
report.write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"Runs found: {len(run_rows)}")
print(f"OK={ok} WARN={warn} FAIL={fail} INCOMPLETE={incomplete}")
print(f"CSV runs: {run_csv}")
print(f"CSV phases: {phase_csv}")
print(f"CSV aggregate: {phase_agg_csv}")
print(f"Report: {report}")
