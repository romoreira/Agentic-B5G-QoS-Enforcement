#!/usr/bin/env bash
set -euo pipefail

CAMPAIGN_ROOT="$HOME/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices"
EXP_DIR="$CAMPAIGN_ROOT/e4b_agentic_hysteresis_realtime"

reset_mbr() {
  echo "[INFO] Resetting MBR to initial vector"
  python3 "$HOME/agentic_qos_scripts/agentic_apply_once.py" --reset || true
}

trap reset_mbr EXIT INT TERM

reset_mbr

if [ -d "$EXP_DIR" ]; then
  find "$EXP_DIR" -maxdepth 1 -type d -name 'run_*' -exec rm -rf {} +
fi

for RUN in $(seq -w 1 10); do
  echo "============================================================"
  echo "[INFO] Starting run_${RUN}"
  echo "============================================================"

  python3 "$HOME/agentic_qos_scripts/run_agentic_realtime_hysteresis.py" \
    --window-sec 10 \
    --windows-per-phase 6 \
    --run-name "run_${RUN}"

  python3 "$HOME/agentic_qos_scripts/analyze_agentic_realtime_run.py" \
    --run-dir "$EXP_DIR/run_${RUN}"

  reset_mbr

  echo "[INFO] Finished run_${RUN}"
done

echo "[INFO] Campaign complete"
find "$EXP_DIR" -maxdepth 1 -type d -name 'run_*' | sort | wc -l
