#!/usr/bin/env bash
set -euo pipefail

CAMPAIGN_ROOT="$HOME/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices"
EXP_DIR="$CAMPAIGN_ROOT/e4_agentic_rtx6000_realtime"

reset_mbr() {
  echo "[INFO] Resetting MBR to initial vector"
  python3 "$HOME/agentic_qos_scripts/agentic_apply_once.py" --reset || true
}

trap reset_mbr EXIT INT TERM

echo "[INFO] Starting E4 agentic RTX6000 realtime RUNS=10"
echo "[INFO] Campaign root: $CAMPAIGN_ROOT"

reset_mbr

rm -rf "$EXP_DIR"

for RUN in $(seq -w 1 10); do
  echo "============================================================"
  echo "[INFO] Starting run_${RUN}"
  echo "============================================================"

  python3 "$HOME/agentic_qos_scripts/run_agentic_realtime_run1.py" \
    --window-sec 10 \
    --windows-per-phase 6 \
    --run-name "run_${RUN}"

  python3 "$HOME/agentic_qos_scripts/analyze_agentic_realtime_run.py" \
    --run-dir "$EXP_DIR/run_${RUN}"

  reset_mbr

  echo "[INFO] Finished run_${RUN}"
done

echo "============================================================"
echo "[INFO] E4 agentic RTX6000 RUNS=10 finished"
echo "============================================================"

find "$EXP_DIR" -maxdepth 1 -type d -name 'run_*' | sort | wc -l
