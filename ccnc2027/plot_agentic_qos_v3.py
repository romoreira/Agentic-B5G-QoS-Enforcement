#!/usr/bin/env python3
"""
plot_agentic_qos_v3.py — minimal companion to plot_agentic_qos_v2.py.

Produces ONLY what the textual revision of Sec. V needs:

  1. figures/fig2b_pareto_ci.pdf
     Corrected version of the throughput-vs-policing figure:
     per-phase panels (B | C), mean markers with 95% CI error bars,
     raw runs as small points. No covariance ellipses.

  2. figures/stats_for_text.txt
     The numbers that fill the placeholders of the revised paragraph:
       - mean ± 95% CI of delivered throughput per controller per phase
       - Mann-Whitney U (two-sided), E4 vs E1/E2/E3, phases B and C
       - action × phase contingency from ALL agentic decisions.jsonl
         (N modify_mbr, % inside overload windows, % keep in steady,
          fallback counts per phase)
     Plus a ready-to-paste LaTeX paragraph with values substituted.

USAGE
    python3 plot_agentic_qos_v3.py
    python3 plot_agentic_qos_v3.py --csv PATH --out DIR --agentic-root DIR
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

HOME = Path.home()
DEFAULT_CSV = HOME / "agentic_qos_results/campaigns/combined_baseline_agentic_phase_metrics.csv"
DEFAULT_AG_ROOT = HOME / (
    "agentic_qos_results/campaigns/"
    "campaign_20260511_agentic_rtx6000_realtime_5slices/"
    "e4_agentic_rtx6000_realtime"
)
DEFAULT_OUT = Path("joberto_review_figures")

FS = 16
plt.rcParams.update({
    "font.size": FS, "axes.labelsize": FS, "axes.titlesize": FS,
    "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 13,
    "figure.dpi": 150, "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.7,
})

EXP_ORDER = ["e1_static", "e2_threshold", "e3_greedy", "e4_agentic_rtx6000_realtime"]
EXP_LABEL = {
    "e1_static": "E1 Static", "e2_threshold": "E2 Threshold",
    "e3_greedy": "E3 Greedy", "e4_agentic_rtx6000_realtime": "E4 Agentic",
}
EXP_COLOR = {
    "e1_static": "#4878CF", "e2_threshold": "#6ACC65",
    "e3_greedy": "#D65F5F", "e4_agentic_rtx6000_realtime": "#9B59B6",
}
OVERLOAD = ["B", "C"]
PHASES = ["A", "B", "C", "D"]


# ── helpers ──────────────────────────────────────────────────────────────────
def ci95(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return 0.0
    return stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"run": str, "phase": str})
    for c in ("delivered_mbps", "policing_ratio"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[df["experiment"].isin(EXP_ORDER) & df["phase"].isin(PHASES)]


def load_all_decisions(root: Path) -> pd.DataFrame:
    """Concatenate decisions.jsonl from every run_* under the agentic root."""
    rows = []
    for run_dir in sorted(root.glob("run_*")):
        f = run_dir / "controller" / "decisions.jsonl"
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            dec = d.get("decision", {}) or {}
            rows.append(dict(
                run=run_dir.name,
                phase=d["phase"],
                action=dec.get("action", "keep"),
                fallback=bool(d.get("fallback_used", False)),
            ))
    return pd.DataFrame(rows)


# ── 1. corrected figure ──────────────────────────────────────────────────────
def fig_pareto_ci(df: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=False)
    rng = np.random.default_rng(7)

    for ax, phase in zip(axes, OVERLOAD):
        sub = df[df["phase"] == phase]
        for e in EXP_ORDER:
            g = sub[sub["experiment"] == e]
            x, y = g["delivered_mbps"].values, g["policing_ratio"].values
            if len(x) == 0:
                continue
            is_ag = "agentic" in e
            # raw runs (jittered slightly in y so identical values remain visible)
            ax.scatter(x, y + rng.normal(0, y.std(ddof=0) * 0.05 + 1e-6, len(y)),
                       s=36, color=EXP_COLOR[e], alpha=0.35,
                       edgecolors="none", zorder=3)
            # mean with 95% CI on both axes
            ax.errorbar(x.mean(), y.mean(),
                        xerr=ci95(x), yerr=ci95(y),
                        fmt="P" if is_ag else "o",
                        ms=14 if is_ag else 10,
                        color=EXP_COLOR[e],
                        markeredgecolor="black", markeredgewidth=1.1,
                        ecolor=EXP_COLOR[e], elinewidth=2.2, capsize=5,
                        label=EXP_LABEL[e], zorder=6 if is_ag else 5)
        ax.set_xlabel(f"Delivered Throughput \u00b7 Phase {phase} (Mbps)")
        ax.ticklabel_format(axis="y", useOffset=False, style="plain")

    axes[0].set_ylabel("Policing Ratio  (app-QER-red \u00f7 received)")
    axes[1].legend(loc="lower right", framealpha=0.95)

    fig.savefig(out / "fig2b_pareto_ci.pdf", bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    print(f"  \u2713  {out / 'fig2b_pareto_ci.pdf'}")


# ── 2. statistics for the revised paragraph ─────────────────────────────────
def stats_for_text(df: pd.DataFrame, dec: pd.DataFrame, out: Path) -> None:
    lines: list[str] = []
    say = lines.append
    vals: dict[str, str] = {}

    say("=" * 72)
    say("A. Delivered throughput, mean \u00b1 95% CI (n = runs)")
    say("=" * 72)
    for phase in OVERLOAD:
        say(f"\nPhase {phase}:")
        for e in EXP_ORDER:
            x = df[(df["experiment"] == e) & (df["phase"] == phase)]["delivered_mbps"].dropna().values
            m, c = x.mean(), ci95(x)
            say(f"  {EXP_LABEL[e]:<14} {m:8.2f} \u00b1 {c:5.2f} Mbps   (n={len(x)})")
            vals[f"{e}_{phase}_mean"] = f"{m:.1f}"
            vals[f"{e}_{phase}_ci"] = f"{c:.1f}"

    say("\n" + "=" * 72)
    say("B. Mann-Whitney U (two-sided), E4 vs baselines")
    say("=" * 72)
    e4 = "e4_agentic_rtx6000_realtime"
    pmax = 0.0
    for phase in OVERLOAD:
        say(f"\nPhase {phase}:")
        a = df[(df["experiment"] == e4) & (df["phase"] == phase)]["delivered_mbps"].dropna().values
        for e in EXP_ORDER[:3]:
            b = df[(df["experiment"] == e) & (df["phase"] == phase)]["delivered_mbps"].dropna().values
            if len(a) < 2 or len(b) < 2:
                say(f"  vs {EXP_LABEL[e]:<14} insufficient data")
                continue
            u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            pmax = max(pmax, p)
            say(f"  vs {EXP_LABEL[e]:<14} U = {u:6.1f}   p = {p:.4g}")
    vals["pmax"] = f"{pmax:.3g}"

    say("\n" + "=" * 72)
    say("C. Agentic audit logs: action \u00d7 phase contingency (all runs pooled)")
    say("=" * 72)
    if dec.empty:
        say("  decisions.jsonl not found \u2014 contingency skipped")
        vals.update(N="[N]", Z="[Z]", S="[S]")
    else:
        tab = pd.crosstab(dec["action"], dec["phase"]).reindex(columns=PHASES, fill_value=0)
        say("\n" + tab.to_string())
        mod = dec[dec["action"] == "modify_mbr"]
        n_mod = len(mod)
        pct_over = 100.0 * (mod["phase"].isin(OVERLOAD)).mean() if n_mod else 0.0
        steady = dec[dec["phase"] == "A"]
        pct_keep = 100.0 * (steady["action"] == "keep").mean() if len(steady) else 0.0
        say(f"\n  modify_mbr total (N)          : {n_mod}")
        say(f"  % of modify_mbr in overload   : {pct_over:.1f}%")
        say(f"  % keep in steady (Phase A)    : {pct_keep:.1f}%")
        say("\n  fallbacks per phase:")
        fb = dec[dec["fallback"]].groupby("phase").size().reindex(PHASES, fill_value=0)
        for p in PHASES:
            say(f"    Phase {p}: {fb[p]}")
        vals.update(N=str(n_mod), Z=f"{pct_over:.0f}", S=f"{pct_keep:.0f}")

    say("\n" + "=" * 72)
    say("D. Ready-to-paste LaTeX (revised paragraph, values substituted)")
    say("=" * 72)
    g = lambda k: vals.get(k, "[?]")
    say(rf"""
Figures~\ref{{fig:pareto_throughput_policing}} and~\ref{{fig:agentic_window}}
jointly test whether the agentic loop constitutes a distinct control regime.
Two rival explanations must be ruled out: that E4 behaves as a passive
baseline in disguise, or as a rigid threshold rule.
Figure~\ref{{fig:pareto_throughput_policing}} rejects the first at the
aggregate level: across ten runs, E4 delivers
${g('e4_agentic_rtx6000_realtime_B_mean')} \pm {g('e4_agentic_rtx6000_realtime_B_ci')}$~Mbps in Phase~B,
significantly below static (${g('e1_static_B_mean')} \pm {g('e1_static_B_ci')}$) and
greedy (${g('e3_greedy_B_mean')} \pm {g('e3_greedy_B_ci')}$), yet above
threshold (${g('e2_threshold_B_mean')} \pm {g('e2_threshold_B_ci')}$)
(Mann--Whitney, $p \leq {g('pmax')}$ across all pairwise tests in Phases B and~C).
Figure~\ref{{fig:agentic_window}} rejects the second at the window level: of
the ${g('N')}$ \textit{{modify\_mbr}} actions recorded in the audit logs,
${g('Z')}\%$ fall inside overload windows, while ${g('S')}\%$ of steady-state
windows resolve to \textit{{keep}} --- actions follow telemetry context, not a
fixed utilization level. The policing ratio, by contrast, separates phases
rather than controllers, indicating that E4 changes \emph{{how}} overload
demand is shaped, not \emph{{how much}} enforcement the datapath applies.
""")

    text = "\n".join(lines)
    (out / "stats_for_text.txt").write_text(text)
    print(text)
    print(f"  \u2713  {out / 'stats_for_text.txt'}")


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Minimal figures+stats for the Sec. V revision")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--agentic-root", type=Path, default=DEFAULT_AG_ROOT)
    args = ap.parse_args()

    if not args.csv.exists():
        sys.exit(f"[ERROR] CSV not found: {args.csv}")
    args.out.mkdir(parents=True, exist_ok=True)

    df = load_csv(args.csv)
    dec = load_all_decisions(args.agentic_root)
    print(f"\nLoaded {len(df)} CSV rows; {len(dec)} decision windows "
          f"from {dec['run'].nunique() if not dec.empty else 0} runs\n")

    fig_pareto_ci(df, args.out)
    stats_for_text(df, dec, args.out)


if __name__ == "__main__":
    main()
