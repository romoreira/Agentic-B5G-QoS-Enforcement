import json
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams.update({
    "font.size": 16,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 12,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

ROOT = Path.home() / "agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime"
runs = sorted(ROOT.glob("run_*/controller/decisions.jsonl"))

fig, ax = plt.subplots(figsize=(6.5, 3.8))

for f in runs:
    seq_x, seq_y = [], []
    for line in f.read_text().splitlines():
        d = json.loads(line)
        if d["phase"] != "B":
            continue
        seq_x.append(d["window_index"])
        seq_y.append(d["new_mbr_kbps"][4] / 1000.0)
    ax.plot(seq_x, seq_y, marker="o", alpha=0.35, linewidth=1.2)

ax.set_xlabel("Window index (Phase B)")
ax.set_ylabel("S5 MBR (Mbps)")
ax.set_xticks([1, 2, 3, 4, 5, 6])
ax.set_yticks([50, 60, 70, 80, 100])
ax.set_ylim(45, 105)
ax.grid(True, linestyle="--", alpha=0.4)

fig.tight_layout()
fig.savefig("fig_oscillation_phase_b.pdf", bbox_inches="tight")
print("Saved fig_oscillation_phase_b.{pdf,png}")
