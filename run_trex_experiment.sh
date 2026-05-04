#!/usr/bin/env bash
set -euo pipefail

# run_trex_experiment.sh
#
# Runs a TRex STL profile and stores experiment artifacts in a local directory.
# Optionally triggers UPF snapshots before and after the TRex run via SSH.
#
# Expected TRex-side runner:
#   /opt/trex/v3.08/automation/exp2/run_profile.py
#
# Expected UPF-side snapshot script:
#   ~/bess-upf/config/collect_upf_snapshot.sh
#
# Example, throughput/capacity mode:
#   ./run_trex_experiment.sh \
#     --name dpdk_3slice_30_60_90_run001 \
#     --profile /opt/trex/v3.08/automation/exp2/exp2_3slice_rates.py \
#     --duration 30 \
#     --trex-mode dpdk \
#     --upf-host ubuntu@192.168.90.1
#
# Example, latency mode:
#   ./run_trex_experiment.sh \
#     --name dpdk_latency_run001 \
#     --profile /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py \
#     --duration 30 \
#     --trex-mode software \
#     --upf-host ubuntu@192.168.90.1

TREX_DIR="/opt/trex/v3.08"
RUNNER="${TREX_DIR}/automation/exp2/run_profile.py"
OUT_BASE="${HOME}/experiments"

NAME=""
PROFILE=""
DURATION="30"
MULT="1"
TREX_MODE="dpdk"          # dpdk or software
UPF_HOST=""               # optional, e.g., ubuntu@192.168.90.1
UPF_SNAPSHOT_SCRIPT="~/bess-upf/config/collect_upf_snapshot.sh"
NO_START_TREX="false"     # set true if TRex server is already running
TX_PORT="0"
RX_PORT="1"

usage() {
  cat <<EOF
Usage:
  $0 --name EXP_NAME --profile PROFILE.py [options]

Required:
  --name NAME                  Experiment name
  --profile FILE               TRex STL profile path

Options:
  --duration SEC               Run duration, default: 30
  --mult MULT                  TRex multiplier, default: 1
  --trex-mode MODE             dpdk or software, default: dpdk
  --upf-host USER@HOST         Optional UPF SSH target for before/after snapshots
  --upf-snapshot-script PATH   Remote UPF snapshot script, default: ~/bess-upf/config/collect_upf_snapshot.sh
  --out-base DIR               Local output base directory, default: ~/experiments
  --no-start-trex              Do not start/restart TRex server
  --tx-port PORT               TX port, default: 0
  --rx-port PORT               RX/service port, default: 1
  -h, --help                   Show this help

Examples:
  $0 --name dpdk_3slice_run001 \\
     --profile /opt/trex/v3.08/automation/exp2/exp2_3slice_rates.py \\
     --duration 30 \\
     --trex-mode dpdk \\
     --upf-host ubuntu@192.168.90.1

  $0 --name dpdk_latency_run001 \\
     --profile /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py \\
     --duration 30 \\
     --trex-mode software \\
     --upf-host ubuntu@192.168.90.1
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      NAME="$2"; shift 2 ;;
    --profile)
      PROFILE="$2"; shift 2 ;;
    --duration)
      DURATION="$2"; shift 2 ;;
    --mult)
      MULT="$2"; shift 2 ;;
    --trex-mode)
      TREX_MODE="$2"; shift 2 ;;
    --upf-host)
      UPF_HOST="$2"; shift 2 ;;
    --upf-snapshot-script)
      UPF_SNAPSHOT_SCRIPT="$2"; shift 2 ;;
    --out-base)
      OUT_BASE="$2"; shift 2 ;;
    --no-start-trex)
      NO_START_TREX="true"; shift ;;
    --tx-port)
      TX_PORT="$2"; shift 2 ;;
    --rx-port)
      RX_PORT="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1 ;;
  esac
done

if [[ -z "$NAME" || -z "$PROFILE" ]]; then
  echo "ERROR: --name and --profile are required." >&2
  usage
  exit 1
fi

if [[ ! -f "$PROFILE" ]]; then
  echo "ERROR: profile not found: $PROFILE" >&2
  exit 1
fi

if [[ ! -f "$RUNNER" ]]; then
  echo "ERROR: TRex runner not found: $RUNNER" >&2
  echo "Create run_profile.py first." >&2
  exit 1
fi

if [[ "$TREX_MODE" != "dpdk" && "$TREX_MODE" != "software" ]]; then
  echo "ERROR: --trex-mode must be either dpdk or software." >&2
  exit 1
fi

EXP_DIR="${OUT_BASE}/${NAME}"
mkdir -p "$EXP_DIR"

LOG_FILE="${EXP_DIR}/experiment.log"
TREX_JSON="${EXP_DIR}/trex.json"
TREX_SERVER_LOG="${EXP_DIR}/trex_server_${TREX_MODE}.log"
META_FILE="${EXP_DIR}/metadata.txt"

log() {
  echo "[$(date -Is)] $*" | tee -a "$LOG_FILE"
}

write_metadata() {
  {
    echo "name=${NAME}"
    echo "timestamp=$(date -Is)"
    echo "host=$(hostname)"
    echo "trex_dir=${TREX_DIR}"
    echo "profile=${PROFILE}"
    echo "duration=${DURATION}"
    echo "mult=${MULT}"
    echo "trex_mode=${TREX_MODE}"
    echo "tx_port=${TX_PORT}"
    echo "rx_port=${RX_PORT}"
    echo "upf_host=${UPF_HOST}"
    echo "out_dir=${EXP_DIR}"
  } > "$META_FILE"
}

start_trex_server() {
  if [[ "$NO_START_TREX" == "true" ]]; then
    log "Skipping TRex server start because --no-start-trex was set."
    return
  fi

  log "Stopping any existing TRex server."
  sudo pkill -f t-rex-64 2>/dev/null || true
  sleep 2

  cd "$TREX_DIR"

  if [[ "$TREX_MODE" == "software" ]]; then
    log "Starting TRex in software mode."
    sudo nohup ./t-rex-64 -i --software --no-ofed-check -c 8 > "$TREX_SERVER_LOG" 2>&1 &
  else
    log "Starting TRex in DPDK mode."
    sudo nohup ./t-rex-64 -i --no-ofed-check -c 8 > "$TREX_SERVER_LOG" 2>&1 &
  fi

  log "Waiting for TRex server to initialize."
  sleep 8

  log "TRex server log tail:"
  tail -40 "$TREX_SERVER_LOG" | tee -a "$LOG_FILE" || true
}

collect_upf_snapshot() {
  local tag="$1"

  if [[ -z "$UPF_HOST" ]]; then
    log "UPF host not provided, skipping UPF ${tag} snapshot."
    return
  fi

  local remote_file="/tmp/${NAME}_upf_${tag}.txt"
  local local_file="${EXP_DIR}/upf_${tag}.txt"

  log "Collecting UPF ${tag} snapshot on ${UPF_HOST}."

  ssh "$UPF_HOST" "bash -lc '${UPF_SNAPSHOT_SCRIPT} ${remote_file}'" | tee -a "$LOG_FILE"

  log "Copying UPF ${tag} snapshot to ${local_file}."
  scp "${UPF_HOST}:${remote_file}" "$local_file" >> "$LOG_FILE" 2>&1

  log "UPF ${tag} snapshot saved: ${local_file}"
}

run_trex_profile() {
  log "Running TRex profile."
  log "Profile: ${PROFILE}"
  log "Duration: ${DURATION}"
  log "Multiplier: ${MULT}"

  cd "$TREX_DIR"

  sudo python3 "$RUNNER" \
    --profile "$PROFILE" \
    --duration "$DURATION" \
    --mult "$MULT" \
    --tx-port "$TX_PORT" \
    --rx-port "$RX_PORT" \
    --out "$TREX_JSON" | tee -a "$LOG_FILE"

  log "TRex JSON saved: ${TREX_JSON}"
}

extract_quick_summary() {
  local summary="${EXP_DIR}/summary.txt"

  {
    echo "Experiment: ${NAME}"
    echo "Timestamp: $(date -Is)"
    echo
    echo "Profile: ${PROFILE}"
    echo "Duration: ${DURATION}"
    echo "TRex mode: ${TREX_MODE}"
    echo
    echo "Artifacts:"
    echo "  ${META_FILE}"
    echo "  ${LOG_FILE}"
    echo "  ${TREX_JSON}"
    [[ -f "${EXP_DIR}/upf_before.txt" ]] && echo "  ${EXP_DIR}/upf_before.txt"
    [[ -f "${EXP_DIR}/upf_after.txt" ]] && echo "  ${EXP_DIR}/upf_after.txt"
    echo
    echo "Quick JSON keys:"
    if command -v jq >/dev/null 2>&1 && [[ -f "$TREX_JSON" ]]; then
      jq '.stats | keys' "$TREX_JSON" 2>/dev/null || true
    else
      echo "jq not available or trex.json missing."
    fi
  } > "$summary"

  log "Summary saved: ${summary}"
}

main() {
  write_metadata
  log "Experiment directory: ${EXP_DIR}"

  start_trex_server

  collect_upf_snapshot "before"

  run_trex_profile

  collect_upf_snapshot "after"

  extract_quick_summary

  log "Done."
  log "Experiment artifacts are in: ${EXP_DIR}"
}

main

