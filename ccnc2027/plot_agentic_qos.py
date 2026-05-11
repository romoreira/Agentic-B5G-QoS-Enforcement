#!/usr/bin/env python3
"""
Agentic B5G QoS Experiment — Publication-quality figures
Produces one PDF per figure, font 16, no titles, EN-US labels.
Run from any directory; paths are resolved from COMBINED_CSV.

Usage:
    python3 plot_agentic_qos.py [--csv PATH] [--out DIR]
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

# ── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_CSV = Path.home() / (
    "agentic_qos_results/campaigns/"
    "combined_baseline_agentic_phase_metrics.csv"
)
DEFAULT_OUT = Path("figures")

# ── Global style ─────────────────────────────────────────────────────────────
FS = 16          # base font size
TICK_FS = 14
LEG_FS  = 13
LW      = 1.4    # line / edge width

plt.rcParams.update({
    "font.size":        FS,
    "axes.labelsize":   FS,
    "axes.titlesize":   FS,
    "xtick.labelsize":  TICK_FS,
    "ytick.labelsize":  TICK_FS,
    "legend.fontsize":  LEG_FS,
    "figure.dpi":       150,
    "pdf.fonttype":     42,   # editable text in Illustrator / Inkscape
    "ps.fonttype":      42,
    "axes.spines.top":  False,
    "axes.spines.right":False,
})

# ── Colours / display names ───────────────────────────────────────────────────
EXP_ORDER   = ["e1_static", "e2_threshold", "e3_greedy", "e4_agentic_rtx6000_realtime"]
EXP_LABEL   = {
    "e1_static":                  "E1 Static",
    "e2_threshold":               "E2 Threshold",
    "e3_greedy":                  "E3 Greedy",
    "e4_agentic_rtx6000_realtime":"E4 Agentic",
}
EXP_COLOR   = {
    "e1_static":                  "#4878CF",
    "e2_threshold":               "#6ACC65",
    "e3_greedy":                  "#D65F5F",
    "e4_agentic_rtx6000_realtime":"#B47CC7",
}
PHASE_ORDER = ["A", "B", "C", "D"]
PHASE_LABEL = {"A": "Phase A\n(Steady)", "B": "Phase B\n(Bronze Burst)",
               "C": "Phase C\n(Silver Flash Crowd)", "D": "Phase D\n(Recovery)"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  {path}")


def grouped_bar(ax, data_mean, data_std, groups, series, colors, width=0.18):
    """Generic grouped-bar helper.  Returns the bar containers."""
    x = np.arange(len(groups))
    n = len(series)
    offsets = np.linspace(-(n - 1) / 2, (n - 1) / 2, n) * width
    containers = []
    for i, (key, label) in enumerate(series):
        vals = [data_mean.get((key, g), 0) for g in groups]
        errs = [data_std.get((key, g),  0) for g in groups]
        c = ax.bar(x + offsets[i], vals, width,
                   yerr=errs, capsize=4,
                   label=label,
                   color=colors[key],
                   edgecolor="white", linewidth=LW,
                   error_kw=dict(elinewidth=1.2, ecolor="#333333"))
        containers.append(c)
    ax.set_xticks(x)
    return containers


# ── Figure 1 — Delivered Throughput by Phase ─────────────────────────────────

def fig1_throughput_by_phase(df: pd.DataFrame, out: Path) -> None:
    """Grouped bar: mean delivered Mbps per experiment × phase."""
    grp = df.groupby(["experiment", "phase"])["delivered_mbps"]
    mn  = grp.mean().to_dict()
    sd  = grp.std().to_dict()

    fig, ax = plt.subplots(figsize=(11, 5))
    series = [(e, EXP_LABEL[e]) for e in EXP_ORDER]
    grouped_bar(ax, mn, sd, PHASE_ORDER, series, EXP_COLOR, width=0.2)

    ax.set_ylabel("Delivered Throughput (Mbps)")
    ax.set_xlabel("Traffic Phase")
    ax.set_xticklabels([PHASE_LABEL[p] for p in PHASE_ORDER])
    ax.legend(loc="upper left", framealpha=0.9)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
    ax.set_ylim(0, ax.get_ylim()[1] * 1.12)

    save(fig, out / "fig1_delivered_throughput_by_phase.pdf")


# ── Figure 2 — Policing Ratio by Phase ───────────────────────────────────────

def fig2_policing_ratio(df: pd.DataFrame, out: Path) -> None:
    """Grouped bar: mean policing ratio in overload phases (B, C)."""
    sub  = df[df["phase"].isin(["B", "C"])].copy()
    grp  = sub.groupby(["experiment", "phase"])["policing_ratio"]
    mn   = grp.mean().to_dict()
    sd   = grp.std().to_dict()

    fig, ax = plt.subplots(figsize=(8, 5))
    series  = [(e, EXP_LABEL[e]) for e in EXP_ORDER]
    grouped_bar(ax, mn, sd, ["B", "C"], series, EXP_COLOR, width=0.2)

    ax.set_ylabel("Policing Ratio  (app-QER-red / received)")
    ax.set_xlabel("Traffic Phase")
    ax.set_xticklabels(["Phase B\n(Bronze Burst)", "Phase C\n(Silver Flash Crowd)"])
    ax.legend(loc="upper right", framealpha=0.9)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.18)

    save(fig, out / "fig2_policing_ratio_overload_phases.pdf")


# ── Figure 3 — Delivered-Throughput Box-Plot (Phases B & C) ──────────────────

def fig3_boxplot_BC(df: pd.DataFrame, out: Path) -> None:
    """Box-plot of run-level delivered Mbps for overload phases."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=False)

    for ax, phase in zip(axes, ["B", "C"]):
        sub = df[df["phase"] == phase]
        data    = [sub[sub["experiment"] == e]["delivered_mbps"].values
                   for e in EXP_ORDER]
        labels  = [EXP_LABEL[e] for e in EXP_ORDER]
        colors  = [EXP_COLOR[e] for e in EXP_ORDER]

        bp = ax.boxplot(data, patch_artist=True, widths=0.5,
                        medianprops=dict(color="black", linewidth=2))
        for patch, c in zip(bp["boxes"], colors):
            patch.set_facecolor(c)
            patch.set_alpha(0.75)

        ax.set_xticklabels(labels, rotation=15, ha="right")
        ax.set_ylabel("Delivered Throughput (Mbps)")
        ax.set_xlabel(PHASE_LABEL[phase].replace("\n", " — "))

    fig.tight_layout(pad=2.0)
    save(fig, out / "fig3_throughput_boxplot_phases_BC.pdf")


# ── Figure 4 — Relative Throughput vs E1-Static Baseline ─────────────────────

def fig4_relative_throughput(df: pd.DataFrame, out: Path) -> None:
    """Normalised delivered Mbps relative to E1-Static per phase."""
    ref = (df[df["experiment"] == "e1_static"]
           .groupby("phase")["delivered_mbps"].mean())

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(PHASE_ORDER))
    width = 0.22

    exps_no_ref = [e for e in EXP_ORDER if e != "e1_static"]
    n = len(exps_no_ref)
    offsets = np.linspace(-(n - 1) / 2, (n - 1) / 2, n) * width

    for i, exp in enumerate(exps_no_ref):
        mn  = df[df["experiment"] == exp].groupby("phase")["delivered_mbps"].mean()
        rel = [(mn.get(p, 0) / ref[p] - 1) * 100 for p in PHASE_ORDER]
        ax.bar(x + offsets[i], rel, width,
               label=EXP_LABEL[exp], color=EXP_COLOR[exp],
               edgecolor="white", linewidth=LW)

    ax.axhline(0, color="#333333", linewidth=1.2, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels([PHASE_LABEL[p] for p in PHASE_ORDER])
    ax.set_ylabel("Δ Delivered Throughput vs. E1-Static (%)")
    ax.set_xlabel("Traffic Phase")
    ax.legend(loc="lower right", framealpha=0.9)

    save(fig, out / "fig4_relative_throughput_vs_static.pdf")


# ── Figure 5 — App-QER Policed Packets (Phases B & C) ────────────────────────

def fig5_policed_packets(df: pd.DataFrame, out: Path) -> None:
    """Grouped bar: mean app-QER-red packets (millions) per experiment × phase."""
    sub  = df[df["phase"].isin(["B", "C"])].copy()
    sub["app_qer_red_M"] = sub["app_qer_red_packets"] / 1e6
    grp  = sub.groupby(["experiment", "phase"])["app_qer_red_M"]
    mn   = grp.mean().to_dict()
    sd   = grp.std().to_dict()

    fig, ax = plt.subplots(figsize=(8, 5))
    series  = [(e, EXP_LABEL[e]) for e in EXP_ORDER]
    grouped_bar(ax, mn, sd, ["B", "C"], series, EXP_COLOR, width=0.2)

    ax.set_ylabel("App-QER Policed Packets (millions)")
    ax.set_xlabel("Traffic Phase")
    ax.set_xticklabels(["Phase B\n(Bronze Burst)", "Phase C\n(Silver Flash Crowd)"])
    ax.legend(loc="upper right", framealpha=0.9)

    save(fig, out / "fig5_app_qer_policed_packets.pdf")


# ── Figure 6 — LLM Inference Latency per Phase (Agentic) ─────────────────────

def fig6_llm_latency(df: pd.DataFrame, out: Path) -> None:
    """Box-plot of mean LLM latency per decision window, by phase."""
    ag   = df[(df["experiment"] == "e4_agentic_rtx6000_realtime") &
              df["mean_llm_latency_ms"].notna()]

    phase_vals = {p: ag[ag["phase"] == p]["mean_llm_latency_ms"].values
                  for p in PHASE_ORDER}

    fig, ax = plt.subplots(figsize=(8, 5))
    bp = ax.boxplot([phase_vals[p] for p in PHASE_ORDER],
                    patch_artist=True, widths=0.5,
                    medianprops=dict(color="black", linewidth=2))
    palette = ["#9FB9D0", "#F4A460", "#CD6889", "#8DB8AD"]
    for patch, c in zip(bp["boxes"], palette):
        patch.set_facecolor(c); patch.set_alpha(0.8)

    ax.set_xticklabels([PHASE_LABEL[p] for p in PHASE_ORDER])
    ax.set_ylabel("Mean LLM Decision Latency (ms)")
    ax.set_xlabel("Traffic Phase")

    save(fig, out / "fig6_llm_latency_per_phase.pdf")


# ── Figure 7 — Oscillations & Fallbacks per Run (Agentic) ────────────────────

def fig7_oscillations_fallbacks(df: pd.DataFrame, out: Path) -> None:
    """Bar chart: oscillations and fallbacks per run (agentic campaign)."""
    ag = df[df["experiment"] == "e4_agentic_rtx6000_realtime"].copy()

    run_osc  = ag.groupby("run")["oscillation_count"].sum()
    run_fall = ag.groupby("run")["fallback_count"].sum()
    runs     = sorted(run_osc.index, key=lambda r: int(r.split("_")[-1]))

    x     = np.arange(len(runs))
    width = 0.38

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - width / 2, [run_osc[r]  for r in runs], width,
           label="Oscillations", color="#B47CC7", edgecolor="white", linewidth=LW)
    ax.bar(x + width / 2, [run_fall[r] for r in runs], width,
           label="Fallbacks",    color="#E8A838", edgecolor="white", linewidth=LW)

    ax.set_xticks(x)
    ax.set_xticklabels([f"Run {int(r.split('_')[-1]):02d}" for r in runs],
                       rotation=30, ha="right")
    ax.set_ylabel("Count (per 60-decision run)")
    ax.set_xlabel("Agentic Run")
    ax.legend(framealpha=0.9)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    save(fig, out / "fig7_oscillations_fallbacks_per_run.pdf")


# ── Figure 8 — Token Usage vs LLM Latency (Agentic scatter) ──────────────────

def fig8_tokens_vs_latency(df: pd.DataFrame, out: Path) -> None:
    """Scatter: total tokens vs LLM decision latency, coloured by phase."""
    ag = df[(df["experiment"] == "e4_agentic_rtx6000_realtime") &
            df["mean_llm_latency_ms"].notna() &
            df["mean_total_tokens"].notna()]

    phase_colors = {"A": "#9FB9D0", "B": "#F4A460",
                    "C": "#CD6889", "D": "#8DB8AD"}

    fig, ax = plt.subplots(figsize=(8, 5))
    for phase in PHASE_ORDER:
        sub = ag[ag["phase"] == phase]
        ax.scatter(sub["mean_total_tokens"], sub["mean_llm_latency_ms"],
                   color=phase_colors[phase], label=PHASE_LABEL[phase].replace("\n", " "),
                   s=80, alpha=0.8, edgecolors="white", linewidths=0.6)

    ax.set_xlabel("Mean Total Tokens per Decision Window")
    ax.set_ylabel("Mean LLM Decision Latency (ms)")
    ax.legend(loc="lower right", framealpha=0.9)

    save(fig, out / "fig8_tokens_vs_latency_scatter.pdf")


# ── Main ──────────────────────────────────────────────────────────────────────

def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"run": str, "phase": str})

    # Numeric coercion
    for col in ["delivered_mbps", "offered_mbps", "policing_ratio",
                "app_qer_red_packets", "mean_llm_latency_ms",
                "mean_total_tokens", "action_count",
                "fallback_count", "oscillation_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["experiment"].isin(EXP_ORDER)]
    df = df[df["phase"].isin(PHASE_ORDER)]
    return df


def main():
    parser = argparse.ArgumentParser(description="Agentic B5G QoS figures")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="Path to combined_baseline_agentic_phase_metrics.csv")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="Output directory for PDF figures")
    args = parser.parse_args()

    if not args.csv.exists():
        sys.exit(f"[ERROR] CSV not found: {args.csv}\n"
                 f"  Run  python3 build_combined_metrics.py  first, or pass --csv PATH")

    args.out.mkdir(parents=True, exist_ok=True)
    df = load_data(args.csv)

    print(f"\nLoaded {len(df)} rows from {args.csv}")
    print(f"Experiments : {df['experiment'].unique().tolist()}")
    print(f"Phases      : {df['phase'].unique().tolist()}")
    print(f"Runs        : {df['run'].nunique()} unique\n")
    print(f"Writing PDFs to: {args.out.resolve()}\n")

    fig1_throughput_by_phase(df, args.out)
    fig2_policing_ratio(df, args.out)
    fig3_boxplot_BC(df, args.out)
    fig4_relative_throughput(df, args.out)
    fig5_policed_packets(df, args.out)
    fig6_llm_latency(df, args.out)
    fig7_oscillations_fallbacks(df, args.out)
    fig8_tokens_vs_latency(df, args.out)

    print("\nAll figures saved.\n")

    # ── Strategic recommendations ─────────────────────────────────────────────
    recs = """
╔═══════════════════════════════════════════════════════════════════════════════╗
║           STRATEGIC RECOMMENDATIONS FOR NEXT EXPERIMENTS                    ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                               ║
║  1.  E5 — Hysteresis Controller                                               ║
║      Add a minimum dwell time (e.g. 2 windows) before allowing MBR changes.  ║
║      Prevents the oscillatory behaviour observed in Phases B and C of E4.    ║
║      Expected result: oscillation_count ≈ 0 while maintaining similar Mbps.  ║
║                                                                               ║
║  2.  E6 — Per-Slice Telemetry Prompt                                          ║
║      Expose per-TEID byte counters to the LLM instead of aggregate Mbps.     ║
║      The model can then reason at slice granularity (Gold vs Silver vs        ║
║      Bronze protection), enabling tier-aware MBR optimisation.               ║
║                                                                               ║
║  3.  E7 — Larger / Stronger Model (e.g. Qwen2.5-72B or Llama-3-70B)          ║
║      Qwen2.5-7B produced valid actions but oscillated.  A larger model may   ║
║      produce more stable decisions and better multi-step reasoning.           ║
║      Compare latency / stability tradeoff vs 7B.                             ║
║                                                                               ║
║  4.  E8 — Prefix-Caching Enabled                                              ║
║      Re-run E4 with --enable-prefix-caching.  The system prompt is constant  ║
║      across windows; caching should cut Phase A/D latency by 30-50%.         ║
║      Validates the latency numbers as a function of prompt reuse.            ║
║                                                                               ║
║  5.  E9 — Chain-of-Thought / Scratchpad Prompt                                ║
║      Add an explicit "think step by step" reasoning section before the JSON   ║
║      action.  Measure whether structured reasoning reduces fallback_count     ║
║      (model trying to modify_mbr with the same vector).                      ║
║                                                                               ║
║  6.  E10 — Multi-Step Look-Ahead (Agentic Planning)                           ║
║      Provide the model with the phase schedule (A→B→C→D) and ask it to plan  ║
║      multiple windows ahead.  Tests whether anticipatory action reduces       ║
║      overload impact rather than only reacting.                               ║
║                                                                               ║
║  7.  Per-slice throughput logging                                              ║
║      The current pipeline exposes only aggregate Access RX / Core TX.        ║
║      Instrument BESS per-TEID counters so figures can show slice-level        ║
║      SLA compliance (Gold never starved, Bronze appropriately policed).       ║
║                                                                               ║
║  8.  Statistical significance                                                 ║
║      N=10 runs are sufficient for means but add Welch t-tests or bootstrap   ║
║      CIs comparing E4 vs E1/E2/E3 for policing ratio and delivered Mbps.     ║
║      This upgrades the plots from exploratory to publication-ready.          ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
    print(recs)


if __name__ == "__main__":
    main()

