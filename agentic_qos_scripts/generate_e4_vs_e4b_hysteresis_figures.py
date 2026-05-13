#!/usr/bin/env python3
"""
Generate ACM-style vector PDF figures comparing E4 original agentic control
against E4b hysteresis agentic control.

Default input paths match the current Agentic B5G QoS Enforcement layout:

E4  ~/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime
E4b ~/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime

Outputs four independent PDF files, one per comparison figure:
  fig01_phase_b_s5_mbr_trajectory.pdf
  fig02_phase_c_silver_mbr_trajectory.pdf
  fig03_fallback_decomposition.pdf
  fig04_throughput_policing_tradeoff.pdf

The script is safe to run while E4b is still executing. It skips incomplete
or partially written JSONL lines and uses the run_* directories currently
available. Re-run it after the campaign finishes to update the figures.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

import matplotlib.pyplot as plt
import numpy as np

PHASES = ["A", "B", "C", "D"]
EXPERIMENTS = ["E4", "E4b"]

DEFAULT_E4_ROOT = Path.home() / "agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime"
DEFAULT_E4B_ROOT = Path.home() / "agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime"
DEFAULT_OUT_DIR = Path.home() / "agentic_qos_results/figures/e4_vs_e4b_hysteresis_acm"

# Grayscale, ACM-friendly visual grammar. No titles are used anywhere.
STYLE = {
    "E4": {
        "color": "0.15",
        "line": "--",
        "marker": "o",
        "hatch": "///",
        "label": "E4 original",
    },
    "E4b": {
        "color": "0.55",
        "line": "-",
        "marker": "s",
        "hatch": "\\\\\\",
        "label": "E4b hysteresis",
    },
}

FALLBACK_ORDER = [
    "Schema action mismatch",
    "Candidate violation",
    "Invalid MBR value",
    "Other fallback",
]
FALLBACK_STYLE = {
    "Schema action mismatch": {"color": "0.15", "hatch": "////"},
    "Candidate violation": {"color": "0.35", "hatch": "...."},
    "Invalid MBR value": {"color": "0.60", "hatch": "xxxx"},
    "Other fallback": {"color": "0.80", "hatch": "----"},
}


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.labelsize": 16,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 13,
        "axes.linewidth": 1.0,
        "lines.linewidth": 2.2,
        "lines.markersize": 7,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
    })


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                # Safe while a run is still writing the file.
                continue
    return records


def load_decisions(root: Path, include_smoke: bool = False) -> list[dict[str, Any]]:
    patterns = ["run_*"]
    if include_smoke:
        patterns.append("smoke_*")

    records: list[dict[str, Any]] = []
    for pattern in patterns:
        for run_dir in sorted(root.glob(pattern)):
            if not run_dir.is_dir():
                continue
            decisions = run_dir / "controller" / "decisions.jsonl"
            for rec in read_jsonl(decisions):
                rec = dict(rec)
                rec.setdefault("run", run_dir.name)
                rec["run_dir_name"] = run_dir.name
                records.append(rec)
    return records


def exp_records(data: dict[str, list[dict[str, Any]]], exp: str) -> list[dict[str, Any]]:
    return data.get(exp, [])


def unique_runs(records: list[dict[str, Any]]) -> list[str]:
    return sorted({str(r.get("run_dir_name") or r.get("run") or "unknown") for r in records})


def get_mbr(rec: dict[str, Any]) -> list[int] | None:
    mbr = rec.get("new_mbr_kbps")
    if isinstance(mbr, list) and len(mbr) == 5:
        try:
            return [int(x) for x in mbr]
        except Exception:
            return None
    decision = rec.get("decision")
    if isinstance(decision, dict):
        mbr = decision.get("mbr_kbps")
        if isinstance(mbr, list) and len(mbr) == 5:
            try:
                return [int(x) for x in mbr]
            except Exception:
                return None
    return None


def telemetry_value(rec: dict[str, Any], key: str) -> float | None:
    tel = rec.get("telemetry")
    if not isinstance(tel, dict):
        return None
    val = tel.get(key)
    if val is None and key == "policing_ratio":
        red = tel.get("app_qer_meter_red_delta")
        passed = tel.get("app_qer_pass_delta")
        try:
            denom = float(red) + float(passed)
            val = float(red) / denom if denom > 0 else 0.0
        except Exception:
            return None
    try:
        return float(val)
    except Exception:
        return None


def action_used(rec: dict[str, Any]) -> bool:
    old = rec.get("old_mbr_kbps")
    new = rec.get("new_mbr_kbps")
    return isinstance(old, list) and isinstance(new, list) and old != new


def fallback_category(error: Any) -> str:
    msg = str(error or "").lower()
    if "modify_mbr requires a changed vector" in msg or "requires a changed vector" in msg:
        return "Schema action mismatch"
    if "not in candidates" in msg or "candidate" in msg:
        return "Candidate violation"
    if "multiple" in msg or "integer" in msg or "mbr values" in msg or "capacity exceeded" in msg:
        return "Invalid MBR value"
    return "Other fallback"


def mean_std(vals: Iterable[float]) -> tuple[float, float, int]:
    arr = np.asarray([v for v in vals if v is not None and math.isfinite(v)], dtype=float)
    if arr.size == 0:
        return float("nan"), float("nan"), 0
    if arr.size == 1:
        return float(arr[0]), 0.0, 1
    return float(arr.mean()), float(arr.std(ddof=1)), int(arr.size)


def trajectory_by_run(records: list[dict[str, Any]], phase: str, value_fn: Callable[[dict[str, Any]], float | None]) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = defaultdict(dict)
    for rec in records:
        if rec.get("phase") != phase:
            continue
        try:
            w = int(rec.get("window_index"))
        except Exception:
            continue
        val = value_fn(rec)
        if val is None or not math.isfinite(val):
            continue
        run = str(rec.get("run_dir_name") or rec.get("run") or "unknown")
        out[run][w] = float(val)
    return out


def aggregate_trajectory(runs: dict[str, dict[int, float]]) -> tuple[list[int], list[float], list[float], int]:
    windows = sorted({w for rd in runs.values() for w in rd})
    means, stds = [], []
    for w in windows:
        vals = [rd[w] for rd in runs.values() if w in rd]
        m, s, _ = mean_std(vals)
        means.append(m)
        stds.append(s)
    return windows, means, stds, len(runs)


def annotate_line_points(ax: plt.Axes, xs: list[int], ys: list[float], dy: float, fmt: str = "{:.0f}") -> None:
    for x, y in zip(xs, ys):
        if y is None or not math.isfinite(y):
            continue
        ax.annotate(
            fmt.format(y),
            xy=(x, y),
            xytext=(0, dy),
            textcoords="offset points",
            ha="center",
            va="bottom" if dy >= 0 else "top",
            fontsize=12,
            color="0.10",
        )


def annotate_bars(ax: plt.Axes, bars, fmt: str = "{:.0f}", dy: float = 3.0, min_label: float = 0.0) -> None:
    for bar in bars:
        h = bar.get_height()
        if h is None or not math.isfinite(h) or abs(h) <= min_label:
            continue
        ax.annotate(
            fmt.format(h),
            xy=(bar.get_x() + bar.get_width() / 2.0, h),
            xytext=(0, dy),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=12,
        )


def annotate_stacked_segment(ax: plt.Axes, x: float, bottom: float, height: float) -> None:
    if height <= 0:
        return
    ax.text(x, bottom + height / 2.0, f"{int(height)}", ha="center", va="center", fontsize=11)


def save_figure(fig: plt.Figure, out_dir: Path, name: str, png: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.pdf")
    if png:
        fig.savefig(out_dir / f"{name}.png", dpi=300)
    plt.close(fig)


def figure_phase_b_s5(data: dict[str, list[dict[str, Any]]], out_dir: Path, png: bool) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))

    def s5_mbps(rec: dict[str, Any]) -> float | None:
        mbr = get_mbr(rec)
        return None if mbr is None else mbr[4] / 1000.0

    for idx, exp in enumerate(EXPERIMENTS):
        runs = trajectory_by_run(exp_records(data, exp), "B", s5_mbps)
        xs, means, stds, n_runs = aggregate_trajectory(runs)
        style = STYLE[exp]

        # Thin per-run trajectories show determinism without dominating the mean.
        for rd in runs.values():
            rx = sorted(rd)
            ry = [rd[w] for w in rx]
            ax.plot(rx, ry, linestyle=style["line"], color=style["color"], alpha=0.18, linewidth=1.0)

        ax.errorbar(
            xs,
            means,
            yerr=stds,
            color=style["color"],
            linestyle=style["line"],
            marker=style["marker"],
            capsize=4,
            label=f"{style['label']} (n={n_runs})",
        )
        annotate_line_points(ax, xs, means, dy=9 if idx == 0 else -18)

    ax.set_xlabel("Phase B window")
    ax.set_ylabel("S5 MBR (Mbps)")
    ax.set_xticks([1, 2, 3, 4, 5, 6])
    ax.grid(axis="y", linestyle=":", linewidth=0.8, color="0.75")
    ax.legend(frameon=False, loc="best")
    save_figure(fig, out_dir, "fig01_phase_b_s5_mbr_trajectory", png)


def figure_phase_c_silver(data: dict[str, list[dict[str, Any]]], out_dir: Path, png: bool) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.2))

    def silver_mbps(rec: dict[str, Any]) -> float | None:
        mbr = get_mbr(rec)
        return None if mbr is None else ((mbr[2] + mbr[3]) / 2.0) / 1000.0

    for idx, exp in enumerate(EXPERIMENTS):
        runs = trajectory_by_run(exp_records(data, exp), "C", silver_mbps)
        xs, means, stds, n_runs = aggregate_trajectory(runs)
        style = STYLE[exp]

        for rd in runs.values():
            rx = sorted(rd)
            ry = [rd[w] for w in rx]
            ax.plot(rx, ry, linestyle=style["line"], color=style["color"], alpha=0.18, linewidth=1.0)

        ax.errorbar(
            xs,
            means,
            yerr=stds,
            color=style["color"],
            linestyle=style["line"],
            marker=style["marker"],
            capsize=4,
            label=f"{style['label']} (n={n_runs})",
        )
        annotate_line_points(ax, xs, means, dy=9 if idx == 0 else -18)

    ax.set_xlabel("Phase C window")
    ax.set_ylabel("Mean Silver MBR, S3/S4 (Mbps)")
    ax.set_xticks([1, 2, 3, 4, 5, 6])
    ax.grid(axis="y", linestyle=":", linewidth=0.8, color="0.75")
    ax.legend(frameon=False, loc="best")
    save_figure(fig, out_dir, "fig02_phase_c_silver_mbr_trajectory", png)


def figure_fallback_decomposition(data: dict[str, list[dict[str, Any]]], out_dir: Path, png: bool) -> None:
    fig, ax = plt.subplots(figsize=(9.0, 4.4))

    labels = []
    x_positions = []
    group_centers = []
    pos = 0.0
    width = 0.72
    gap = 0.65

    for phase in PHASES:
        phase_positions = []
        for exp in EXPERIMENTS:
            labels.append(f"{phase}\n{exp}")
            x_positions.append(pos)
            phase_positions.append(pos)
            pos += 1.0
        group_centers.append(sum(phase_positions) / len(phase_positions))
        pos += gap

    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    totals: dict[tuple[str, str], int] = defaultdict(int)
    for exp in EXPERIMENTS:
        for rec in exp_records(data, exp):
            if not rec.get("fallback_used"):
                continue
            phase = str(rec.get("phase"))
            cat = fallback_category(rec.get("decision_error"))
            counts[(phase, exp, cat)] += 1
            totals[(phase, exp)] += 1

    bottoms = np.zeros(len(x_positions), dtype=float)
    bar_index = {(phase, exp): i for i, (phase, exp) in enumerate((p, e) for p in PHASES for e in EXPERIMENTS)}

    for cat in FALLBACK_ORDER:
        heights = []
        for phase in PHASES:
            for exp in EXPERIMENTS:
                heights.append(counts[(phase, exp, cat)])
        style = FALLBACK_STYLE[cat]
        bars = ax.bar(
            x_positions,
            heights,
            width=width,
            bottom=bottoms,
            color=style["color"],
            edgecolor="black",
            linewidth=0.7,
            hatch=style["hatch"],
            label=cat,
        )
        for i, bar in enumerate(bars):
            annotate_stacked_segment(ax, bar.get_x() + bar.get_width() / 2.0, bottoms[i], heights[i])
        bottoms += np.asarray(heights, dtype=float)

    for i, total in enumerate(bottoms):
        if total > 0:
            ax.annotate(
                f"{int(total)}",
                xy=(x_positions[i], total),
                xytext=(0, 5),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=12,
                fontweight="bold",
            )

    ax.set_ylabel("Fallback decisions")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.grid(axis="y", linestyle=":", linewidth=0.8, color="0.75")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    save_figure(fig, out_dir, "fig03_fallback_decomposition", png)


def per_run_phase_values(records: list[dict[str, Any]], metric_fn: Callable[[dict[str, Any]], float | None]) -> dict[tuple[str, str], list[float]]:
    tmp: dict[tuple[str, str], list[float]] = defaultdict(list)
    for rec in records:
        phase = str(rec.get("phase"))
        if phase not in PHASES:
            continue
        run = str(rec.get("run_dir_name") or rec.get("run") or "unknown")
        val = metric_fn(rec)
        if val is None or not math.isfinite(val):
            continue
        tmp[(run, phase)].append(float(val))

    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for (run, phase), vals in tmp.items():
        if vals:
            out[(phase, run)].append(float(np.mean(vals)))
    return out


def phase_aggregate(records: list[dict[str, Any]], metric_fn: Callable[[dict[str, Any]], float | None]) -> dict[str, tuple[float, float, int]]:
    grouped = per_run_phase_values(records, metric_fn)
    out: dict[str, tuple[float, float, int]] = {}
    for phase in PHASES:
        vals = []
        for (p, _run), phase_vals in grouped.items():
            if p == phase:
                vals.extend(phase_vals)
        out[phase] = mean_std(vals)
    return out


def figure_throughput_policing(data: dict[str, list[dict[str, Any]]], out_dir: Path, png: bool) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.3))
    width = 0.36
    x = np.arange(len(PHASES))

    metrics = [
        (
            axes[0],
            "Delivered throughput (Mbps)",
            lambda rec: telemetry_value(rec, "delivered_mbps"),
            "{:.1f}",
        ),
        (
            axes[1],
            "Policing ratio (%)",
            lambda rec: (telemetry_value(rec, "policing_ratio") or 0.0) * 100.0,
            "{:.2f}",
        ),
    ]

    for ax, ylabel, metric_fn, label_fmt in metrics:
        for idx, exp in enumerate(EXPERIMENTS):
            agg = phase_aggregate(exp_records(data, exp), metric_fn)
            means = [agg[p][0] for p in PHASES]
            stds = [agg[p][1] for p in PHASES]
            xpos = x + (idx - 0.5) * width
            style = STYLE[exp]
            bars = ax.bar(
                xpos,
                means,
                yerr=stds,
                capsize=4,
                width=width,
                color=style["color"],
                edgecolor="black",
                linewidth=0.7,
                hatch=style["hatch"],
                label=style["label"],
            )
            annotate_bars(ax, bars, fmt=label_fmt, dy=4, min_label=0.00001)

        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels(PHASES)
        ax.set_xlabel("Phase")
        ax.grid(axis="y", linestyle=":", linewidth=0.8, color="0.75")

    axes[0].legend(frameon=False, loc="best")
    save_figure(fig, out_dir, "fig04_throughput_policing_tradeoff", png)


def write_summary(data: dict[str, list[dict[str, Any]]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# E4 vs E4b hysteresis figure generation summary")
    lines.append("")
    for exp in EXPERIMENTS:
        records = exp_records(data, exp)
        runs = unique_runs(records)
        fallbacks = sum(1 for r in records if r.get("fallback_used"))
        tool_failures = 0
        for r in records:
            app = r.get("apply_result")
            if isinstance(app, dict) and app.get("returncode") not in (None, 0):
                tool_failures += 1
        actions = sum(1 for r in records if action_used(r))
        lines.append(f"## {exp}")
        lines.append(f"Runs read: {len(runs)}")
        lines.append(f"Decisions read: {len(records)}")
        lines.append(f"Actions inferred: {actions}")
        lines.append(f"Fallbacks: {fallbacks}")
        lines.append(f"Tool failures inferred from apply_result: {tool_failures}")
        lines.append("")
    lines.append("## Output files")
    for name in [
        "fig01_phase_b_s5_mbr_trajectory.pdf",
        "fig02_phase_c_silver_mbr_trajectory.pdf",
        "fig03_fallback_decomposition.pdf",
        "fig04_throughput_policing_tradeoff.pdf",
    ]:
        lines.append(f"- {name}")
    (out_dir / "summary_e4_vs_e4b.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate E4 vs E4b hysteresis ACM-style PDF figures.")
    parser.add_argument("--e4-root", type=Path, default=DEFAULT_E4_ROOT)
    parser.add_argument("--e4b-root", type=Path, default=DEFAULT_E4B_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--include-smoke", action="store_true", help="Also include smoke_* directories. Default uses run_* only.")
    parser.add_argument("--png", action="store_true", help="Also export PNG previews.")
    args = parser.parse_args()

    configure_matplotlib()

    data = {
        "E4": load_decisions(args.e4_root, include_smoke=args.include_smoke),
        "E4b": load_decisions(args.e4b_root, include_smoke=args.include_smoke),
    }

    for exp in EXPERIMENTS:
        runs = unique_runs(data[exp])
        print(f"{exp}: {len(data[exp])} decisions across {len(runs)} run directories")
        if len(data[exp]) == 0:
            raise SystemExit(f"No decisions found for {exp}. Check the root path.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    figure_phase_b_s5(data, args.out_dir, args.png)
    figure_phase_c_silver(data, args.out_dir, args.png)
    figure_fallback_decomposition(data, args.out_dir, args.png)
    figure_throughput_policing(data, args.out_dir, args.png)
    write_summary(data, args.out_dir)

    print(f"\nDone. Files written to: {args.out_dir}")
    print("  fig01_phase_b_s5_mbr_trajectory.pdf")
    print("  fig02_phase_c_silver_mbr_trajectory.pdf")
    print("  fig03_fallback_decomposition.pdf")
    print("  fig04_throughput_policing_tradeoff.pdf")
    print("  summary_e4_vs_e4b.md")


if __name__ == "__main__":
    main()

