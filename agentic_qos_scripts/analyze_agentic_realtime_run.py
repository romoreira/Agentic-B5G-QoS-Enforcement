#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from collections import defaultdict
from pathlib import Path
from statistics import mean

DEFAULT_RUN_DIR = Path.home()/"agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_01"

def read_jsonl(path: Path):
    rows = []
    if not path.exists(): return rows
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if line: rows.append(json.loads(line))
    return rows

def avg(xs):
    xs = [x for x in xs if x is not None]
    return mean(xs) if xs else 0.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = ap.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    decisions = read_jsonl(run_dir/"controller/decisions.jsonl")
    telemetry = read_jsonl(run_dir/"controller/telemetry_windows.jsonl")
    if not decisions: raise SystemExit(f"No decisions found under {run_dir}")
    if not telemetry: raise SystemExit(f"No telemetry windows found under {run_dir}")
    byp, dbyp = defaultdict(list), defaultdict(list)
    for t in telemetry: byp[t["phase"]].append(t)
    for d in decisions: dbyp[d["phase"]].append(d)
    rows = []
    for phase in ["A","B","C","D"]:
        ts, ds = byp[phase], dbyp[phase]
        access_rx = sum(float(x.get("access_rx_packets_delta",0)) for x in ts)
        core_tx = sum(float(x.get("core_tx_packets_delta",0)) for x in ts)
        app_red = sum(int(x.get("app_qer_meter_red_delta",0)) for x in ts)
        pdr_fail = sum(int(x.get("pdr_fail_delta",0)) for x in ts)
        far_fail = sum(int(x.get("far_fail_delta",0)) for x in ts)
        bad_route = sum(int(x.get("bad_route_delta",0)) for x in ts)
        n3_drop = sum(int(x.get("n3_rx_dropped_delta",0)) for x in ts)
        n6_drop = sum(int(x.get("n6_tx_dropped_delta",0)) for x in ts)
        action_count = sum(1 for d in ds if d.get("old_mbr_kbps") != d.get("new_mbr_kbps"))
        fallback_count = sum(1 for d in ds if d.get("fallback_used"))
        tool_fail = sum(1 for d in ds if d.get("apply_result") and d["apply_result"].get("returncode") != 0)
        status, notes = "OK", []
        if pdr_fail or far_fail or bad_route:
            status = "FAIL"; notes.append("datapath failures detected")
        if tool_fail:
            status = "FAIL"; notes.append("tool failure detected")
        if fallback_count:
            status = "WARN" if status == "OK" else status; notes.append("fallback used")
        if n3_drop or n6_drop:
            rate = (n3_drop+n6_drop)/max(access_rx+core_tx,1)
            if rate > 0.001:
                status = "FAIL"; notes.append(f"NIC drop rate too high {rate:.6f}")
            else:
                status = "WARN" if status == "OK" else status; notes.append(f"tiny NIC drops {rate:.6f}")
        rows.append({"phase":phase, "windows":len(ts), "decisions":len(ds), "status":status, "access_rx_packets":int(access_rx), "core_tx_packets":int(core_tx), "app_qer_meter_red_packets":int(app_red), "mean_offered_mbps":avg([float(x.get("offered_mbps",0)) for x in ts]), "mean_delivered_mbps":avg([float(x.get("delivered_mbps",0)) for x in ts]), "mean_policing_ratio":avg([float(x.get("policing_ratio",0)) for x in ts]), "pdr_fail":pdr_fail, "far_fail":far_fail, "bad_route":bad_route, "n3_rx_drops":n3_drop, "n6_tx_drops":n6_drop, "action_count":action_count, "fallback_count":fallback_count, "tool_failure_count":tool_fail, "mean_decision_latency_ms":avg([d.get("decision_latency_ms") for d in ds]), "mean_total_tokens":avg([d.get("total_tokens") for d in ds]), "notes":"; ".join(notes) if notes else "clean"})
    out = run_dir/"analysis_ready"; out.mkdir(parents=True, exist_ok=True)
    with (out/"agentic_phase_summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    summary = {"run_dir":str(run_dir), "total_windows":len(telemetry), "total_decisions":len(decisions), "total_actions":sum(r["action_count"] for r in rows), "total_fallbacks":sum(r["fallback_count"] for r in rows), "total_tool_failures":sum(r["tool_failure_count"] for r in rows), "phase_rows":rows}
    (out/"agentic_run_summary.json").write_text(json.dumps(summary, indent=2))
    lines = ["# Agentic realtime run sanity report", "", f"Run directory `{run_dir}`", "", f"Total windows `{summary['total_windows']}`", f"Total decisions `{summary['total_decisions']}`", f"Total actions `{summary['total_actions']}`", f"Total fallbacks `{summary['total_fallbacks']}`", f"Total tool failures `{summary['total_tool_failures']}`", "", "| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        lines.append(f"| {r['phase']} | {r['status']} | {r['windows']} | {r['action_count']} | {r['fallback_count']} | {r['mean_delivered_mbps']:.2f} | {r['app_qer_meter_red_packets']} | {r['pdr_fail']} | {r['far_fail']} | {r['bad_route']} | {r['mean_decision_latency_ms']:.2f} | {r['notes']} |")
    (out/"agentic_sanity_report.md").write_text("\n".join(lines)+"\n")
    print(f"Analysed run: {run_dir}")
    print(f"Total windows: {summary['total_windows']}")
    print(f"Total decisions: {summary['total_decisions']}")
    print(f"Total actions: {summary['total_actions']}")
    print(f"Total fallbacks: {summary['total_fallbacks']}")
    print(f"Total tool failures: {summary['total_tool_failures']}")
    print(f"Report: {out/'agentic_sanity_report.md'}")

if __name__ == "__main__":
    main()

