#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


PHASES = ["A", "B", "C", "D"]

SNAPSHOT_ORDER = [
    ("before", "before"),
    ("phase_A_after", "phase_A_after"),
    ("phase_B_after", "phase_B_after"),
    ("phase_C_after", "phase_C_after"),
    ("phase_D_after", "phase_D_after"),
    ("after", "after"),
]

PHASE_PAIRS = [
    ("A", "before", "phase_A_after"),
    ("B", "phase_A_after", "phase_B_after"),
    ("C", "phase_B_after", "phase_C_after"),
    ("D", "phase_C_after", "phase_D_after"),
]

EXPECTED_SLICES = {
    "S1": {"tier": "Gold", "teid": 1, "cap_mbps": 200},
    "S2": {"tier": "Gold", "teid": 11, "cap_mbps": 200},
    "S3": {"tier": "Silver", "teid": 21, "cap_mbps": 150},
    "S4": {"tier": "Silver", "teid": 31, "cap_mbps": 150},
    "S5": {"tier": "Bronze", "teid": 41, "cap_mbps": 100},
}


def parse_number(text: str) -> float:
    text = text.strip().replace(",", "")
    if text == "":
        return 0.0
    return float(text)


def parse_int(text: str) -> int:
    return int(parse_number(text))


def parse_timestamp_file(path: Path) -> Optional[datetime]:
    if not path.exists():
        return None
    text = path.read_text(errors="replace").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_prometheus_metrics(path: Path) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    if not path.exists():
        return metrics

    line_re = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+([0-9eE+\-.]+)$')
    label_re = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')

    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        m = line_re.match(line)
        if not m:
            continue

        name, labels_text, value_text = m.groups()
        labels = dict(label_re.findall(labels_text))
        value = float(value_text)

        if name == "pfcp_sessions":
            node_id = labels.get("node_id", "unknown")
            metrics[f"pfcp_sessions.node_{node_id}"] = value

        elif name == "upf_packets_count":
            direction = labels.get("dir", "unknown")
            iface = labels.get("iface", "unknown")
            metrics[f"upf_packets.{direction}.{iface}"] = value

        elif name == "upf_bytes_count":
            direction = labels.get("dir", "unknown")
            iface = labels.get("iface", "unknown")
            metrics[f"upf_bytes.{direction}.{iface}"] = value

        elif name == "upf_dropped_count":
            direction = labels.get("dir", "unknown")
            iface = labels.get("iface", "unknown")
            metrics[f"upf_dropped.{direction}.{iface}"] = value

        elif name == "upf_latency_ns":
            iface = labels.get("iface", "unknown")
            q = labels.get("quantile")
            if q is not None:
                metrics[f"upf_latency_ns.{iface}.q{q}"] = value

        elif name == "upf_jitter_ns":
            iface = labels.get("iface", "unknown")
            q = labels.get("quantile")
            if q is not None:
                metrics[f"upf_jitter_ns.{iface}.q{q}"] = value

    return metrics


def parse_bess_module(path: Path) -> Dict[str, int]:
    result: Dict[str, int] = {}
    if not path.exists():
        return result

    text = path.read_text(errors="replace").splitlines()
    section = None

    gate_re = re.compile(
        r'^\s*(\d+):\s+batches\s+([\d,]+)\s+packets\s+([\d,]+)\s*(?:->\s*\d*:?\s*([A-Za-z0-9_]+))?'
    )

    for line in text:
        if "Input gates:" in line:
            section = "input"
            continue
        if "Output gates:" in line:
            section = "output"
            continue
        if "Deadends:" in line:
            section = None
            continue

        if section != "output":
            continue

        m = gate_re.match(line)
        if not m:
            continue

        gate, _batches, packets, target = m.groups()
        target = target or f"gate_{gate}"
        result[f"gate_{gate}.{target}"] = parse_int(packets)

    return result


def parse_ports(path: Path) -> Dict[str, int]:
    result: Dict[str, int] = {}
    if not path.exists():
        return result

    current_port = None
    last_direction = None

    port_re = re.compile(r'^\s*([A-Za-z0-9_]+)\s+Driver\s+')
    packets_re = re.compile(r'(Inc/RX|Out/TX)\s+packets:\s+([\d,]+)\s+bytes:\s+([\d,]+)')
    dropped_re = re.compile(r'dropped:\s+([\d,]+)')

    for line in path.read_text(errors="replace").splitlines():
        pm = port_re.match(line)
        if pm:
            current_port = pm.group(1)
            last_direction = None
            continue

        if current_port is None:
            continue

        m = packets_re.search(line)
        if m:
            direction_raw, packets, bytes_ = m.groups()
            direction = "rx" if direction_raw == "Inc/RX" else "tx"
            result[f"port.{current_port}.{direction}.packets"] = parse_int(packets)
            result[f"port.{current_port}.{direction}.bytes"] = parse_int(bytes_)
            last_direction = direction
            continue

        dm = dropped_re.search(line)
        if dm and last_direction:
            result[f"port.{current_port}.{last_direction}.dropped"] = parse_int(dm.group(1))

    return result


def parse_trex_console(path: Path) -> Dict[str, object]:
    result: Dict[str, object] = {
        "exists": path.exists(),
        "has_error": False,
        "has_job_done": False,
        "has_stats": False,
        "error_lines": [],
    }

    if not path.exists():
        return result

    text = path.read_text(errors="replace")
    lower = text.lower()

    result["has_job_done"] = "job done" in lower
    result["has_stats"] = "global statistics" in lower or "port statistics" in lower or "tx bps" in lower

    error_keywords = [
        "failed to",
        "failed with",
        "failed:",
        "traceback",
        "unrecognized arguments",
        "not connected",
        "connection refused",
        "syntax error",
        "exception",
    ]

    lines = []
    for line in text.splitlines():
        ll = line.lower()

        # Ignore normal TRex counters such as oerrors, ierrors, and Errors.
        if "oerrors" in ll or "ierrors" in ll or re.match(r"^\\s*errors\\s+", ll):
            continue

        if any(k in ll for k in error_keywords):
            lines.append(line.strip())

    result["error_lines"] = lines
    result["has_error"] = len(lines) > 0

    return result


@dataclass
class Snapshot:
    label: str
    path: Path
    timestamp: Optional[datetime]
    metrics: Dict[str, float]
    modules: Dict[str, Dict[str, int]]
    ports: Dict[str, int]


@dataclass
class PhaseSummary:
    experiment: str
    run: str
    phase: str
    elapsed_between_snapshots_s: Optional[float]

    access_rx_packets_delta: float
    core_tx_packets_delta: float
    access_rx_bytes_delta: float
    core_tx_bytes_delta: float

    estimated_access_rx_mbps_expected_window: float
    estimated_core_tx_mbps_expected_window: float
    estimated_access_rx_mbps_elapsed_window: Optional[float]
    estimated_core_tx_mbps_elapsed_window: Optional[float]

    pdr_to_gtpu_delta: int
    pdr_fail_delta: int
    gtpu_decap_delta: int
    app_qer_pass_delta: int
    app_qer_meter_red_delta: int
    app_qer_fail_delta: int
    session_qer_meter_red_delta: int
    far_forward_delta: int
    far_fail_delta: int
    route_forward_delta: int
    bad_route_delta: int

    n3_rx_packets_delta: int
    n6_tx_packets_delta: int
    n3_rx_dropped_delta: int
    n6_tx_dropped_delta: int

    pfcp_sessions_before: Optional[float]
    pfcp_sessions_after: Optional[float]

    trex_has_error: bool
    trex_has_job_done: bool

    health_status: str
    notes: str


def load_snapshot(run_dir: Path, snapshot_dir_name: str, tag: str) -> Snapshot:
    path = run_dir / "snapshots" / snapshot_dir_name

    timestamp = parse_timestamp_file(path / f"timestamp_{tag}.txt")

    metrics = parse_prometheus_metrics(path / f"upf_metrics_{tag}.txt")

    modules = {
        "pdrLookup": parse_bess_module(path / f"pdrLookup_{tag}.txt"),
        "gtpuDecap": parse_bess_module(path / f"gtpuDecap_{tag}.txt"),
        "appQERLookup": parse_bess_module(path / f"appQERLookup_{tag}.txt"),
        "sessionQERLookup": parse_bess_module(path / f"sessionQERLookup_{tag}.txt"),
        "farLookup": parse_bess_module(path / f"farLookup_{tag}.txt"),
        "routes": parse_bess_module(path / f"routes_{tag}.txt"),
    }

    ports = parse_ports(path / f"ports_{tag}.txt")

    return Snapshot(
        label=snapshot_dir_name,
        path=path,
        timestamp=timestamp,
        metrics=metrics,
        modules=modules,
        ports=ports,
    )


def metric_delta(before: Snapshot, after: Snapshot, key: str) -> float:
    return after.metrics.get(key, 0.0) - before.metrics.get(key, 0.0)


def module_delta(before: Snapshot, after: Snapshot, module: str, key_contains: str) -> int:
    bmod = before.modules.get(module, {})
    amod = after.modules.get(module, {})

    b = sum(v for k, v in bmod.items() if key_contains in k)
    a = sum(v for k, v in amod.items() if key_contains in k)
    return a - b


def port_delta(before: Snapshot, after: Snapshot, key: str) -> int:
    return int(after.ports.get(key, 0) - before.ports.get(key, 0))


def get_pfcp_sessions(snapshot: Snapshot) -> Optional[float]:
    for k, v in snapshot.metrics.items():
        if k.startswith("pfcp_sessions."):
            return v
    return None


def mbps_from_bytes(byte_delta: float, seconds: float) -> float:
    if seconds <= 0:
        return 0.0
    return (byte_delta * 8.0) / seconds / 1_000_000.0


def summarize_phase(
    experiment: str,
    run: str,
    phase: str,
    before: Snapshot,
    after: Snapshot,
    trex_info: Dict[str, object],
    expected_phase_duration_s: float,
) -> PhaseSummary:
    elapsed = None
    if before.timestamp and after.timestamp:
        elapsed = (after.timestamp - before.timestamp).total_seconds()

    access_rx_packets = metric_delta(before, after, "upf_packets.rx.Access")
    core_tx_packets = metric_delta(before, after, "upf_packets.tx.Core")
    access_rx_bytes = metric_delta(before, after, "upf_bytes.rx.Access")
    core_tx_bytes = metric_delta(before, after, "upf_bytes.tx.Core")

    elapsed_access_mbps = None
    elapsed_core_mbps = None
    if elapsed and elapsed > 0:
        elapsed_access_mbps = mbps_from_bytes(access_rx_bytes, elapsed)
        elapsed_core_mbps = mbps_from_bytes(core_tx_bytes, elapsed)

    pdr_to_gtpu = module_delta(before, after, "pdrLookup", "gtpuDecap")
    pdr_fail = module_delta(before, after, "pdrLookup", "pdrLookupFail")
    gtpu_decap = module_delta(before, after, "gtpuDecap", "appQERLookup")

    app_pass = (
        module_delta(before, after, "appQERLookup", "sessionQERLookup")
    )
    app_meter_red = module_delta(before, after, "appQERLookup", "appQERMeterRed")
    app_fail = module_delta(before, after, "appQERLookup", "appQERLookupFail")
    session_meter_red = module_delta(before, after, "sessionQERLookup", "sessionQERMeterRed")

    far_forward = module_delta(before, after, "farLookup", "farMerge")
    far_fail = module_delta(before, after, "farLookup", "farLookupFail")
    route_forward = module_delta(before, after, "routes", "DstMAC")
    bad_route = module_delta(before, after, "routes", "bad_route")

    n3_rx = port_delta(before, after, "port.enp7s0np0Fast.rx.packets")
    n6_tx = port_delta(before, after, "port.enp8s0np0Fast.tx.packets")
    n3_drop = port_delta(before, after, "port.enp7s0np0Fast.rx.dropped")
    n6_drop = port_delta(before, after, "port.enp8s0np0Fast.tx.dropped")

    notes = []
    status = "OK"

    if elapsed is None:
        status = "WARN"
        notes.append("missing snapshot timestamps")
    elif elapsed < expected_phase_duration_s * 0.8:
        status = "FAIL"
        notes.append(
            f"elapsed between snapshots is only {elapsed:.1f}s, expected about {expected_phase_duration_s}s or more"
        )

    if pdr_fail != 0:
        status = "FAIL"
        notes.append(f"pdrLookupFail delta {pdr_fail}")

    if far_fail != 0:
        status = "FAIL"
        notes.append(f"farLookupFail delta {far_fail}")

    if bad_route != 0:
        status = "FAIL"
        notes.append(f"bad_route delta {bad_route}")

    total_nic_drop = n3_drop + n6_drop
    total_nic_packets = max(n3_rx + n6_tx, 1)
    nic_drop_rate = total_nic_drop / total_nic_packets

    if total_nic_drop != 0:
        if nic_drop_rate > 0.001:
            status = "FAIL"
            notes.append(
                f"NIC drops n3_rx={n3_drop}, n6_tx={n6_drop}, rate={nic_drop_rate:.6f}"
            )
        else:
            status = "WARN" if status == "OK" else status
            notes.append(
                f"tiny NIC drops n3_rx={n3_drop}, n6_tx={n6_drop}, rate={nic_drop_rate:.6f}"
            )


    if get_pfcp_sessions(before) != 5 or get_pfcp_sessions(after) != 5:
        status = "FAIL"
        notes.append(
            f"pfcp_sessions before={get_pfcp_sessions(before)}, after={get_pfcp_sessions(after)}"
        )

    if bool(trex_info.get("has_error")):
        status = "FAIL"
        notes.append("TRex console file has error lines")

    if access_rx_packets <= 0 or core_tx_packets <= 0:
        status = "FAIL"
        notes.append("no positive UPF packet delta")

    # Conservation checks.
    if pdr_to_gtpu > 0:
        diff = abs(pdr_to_gtpu - gtpu_decap)
        rel = diff / max(pdr_to_gtpu, 1)
        if rel > 0.02:
            status = "WARN" if status == "OK" else status
            notes.append(f"pdr_to_gtpu and gtpu_decap differ by {diff} packets")

    if far_forward > 0 and route_forward > 0:
        diff = abs(far_forward - route_forward)
        rel = diff / max(far_forward, 1)
        if rel > 0.02:
            status = "WARN" if status == "OK" else status
            notes.append(f"far_forward and route_forward differ by {diff} packets")

    return PhaseSummary(
        experiment=experiment,
        run=run,
        phase=phase,
        elapsed_between_snapshots_s=elapsed,

        access_rx_packets_delta=access_rx_packets,
        core_tx_packets_delta=core_tx_packets,
        access_rx_bytes_delta=access_rx_bytes,
        core_tx_bytes_delta=core_tx_bytes,

        estimated_access_rx_mbps_expected_window=mbps_from_bytes(access_rx_bytes, expected_phase_duration_s),
        estimated_core_tx_mbps_expected_window=mbps_from_bytes(core_tx_bytes, expected_phase_duration_s),
        estimated_access_rx_mbps_elapsed_window=elapsed_access_mbps,
        estimated_core_tx_mbps_elapsed_window=elapsed_core_mbps,

        pdr_to_gtpu_delta=pdr_to_gtpu,
        pdr_fail_delta=pdr_fail,
        gtpu_decap_delta=gtpu_decap,
        app_qer_pass_delta=app_pass,
        app_qer_meter_red_delta=app_meter_red,
        app_qer_fail_delta=app_fail,
        session_qer_meter_red_delta=session_meter_red,
        far_forward_delta=far_forward,
        far_fail_delta=far_fail,
        route_forward_delta=route_forward,
        bad_route_delta=bad_route,

        n3_rx_packets_delta=n3_rx,
        n6_tx_packets_delta=n6_tx,
        n3_rx_dropped_delta=n3_drop,
        n6_tx_dropped_delta=n6_drop,

        pfcp_sessions_before=get_pfcp_sessions(before),
        pfcp_sessions_after=get_pfcp_sessions(after),

        trex_has_error=bool(trex_info.get("has_error")),
        trex_has_job_done=bool(trex_info.get("has_job_done")),

        health_status=status,
        notes="; ".join(notes) if notes else "clean",
    )


def find_run_dirs(root: Path) -> List[Tuple[str, str, Path]]:
    results = []
    for exp_dir in sorted(root.iterdir()):
        if not exp_dir.is_dir():
            continue
        if not exp_dir.name.startswith("e"):
            continue
        for run_dir in sorted(exp_dir.glob("run_*")):
            if run_dir.is_dir():
                results.append((exp_dir.name, run_dir.name, run_dir))
    return results


def analyse_run(
    experiment: str,
    run_name: str,
    run_dir: Path,
    expected_phase_duration_s: float,
) -> List[PhaseSummary]:
    snapshots = {}
    for snap_dir, tag in SNAPSHOT_ORDER:
        snapshots[snap_dir] = load_snapshot(run_dir, snap_dir, tag)

    summaries = []
    for phase, before_key, after_key in PHASE_PAIRS:
        trex_file = run_dir / "trex" / f"phase_{phase}_console.txt"
        trex_info = parse_trex_console(trex_file)

        summaries.append(
            summarize_phase(
                experiment=experiment,
                run=run_name,
                phase=phase,
                before=snapshots[before_key],
                after=snapshots[after_key],
                trex_info=trex_info,
                expected_phase_duration_s=expected_phase_duration_s,
            )
        )

    return summaries


def write_csv(rows: List[PhaseSummary], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(rows[0]).keys()) if rows else []

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(rows: List[PhaseSummary], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(row) for row in rows]
    path.write_text(json.dumps(data, indent=2, default=str))


def write_markdown_report(rows: List[PhaseSummary], root: Path, out_path: Path) -> None:
    total = len(rows)
    ok = sum(1 for r in rows if r.health_status == "OK")
    warn = sum(1 for r in rows if r.health_status == "WARN")
    fail = sum(1 for r in rows if r.health_status == "FAIL")

    lines = []
    lines.append("# Baseline campaign sanity report")
    lines.append("")
    lines.append(f"Campaign root `{root}`")
    lines.append("")
    lines.append("## Overall status")
    lines.append("")
    lines.append(f"Total phase records `{total}`")
    lines.append(f"OK `{ok}`")
    lines.append(f"WARN `{warn}`")
    lines.append(f"FAIL `{fail}`")
    lines.append("")

    if fail > 0:
        lines.append("## Recommendation")
        lines.append("")
        lines.append("Do not run the 10 repetitions yet. Fix the failed items first.")
        lines.append("")
    elif warn > 0:
        lines.append("## Recommendation")
        lines.append("")
        lines.append("Review the warnings before running the 10 repetitions.")
        lines.append("")
    else:
        lines.append("## Recommendation")
        lines.append("")
        lines.append("The smoke campaign looks clean enough to proceed with 10 repetitions.")
        lines.append("")

    lines.append("## Phase summary")
    lines.append("")
    lines.append(
        "| experiment | run | phase | status | elapsed s | access RX pkts | core TX pkts | core TX Mbps expected window | app QER drop | pdr fail | far fail | bad route | notes |"
    )
    lines.append(
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    )

    for r in rows:
        elapsed = "" if r.elapsed_between_snapshots_s is None else f"{r.elapsed_between_snapshots_s:.1f}"
        lines.append(
            f"| {r.experiment} | {r.run} | {r.phase} | {r.health_status} | "
            f"{elapsed} | {int(r.access_rx_packets_delta)} | {int(r.core_tx_packets_delta)} | "
            f"{r.estimated_core_tx_mbps_expected_window:.2f} | "
            f"{r.app_qer_meter_red_delta} | {r.pdr_fail_delta} | {r.far_fail_delta} | "
            f"{r.bad_route_delta} | {r.notes} |"
        )

    out_path.write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.home() / "agentic_qos_results" / "campaigns" / "campaign_20260509_baselines_5slices",
        help="Campaign root directory",
    )
    parser.add_argument(
        "--expected-phase-duration",
        type=float,
        default=60.0,
        help="Expected duration in seconds for each phase",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory for analysis files",
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    out_dir = args.out_dir or (root / "analysis_ready")
    out_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = find_run_dirs(root)
    if not run_dirs:
        raise SystemExit(f"No run directories found under {root}")

    all_rows: List[PhaseSummary] = []

    for experiment, run_name, run_dir in run_dirs:
        rows = analyse_run(
            experiment=experiment,
            run_name=run_name,
            run_dir=run_dir,
            expected_phase_duration_s=args.expected_phase_duration,
        )
        all_rows.extend(rows)

    csv_path = out_dir / "phase_summary.csv"
    json_path = out_dir / "phase_summary.json"
    md_path = out_dir / "sanity_report.md"

    write_csv(all_rows, csv_path)
    write_json(all_rows, json_path)
    write_markdown_report(all_rows, root, md_path)

    total = len(all_rows)
    ok = sum(1 for r in all_rows if r.health_status == "OK")
    warn = sum(1 for r in all_rows if r.health_status == "WARN")
    fail = sum(1 for r in all_rows if r.health_status == "FAIL")

    print(f"Analysed phases: {total}")
    print(f"OK: {ok}")
    print(f"WARN: {warn}")
    print(f"FAIL: {fail}")
    print()
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print(f"Report: {md_path}")

    if fail > 0:
        print()
        print("Recommendation: do not run 10x yet. Inspect sanity_report.md.")
        raise SystemExit(2)

    if warn > 0:
        print()
        print("Recommendation: inspect warnings before running 10x.")
        raise SystemExit(1)

    print()
    print("Recommendation: smoke campaign looks clean enough to proceed with 10x.")


if __name__ == "__main__":
    main()
