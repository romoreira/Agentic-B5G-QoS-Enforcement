#!/usr/bin/env python3
"""
Agentic B5G QoS — sophisticated visualizations
8 individual PDFs.  Font 16.  No plt.title.  EN-US labels.

Designed to surface the *real* advantages of the agentic controller:
    – decision variance / reasoning footprint  (ridge, parallel coords)
    – exclusive window-resolved telemetry      (trajectory)
    – multi-dimensional positioning             (radar, heatmap)
    – trade-off region in (Mbps, policing)     (Pareto scatter, ECDF)
    – control-loop economics                    (joint scatter w/ marginals)

USAGE
    python3 plot_agentic_qos.py
    python3 plot_agentic_qos.py --csv PATH --out DIR --agentic-run run_01
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

# ── Paths ────────────────────────────────────────────────────────────────────
HOME = Path.home()
DEFAULT_CSV = HOME / "agentic_qos_results/campaigns/combined_baseline_agentic_phase_metrics.csv"
DEFAULT_AG_ROOT = HOME / (
    "agentic_qos_results/campaigns/"
    "campaign_20260511_agentic_rtx6000_realtime_5slices/"
    "e4_agentic_rtx6000_realtime"
)
DEFAULT_OUT = Path("figures")

# ── Style ────────────────────────────────────────────────────────────────────
FS = 16
plt.rcParams.update({
    "font.size":        FS,
    "axes.labelsize":   FS,
    "axes.titlesize":   FS,
    "xtick.labelsize":  14,
    "ytick.labelsize":  14,
    "legend.fontsize":  13,
    "figure.dpi":       150,
    "pdf.fonttype":     42,
    "ps.fonttype":      42,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":        True,
    "grid.alpha":       0.25,
    "grid.linewidth":   0.7,
})

EXP_ORDER = ["e1_static", "e2_threshold", "e3_greedy", "e4_agentic_rtx6000_realtime"]
EXP_LABEL = {
    "e1_static":                   "E1 Static",
    "e2_threshold":                "E2 Threshold",
    "e3_greedy":                   "E3 Greedy",
    "e4_agentic_rtx6000_realtime": "E4 Agentic",
}
EXP_COLOR = {
    "e1_static":                   "#4878CF",
    "e2_threshold":                "#6ACC65",
    "e3_greedy":                   "#D65F5F",
    "e4_agentic_rtx6000_realtime": "#9B59B6",
}
PHASE_ORDER = ["A", "B", "C", "D"]
PHASE_LABEL = {"A": "A (Steady)", "B": "B (Bronze Burst)",
               "C": "C (Silver Flash)", "D": "D (Recovery)"}
PHASE_COLOR = {"A": "#7FA7C7", "B": "#E5A04E", "C": "#C57186", "D": "#7FB39B"}


# ── I/O helpers ──────────────────────────────────────────────────────────────
def save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    print(f"  \u2713  {path}")


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"run": str, "phase": str})
    num_cols = [
        "delivered_mbps", "offered_mbps", "policing_ratio",
        "app_qer_red_packets", "mean_llm_latency_ms",
        "mean_total_tokens", "action_count",
        "fallback_count", "oscillation_count",
        "access_rx_packets", "core_tx_packets",
        "n3_rx_drops", "n6_tx_drops",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["experiment"].isin(EXP_ORDER) & df["phase"].isin(PHASE_ORDER)]
    return df.reset_index(drop=True)


def load_agentic_decisions(run_dir: Path) -> pd.DataFrame:
    """Read decisions.jsonl → per-window DataFrame for the time-resolved plot."""
    path = run_dir / "controller" / "decisions.jsonl"
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        t   = d.get("telemetry", {})
        dec = d.get("decision", {}) or {}
        mbr = dec.get("mbr_kbps", [0]*5)
        rows.append(dict(
            phase=d["phase"],
            window=d["window_index"],
            delivered_mbps=t.get("delivered_mbps", np.nan),
            offered_mbps=t.get("offered_mbps", np.nan),
            policing_ratio=t.get("policing_ratio", 0.0),
            action=dec.get("action", "keep"),
            mbr_s5=mbr[4] / 1000 if len(mbr) >= 5 else np.nan,  # Mbps
            latency_ms=d.get("decision_latency_ms", np.nan),
            fallback=bool(d.get("fallback_used", False)),
        ))
    out = pd.DataFrame(rows)
    if not out.empty:
        out["t_idx"] = (
            out["phase"].map({p: i for i, p in enumerate(PHASE_ORDER)}) * 6
            + (out["window"] - 1)
        )
    return out


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — Radar / Spider chart: multi-dim positioning
# ═════════════════════════════════════════════════════════════════════════════
def fig1_radar(df: pd.DataFrame, out: Path) -> None:
    metrics = ["Throughput\nin Overload",
               "QoS\nEnforcement",
               "Adaptive\nActions",
               "Run-to-Run\nConsistency",
               "Recovery\nFidelity",
               "Operational\nReliability"]

    overload = df[df["phase"].isin(["B", "C"])]

    raw = {}
    for e in EXP_ORDER:
        sub_all  = df[df["experiment"] == e]
        sub_over = overload[overload["experiment"] == e]
        thr  = sub_over["delivered_mbps"].mean()
        pol  = sub_over["policing_ratio"].mean()
        act  = sub_all["action_count"].fillna(0).groupby(sub_all["run"]).sum().mean()
        cov  = sub_over["delivered_mbps"].std() / max(sub_over["delivered_mbps"].mean(), 1e-9)
        cons = 1.0 / (1.0 + cov)
        a    = sub_all[sub_all["phase"] == "A"]["delivered_mbps"].mean()
        d    = sub_all[sub_all["phase"] == "D"]["delivered_mbps"].mean()
        rec  = 1 - abs(d - a) / max(a, 1e-9)
        drops = sub_all["n3_rx_drops"].fillna(0).sum() + sub_all["n6_tx_drops"].fillna(0).sum()
        rx    = sub_all["access_rx_packets"].sum()
        rel   = 1 - drops / max(rx, 1)
        raw[e] = [thr, pol, act, cons, rec, rel]

    arr = np.array([raw[e] for e in EXP_ORDER])
    mn, mx = arr.min(axis=0), arr.max(axis=0)
    norm = (arr - mn) / np.where(mx - mn == 0, 1, mx - mn)

    angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(9, 9), subplot_kw=dict(projection="polar"))
    for i, e in enumerate(EXP_ORDER):
        vals = norm[i].tolist() + [norm[i][0]]
        is_ag = "agentic" in e
        lw = 3.0 if is_ag else 1.8
        alpha_fill = 0.30 if is_ag else 0.12
        ax.plot(angles, vals, color=EXP_COLOR[e], linewidth=lw,
                label=EXP_LABEL[e], marker="o", markersize=7,
                zorder=4 if is_ag else 3)
        ax.fill(angles, vals, color=EXP_COLOR[e], alpha=alpha_fill,
                zorder=2 if is_ag else 1)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics, fontsize=14)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.25, 0.50, 0.75, 1.00])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=11, color="#555")
    ax.tick_params(axis="x", pad=18)
    ax.set_rlabel_position(90)
    ax.grid(color="#888888", linewidth=0.5, alpha=0.6)
    ax.spines["polar"].set_color("#888888")
    ax.legend(loc="upper right", bbox_to_anchor=(1.32, 1.10),
              framealpha=0.95, handlelength=2.4)

    save(fig, out / "fig1_radar_multidimensional.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — Pareto scatter: throughput vs policing trade-off
# ═════════════════════════════════════════════════════════════════════════════
def fig2_pareto(df: pd.DataFrame, out: Path) -> None:
    over = df[df["phase"].isin(["B", "C"])].copy()

    fig, ax = plt.subplots(figsize=(9, 6.5))

    for e in EXP_ORDER:
        sub = over[over["experiment"] == e]
        is_ag = "agentic" in e
        ax.scatter(sub["delivered_mbps"], sub["policing_ratio"],
                   s=130 if is_ag else 80,
                   marker="P" if is_ag else "o",
                   alpha=0.85 if is_ag else 0.55,
                   color=EXP_COLOR[e],
                   edgecolors="black" if is_ag else "white",
                   linewidths=1.0 if is_ag else 0.6,
                   label=EXP_LABEL[e],
                   zorder=5 if is_ag else 3)
        cx = sub["delivered_mbps"].mean()
        cy = sub["policing_ratio"].mean()
        sx = sub["delivered_mbps"].std()  * 2
        sy = sub["policing_ratio"].std() * 2
        if not (np.isnan(sx) or np.isnan(sy)):
            ellipse = mpatches.Ellipse((cx, cy), max(sx, 1), max(sy, 0.001),
                                       facecolor=EXP_COLOR[e], alpha=0.10,
                                       edgecolor=EXP_COLOR[e], linewidth=1.2,
                                       linestyle="--", zorder=1)
            ax.add_patch(ellipse)

    for phase in ["B", "C"]:
        for e in EXP_ORDER:
            sub = over[(over["experiment"] == e) & (over["phase"] == phase)]
            cx = sub["delivered_mbps"].mean()
            cy = sub["policing_ratio"].mean()
            if not np.isnan(cx):
                ax.annotate(phase, xy=(cx, cy), xytext=(6, 6),
                            textcoords="offset points",
                            fontsize=11, color="#444", weight="bold")

    ax.set_xlabel("Delivered Throughput in Overload (Mbps)")
    ax.set_ylabel("Policing Ratio  (app-QER-red \u00f7 received)")
    ax.legend(loc="upper left", framealpha=0.95)
    ax.text(0.02, 0.96, "\u2190 lower throughput \u00b7 more enforcement",
            transform=ax.transAxes, fontsize=11, color="#666", style="italic")
    ax.text(0.98, 0.04, "higher throughput \u00b7 less enforcement \u2192",
            transform=ax.transAxes, fontsize=11, color="#666",
            style="italic", ha="right")

    save(fig, out / "fig2_pareto_throughput_vs_policing.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — Ridge (joy) plot of delivered_mbps in Phase C
# ═════════════════════════════════════════════════════════════════════════════
def fig3_ridge(df: pd.DataFrame, out: Path) -> None:
    phase_pick = "C"
    sub = df[df["phase"] == phase_pick]

    fig, ax = plt.subplots(figsize=(10, 6))
    xmin = sub["delivered_mbps"].min() - 2
    xmax = sub["delivered_mbps"].max() + 2
    x = np.linspace(xmin, xmax, 600)

    spacing = 1.0
    labels_y = []

    for i, e in enumerate(reversed(EXP_ORDER)):
        data = sub[sub["experiment"] == e]["delivered_mbps"].values
        offset = i * spacing
        labels_y.append(offset)

        is_ag = "agentic" in e
        if len(data) < 2 or data.std() < 1e-6:
            ax.vlines(data.mean(), offset, offset + 0.85,
                      color=EXP_COLOR[e], linewidth=4, alpha=0.85)
            ax.scatter([data.mean()], [offset], s=80,
                       color=EXP_COLOR[e], edgecolor="black", linewidth=1.2,
                       zorder=5)
        else:
            kde = gaussian_kde(data, bw_method=0.4)
            y = kde(x)
            y = y / y.max() * 0.85
            ax.fill_between(x, offset, offset + y,
                            color=EXP_COLOR[e], alpha=0.65,
                            edgecolor=EXP_COLOR[e], linewidth=2,
                            zorder=4 if is_ag else 3)
            ax.scatter([data.mean()], [offset + 0.05], s=60,
                       color="white", edgecolor=EXP_COLOR[e],
                       linewidth=2, zorder=5)
            ax.scatter(data, [offset - 0.05] * len(data),
                       marker="|", color=EXP_COLOR[e], s=120, linewidth=1.5,
                       alpha=0.7)

    ax.set_yticks(labels_y)
    ax.set_yticklabels([EXP_LABEL[e] for e in reversed(EXP_ORDER)])
    ax.set_xlabel(f"Delivered Throughput in Phase {phase_pick} (Mbps)")
    ax.set_ylabel("")
    ax.grid(axis="x", alpha=0.3)
    ax.grid(axis="y", alpha=0)
    ax.set_ylim(-0.5, len(EXP_ORDER) * spacing + 0.5)

    ag_data = sub[sub["experiment"] == "e4_agentic_rtx6000_realtime"]["delivered_mbps"]
    if len(ag_data) > 1:
        ax.annotate(f"agentic \u03c3 = {ag_data.std():.3f}\n\u2192 active reasoning",
                    xy=(ag_data.mean(), 0.85), xytext=(15, 35),
                    textcoords="offset points",
                    fontsize=12, color="#2c2c2c",
                    bbox=dict(boxstyle="round,pad=0.4",
                              facecolor="white", edgecolor="#9B59B6", linewidth=1.2),
                    arrowprops=dict(arrowstyle="->",
                                    connectionstyle="arc3,rad=-0.2",
                                    color="#9B59B6"))

    save(fig, out / "fig3_ridge_throughput_distribution_phaseC.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — Heatmap of z-scores
# ═════════════════════════════════════════════════════════════════════════════
def fig4_heatmap(df: pd.DataFrame, out: Path) -> None:
    metric_funcs = {
        "Throughput \u00b7 A (Mbps)":  lambda s: s[s["phase"] == "A"]["delivered_mbps"].mean(),
        "Throughput \u00b7 B (Mbps)":  lambda s: s[s["phase"] == "B"]["delivered_mbps"].mean(),
        "Throughput \u00b7 C (Mbps)":  lambda s: s[s["phase"] == "C"]["delivered_mbps"].mean(),
        "Throughput \u00b7 D (Mbps)":  lambda s: s[s["phase"] == "D"]["delivered_mbps"].mean(),
        "Policing \u00b7 B (ratio)":   lambda s: s[s["phase"] == "B"]["policing_ratio"].mean(),
        "Policing \u00b7 C (ratio)":   lambda s: s[s["phase"] == "C"]["policing_ratio"].mean(),
        "Decision variance \u00b7 BC": lambda s: s[s["phase"].isin(["B","C"])]["delivered_mbps"].std(),
        "Adaptive actions / run":      lambda s: s["action_count"].fillna(0).groupby(s["run"]).sum().mean(),
    }

    M = np.zeros((len(metric_funcs), len(EXP_ORDER)))
    for j, e in enumerate(EXP_ORDER):
        sub = df[df["experiment"] == e]
        for i, (_, fn) in enumerate(metric_funcs.items()):
            try:
                M[i, j] = fn(sub)
            except Exception:
                M[i, j] = np.nan
    M = np.nan_to_num(M, nan=0.0)

    mu = M.mean(axis=1, keepdims=True)
    sd = M.std(axis=1, keepdims=True)
    sd[sd == 0] = 1
    Z  = (M - mu) / sd

    fig, ax = plt.subplots(figsize=(9, 7))
    im = ax.imshow(Z, cmap="RdBu_r", aspect="auto", vmin=-1.8, vmax=1.8)

    ax.set_xticks(range(len(EXP_ORDER)))
    ax.set_xticklabels([EXP_LABEL[e] for e in EXP_ORDER], rotation=15, ha="right")
    ax.set_yticks(range(len(metric_funcs)))
    ax.set_yticklabels(list(metric_funcs.keys()))

    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            val = M[i, j]
            label = (f"{val:.0f}" if abs(val) >= 100 else
                     f"{val:.2f}" if abs(val) >= 1   else
                     f"{val:.3f}")
            color = "white" if abs(Z[i, j]) > 1.1 else "#222"
            ax.text(j, i, label, ha="center", va="center",
                    fontsize=12, color=color, weight="bold")

    cbar = plt.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
    cbar.set_label("z-score across experiments", fontsize=14)
    cbar.ax.tick_params(labelsize=12)

    ax.grid(False)
    ax.set_xlim(-0.5, len(EXP_ORDER) - 0.5)
    ax.set_ylim(len(metric_funcs) - 0.5, -0.5)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#888")

    save(fig, out / "fig4_heatmap_zscore_matrix.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — Window-resolved trajectory (agentic exclusive)
# ═════════════════════════════════════════════════════════════════════════════
def fig5_window_trajectory(dec: pd.DataFrame, out: Path) -> None:
    if dec.empty:
        print("  \u26a0  fig5: decisions.jsonl not found; skipping")
        return

    dec = dec.sort_values("t_idx").reset_index(drop=True)
    n = len(dec)

    fig = plt.figure(figsize=(12, 6.5))
    gs  = fig.add_gridspec(2, 1, height_ratios=[3, 1.2], hspace=0.10)
    ax  = fig.add_subplot(gs[0])
    axL = fig.add_subplot(gs[1], sharex=ax)

    for i, p in enumerate(PHASE_ORDER):
        ax.axvspan(i * 6 - 0.5, (i + 1) * 6 - 0.5,
                   color=PHASE_COLOR[p], alpha=0.10, zorder=0)
        axL.axvspan(i * 6 - 0.5, (i + 1) * 6 - 0.5,
                    color=PHASE_COLOR[p], alpha=0.10, zorder=0)
        ax.text(i * 6 + 2.5, 1.02,
                f"Phase {p}", transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=13, color="#444",
                weight="bold")

    ax.plot(dec["t_idx"], dec["offered_mbps"], color="#888888",
            linewidth=2, linestyle="--", label="Offered (Mbps)", zorder=3)
    ax.plot(dec["t_idx"], dec["delivered_mbps"], color="#9B59B6",
            linewidth=2.5, marker="o", markersize=6,
            markerfacecolor="white", markeredgewidth=2,
            label="Delivered (Mbps)", zorder=5)

    mod = dec[dec["action"] == "modify_mbr"]
    fbk = dec[dec["fallback"] == True]
    if not mod.empty:
        ax.scatter(mod["t_idx"], mod["delivered_mbps"],
                   s=200, marker="^", color="#27AE60",
                   edgecolor="black", linewidth=1.2,
                   label="modify_mbr action", zorder=7)
    if not fbk.empty:
        ax.scatter(fbk["t_idx"], fbk["delivered_mbps"],
                   s=160, marker="X", color="#E74C3C",
                   edgecolor="black", linewidth=1.0,
                   label="fallback", zorder=8)

    ax.set_ylabel("Throughput (Mbps)")
    ax.legend(loc="center left", bbox_to_anchor=(1.005, 0.5),
              framealpha=0.95, handlelength=2.6)
    ax.tick_params(labelbottom=False)

    axL.bar(dec["t_idx"], dec["latency_ms"], width=0.78,
            color="#34495E", alpha=0.7, edgecolor="white", linewidth=0.7)
    axL.set_xlabel("Decision Window  (6 windows \u00d7 4 phases = 24)")
    axL.set_ylabel("LLM Latency (ms)")
    axL.set_xticks(range(0, n, 2))

    save(fig, out / "fig5_agentic_window_trajectory.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 6 — ECDF of delivered throughput in overload phases
# ═════════════════════════════════════════════════════════════════════════════
def fig6_ecdf(df: pd.DataFrame, out: Path) -> None:
    over = df[df["phase"].isin(["B", "C"])]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)

    for ax, phase in zip(axes, ["B", "C"]):
        sub = over[over["phase"] == phase]
        for e in EXP_ORDER:
            data = np.sort(sub[sub["experiment"] == e]["delivered_mbps"].values)
            if len(data) == 0:
                continue
            y = np.arange(1, len(data) + 1) / len(data)
            is_ag = "agentic" in e
            ax.step(data, y, where="post",
                    linewidth=3.2 if is_ag else 1.8,
                    color=EXP_COLOR[e], label=EXP_LABEL[e],
                    alpha=0.95 if is_ag else 0.75,
                    zorder=5 if is_ag else 3)
            ax.axvline(np.median(data), color=EXP_COLOR[e],
                       linestyle=":", linewidth=1, alpha=0.5)
        ax.set_xlabel(f"Delivered Throughput \u00b7 Phase {phase} (Mbps)")
        ax.set_ylim(-0.02, 1.02)
        ax.grid(True, alpha=0.3)

    axes[0].set_ylabel("Empirical CDF")
    axes[1].legend(loc="lower right", framealpha=0.95)

    save(fig, out / "fig6_ecdf_overload_phases.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 7 — Parallel coordinates: per-run multi-phase trajectories
# ═════════════════════════════════════════════════════════════════════════════
def fig7_parallel_coordinates(df: pd.DataFrame, out: Path) -> None:
    pivot = (df.pivot_table(index=["experiment", "run"],
                            columns="phase",
                            values="delivered_mbps",
                            aggfunc="mean")
               .reindex(columns=PHASE_ORDER)
               .reset_index())

    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(PHASE_ORDER))
    rng = np.random.default_rng(42)

    for e in EXP_ORDER:
        sub = pivot[pivot["experiment"] == e]
        is_ag = "agentic" in e
        for _, row in sub.iterrows():
            y = row[PHASE_ORDER].values.astype(float)
            jitter = rng.normal(0, 0.04, size=len(x))
            ax.plot(x + jitter, y, color=EXP_COLOR[e],
                    linewidth=2.2 if is_ag else 1.0,
                    alpha=0.85  if is_ag else 0.45,
                    marker="o", markersize=5,
                    zorder=5 if is_ag else 3)

    for e in EXP_ORDER:
        sub = pivot[pivot["experiment"] == e]
        y_mean = sub[PHASE_ORDER].mean(axis=0).values
        ax.plot(x, y_mean, color=EXP_COLOR[e], linewidth=4,
                marker="D", markersize=10, markerfacecolor="white",
                markeredgewidth=2.5, label=EXP_LABEL[e] + "  (mean)",
                zorder=10)

    ax.set_xticks(x)
    ax.set_xticklabels([PHASE_LABEL[p] for p in PHASE_ORDER])
    ax.set_ylabel("Delivered Throughput (Mbps)")
    ax.set_xlabel("Traffic Phase")
    ax.legend(loc="upper left", framealpha=0.95, ncol=2)

    for xi in x:
        ax.axvline(xi, color="#aaaaaa", linewidth=0.5, alpha=0.4, zorder=0)

    save(fig, out / "fig7_parallel_coordinates.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 8 — Joint scatter with marginal distributions
# ═════════════════════════════════════════════════════════════════════════════
def fig8_joint_scatter(df: pd.DataFrame, out: Path) -> None:
    ag = df[(df["experiment"] == "e4_agentic_rtx6000_realtime")
            & df["mean_llm_latency_ms"].notna()
            & df["mean_total_tokens"].notna()]

    if ag.empty:
        print("  \u26a0  fig8: no agentic LLM-latency data; skipping")
        return

    fig = plt.figure(figsize=(9, 8))
    gs  = fig.add_gridspec(2, 2, width_ratios=[4, 1], height_ratios=[1, 4],
                           wspace=0.05, hspace=0.05)
    ax  = fig.add_subplot(gs[1, 0])
    axT = fig.add_subplot(gs[0, 0], sharex=ax)
    axR = fig.add_subplot(gs[1, 1], sharey=ax)

    for phase in PHASE_ORDER:
        sub = ag[ag["phase"] == phase]
        ax.scatter(sub["mean_total_tokens"], sub["mean_llm_latency_ms"],
                   color=PHASE_COLOR[phase], s=110, alpha=0.78,
                   edgecolors="white", linewidth=0.9,
                   label=f"Phase {phase}", zorder=5)

    x_all = ag["mean_total_tokens"].values
    y_all = ag["mean_llm_latency_ms"].values

    if len(x_all) > 5 and x_all.std() > 1e-6:
        xs = np.linspace(x_all.min() - 5, x_all.max() + 5, 300)
        kde_x = gaussian_kde(x_all, bw_method=0.45)(xs)
        axT.fill_between(xs, 0, kde_x, color="#9B59B6", alpha=0.35)
        axT.plot(xs, kde_x, color="#7D3C98", linewidth=2)
    axT.hist(x_all, bins=12, color="#9B59B6", alpha=0.45,
             edgecolor="white", linewidth=1, density=True)
    axT.tick_params(labelbottom=False, labelleft=False, left=False)
    axT.set_yticks([])
    for s in ("top", "right", "left"):
        axT.spines[s].set_visible(False)
    axT.grid(False)

    if len(y_all) > 5 and y_all.std() > 1e-6:
        ys = np.linspace(y_all.min() - 50, y_all.max() + 50, 300)
        kde_y = gaussian_kde(y_all, bw_method=0.45)(ys)
        axR.fill_betweenx(ys, 0, kde_y, color="#9B59B6", alpha=0.35)
        axR.plot(kde_y, ys, color="#7D3C98", linewidth=2)
    axR.hist(y_all, bins=12, orientation="horizontal",
             color="#9B59B6", alpha=0.45,
             edgecolor="white", linewidth=1, density=True)
    axR.tick_params(labelleft=False, labelbottom=False, bottom=False)
    axR.set_xticks([])
    for s in ("top", "right", "bottom"):
        axR.spines[s].set_visible(False)
    axR.grid(False)

    if len(x_all) > 2:
        slope, intercept = np.polyfit(x_all, y_all, 1)
        xr = np.array([x_all.min(), x_all.max()])
        ax.plot(xr, slope * xr + intercept, color="#333333",
                linewidth=1.3, linestyle="--", alpha=0.65, zorder=4)
        r = np.corrcoef(x_all, y_all)[0, 1]
        ax.text(0.03, 0.97, f"r = {r:.3f}",
                transform=ax.transAxes, fontsize=13,
                va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="white", edgecolor="#888"))

    ax.set_xlabel("Mean Total Tokens per Decision Window")
    ax.set_ylabel("Mean LLM Decision Latency (ms)")
    ax.legend(loc="lower right", framealpha=0.95, title="Phase",
              title_fontsize=12)

    save(fig, out / "fig8_joint_tokens_vs_latency.pdf")


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description="Agentic B5G QoS \u2014 sophisticated figures")
    ap.add_argument("--csv",          type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out",          type=Path, default=DEFAULT_OUT)
    ap.add_argument("--agentic-root", type=Path, default=DEFAULT_AG_ROOT,
                    help="Directory containing run_01..run_10 of the agentic campaign")
    ap.add_argument("--agentic-run",  type=str,  default="run_01",
                    help="Representative run used in fig5 trajectory")
    args = ap.parse_args()

    if not args.csv.exists():
        sys.exit(f"[ERROR] CSV not found: {args.csv}")

    args.out.mkdir(parents=True, exist_ok=True)
    df = load_data(args.csv)
    print(f"\nLoaded {len(df)} rows from {args.csv}")
    print(f"Writing PDFs to {args.out.resolve()}\n")

    dec = load_agentic_decisions(args.agentic_root / args.agentic_run)

    fig1_radar(df, args.out)
    fig2_pareto(df, args.out)
    fig3_ridge(df, args.out)
    fig4_heatmap(df, args.out)
    fig5_window_trajectory(dec, args.out)
    fig6_ecdf(df, args.out)
    fig7_parallel_coordinates(df, args.out)
    fig8_joint_scatter(df, args.out)

    print("\nAll figures written.\n")
    print_recommendations()


def print_recommendations() -> None:
    msg = """
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
  RESEARCH-LEVEL RECOMMENDATIONS  \u00b7  How to strengthen the contribution
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

  \u25b6 1.  PER-SLICE TELEMETRY  (highest leverage)
        Today the pipeline exposes only aggregate access-RX / core-TX.
        Add per-TEID / per-QER counters via BESS modules so every plot
        can be redone at slice granularity.  This unlocks the *real*
        QoS narrative: "Gold never starved \u00b7 Bronze policed under load".
        Without it, no reviewer will accept the SLA-compliance claim.

  \u25b6 2.  RL BASELINE  (the fair comparison)
        The community will ask "why an LLM, not PPO/DQN?"  Train a small
        DRL agent on the same MDP (same state, same action set) and add
        it as E5 alongside the others.  Headline if the LLM matches RL
        *without training data*: zero-shot operational competence.

  \u25b6 3.  STATEFUL / CONTEXTUAL PROMPTING  (kills oscillation)
        Each window prompt today is stateless.  Inject the last K=3
        decisions, action history, and recent SLA breaches into the
        prompt.  Hypothesis: oscillation_count \u2192 0 and fallback_count
        drops by \u2265 50 %.  Cheapest improvement on the controller side.

  \u25b6 4.  MODEL-SIZE SWEEP
        Qwen2.5-{1.5B, 7B, 14B, 72B}, Llama-3-{8B, 70B}, Mistral-7B-v0.3.
        Plot model size \u00d7 decision quality \u00d7 latency.  Lets operators
        pick a deployment point on the Pareto curve.  Currently there is
        one data point (7B) and no curve.

  \u25b6 5.  PREFIX-CACHING / CONSTRAINED-DECODING
        Enable vLLM prefix caching: the system prompt is identical
        every window, so cache hit-rate should be ~90 %.  Combine with
        guided JSON decoding (Outlines / XGrammar).  Expected gain:
        Phase-A/D latency drops 40-60 %, plus zero JSON parse errors.

  \u25b6 6.  ADVERSARIAL / FAILURE-INJECTION CAMPAIGN
        Run all 4 controllers under: pfcpsim restart mid-phase, N6
        link flap, 10 % packet-drop on PFCP plane, 5\u00d7 MBR-budget
        constraint.  Show that agentic *recovers* where threshold/
        greedy diverge.  This is the unique selling point of LLM
        control and is missing from the current dataset.

  \u25b6 7.  REASONING-TRACE TAXONOMY  (explainability)
        Enable Chain-of-Thought in the prompt, extract the reasoning
        for all 240 decisions, then cluster them (BERTopic / sentence-
        transformers).  Build a decision taxonomy: "burst-detection",
        "tier-protection", "recovery-restoration", etc.  Telecom
        standards bodies (3GPP SA5) require explainability \u2014 this
        delivers it.

  \u25b6 8.  LATENCY-BUDGET ANALYSIS  (deployment guidance)
        Sweep window_sec \u2208 {1, 2, 5, 10, 20, 60} and measure SLA
        breach.  Produces a curve: "agentic is viable above N ms
        control-loop period".  Gives operators a concrete rule for
        deciding whether to deploy this in their RIC.

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
"""
    print(msg)


if __name__ == "__main__":
    main()
