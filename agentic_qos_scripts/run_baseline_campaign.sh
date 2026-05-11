#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Agentic QoS baseline campaign runner
# Run this script on the TRex host.
# It controls TRex and pfcpsim locally, and collects UPF metrics
# remotely through SSH.
# ============================================================

UPF_SSH="${UPF_SSH:-ubuntu@192.168.90.1}"

TREX_DIR="/opt/trex/v3.08"
TREX_PROFILE="/opt/trex/v3.08/automation/exp2/agentic_5slice_phase_profile.py"

ROOT="${ROOT:-$HOME/agentic_qos_results/campaigns/campaign_20260509_baselines_5slices}"

PHASE_DURATION="${PHASE_DURATION:-60}"
SCALE="${SCALE:-1.0}"
RUNS="${RUNS:-10}"

# Initial MBRs in kbps
INITIAL_MBR="200000,200000,150000,150000,100000"

# Alternative MBRs for simple baseline actions
# E2 threshold, contain overloaded slice in phase B, then contain silver in phase C
E2_PHASE_B_MBR="200000,200000,150000,150000,50000"
E2_PHASE_C_MBR="200000,200000,120000,120000,50000"

# E3 greedy, shifts more budget to the overloaded slices
E3_PHASE_B_MBR="180000,180000,140000,140000,160000"
E3_PHASE_C_MBR="170000,170000,180000,180000,100000"

mkdir -p "$ROOT"

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

run_remote() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$UPF_SSH" "$@"
}

collect_upf_snapshot() {
  local out_dir="$1"
  local tag="$2"

  mkdir -p "$out_dir"

  log "Collecting UPF snapshot: $tag -> $out_dir"

  run_remote "date -u +%Y-%m-%dT%H:%M:%SZ" \
    > "$out_dir/timestamp_${tag}.txt"

  run_remote "curl -s http://127.0.0.1:8080/metrics" \
    > "$out_dir/upf_metrics_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup" \
    > "$out_dir/pdrLookup_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show module gtpuDecap" \
    > "$out_dir/gtpuDecap_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show module appQERLookup" \
    > "$out_dir/appQERLookup_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show module sessionQERLookup" \
    > "$out_dir/sessionQERLookup_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup" \
    > "$out_dir/farLookup_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes" \
    > "$out_dir/routes_${tag}.txt"

  run_remote "sudo docker exec bess /opt/bess/bessctl/bessctl show port" \
    > "$out_dir/ports_${tag}.txt"

  run_remote "sudo docker ps" \
    > "$out_dir/docker_ps_${tag}.txt"

  run_remote "sudo docker logs pfcpiface --tail 80 2>&1 || true" \
    > "$out_dir/pfcpiface_logs_${tag}.txt"

  run_remote "sudo docker logs bess-routectl --tail 80 2>&1 || true" \
    > "$out_dir/bess_routectl_logs_${tag}.txt"
}

reset_mbr() {
  local mbr="$1"

  log "Setting app MBRs to $mbr kbps"

  sudo docker exec pfcpsim pfcpctl -s localhost:12345 session modify \
    --count 5 --baseID 1 \
    --app-filter "udp:any:any:allow:100" \
    --app-mbr-uplink "$mbr" \
    --app-mbr-downlink "$mbr"
}

record_action() {
  local actions_file="$1"
  local phase="$2"
  local controller="$3"
  local old_mbr="$4"
  local new_mbr="$5"
  local reason="$6"

  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$phase,$controller,\"$old_mbr\",\"$new_mbr\",\"$reason\"" \
    >> "$actions_file"
}

run_trex_phase() {
  local phase="$1"
  local run_dir="$2"

  local out_file="$run_dir/trex/phase_${phase}_console.txt"

  log "Starting TRex phase $phase for ${PHASE_DURATION}s"

  cd "$TREX_DIR"

  {
    echo "============================================================"
    echo "TRex phase $phase"
    echo "Started at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Duration requested: ${PHASE_DURATION}s"
    echo "Profile: $TREX_PROFILE"
    echo "Scale: $SCALE"
    echo "============================================================"
    echo

    sudo ./trex-console <<EOF
service --port 1
start --force -f $TREX_PROFILE -p 0 -d $PHASE_DURATION -t phase=$phase,scale=$SCALE,latency=0
quit
EOF

    echo
    echo "Traffic started. Sleeping for ${PHASE_DURATION}s before collecting stats."
  } > "$out_file" 2>&1

  sleep "$PHASE_DURATION"
  sleep 3

  {
    echo
    echo "============================================================"
    echo "Stats after phase $phase"
    echo "Collected at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "============================================================"
    echo

    sudo ./trex-console <<EOF
stats
quit
EOF

    echo
    echo "Finished at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } >> "$out_file" 2>&1

  log "Finished TRex phase $phase"
}


write_metadata() {
  local exp="$1"
  local run_id="$2"
  local controller="$3"
  local run_dir="$4"

  mkdir -p "$run_dir/metadata"

  cat > "$run_dir/metadata/run_info.env" <<EOF
campaign=campaign_20260509_baselines_5slices
experiment=$exp
run=$run_id
controller=$controller
date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
slices=5
phase_duration_s=$PHASE_DURATION
duration_total_s=$((PHASE_DURATION * 4))
scale=$SCALE
initial_caps_mbps=200,200,150,150,100
total_capacity_mbps=800
trex_profile=$TREX_PROFILE
upf_ssh=$UPF_SSH
EOF

  cat > "$run_dir/metadata/slice_config.csv" <<'EOF'
slice,tier,teid,ue_ip,initial_cap_mbps,sla_loss_max_percent,sla_throughput_min_mbps
S1,Gold,1,10.250.0.1,200,0.1,150
S2,Gold,11,10.250.0.2,200,0.1,150
S3,Silver,21,10.250.0.3,150,1.0,100
S4,Silver,31,10.250.0.4,150,1.0,100
S5,Bronze,41,10.250.0.5,100,5.0,50
EOF

  cat > "$run_dir/metadata/phase_schedule.csv" <<EOF
phase,duration_s,description
A,$PHASE_DURATION,steady load below cap
B,$PHASE_DURATION,bronze burst on S5
C,$PHASE_DURATION,flash crowd on S3 and S4
D,$PHASE_DURATION,recovery
EOF
}

prepare_run_dir() {
  local exp="$1"
  local run_id="$2"

  local run_dir="$ROOT/$exp/run_${run_id}"

  mkdir -p "$run_dir/metadata"
  mkdir -p "$run_dir/snapshots/before"
  mkdir -p "$run_dir/snapshots/phase_A_after"
  mkdir -p "$run_dir/snapshots/phase_B_after"
  mkdir -p "$run_dir/snapshots/phase_C_after"
  mkdir -p "$run_dir/snapshots/phase_D_after"
  mkdir -p "$run_dir/snapshots/after"
  mkdir -p "$run_dir/trex"
  mkdir -p "$run_dir/controller"
  mkdir -p "$run_dir/logs"

  echo "$run_dir"
}

run_one_experiment_run() {
  local exp="$1"
  local run_id="$2"

  local controller="$exp"
  local run_dir
  run_dir=$(prepare_run_dir "$exp" "$run_id")

  log "============================================================"
  log "Starting $exp run_$run_id"
  log "Run directory: $run_dir"
  log "============================================================"

  write_metadata "$exp" "$run_id" "$controller" "$run_dir"

  local actions_file="$run_dir/controller/actions.csv"
  echo 'timestamp_utc,phase,controller,old_mbr_kbps,new_mbr_kbps,reason' > "$actions_file"

  # Always start each run from the same initial MBR state.
  reset_mbr "$INITIAL_MBR"
  sleep 2

  collect_upf_snapshot "$run_dir/snapshots/before" "before"

  # -------------------------
  # Phase A
  # -------------------------
  run_trex_phase "A" "$run_dir"
  sleep 2
  collect_upf_snapshot "$run_dir/snapshots/phase_A_after" "phase_A_after"

  # -------------------------
  # Controller action before B
  # -------------------------
  if [[ "$exp" == "e1_static" ]]; then
    :
  elif [[ "$exp" == "e2_threshold" ]]; then
    reset_mbr "$E2_PHASE_B_MBR"
    record_action "$actions_file" "B" "$controller" "$INITIAL_MBR" "$E2_PHASE_B_MBR" "threshold baseline contains bronze slice during S5 burst"
  elif [[ "$exp" == "e3_greedy" ]]; then
    reset_mbr "$E3_PHASE_B_MBR"
    record_action "$actions_file" "B" "$controller" "$INITIAL_MBR" "$E3_PHASE_B_MBR" "greedy baseline reallocates capacity toward overloaded S5"
  fi

  # -------------------------
  # Phase B
  # -------------------------
  run_trex_phase "B" "$run_dir"
  sleep 2
  collect_upf_snapshot "$run_dir/snapshots/phase_B_after" "phase_B_after"

  # -------------------------
  # Controller action before C
  # -------------------------
  if [[ "$exp" == "e1_static" ]]; then
    :
  elif [[ "$exp" == "e2_threshold" ]]; then
    reset_mbr "$E2_PHASE_C_MBR"
    record_action "$actions_file" "C" "$controller" "$E2_PHASE_B_MBR" "$E2_PHASE_C_MBR" "threshold baseline contains silver slices during flash crowd"
  elif [[ "$exp" == "e3_greedy" ]]; then
    reset_mbr "$E3_PHASE_C_MBR"
    record_action "$actions_file" "C" "$controller" "$E3_PHASE_B_MBR" "$E3_PHASE_C_MBR" "greedy baseline reallocates capacity toward S3 and S4"
  fi

  # -------------------------
  # Phase C
  # -------------------------
  run_trex_phase "C" "$run_dir"
  sleep 2
  collect_upf_snapshot "$run_dir/snapshots/phase_C_after" "phase_C_after"

  # -------------------------
  # Recovery before D
  # -------------------------
  if [[ "$exp" != "e1_static" ]]; then
    reset_mbr "$INITIAL_MBR"
    record_action "$actions_file" "D" "$controller" "current" "$INITIAL_MBR" "recovery restores initial MBRs"
  fi

  # -------------------------
  # Phase D
  # -------------------------
  run_trex_phase "D" "$run_dir"
  sleep 2
  collect_upf_snapshot "$run_dir/snapshots/phase_D_after" "phase_D_after"

  collect_upf_snapshot "$run_dir/snapshots/after" "after"

  sudo docker logs pfcpsim --tail 200 > "$run_dir/logs/pfcpsim_logs.txt" 2>&1 || true
  run_remote "sudo docker logs pfcpiface --tail 200 2>&1 || true" > "$run_dir/logs/pfcpiface_logs.txt"
  run_remote "sudo docker logs bess-routectl --tail 200 2>&1 || true" > "$run_dir/logs/bess_routectl_logs.txt"

  tar -czf "$run_dir.tar.gz" -C "$(dirname "$run_dir")" "$(basename "$run_dir")"

  log "Finished $exp run_$run_id"
}

preflight() {
  log "Running preflight checks"

  test -f "$TREX_PROFILE"

  sudo docker ps | grep pfcpsim >/dev/null

  run_remote "sudo docker ps | grep bess >/dev/null"
  run_remote "curl -s http://127.0.0.1:8080/metrics | grep 'pfcp_sessions.* 5' >/dev/null"

  log "Preflight OK"
}

main() {
  preflight

  for exp in e1_static e2_threshold e3_greedy; do
    for n in $(seq -w 1 "$RUNS"); do
      run_one_experiment_run "$exp" "$n"
    done
  done

  log "Campaign finished: $ROOT"
}

main "$@"
