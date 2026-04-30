# BESS-UPF + TRex Setup Guide

End-to-end setup for a standalone BESS-UPF testbed with TRex as the GTP-U
traffic generator. AF_PACKET mode (kernel) for initial validation; DPDK
migration documented as Phase 5 for production performance.

Two-host topology, no 5G core required. PFCP control plane via pfcpsim.

---

## Topology

```
   trex host (GPN)                              upf host (UCSD)
   ─────────────────                            ──────────────────
   enp3s0   10.30.6.27/23     mgmt (SSH only)    enp3s0  10.30.6.x/23
   enp7s0np0  192.168.70.2/24   ◀── N3 ──▶       enp7s0np0  192.168.70.1/24
   enp8s0np0  192.168.80.2/24   ◀── N6 ──▶       enp8s0np0  192.168.80.1/24

   - TRex stateless (DPDK, takes both Mellanox)
   - pfcpsim (patched, runs in container)
   - 3 PDU sessions: TEIDs 1, 11, 21
   - UE IPs 10.250.0.1, 10.250.0.2, 10.250.0.3

   - BESS-UPF (AF_PACKET on Mellanox, kernel)
   - pfcpiface (Go agent, listens on 8805)
   - Per-slice metrics via Prometheus on :8080
```

---

## Phase 1 — Prepare the UPF host

Run on the **upf** host. Assumes Ubuntu 22.04.5, kernel 5.15.

### 1.1 Bring up Mellanox interfaces

```bash
sudo ip link set enp7s0np0 up
sudo ip link set enp8s0np0 up

sudo ip addr add 192.168.70.1/24 dev enp7s0np0
sudo ip addr add 192.168.80.1/24 dev enp8s0np0

sudo ip link set enp7s0np0 mtu 1500
sudo ip link set enp8s0np0 mtu 1500

ip -br addr show enp7s0np0
ip -br addr show enp8s0np0
```

Persist across reboots (optional but recommended):

```bash
sudo tee /etc/netplan/60-mellanox.yaml > /dev/null <<EOF
network:
  version: 2
  ethernets:
    enp7s0np0:
      addresses: [192.168.70.1/24]
      mtu: 1500
    enp8s0np0:
      addresses: [192.168.80.1/24]
      mtu: 1500
EOF
sudo netplan apply
```

### 1.2 Install dependencies

```bash
sudo apt update
sudo apt install -y \
    build-essential \
    git \
    docker.io \
    docker-compose-v2 \
    make \
    curl \
    jq \
    net-tools \
    tcpdump

sudo systemctl enable --now docker

# add user to docker group (re-login required)
sudo usermod -aG docker $USER
```

### 1.3 Validate

```bash
docker --version
sudo docker run --rm hello-world
ping -c 2 192.168.70.2   # may fail if trex has TRex DPDK-bound; ok
```

---

## Phase 2 — Build BESS-UPF on the UPF host

### 2.1 Clone repos

```bash
mkdir -p ~/bess-upf
cd ~/bess-upf

git clone https://github.com/omec-project/upf.git
git clone https://github.com/omec-project/bess.git
```

### 2.2 Build BESS Docker images

```bash
cd ~/bess-upf/upf
sudo make docker-build
```

This step takes 15–30 minutes. It pulls the bess_build image, compiles BESS,
the BESS-UPF modules, and pfcpiface (Go).

Outputs (verify):

```bash
sudo docker images | grep -E "upf|bess"
```

Expected images:

```
upf-epc-pfcpiface     latest      ...
upf-epc-bess          latest      ...
```

If build fails on `make docker-build`, try the lower-level target first:

```bash
sudo docker pull omecproject/upf-epc-bess:master-latest
sudo docker pull omecproject/upf-epc-pfcpiface:master-latest
sudo docker tag omecproject/upf-epc-bess:master-latest upf-epc-bess:latest
sudo docker tag omecproject/upf-epc-pfcpiface:master-latest upf-epc-pfcpiface:latest
```

This skips local build and uses pre-published images.

---

## Phase 3 — Configure BESS-UPF (AF_PACKET mode)

### 3.1 Create config directory

```bash
mkdir -p ~/bess-upf/config
cd ~/bess-upf/config
```

### 3.2 Write upf.jsonc

```bash
cat > ~/bess-upf/config/upf.jsonc <<'EOF'
{
  "mode": "af_packet",
  "log_level": "info",
  "max_sessions": 1024,
  "table_sizes": {
    "pdrLookup": 1024,
    "flowMeasure": 1024,
    "appQERLookup": 1024,
    "sessionQERLookup": 1024,
    "farLookup": 1024
  },
  "access": {
    "ifname": "enp7s0np0"
  },
  "core": {
    "ifname": "enp8s0np0"
  },
  "measure_upf": true,
  "measure_flow": true,
  "enable_notify_bess": false,
  "enable_end_marker": false,
  "workers": 1,
  "read_timeout": 25,
  "cpiface": {
    "dnn": "internet",
    "hostname": "upf",
    "http_port": "8080",
    "enable_ue_ip_alloc": false,
    "ue_ip_pool": "10.250.0.0/24"
  },
  "slice_rate_limit_config": {
    "n6_bps": 1000000000,
    "n6_burst_bytes": 12500000,
    "n3_bps": 1000000000,
    "n3_burst_bytes": 12500000
  }
}
EOF
```

Key settings:

- `mode: af_packet` — uses kernel sockets, not DPDK
- `access.ifname: enp7s0np0` — N3 (where GTP-U arrives from gNB/TRex)
- `core.ifname: enp8s0np0` — N6 (where decapsulated traffic exits to DN)
- `measure_flow: true` — enables per-PDR/per-flow metrics
- `cpiface.http_port: 8080` — Prometheus and HTTP endpoints

### 3.3 Write docker-compose.yml

```bash
cat > ~/bess-upf/config/docker-compose.yml <<'EOF'
version: "3.7"

services:
  bess:
    image: upf-epc-bess:latest
    container_name: bess
    network_mode: host
    privileged: true
    cap_add:
      - IPC_LOCK
      - NET_ADMIN
      - SYS_ADMIN
      - SYS_NICE
      - SYS_RESOURCE
    volumes:
      - ./upf.jsonc:/opt/bess/bessctl/conf/upf.jsonc
      - /sys/devices/system/node:/sys/devices/system/node
      - /lib/modules:/lib/modules
    command: >
      -grpc-url=0.0.0.0:10514
    healthcheck:
      test: ["CMD", "/opt/bess/bessctl/bessctl", "show", "version"]
      interval: 30s
      timeout: 10s
      retries: 3

  bess-routectl:
    image: upf-epc-bess:latest
    container_name: bess-routectl
    network_mode: host
    pid: "host"
    depends_on:
      - bess
    entrypoint: ["/opt/bess/bessctl/conf/route_control.py"]
    command: ["-i", "enp7s0np0", "enp8s0np0"]

  pfcpiface:
    image: upf-epc-pfcpiface:latest
    container_name: pfcpiface
    network_mode: host
    cap_add:
      - NET_ADMIN
    depends_on:
      - bess
    volumes:
      - ./upf.jsonc:/conf/upf.jsonc
    command: >
      -config /conf/upf.jsonc
EOF
```

### 3.4 Bring up BESS-UPF

```bash
cd ~/bess-upf/config
sudo docker compose up -d

sleep 10
sudo docker ps
sudo docker logs bess --tail 30
sudo docker logs pfcpiface --tail 30
```

Expected logs:

```
bess:        BESS daemon started, listening on 0.0.0.0:10514
pfcpiface:   PFCP server started on 0.0.0.0:8805
pfcpiface:   gRPC connected to bess at localhost:10514
```

### 3.5 Validate PFCP listener

```bash
sudo ss -lunp | grep 8805
curl -s http://127.0.0.1:8080/metrics | head -20
```

Expected:

```
UNCONN  *:8805  ...  pfcpiface
# HELP upf_messages_total ...
# TYPE upf_messages_total counter
```

If this works, BESS-UPF is up and waiting for PFCP from pfcpsim.

---

## Phase 4 — Configure pfcpsim on the TRex host

The pfcpsim is already patched (URR per TEID via AddURRID). It runs in a
container on the trex host.

### 4.1 Image and run

```bash
# on trex host
sudo docker rm -f pfcpsim 2>/dev/null

sudo docker run --rm -d --network host \
  --name pfcpsim \
  pfcpsim:patched \
  -p 12345 \
  --interface enp7s0np0
```

If you don't have the patched image on this host, copy it from the build host:

```bash
# on the host where pfcpsim:patched was built
sudo docker save pfcpsim:patched | gzip > pfcpsim-patched.tar.gz
scp pfcpsim-patched.tar.gz ubuntu@trex:/tmp/

# on trex host
sudo docker load < /tmp/pfcpsim-patched.tar.gz
```

### 4.2 Configure and associate

```bash
# on trex host

# point pfcpsim at the new BESS-UPF
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.2 \
  --remote-peer-addr 192.168.70.1

sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate
```

Expected: `Association established`.

### 4.3 Create 3 sessions (UDP filter for TRex compatibility)

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2 \
  --app-filter "udp:any:any:allow:100"
```

Expected: `3 sessions were established using 1 as baseID`.

### 4.4 Validate sessions on UPF host

```bash
# on upf host
curl -s http://127.0.0.1:8080/metrics | grep -E "session|pdr" | head -20
```

Look for non-zero session/PDR counters.

You can also inspect BESS modules directly:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show pipeline | head -30
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup
```

---

## Phase 5 — Generate traffic with TRex

### 5.1 Profile (3 streams, UDP inner, per-TEID pg_id)

On the trex host, place the profile at
`/opt/trex/v3.08/automation/exp2/exp2_profile.py`:

```python
"""
TRex stateless profile for 3 concurrent GTP-U streams.
TEIDs 1, 11, 21. Inner UDP (matches BESS-UPF SDF filter).
Per-stream tx/rx/latency via STLFlowLatencyStats.
"""
from trex_stl_lib.api import (
    Ether, IP, UDP,
    STLStream, STLPktBuilder, STLTXCont, STLFlowLatencyStats,
)
from scapy.contrib.gtp import GTP_U_Header

GNB_IP = "192.168.70.2"
UPF_N3_IP = "192.168.70.1"
DN_IP = "192.168.80.2"
PAYLOAD_BYTES = 64

SLICES = [
    {"teid": 1,  "ue_ip": "10.250.0.1", "src_port": 10001},
    {"teid": 11, "ue_ip": "10.250.0.2", "src_port": 10011},
    {"teid": 21, "ue_ip": "10.250.0.3", "src_port": 10021},
]


class STLS1(object):
    def get_streams(self, direction=0, **kwargs):
        streams = []
        for s in SLICES:
            outer = IP(src=GNB_IP, dst=UPF_N3_IP) / UDP(sport=2152, dport=2152)
            gtpu = GTP_U_Header(teid=s["teid"])
            inner = (
                IP(src=s["ue_ip"], dst=DN_IP)
                / UDP(sport=s["src_port"], dport=5555)
                / ("X" * PAYLOAD_BYTES)
            )
            pkt = Ether() / outer / gtpu / inner
            streams.append(
                STLStream(
                    packet=STLPktBuilder(pkt=pkt),
                    mode=STLTXCont(pps=1000),
                    flow_stats=STLFlowLatencyStats(pg_id=s["teid"]),
                )
            )
        return streams


def register():
    return STLS1()
```

### 5.2 Start TRex daemon

```bash
sudo /opt/trex/v3.08/t-rex-64 -i --no-ofed-check -c 8 &
sleep 30
```

### 5.3 Inject traffic

```bash
sudo /opt/trex/v3.08/trex-console
```

In the console:

```
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_profile.py -p 0 -m 90mbps -d 30 --force
```

After 30 seconds:

```
stats -s
```

Expected (this is the validation that BESS-UPF works where eUPF didn't):

```
PG ID    |   1   |   11   |   21
Tx pps   |  ~10k |  ~10k  |  ~10k
Rx pps   |  ~10k |  ~10k  |  ~10k     ← non-zero!
opackets | ~300k | ~300k  | ~300k
ipackets | ~300k | ~300k  | ~300k     ← non-zero!
```

If `ipackets > 0` per pg_id, BESS-UPF is correctly delivering and TRex
correctly correlates per-stream — what you couldn't get with eUPF.

---

## Phase 6 — Per-slice metrics via Prometheus

### 6.1 Query BESS-UPF metrics on the UPF host

```bash
# total per-PDR packet count
curl -s http://127.0.0.1:8080/metrics | grep upf_pdr_packets_total

# per-flow latency (if measure_flow=true was set)
curl -s http://127.0.0.1:8080/metrics | grep upf_flow_latency

# per-slice byte counters
curl -s http://127.0.0.1:8080/metrics | grep upf_session_bytes
```

You can also use the bessctl CLI for live introspection:

```bash
# inside bess container
sudo docker exec -it bess /opt/bess/bessctl/bessctl
> show module qosMeasureIn
> show module qosMeasureOut
> monitor pipeline
> quit
```

### 6.2 Wire into your existing InfluxDB collector

Modify your existing `collector_eupf_influx.py` (rename to
`collector_bess_influx.py`) to scrape Prometheus instead of bpftool.

Pseudo-pattern:

```python
import requests
metrics = requests.get("http://127.0.0.1:8080/metrics", timeout=2).text
# parse Prometheus exposition format
# tag each metric with teid (extract from labels)
# write to InfluxDB
```

The Prometheus Python client (`prometheus_client.parser`) parses the
exposition format directly:

```python
from prometheus_client.parser import text_string_to_metric_families
for family in text_string_to_metric_families(metrics):
    for sample in family.samples:
        # sample.name, sample.labels, sample.value
        ...
```

---

## Phase 7 — DPDK migration (when ready for line rate)

When AF_PACKET caps you at 5–10 Gbps and you want to push 25 Gbps:

### 7.1 Hugepages

```bash
sudo sysctl -w vm.nr_hugepages=2048
echo "vm.nr_hugepages=2048" | sudo tee -a /etc/sysctl.conf
```

### 7.2 OFED userspace (matches what TRex needs)

```bash
# download MLNX_OFED 5.9 for Ubuntu 22.04
wget https://www.mellanox.com/downloads/ofed/MLNX_OFED-5.9-0.5.6.0/MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64.tgz
tar xzf MLNX_OFED_LINUX-*-ubuntu22.04-x86_64.tgz
cd MLNX_OFED_LINUX-*-ubuntu22.04-x86_64
sudo ./mlnxofedinstall --user-space-only --without-fw-update
```

### 7.3 Update upf.jsonc

```jsonc
{
  "mode": "dpdk",
  "access": {
    "ifname": "0000:07:00.0"   // PCI address, not interface name
  },
  "core": {
    "ifname": "0000:08:00.0"
  },
  ...
}
```

### 7.4 Recreate compose with hugepages mount

Add to docker-compose.yml under bess service:

```yaml
    volumes:
      - /dev/hugepages:/dev/hugepages
    cap_add:
      - SYS_NICE
      - SYS_ADMIN
      - IPC_LOCK
```

### 7.5 Restart

```bash
sudo docker compose down
sudo docker compose up -d
```

Expected: BESS now uses DPDK PMD on Mellanox, kernel loses access to those
interfaces (just like TRex). Throughput jumps from ~5 Gbps to 25 Gbps.

---

## Troubleshooting

### BESS won't start

```bash
sudo docker logs bess
```

Common issues:

- "interface not found" — Mellanox names changed; update upf.jsonc
- "permission denied on hugepages" — only relevant in DPDK mode
- "module already loaded" — `sudo docker compose down` and try again

### pfcpiface logs show "could not connect to bess"

bess container failed to start. Check `docker logs bess`. Confirm gRPC
port 10514 is open:

```bash
sudo ss -ltnp | grep 10514
```

### pfcpsim association timeouts

Same diagnosis as before. Confirm PFCP destination is reachable:

```bash
# on trex host
sudo docker exec pfcpsim ping -c 2 192.168.70.1
```

If no route, restart pfcpsim with the right interface:

```bash
sudo docker rm -f pfcpsim
sudo docker run --rm -d --network host --name pfcpsim \
  pfcpsim:patched -p 12345 --interface enp7s0np0
```

### TRex porta 1 ipackets stays 0

Service mode required (TRex defaults to MAC-filtered RX):

```
service --port 1
```

If still zero, BESS-UPF is not forwarding. Check:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show port
```

---

## Reference

- [omec-project/upf](https://github.com/omec-project/upf)
- [omec-project/bess](https://github.com/omec-project/bess)
- [omec-project/pfcpsim](https://github.com/omec-project/pfcpsim)
- [BESS-UPF docs](https://github.com/omec-project/upf/tree/master/docs)
- [Aether SD-Core docs](https://docs.sd-core.opennetworking.org/)

## Quick reference — run order each session

```
upf:   sudo docker compose -f ~/bess-upf/config/docker-compose.yml up -d
trex:  sudo docker run --rm -d --network host --name pfcpsim pfcpsim:patched -p 12345 --interface enp7s0np0
trex:  sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure --n3-addr 192.168.70.2 --remote-peer-addr 192.168.70.1
trex:  sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate
trex:  sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create --count 3 --baseID 1 --ue-pool 10.250.0.0/24 --gnb-addr 192.168.70.2 --app-filter "udp:any:any:allow:100"
trex:  sudo /opt/trex/v3.08/t-rex-64 -i --no-ofed-check -c 8 &
trex:  sudo /opt/trex/v3.08/trex-console
```
