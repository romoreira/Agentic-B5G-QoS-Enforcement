#!/usr/bin/env python3
# build_combined_metrics.py
#
# Consolidates phase-level metrics across:
#   E1 Static, E2 Threshold, E3 Greedy   (baselines campaign)
#   E4  agentic (original)               (LLM realtime, no hysteresis)
#   E4b agentic (hysteresis)             (LLM realtime + monotonic candidates + derived action)
#
# Produces:
#   combined_baseline_agentic_phase_metrics.csv
#   combined_baseline_agentic_phase_metrics_summary.md
#
# If the E4b campaign directory does not exist yet, the script skips it gracefully.

import csv
import json
from pathlib import Path
from statistics import mean, stdev
from collections import defaultdict

BASELINE_ROOT = Path.home() / "agentic_qos_results/campaigns/campaign_20260509_baselines_5slices"
BASELINE_CSV  = BASELINE_ROOT / "analysis_ready/phase_summary.csv"

AGENTIC_E4_ROOT   = Path.home() / "agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices"
AGENTIC_E4_EXP    = AGENTIC_E4_ROOT / "e4_agentic_rtx6000_realtime"
AGENTIC_E4_CSV    = AGENTIC_E4_EXP / "analysis_ready_campaign/agentic_phase_rows_all.csv"

AGENTIC_E4B_ROOT  = Path.home() / "agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices"
AGENTIC_E4B_EXP   = AGENTIC_E4B_ROOT / "e4b_agentic_hysteresis_realtime"
AGENTIC_E4B_CSV   = AGENTIC_E4B_EXP / "analysis_ready_campaign/agentic_phase_rows_all.csv"

OUT_DIR = Path.home() / "agentic_qos_results/campaigns"
OUT_CSV = OUT_DIR / "combined_baseline_agentic_phase_metrics.csv"
OUT_MD  = OUT_DIR / "combined_baseline_agentic_phase_metrics_summary.md"


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_jsonl(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def fnum(x, default=0.0):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def inum(x, default=0):
    try:
        if x is None or x == "":
            return default
        return int(float(x))
    except Exception:
        return default


def policing_ratio(red, passed):
    red = fnum(red)
    passed = fnum(passed)
    denom = red + passed
    if denom <= 0:
        return 0.0
    return red / denom


def count_oscillations_by_phase(run_dir):
    """Oscillation = vector at window i equals vector at window i-2 but differs from i-1."""
    decisions = read_jsonl(run_dir / "controller/decisions.jsonl")
    by_phase = defaultdict(list)
    for d in decisions:
        phase = d.get("phase")
        if not phase:
            continue
        by_phase[phase].append(tuple(d.get("new_mbr_kbps", [])))
    out = {}
    for phase, seq in by_phase.items():
        osc = 0
        for i in range(2, len(seq)):
            if seq[i] == seq[i - 2] and seq[i] != seq[i - 1]:
                osc += 1
        out[phase] = osc
    return out


def count_schema_fallbacks_by_phase(run_dir):
    """Count fallbacks attributable to the legacy schema rule
    'modify_mbr requires a changed vector'. Useful to highlight that E4b
    eliminates this failure mode by design."""
    decisions = read_jsonl(run_dir / "controller/decisions.jsonl")
    out = defaultdict(int)
    for d in decisions:
        if not d.get("fallback_used"):
            continue
        err = (d.get("decision_error") or "").lower()
        if "modify_mbr requires a changed vector" in err:
            out[d.get("phase", "")] += 1
    return dict(out)


def get_agentic_run_info(exp_dir, run_name):
    p = exp_dir / run_name / "metadata/run_info.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def mean_std(values):
    values = [fnum(v) for v in values]
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return mean(values), stdev(values)


# ---------------------------------------------------------------------------
# Build rows
# ---------------------------------------------------------------------------
rows = []

# Baselines E1, E2, E3
for r in read_csv(BASELINE_CSV):
    rows.append({
        "experiment": r.get("experiment", ""),
        "controller_group": "baseline",
        "model": "",
        "gpu": "",
        "prefix_cache": "",
        "run": r.get("run", ""),
        "phase": r.get("phase", ""),
        "health_status": r.get("health_status", r.get("status", "")),
        "duration_s": r.get("elapsed_between_snapshots_s", ""),
        "windows": "",
        "offered_mbps": r.get("estimated_access_rx_mbps_expected_window", ""),
        "delivered_mbps": r.get("estimated_core_tx_mbps_expected_window", ""),
        "access_rx_packets": r.get("access_rx_packets_delta", ""),
        "core_tx_packets": r.get("core_tx_packets_delta", ""),
        "app_qer_red_packets": r.get("app_qer_meter_red_delta", ""),
        "policing_ratio": policing_ratio(
            r.get("app_qer_meter_red_delta", 0),
            r.get("app_qer_pass_delta", 0),
        ),
        "pdr_fail": r.get("pdr_fail_delta", ""),
        "far_fail": r.get("far_fail_delta", ""),
        "bad_route": r.get("bad_route_delta", ""),
        "n3_rx_drops": r.get("n3_rx_dropped_delta", ""),
        "n6_tx_drops": r.get("n6_tx_dropped_delta", ""),
        "action_count": "",
        "fallback_count": "",
        "schema_fallback_count": "",
        "tool_failure_count": "",
        "oscillation_count": "",
        "mean_llm_latency_ms": "",
        "mean_total_tokens": "",
        "notes": r.get("notes", ""),
        "source_campaign": str(BASELINE_ROOT),
    })


def add_agentic_rows(exp_dir, phase_csv, experiment_label, source_campaign):
    if not phase_csv.exists():
        print(f"[skip] {experiment_label}: missing {phase_csv}")
        return 0
    n = 0
    for r in read_csv(phase_csv):
        run_name = r.get("run", "")
        run_info = get_agentic_run_info(exp_dir, run_name)
        window_sec = inum(run_info.get("window_sec", 10), 10)
        windows = inum(r.get("windows", 0), 0)
        run_path = exp_dir / run_name
        osc = count_oscillations_by_phase(run_path).get(r.get("phase", ""), 0)
        schema_fb = count_schema_fallbacks_by_phase(run_path).get(r.get("phase", ""), 0)

        rows.append({
            "experiment": experiment_label,
            "controller_group": "agentic",
            "model": run_info.get("vllm_model", "Qwen/Qwen2.5-7B-Instruct"),
            "gpu": "RTX A4000",
            "prefix_cache": "disabled",
            "run": run_name,
            "phase": r.get("phase", ""),
            "health_status": r.get("status", ""),
            "duration_s": windows * window_sec,
            "windows": r.get("windows", ""),
            "offered_mbps": r.get("mean_offered_mbps", ""),
            "delivered_mbps": r.get("mean_delivered_mbps", ""),
            "access_rx_packets": r.get("access_rx_packets", ""),
            "core_tx_packets": r.get("core_tx_packets", ""),
            "app_qer_red_packets": r.get("app_qer_meter_red_packets", ""),
            "policing_ratio": r.get("mean_policing_ratio", ""),
            "pdr_fail": r.get("pdr_fail", ""),
            "far_fail": r.get("far_fail", ""),
            "bad_route": r.get("bad_route", ""),
            "n3_rx_drops": r.get("n3_rx_drops", ""),
            "n6_tx_drops": r.get("n6_tx_drops", ""),
            "action_count": r.get("action_count", ""),
            "fallback_count": r.get("fallback_count", ""),
            "schema_fallback_count": schema_fb,
            "tool_failure_count": r.get("tool_failure_count", ""),
            "oscillation_count": osc,
            "mean_llm_latency_ms": r.get("mean_decision_latency_ms", ""),
            "mean_total_tokens": r.get("mean_total_tokens", ""),
            "notes": r.get("notes", ""),
            "source_campaign": source_campaign,
        })
        n += 1
    return n


n4  = add_agentic_rows(AGENTIC_E4_EXP,  AGENTIC_E4_CSV,
                       "e4_agentic_rtx6000_realtime", str(AGENTIC_E4_ROOT))
n4b = add_agentic_rows(AGENTIC_E4B_EXP, AGENTIC_E4B_CSV,
                       "e4b_agentic_hysteresis_realtime", str(AGENTIC_E4B_ROOT))


# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------
fieldnames = [
    "experiment", "controller_group", "model", "gpu", "prefix_cache",
    "run", "phase", "health_status",
    "duration_s", "windows",
    "offered_mbps", "delivered_mbps",
    "access_rx_packets", "core_tx_packets",
    "app_qer_red_packets", "policing_ratio",
    "pdr_fail", "far_fail", "bad_route",
    "n3_rx_drops", "n6_tx_drops",
    "action_count", "fallback_count", "schema_fallback_count",
    "tool_failure_count", "oscillation_count",
    "mean_llm_latency_ms", "mean_total_tokens",
    "notes", "source_campaign",
]

OUT_DIR.mkdir(parents=True, exist_ok=True)

with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------
by_exp_phase = defaultdict(list)
for r in rows:
    by_exp_phase[(r["experiment"], r["phase"])].append(r)

EXP_ORDER = [
    "e1_static",
    "e2_threshold",
    "e3_greedy",
    "e4_agentic_rtx6000_realtime",
    "e4b_agentic_hysteresis_realtime",
]
PHASE_ORDER = ["A", "B", "C", "D"]


def exp_sort_key(name):
    try:
        return (EXP_ORDER.index(name), name)
    except ValueError:
        return (len(EXP_ORDER), name)


summary_rows = []
for (exp, phase) in sorted(by_exp_phase.keys(),
                           key=lambda k: (exp_sort_key(k[0]),
                                          PHASE_ORDER.index(k[1]) if k[1] in PHASE_ORDER else 99)):
    rs = by_exp_phase[(exp, phase)]
    delivered = [fnum(x["delivered_mbps"]) for x in rs]
    red = [fnum(x["app_qer_red_packets"]) for x in rs]
    actions = [fnum(x["action_count"]) for x in rs if x["action_count"] != ""]
    fallbacks = [fnum(x["fallback_count"]) for x in rs if x["fallback_count"] != ""]
    schema_fb = [fnum(x["schema_fallback_count"]) for x in rs if x["schema_fallback_count"] != ""]
    oscillations = [fnum(x["oscillation_count"]) for x in rs if x["oscillation_count"] != ""]
    lat = [fnum(x["mean_llm_latency_ms"]) for x in rs if x["mean_llm_latency_ms"] != ""]

    d_mean, d_std = mean_std(delivered)
    red_mean, red_std = mean_std(red)

    summary_rows.append({
        "experiment": exp,
        "phase": phase,
        "n": len(rs),
        "delivered_mbps_mean": d_mean,
        "delivered_mbps_std": d_std,
        "app_qer_red_mean": red_mean,
        "app_qer_red_std": red_std,
        "actions_mean": mean(actions) if actions else "",
        "fallbacks_mean": mean(fallbacks) if fallbacks else "",
        "schema_fb_mean": mean(schema_fb) if schema_fb else "",
        "oscillations_mean": mean(oscillations) if oscillations else "",
        "llm_latency_ms_mean": mean(lat) if lat else "",
    })

md = []
md.append("# Combined baseline and agentic phase metrics")
md.append("")
md.append(f"Output CSV `{OUT_CSV}`")
md.append("")
md.append(f"Total rows `{len(rows)}`")
md.append("")
md.append("Experiments included")
md.append("")
md.append("- E1 Static, E2 Threshold, E3 Greedy from baseline campaign")
md.append(f"- E4 agentic (no hysteresis): {n4 // 4 if n4 else 0} runs")
md.append(f"- E4b agentic (hysteresis):  {n4b // 4 if n4b else 0} runs")
md.append("")
md.append("| experiment | phase | n | delivered Mbps mean | delivered Mbps std | "
          "app QER red mean | actions mean | fallbacks mean | schema fb mean | "
          "oscillations mean | LLM latency mean ms |")
md.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")


def fmt(x, spec=""):
    if x == "" or x is None:
        return ""
    if spec:
        try:
            return format(float(x), spec)
        except Exception:
            return str(x)
    return str(x)


for r in summary_rows:
    md.append(
        f"| {r['experiment']} | {r['phase']} | {r['n']} | "
        f"{fmt(r['delivered_mbps_mean'], '.2f')} | "
        f"{fmt(r['delivered_mbps_std'], '.2f')} | "
        f"{fmt(r['app_qer_red_mean'], '.2f')} | "
        f"{fmt(r['actions_mean'], '.2f')} | "
        f"{fmt(r['fallbacks_mean'], '.2f')} | "
        f"{fmt(r['schema_fb_mean'], '.2f')} | "
        f"{fmt(r['oscillations_mean'], '.2f')} | "
        f"{fmt(r['llm_latency_ms_mean'], '.0f')} |"
    )

OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"Combined rows: {len(rows)}")
print(f"  baseline rows: {sum(1 for r in rows if r['controller_group']=='baseline')}")
print(f"  E4 rows:       {n4}")
print(f"  E4b rows:      {n4b}")
print(f"CSV:     {OUT_CSV}")
print(f"Summary: {OUT_MD}")

