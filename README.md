# Agentic-B5G-QoS-Enforcement

This repository documents and implements an experimental platform for agentic QoS enforcement in B5G user plane environments.

The current prototype uses eUPF as an eBPF/XDP based UPF, pfcpsim as the PFCP control plane simulator, T-Rex as the planned high rate traffic generator, and InfluxDB as the time series backend for experiment data. An external Agentic AI controller can consume the stored measurements through APIs and interact with the deployment through SSH or HTTP based control actions.

## 1. Project goal

The goal is to evaluate whether an external Agentic AI controller can observe user plane behavior, reason about QoS conditions, and change QoS related rules during runtime.

The initial validated focus is uplink user plane processing.

```text
Traffic generator
  sends GTP-U packets on N3
        |
        v
eUPF
  receives GTP-U
  matches TEID
  applies PDR, FAR, QER
  decapsulates packets
  forwards plain IP packets to N6
        |
        v
Data network receiver
  measures per-slice traffic
```

The downlink path is not required for the first throughput experiments. The current pfcpsim generated downlink FARs have incomplete outer header creation fields, so downlink packets reach XDP but are dropped. This is documented as a known limitation for the current smoke test setup.

## 2. Physical and logical topology

Two machines are used.

### 2.1 UPF machine

Hostname used during setup

```text
upf
```

Role

```text
Runs eUPF
Runs InfluxDB
Runs eUPF collectors
Exposes eUPF API, metrics, and PFCP
```

Interfaces used during validation

```text
Management
  enp3s0
  10.30.6.145/23

N3
  enp7s0np0
  192.168.70.1/24

N6
  enp8s0np0
  192.168.80.1/24
```

Runtime environment observed during setup

```text
Linux kernel
  5.15.0-143-generic

Docker
  29.1.3

eUPF image
  ghcr.io/edgecomllc/eupf:main

XDP attach mode used for functional validation
  generic
```

### 2.2 Traffic generator machine

Hostname used during setup

```text
trex
```

Role

```text
Runs pfcpsim
Runs or will run T-Rex
Generates GTP-U traffic on N3
Receives decapsulated traffic on N6
```

Interfaces used during validation

```text
Management
  enp3s0
  10.30.6.27/23

N3
  enp7s0np0
  192.168.70.2/24

N6
  enp8s0np0
  192.168.80.2/24
```

PFCP and GTP-U relationship

```text
PFCP control plane
  pfcpsim on trex
  eUPF PFCP endpoint on 192.168.70.1:8805

GTP-U user plane
  traffic generator on 192.168.70.2
  eUPF N3 endpoint on 192.168.70.1
  UDP port 2152
```

## 3. Repository structure

Suggested repository layout.

```text
Agentic-B5G-QoS-Enforcement/
  README.md

  configs/
    docker-compose.influxdb.yml
    env.example
    eupf.env.example
    influx.env.example

  deploy/
    start_eupf.sh
    stop_eupf.sh
    start_pfcpsim.sh
    create_pfcp_sessions.sh
    validate_eupf.sh

  collectors/
    collector_eupf_influx.py
    collector_eupf_influx_auto_teid.py
    export_influx_csv.sh

  trex/
    profiles/
      gtpu_ul_multi_slice.py
    scripts/
      start_trex.sh
      stop_trex.sh
      query_trex_stats.py

  agent/
    api/
      influx_client.py
      eupf_client.py
    ssh_actions/
      read_status.sh
      modify_qer.sh
      restart_eupf.sh
    policies/
      qos_policy_baseline.md
      qos_policy_agentic.md

  experiments/
    case_01_single_slice_baseline/
    case_02_multi_slice_baseline/
    case_03_qos_enforcement/
    case_04_overload_response/
    case_05_xdp_native_mellanox/

  exports/
    README.md

  docs/
    deployment_status.md
    known_limitations.md
    troubleshooting.md
```

## 4. Validated deployment status

The following items were validated.

### 4.1 eUPF startup

eUPF successfully runs in Docker with host networking, privileged mode, mounted BPF filesystem, and mounted debugfs.

Final working eUPF command pattern

```bash
sudo docker run -d --privileged --network host \
  -v /sys/fs/bpf:/sys/fs/bpf \
  -v /sys/kernel/debug:/sys/kernel/debug:ro \
  -e UPF_INTERFACE_NAME="enp7s0np0,enp8s0np0" \
  -e UPF_XDP_ATTACH_MODE=generic \
  -e UPF_N3_ADDRESS=192.168.70.1 \
  -e UPF_PFCP_NODE_ID=192.168.70.1 \
  -e UPF_GTP_PEER="192.168.70.2:2152" \
  -e UPF_GTP_ECHO_INTERVAL=3600 \
  -e UPF_HEARTBEAT_INTERVAL=3600 \
  -e UPF_HEARTBEAT_TIMEOUT=30 \
  -e UPF_HEARTBEAT_RETRIES=100 \
  -e UPF_PFCP_ADDRESS="0.0.0.0:8805" \
  -e UPF_API_ADDRESS="0.0.0.0:8080" \
  -e UPF_METRICS_ADDRESS="0.0.0.0:9090" \
  --name eupf \
  ghcr.io/edgecomllc/eupf:main
```

Important runtime notes

```text
UPF_INTERFACE_NAME must be comma separated without brackets.

Correct
  enp7s0np0,enp8s0np0

Incorrect
  [enp7s0np0,enp8s0np0]
```

eUPF API health check

```bash
curl -s http://127.0.0.1:8080/api/v1/health
```

Expected result

```text
"OK"
```

Validated eUPF services

```text
PFCP
  UDP 8805

API
  TCP 8080

Metrics
  TCP 9090
```

### 4.2 XDP attachment

Validated XDP attachment on both interfaces.

```text
enp7s0np0
  N3

enp8s0np0
  N6
```

The eUPF logs showed successful attachment to both interfaces.

### 4.3 PFCP simulator

The working pfcpsim image was

```text
omecproject/pfcpsim:rel-1.4.3
```

Start pfcpsim on the traffic generator machine.

```bash
sudo docker run --rm -d --network host \
  --name pfcpsim \
  omecproject/pfcpsim:rel-1.4.3 \
  -p 12345 \
  --interface enp7s0np0
```

Configure pfcpsim.

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.2 \
  --remote-peer-addr 192.168.70.1
```

Associate with eUPF.

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate
```

Create three PFCP sessions.

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 \
  --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2
```

Validated association state on eUPF

```bash
curl -s http://127.0.0.1:8080/api/v1/pfcp_associations
```

Expected logical state

```text
Association with 192.168.70.2 exists
NextSessionID advances after session creation
```

### 4.4 PFCP session behavior

With three sessions, pfcpsim generated multiple TEIDs.

Observed TEIDs

```text
TEID 1
TEID 11
TEID 21
```

Observed UE addresses

```text
10.250.0.1
10.250.0.2
10.250.0.3
```

Observed mapping through BPF lookup

```text
TEID 1
  far_id 0
  qer_id 0

TEID 11
  far_id 2
  qer_id 3

TEID 21
  far_id 4
  qer_id 6
```

This confirms that TEID is the correct slice identifier for the uplink experiment.

### 4.5 Uplink GTP-U smoke test

A small Python sender was used to generate five GTP-U packets with TEID 1 from the traffic generator machine to the eUPF N3 address.

The eUPF counters confirmed successful processing.

Observed result

```text
packet_rx_gtp_pdu increased by 5
route_fib_lookup_ip4_ok increased by 5
xdp_redirect increased by 5
```

The N6 tcpdump on the traffic generator machine saw five decapsulated UDP packets.

Observed N6 packets

```text
10.250.0.1.12345 > 192.168.80.2.5555
```

This validates the uplink path.

```text
192.168.70.2
  sends GTP-U TEID 1
        |
        v
192.168.70.1
  eUPF decapsulates
        |
        v
192.168.80.2
  receives plain IP traffic
```

### 4.6 Downlink status

Downlink was tested only as a diagnostic. It is not part of the initial benchmark.

Observed behavior

```text
A packet from N6 to UE IP reaches XDP
xdp_drop increases
No GTP-U packet appears on N3
```

Likely cause

```text
pfcpsim creates downlink FAR with outer header creation fields set to zero.
The eUPF does not have enough information to encapsulate the downlink packet.
```

Current decision

```text
Do not use downlink for the initial throughput benchmark.
Use uplink only for GTP-U decapsulation and N3 to N6 forwarding.
```

## 5. Data storage layer

InfluxDB 2.7 is used as the time series backend.

### 5.1 InfluxDB service

Docker Compose service

```yaml
services:
  influxdb:
    image: influxdb:2.7
    container_name: influxdb
    restart: unless-stopped
    ports:
      - "8086:8086"
    volumes:
      - ./influxdb:/var/lib/influxdb2
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: ${INFLUX_PASSWORD}
      DOCKER_INFLUXDB_INIT_ORG: eupf-lab
      DOCKER_INFLUXDB_INIT_BUCKET: eupf_metrics
      DOCKER_INFLUXDB_INIT_ADMIN_TOKEN: ${INFLUX_TOKEN}
```

Health check

```bash
curl -s http://127.0.0.1:8086/health
```

Expected status

```text
pass
```

Important note

```text
InfluxDB initialization variables are only applied on the first creation of the data volume.
If the token is changed after initialization, the old token remains active until the volume is reset or the token is changed through InfluxDB itself.
```

### 5.2 Measurements

The current collector writes two measurements.

#### eupf_global_metrics

Purpose

```text
Stores global eUPF counters and rates.
```

Tags

```text
host
source
```

Core fields

```text
packet_rx_gtp_pdu
packet_rx_gtp_pdu_delta
packet_rx_gtp_pdu_rate_per_sec

xdp_redirect
xdp_redirect_delta
xdp_redirect_rate_per_sec

xdp_drop
xdp_drop_delta
xdp_drop_rate_per_sec

route_fib_lookup_ip4_ok
route_fib_lookup_ip4_ok_delta
route_fib_lookup_ip4_ok_rate_per_sec
```

#### eupf_teid_metrics

Purpose

```text
Stores TEID scoped eUPF state discovered from BPF maps.
```

Tags

```text
host
source
teid
slice_id
```

Core fields

```text
teid_present

far_id
qer_id
urr1_id
urr2_id

qer_ul_maximum_bitrate
qer_dl_maximum_bitrate
qer_ul_gate_status
qer_dl_gate_status
qer_qfi

far_action
far_outer_header_creation
far_teid
far_remoteip

urr1_ul_bytes
urr1_dl_bytes
urr2_ul_bytes
urr2_dl_bytes
```

Observed TEID series in InfluxDB

```text
teid 1
teid 11
teid 21
```

### 5.3 Generic TEID collector

The generic collector should not depend on a static slice map.

Expected behavior

```text
Discover pdr_map_teid_ip using bpftool
Dump active TEID keys
Lookup each TEID
Extract far_id, qer_id, urr ids
Lookup qer_map, far_map, urr_map
Write one InfluxDB series per TEID
```

Run example

```bash
cd ~/eupf-monitoring

INFLUX_TOKEN="${INFLUX_TOKEN}" \
python3 collector_eupf_influx_auto_teid.py
```

Validate TEID metrics

```bash
sudo docker exec influxdb influx query '
from(bucket: "eupf_metrics")
  |> range(start: -10m)
  |> filter(fn: (r) => r._measurement == "eupf_teid_metrics")
  |> filter(fn: (r) => r._field == "qer_id" or r._field == "qer_ul_maximum_bitrate" or r._field == "far_id")
  |> last()
' \
--org eupf-lab \
--token "${INFLUX_TOKEN}"
```

### 5.4 CSV export

Export TEID scoped metrics.

```bash
mkdir -p exports

sudo docker exec influxdb influx query --raw '
from(bucket: "eupf_metrics")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "eupf_teid_metrics")
  |> filter(fn: (r) =>
      r._field == "far_id" or
      r._field == "qer_id" or
      r._field == "qer_ul_maximum_bitrate" or
      r._field == "qer_dl_maximum_bitrate" or
      r._field == "teid_present"
  )
  |> pivot(rowKey: ["_time", "teid", "slice_id"], columnKey: ["_field"], valueColumn: "_value")
' \
--org eupf-lab \
--token "${INFLUX_TOKEN}" \
> exports/eupf_teid_metrics_last_30m.csv
```

Export global eUPF metrics.

```bash
sudo docker exec influxdb influx query --raw '
from(bucket: "eupf_metrics")
  |> range(start: -30m)
  |> filter(fn: (r) => r._measurement == "eupf_global_metrics")
  |> filter(fn: (r) =>
      r._field == "packet_rx_gtp_pdu" or
      r._field == "packet_rx_gtp_pdu_rate_per_sec" or
      r._field == "xdp_redirect" or
      r._field == "xdp_redirect_rate_per_sec" or
      r._field == "xdp_drop" or
      r._field == "xdp_drop_rate_per_sec" or
      r._field == "route_fib_lookup_ip4_ok" or
      r._field == "route_fib_lookup_ip4_ok_rate_per_sec"
  )
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
' \
--org eupf-lab \
--token "${INFLUX_TOKEN}" \
> exports/eupf_global_metrics_last_30m.csv
```

## 6. Traffic generation by slice

The traffic generator should use one stream per TEID.

### 6.1 Slice identity

In the current uplink experiment, a slice is identified by TEID.

```text
slice_id
  teid_1
  teid_11
  teid_21
```

Logical mapping

```text
T-Rex stream 1
  TEID 1
  UE IP 10.250.0.1
  slice_id teid_1

T-Rex stream 2
  TEID 11
  UE IP 10.250.0.2
  slice_id teid_11

T-Rex stream 3
  TEID 21
  UE IP 10.250.0.3
  slice_id teid_21
```

### 6.2 Per-slice GTP-U traffic

Each T-Rex stream should create an outer GTP-U packet.

Outer packet

```text
Source IP
  192.168.70.2

Destination IP
  192.168.70.1

UDP destination port
  2152

GTP-U TEID
  one TEID per slice
```

Inner packet

```text
Source IP
  UE IP from the slice

Destination IP
  N6 receiver address or service address

Example destination
  192.168.80.2
```

Expected eUPF behavior

```text
Match TEID in pdr_map_teid_ip
Apply associated PDR and QER
Decapsulate GTP-U
Forward inner IP packet to N6
```

### 6.3 Where throughput should be measured

Per-slice throughput should be measured from T-Rex stream statistics.

Reason

```text
eUPF packet_stats, route_stats, and xdp_stats are global.
Current URR entries are not reliably separated per TEID with this pfcpsim setup.
T-Rex stream statistics can be mapped directly to TEID.
```

Recommended measurement mapping

```text
T-Rex stream id
  maps to TEID

TEID
  maps to slice_id

slice_id
  maps to InfluxDB tag
```

Recommended T-Rex measurement

```text
trex_slice_metrics

tags
  host
  teid
  slice_id
  stream_id

fields
  tx_bps
  rx_bps
  tx_pps
  rx_pps
  loss_pkts
  loss_percent
  latency_avg_us
  latency_p99_us
```

## 7. Agentic controller integration

The Agentic AI controller is external to the UPF and traffic generator machines.

### 7.1 Agent inputs

The agent should consume data from InfluxDB and, when needed, from the eUPF API.

Primary data source

```text
InfluxDB API
```

Useful InfluxDB measurements

```text
eupf_global_metrics
eupf_teid_metrics
trex_slice_metrics
```

Optional live source

```text
eUPF API on 192.168.70.1 or localhost through SSH tunnel
```

Useful eUPF endpoints

```text
/api/v1/health
/api/v1/config
/api/v1/xdp_stats
/api/v1/packet_stats
/api/v1/route_stats
/api/v1/qer_map
/api/v1/qer_map/:id
/api/v1/far_map/:id
/api/v1/uplink_pdr_map/:id
/api/v1/pfcp_associations
```

### 7.2 Agent actions

The first version should use a narrow and auditable action set.

Recommended action classes

```text
Read status
  query InfluxDB
  query eUPF API
  query T-Rex stats

Change QoS
  modify QER or PFCP session rules through a validated script

Restart components
  restart collector
  restart pfcpsim
  restart eUPF only when explicitly allowed

Export data
  run a CSV export script
```

Important safety rule

```text
The agent should not directly write arbitrary BPF map entries during the main experiment.
Low level bpftool updates should be kept for controlled debugging only.
```

### 7.3 Suggested agent loop

```text
1. Read the last 10 to 30 seconds from InfluxDB
2. Aggregate per-slice T-Rex throughput and loss
3. Read current TEID to QER mapping from eupf_teid_metrics
4. Detect policy violation or overload
5. Select a bounded action
6. Execute action through SSH
7. Wait for cooldown
8. Re-evaluate outcome
```

Recommended timing

```text
Collector interval
  1 second

Agent decision interval
  10 seconds

Cooldown after action
  30 to 60 seconds
```

## 8. Experimental cases

### Case 01. Single slice baseline

Purpose

```text
Validate stable uplink throughput through the eUPF for one TEID.
```

Traffic

```text
One T-Rex stream
One TEID
One UE IP
Fixed QER
```

Expected data

```text
eUPF global counters increase
eUPF TEID state remains stable
T-Rex reports one stream throughput
```

### Case 02. Multi-slice baseline

Purpose

```text
Validate simultaneous slices with one stream per TEID.
```

Traffic

```text
Three or more T-Rex streams
One TEID per stream
One UE IP per stream
Fixed QER per TEID
```

Expected data

```text
eupf_teid_metrics contains multiple TEIDs
trex_slice_metrics separates throughput per TEID
global eUPF counters capture aggregate load
```

### Case 03. QoS enforcement

Purpose

```text
Evaluate whether changing QER settings affects per-slice throughput.
```

Traffic

```text
Multiple active TEIDs
One or more congested slices
One or more protected slices
```

Action

```text
Modify QER bitrate or related QoS policy for selected TEID or QER
```

Metrics

```text
Per-slice throughput before and after the action
Loss before and after the action
Global drops and redirects
Time to effect
```

### Case 04. Overload response

Purpose

```text
Evaluate agent behavior under overload.
```

Traffic

```text
Offered load exceeds target capacity
Multiple competing slices
```

Action

```text
Agent reduces bitrate for lower priority slices
Agent preserves throughput for priority slice
```

Metrics

```text
Priority slice throughput
Best effort slice throughput
Loss
XDP drops
Action count
Stability after action
```

### Case 05. XDP native and Mellanox tuning

Purpose

```text
Evaluate performance after functional validation.
```

Changes to test later

```text
XDP native mode
MTU 9000 end to end
IRQ pinning
RSS queues
CPU isolation
T-Rex CPU pinning
NIC offload review
```

This case should only be run after the generic mode pipeline is stable.

## 9. Mellanox and performance notes

The current validation used XDP generic mode.

Recommended order

```text
First validate functional behavior in generic mode.
Then move to native XDP for performance.
Then tune Mellanox and CPU settings.
```

ConnectX-5 interfaces used in the setup

```text
enp7s0np0
enp8s0np0
```

Performance tuning items for later

```text
MTU consistency across N3 and N6
XDP native mode
CPU pinning for eUPF
CPU pinning for T-Rex
NIC queue configuration
IRQ affinity
RSS configuration
NUMA locality
Clock synchronization with chrony
```

Clock synchronization note

```text
NICs do not need to be synchronized for throughput forwarding.
Host clocks should be synchronized if latency, jitter, or cross-host timestamps are analyzed.
```

## 10. Known limitations

### 10.1 Downlink is not part of the first benchmark

Downlink currently drops because the pfcpsim generated FAR fields for downlink encapsulation are incomplete.

Current decision

```text
Do not block uplink throughput experiments on downlink.
Document downlink as future work for bidirectional or RTT experiments.
```

### 10.2 eUPF global counters are not per slice

The following are global counters.

```text
packet_stats
route_stats
xdp_stats
```

They are still useful for system level behavior.

Per-slice throughput should come from T-Rex stream statistics.

### 10.3 URR is not reliable for per-slice throughput in this setup

With the current pfcpsim setup, URR IDs are not providing clean per-TEID volume separation.

Current decision

```text
Use TEID based state from eUPF.
Use T-Rex stream based measurements for throughput by slice.
```

### 10.4 pfcpsim delete may fail for some sessions

A failed `session delete` was observed during testing.

Practical workaround

```text
For clean smoke tests, restart eUPF and pfcpsim.
Then recreate association and sessions.
```

## 11. Minimal end-to-end runbook

### Step 1. Start eUPF on the UPF machine

```bash
sudo docker rm -f eupf 2>/dev/null || true
sudo rm -rf /sys/fs/bpf/upf_pipeline

sudo docker run -d --privileged --network host \
  -v /sys/fs/bpf:/sys/fs/bpf \
  -v /sys/kernel/debug:/sys/kernel/debug:ro \
  -e UPF_INTERFACE_NAME="enp7s0np0,enp8s0np0" \
  -e UPF_XDP_ATTACH_MODE=generic \
  -e UPF_N3_ADDRESS=192.168.70.1 \
  -e UPF_PFCP_NODE_ID=192.168.70.1 \
  -e UPF_GTP_PEER="192.168.70.2:2152" \
  -e UPF_GTP_ECHO_INTERVAL=3600 \
  -e UPF_HEARTBEAT_INTERVAL=3600 \
  -e UPF_HEARTBEAT_TIMEOUT=30 \
  -e UPF_HEARTBEAT_RETRIES=100 \
  -e UPF_PFCP_ADDRESS="0.0.0.0:8805" \
  -e UPF_API_ADDRESS="0.0.0.0:8080" \
  -e UPF_METRICS_ADDRESS="0.0.0.0:9090" \
  --name eupf \
  ghcr.io/edgecomllc/eupf:main
```

### Step 2. Start pfcpsim on the traffic generator machine

```bash
sudo docker rm -f pfcpsim 2>/dev/null || true

sudo docker run --rm -d --network host \
  --name pfcpsim \
  omecproject/pfcpsim:rel-1.4.3 \
  -p 12345 \
  --interface enp7s0np0
```

### Step 3. Create association and sessions

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.2 \
  --remote-peer-addr 192.168.70.1

sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate

sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 \
  --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2
```

### Step 4. Start InfluxDB on the UPF machine

```bash
cd ~/eupf-monitoring
sudo docker compose up -d
curl -s http://127.0.0.1:8086/health
```

### Step 5. Start the TEID collector on the UPF machine

```bash
cd ~/eupf-monitoring

INFLUX_TOKEN="${INFLUX_TOKEN}" \
python3 collector_eupf_influx_auto_teid.py
```

### Step 6. Start T-Rex traffic

Planned behavior

```text
Start one T-Rex stream per TEID.
Use TEIDs discovered from eUPF.
Write T-Rex per-stream stats to InfluxDB with tag teid.
```

### Step 7. Run external Agentic AI controller

Planned behavior

```text
Read InfluxDB metrics.
Determine whether QoS action is needed.
Execute bounded SSH action.
Wait for cooldown.
Measure effect.
```

## 12. Current validated conclusion

The current deployment has already validated the core foundation required for the initial experiment.

Validated

```text
Two machine topology is working.
eUPF runs with XDP on N3 and N6.
pfcpsim establishes PFCP association.
pfcpsim creates multiple sessions.
eUPF installs TEID based PDRs.
Uplink GTP-U decapsulation and N6 forwarding works.
InfluxDB stores global eUPF metrics.
InfluxDB stores TEID scoped eUPF state.
TEID can be used as the slice identifier.
```

Next major implementation step

```text
Add T-Rex multi-stream GTP-U profile.
Map each T-Rex stream to one TEID.
Store per-stream throughput and loss in InfluxDB.
Use those per-slice metrics as the main input for QoS enforcement.
```
