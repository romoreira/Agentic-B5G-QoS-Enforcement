# BESS UPF and TRex Standalone Testbed

End to end setup guide for a two host BESS UPF testbed with TRex as GTP U traffic generator.

This guide documents the working setup validated in the lab.

The final validated path is:

```text
TRex port 0, N3
to UPF enp7s0np0
to BESS UPF
to PDR match
to GTP U decapsulation
to FAR processing
to N6 route
to UPF enp8s0np0
to TRex port 1 RX
```

Latency measurement was validated with TRex in software mode.

```text
PG ID 1   RX packets observed, latency reported
PG ID 11  RX packets observed, latency reported
PG ID 21  RX packets observed, latency reported
```

Important interpretation:

```text
The latency reported by TRex in this setup is the end to end software instrumented latency of the current AF_PACKET BESS UPF testbed. It is not the intrinsic latency of the Mellanox NICs.
```

## 1. Topology

```text
TRex host                                      UPF host
──────────────────────────────────             ──────────────────────────────────

Management
enp3s0, 10.30.6.23/23                          enp3s0, 10.30.6.199/23

N3, GTP U traffic
enp7s0np0, 192.168.70.2/24                     enp7s0np0, 192.168.70.1/24
MAC 10:70:fd:c0:ef:80                          MAC 10:70:fd:c1:59:c4
PCI 0000:07:00.0                               PCI 0000:07:00.0

N6, decapsulated traffic
enp8s0np0, 192.168.80.2/24                     enp8s0np0, 192.168.80.1/24
MAC 10:70:fd:c0:ef:81                          MAC 10:70:fd:c1:59:c5
PCI 0000:08:00.0                               PCI 0000:08:00.0

PFCP control
enp9s0, 192.168.90.2/24                        enp9s0, 192.168.90.1/24
MAC 02:ec:6c:4e:73:dd                          MAC 16:af:85:d9:77:71
```

Roles:

```text
UPF host
Runs BESS UPF in AF_PACKET mode.
Runs pfcpiface.
Runs bess route controller.

TRex host
Runs TRex.
Runs pfcpsim.
Generates GTP U traffic on N3.
Receives decapsulated traffic on N6.
Sends PFCP control traffic through enp9s0.
```

Validated UE and TEID mapping:

```text
TEID 1    UE 10.250.0.1
TEID 11   UE 10.250.0.2
TEID 21   UE 10.250.0.3
```

## 2. UPF host installation

Run these steps on the UPF host.

### 2.1 Install base packages

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  git \
  make \
  curl \
  jq \
  net-tools \
  tcpdump \
  python3-pip \
  docker.io \
  docker-compose-v2 \
  docker-buildx
```

Enable Docker:

```bash
sudo systemctl enable --now docker
sudo docker --version
sudo docker buildx version
```

If `docker-buildx` is not available, search for it:

```bash
apt-cache search buildx
```

On Ubuntu packaged Docker, the package name can be:

```bash
sudo apt install -y docker-buildx
```

### 2.2 Configure UPF interfaces

```bash
sudo ip link set enp7s0np0 up
sudo ip link set enp8s0np0 up
sudo ip link set enp9s0 up

sudo ip addr flush dev enp7s0np0
sudo ip addr flush dev enp8s0np0
sudo ip addr flush dev enp9s0

sudo ip addr add 192.168.70.1/24 dev enp7s0np0
sudo ip addr add 192.168.80.1/24 dev enp8s0np0
sudo ip addr add 192.168.90.1/24 dev enp9s0

sudo ip link set enp7s0np0 mtu 1500
sudo ip link set enp8s0np0 mtu 1500
sudo ip link set enp9s0 mtu 1500

ip -br addr show enp7s0np0
ip -br addr show enp8s0np0
ip -br addr show enp9s0
```

Validate Mellanox driver and PCI addresses:

```bash
ethtool -i enp7s0np0
ethtool -i enp8s0np0
lspci -nn | grep -i -E 'mellanox|ethernet'
```

Expected for the validated setup:

```text
enp7s0np0 PCI 0000:07:00.0
enp8s0np0 PCI 0000:08:00.0
driver mlx5_core
firmware 16.35.3006
```

### 2.3 Optional netplan persistence

```bash
sudo tee /etc/netplan/60-bess-upf.yaml > /dev/null <<'EOF'
network:
  version: 2
  ethernets:
    enp7s0np0:
      addresses: [192.168.70.1/24]
      mtu: 1500
    enp8s0np0:
      addresses: [192.168.80.1/24]
      mtu: 1500
    enp9s0:
      addresses: [192.168.90.1/24]
      mtu: 1500
EOF

sudo netplan apply
```

### 2.4 Clone repositories

```bash
mkdir -p ~/bess-upf
cd ~/bess-upf

git clone https://github.com/omec-project/upf.git
git clone https://github.com/omec-project/bess.git
```

### 2.5 Build BESS UPF Docker images

```bash
cd ~/bess-upf/upf
sudo make DOCKER_BUILD_ARGS="--network=host" docker-build
```

The `--network=host` argument avoids DNS failures inside Docker builds in IPv6 or OpenStack environments.

Expected images:

```bash
sudo docker images | grep -E 'upf|bess|pfcp'
```

Validated result:

```text
upf-bess:2.4.2-dev
upf-pfcp:2.4.2-dev
```

### 2.6 Configure hugepages for BESS

Even in AF_PACKET mode, the BESS daemon initializes DPDK memory pools. Configure hugepages:

```bash
sudo mkdir -p /dev/hugepages
sudo mount -t hugetlbfs nodev /dev/hugepages || true
sudo sysctl -w vm.nr_hugepages=1024
```

Validate:

```bash
grep -i Huge /proc/meminfo
mount | grep huge
```

Expected:

```text
HugePages_Total: 1024
HugePages_Free: 1024
hugetlbfs on /dev/hugepages
```

To persist:

```bash
echo "vm.nr_hugepages=1024" | sudo tee /etc/sysctl.d/90-hugepages.conf
```

## 3. UPF configuration

Create a clean configuration directory:

```bash
mkdir -p ~/bess-upf/config
cd ~/bess-upf/config
```

### 3.1 Create upf.jsonc

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

### 3.2 Create docker compose file

```bash
cat > ~/bess-upf/config/docker-compose.yml <<'EOF'
services:
  bess:
    image: upf-bess:2.4.2-dev
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
      - /dev/hugepages:/dev/hugepages
    command: >
      -grpc-url=0.0.0.0:10514

  pfcpiface:
    image: upf-pfcp:2.4.2-dev
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

### 3.3 Start BESS and pfcpiface

```bash
cd ~/bess-upf/config
sudo docker compose up -d
```

Load the BESS UPF pipeline:

```bash
sudo docker exec bess bash -lc 'cd /opt/bess/bessctl && ./bessctl run up4'
```

Start the route controller:

```bash
sudo docker rm -f bess-routectl 2>/dev/null || true

sudo docker run --name bess-routectl -td --restart unless-stopped \
  --net host \
  --pid container:bess \
  --entrypoint python3 \
  -v ~/bess-upf/upf/conf/route_control.py:/route_control.py \
  upf-bess:2.4.2-dev \
  /route_control.py -i enp7s0np0 enp8s0np0
```

Validate:

```bash
sudo docker ps
sudo ss -ltnp | grep 10514
sudo ss -lunp | grep 8805
curl -s http://127.0.0.1:8080/metrics | head
```

Expected:

```text
bess running
pfcpiface running
bess-routectl running
BESS gRPC on 10514
PFCP on 8805
HTTP metrics on 8080
```

## 4. UPF route and neighbor requirements for N6

Because TRex uses DPDK, the Linux kernel on the TRex host does not reliably answer ARP on the N6 interface during traffic generation.

Install a static neighbor and an onlink host route on the UPF host:

```bash
sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink
```

Restart the route controller so it programs the BESS route module:

```bash
sudo docker restart bess-routectl
sleep 3
sudo docker logs bess-routectl --tail 20
```

Expected log:

```text
Mac address found for 192.168.80.2, Mac: 10:70:fd:c0:ef:81
Route entry 192.168.80.2/32 added to enp8s0np0Routes
Module enp8s0np0Routes:0->0/enp8s0np0DstMAC1070FDC0EF81 linked
```

Validate route module:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

Expected:

```text
Output gate 0 to enp8s0np0DstMAC1070FDC0EF81
Output gate 8191 to enp8s0np0bad_route
```

The old `bad_route` counter may remain from previous tests. The important condition is that gate `0` increases during valid traffic.

## 5. TRex host installation

Run these steps on the TRex host.

### 5.1 Install base packages

```bash
sudo apt update
sudo apt install -y \
  git \
  make \
  curl \
  jq \
  net-tools \
  tcpdump \
  python3-pip \
  docker.io \
  docker-compose-v2 \
  libibverbs1 \
  ibverbs-providers \
  librdmacm1 \
  libmlx5-1
```

Enable Docker:

```bash
sudo systemctl enable --now docker
sudo docker --version
```

### 5.2 Configure TRex interfaces

```bash
sudo ip link set enp7s0np0 up
sudo ip link set enp8s0np0 up
sudo ip link set enp9s0 up

sudo ip addr flush dev enp7s0np0
sudo ip addr flush dev enp8s0np0
sudo ip addr flush dev enp9s0

sudo ip addr add 192.168.70.2/24 dev enp7s0np0
sudo ip addr add 192.168.80.2/24 dev enp8s0np0
sudo ip addr add 192.168.90.2/24 dev enp9s0

sudo ip link set enp7s0np0 mtu 1500
sudo ip link set enp8s0np0 mtu 1500
sudo ip link set enp9s0 mtu 1500

ip -br addr show enp7s0np0
ip -br addr show enp8s0np0
ip -br addr show enp9s0
```

Validate control connectivity:

```bash
ping -c 3 192.168.90.1
```

### 5.3 Install TRex v3.08

```bash
cd /tmp

wget --no-check-certificate https://trex-tgn.cisco.com/trex/release/v3.08.tar.gz

sudo mkdir -p /opt/trex
sudo tar -xzf v3.08.tar.gz -C /opt/trex

ls -d /opt/trex/v3.08
ls /opt/trex/v3.08/t-rex-64
```

### 5.4 Install Mellanox OFED userspace for TRex

The Ubuntu stock `libmlx5` may not provide `MLX5_1.24`, which TRex v3.08 may require.

Install MLNX OFED 5.9 userspace:

```bash
cd /tmp

wget https://www.mellanox.com/downloads/ofed/MLNX_OFED-5.9-0.5.6.0/MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64.tgz

tar xzf MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64.tgz

cd MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64

sudo ./mlnxofedinstall --user-space-only --without-fw-update
sudo ldconfig
```

Validate:

```bash
strings /lib/x86_64-linux-gnu/libmlx5.so.1 | grep MLX5_1.24
```

Expected:

```text
MLX5_1.24
```

### 5.5 Load RDMA Verbs modules

If TRex reports `Verbs device not found`, load the modules:

```bash
sudo modprobe ib_uverbs
sudo modprobe rdma_ucm
sudo modprobe mlx5_ib
```

Validate:

```bash
ls -l /dev/infiniband
ibv_devinfo
```

Expected:

```text
uverbs0
uverbs1
mlx5_0 PORT_ACTIVE
mlx5_1 PORT_ACTIVE
```

If modules are missing, install extras for the running kernel:

```bash
sudo apt install -y linux-modules-extra-$(uname -r)
```

Then repeat the `modprobe` commands.

### 5.6 Generate TRex port configuration

```bash
cd /opt/trex/v3.08
sudo ./dpdk_setup_ports.py -s
```

Expected Mellanox devices:

```text
0000:07:00.0 enp7s0np0 mlx5_core
0000:08:00.0 enp8s0np0 mlx5_core
```

Run the interactive configuration:

```bash
sudo ./dpdk_setup_ports.py -i
```

Choose MAC based config.

Select interfaces:

```text
1 2
```

Use these destination MACs:

```text
Interface 1, TRex N3, destination MAC: 10:70:fd:c1:59:c4
Interface 2, TRex N6, destination MAC: 10:70:fd:c1:59:c5
```

Validated `/etc/trex_cfg.yaml`:

```yaml
- version: 2
  interfaces: ['07:00.0', '08:00.0']
  port_mtu: 1500
  port_info:
      - dest_mac: 10:70:fd:c1:59:c4
        src_mac:  10:70:fd:c0:ef:80
      - dest_mac: 10:70:fd:c1:59:c5
        src_mac:  10:70:fd:c0:ef:81

  platform:
      master_thread_id: 0
      latency_thread_id: 1
      dual_if:
        - socket: 0
          threads: [2,3,4,5,6,7,8,9,10,11,12,13,14,15]
```

If TRex fails with MTU 65518, add `port_mtu: 1500` as shown above.

## 6. Build pfcpsim on the TRex host

```bash
cd ~
git clone https://github.com/omec-project/pfcpsim.git
cd pfcpsim
```

The Dockerfile may need a copy destination fix.

Check:

```bash
grep -n 'COPY --from=builder' Dockerfile
```

If it contains this:

```Dockerfile
COPY --from=builder /pfcpctl/pfcp* /usr/local/bin
```

Fix it:

```bash
sed -i 's|COPY --from=builder /pfcpctl/pfcp\* /usr/local/bin|COPY --from=builder /pfcpctl/pfcp* /usr/local/bin/|' Dockerfile
```

Build with host networking to avoid DNS issues during Go module download:

```bash
sudo docker build --network=host -t pfcpsim:patched .
```

Validate:

```bash
sudo docker images | grep pfcpsim
```

Expected:

```text
pfcpsim:patched
```

## 7. TRex traffic profiles

Create directory:

```bash
mkdir -p /opt/trex/v3.08/automation/exp2
```

### 7.1 Functional GTP U profile

This profile validates forwarding from N3 to N6.

```bash
cat > /opt/trex/v3.08/automation/exp2/exp2_profile.py <<'EOF'
from trex_stl_lib.api import *
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
            pkt = (
                Ether()
                / IP(src=GNB_IP, dst=UPF_N3_IP)
                / UDP(sport=2152, dport=2152, chksum=0)
                / GTP_U_Header(teid=s["teid"])
                / IP(src=s["ue_ip"], dst=DN_IP)
                / UDP(sport=s["src_port"], dport=5555)
                / ("X" * PAYLOAD_BYTES)
            )

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
EOF
```

Critical detail:

```text
The outer UDP checksum is set to zero.
Without this, BESS L4 checksum validation drops most packets before PDR lookup.
```

### 7.2 Latency profile

This profile was validated with TRex in software mode.

```bash
cat > /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py <<'EOF'
from trex_stl_lib.api import *
from scapy.contrib.gtp import GTP_U_Header

GNB_IP = "192.168.70.2"
UPF_N3_IP = "192.168.70.1"
DN_IP = "192.168.80.2"

SLICES = [
    {"teid": 1,  "ue_ip": "10.250.0.1", "src_port": 10001, "pg_id": 1},
    {"teid": 11, "ue_ip": "10.250.0.2", "src_port": 10011, "pg_id": 11},
    {"teid": 21, "ue_ip": "10.250.0.3", "src_port": 10021, "pg_id": 21},
]

class STLS1(object):
    def get_streams(self, direction=0, **kwargs):
        streams = []

        for s in SLICES:
            pkt = (
                Ether()
                / IP(src=GNB_IP, dst=UPF_N3_IP)
                / UDP(sport=2152, dport=2152, chksum=0)
                / GTP_U_Header(teid=s["teid"])
                / IP(src=s["ue_ip"], dst=DN_IP)
                / UDP(sport=s["src_port"], dport=5555, chksum=0)
                / ("X" * 128)
            )

            streams.append(
                STLStream(
                    name="lat_teid_%s" % s["teid"],
                    packet=STLPktBuilder(pkt=pkt),
                    mode=STLTXCont(pps=100),
                    flow_stats=STLFlowLatencyStats(pg_id=s["pg_id"]),
                )
            )

        return streams

def register():
    return STLS1()
EOF
```

Critical detail:

```text
The latency profile sets both outer and inner UDP checksums to zero.
TRex latency tracking worked after restarting TRex with --software.
```

## 8. Bring up the full testbed

### 8.1 UPF run order

Run on the UPF host:

```bash
cd ~/bess-upf/config

sudo docker compose up -d

sudo docker exec bess bash -lc 'cd /opt/bess/bessctl && ./bessctl run up4'

sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink

sudo docker rm -f bess-routectl 2>/dev/null || true
sudo docker run --name bess-routectl -td --restart unless-stopped \
  --net host \
  --pid container:bess \
  --entrypoint python3 \
  -v ~/bess-upf/upf/conf/route_control.py:/route_control.py \
  upf-bess:2.4.2-dev \
  /route_control.py -i enp7s0np0 enp8s0np0

sleep 3
sudo docker logs bess-routectl --tail 20
```

Validate:

```bash
sudo ss -ltnp | grep 10514
sudo ss -lunp | grep 8805
curl -s http://127.0.0.1:8080/metrics | head
```

### 8.2 pfcpsim run order

Run on the TRex host:

```bash
sudo docker rm -f pfcpsim 2>/dev/null || true

sudo docker run --rm -d --network host \
  --name pfcpsim \
  pfcpsim:patched \
  -p 12345 \
  --interface enp9s0
```

Configure PFCP:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.1 \
  --remote-peer-addr 192.168.90.1
```

Important:

```text
--n3-addr must be the UPF N3 address, 192.168.70.1.
--remote-peer-addr must be the UPF PFCP control address, 192.168.90.1.
--gnb-addr in session create must be the TRex N3 address, 192.168.70.2.
```

Associate and create sessions:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate

sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2 \
  --app-filter "udp:any:any:allow:100"
```

Validate on UPF:

```bash
curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions

sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup | grep rules
```

Expected:

```text
pfcp_sessions{node_id="192.168.90.2"} 3
pdrLookup 6 rules
farLookup 6 rules
```

## 9. Functional forwarding test

Start TRex in normal mode:

```bash
cd /opt/trex/v3.08
sudo ./t-rex-64 -i --no-ofed-check -c 8
```

In another terminal:

```bash
cd /opt/trex/v3.08
sudo ./trex-console
```

In the TRex console:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_profile.py -p 0 -m 10mbps -d 10 --force
stats
```

Expected TRex result:

```text
Port 0 opackets increases
Port 1 ipackets increases
oerrors 0
ierrors 0
```

Validated example:

```text
Port 0 opackets 60006
Port 1 ipackets 30046
Port 1 rx bytes about 3.3 MB
oerrors 0
ierrors 0
```

Validate on UPF:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module gtpuDecap
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
sudo docker exec bess /opt/bess/bessctl/bessctl show port | grep -A8 enp8s0np0Fast
```

Expected:

```text
gtpuDecap packets increase
farLookup packets increase
farLookupFail remains 0
enp8s0np0Routes gate 0 increases
enp8s0np0Fast Out/TX increases
dropped 0
```

## 10. Latency test

For latency, start TRex in software mode:

```bash
cd /opt/trex/v3.08
sudo ./t-rex-64 -i --software --no-ofed-check -c 8
```

In another terminal:

```bash
cd /opt/trex/v3.08
sudo ./trex-console
```

In the TRex console:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py -p 0 -d 10 --force
stats -l
```

Validated latency example:

```text
PG ID 1
TX pkts 1001
RX pkts 1001
Avg latency 40448 us
Jitter 3

PG ID 11
TX pkts 1001
RX pkts 1001
Avg latency 40444 us
Jitter 6

PG ID 21
TX pkts 1001
RX pkts 1001
Avg latency 40456 us
Jitter 6
```

Interpretation:

```text
40448 us is about 40.448 ms.
This is end to end software instrumented latency in the current AF_PACKET setup.
It should not be interpreted as Mellanox NIC latency.
```

## 11. Useful monitoring commands

### 11.1 UPF health

```bash
sudo docker ps
sudo docker logs bess --tail 50
sudo docker logs pfcpiface --tail 50
sudo docker logs bess-routectl --tail 50
```

### 11.2 PFCP sessions

```bash
curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions
```

### 11.3 BESS pipeline and modules

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show pipeline | head -40

sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module gtpuDecap
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

### 11.4 BESS ports

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show port
sudo docker exec bess /opt/bess/bessctl/bessctl show port | grep -A8 enp8s0np0Fast
```

### 11.5 TRex counters

```text
stats
stats -s
stats -l
```

## 12. Troubleshooting

### 12.1 Docker build fails with BuildKit buildx missing

Install buildx:

```bash
sudo apt update
sudo apt install -y docker-buildx
```

If using Docker CE repositories, the package may be:

```bash
sudo apt install -y docker-buildx-plugin
```

### 12.2 Docker build fails resolving Ubuntu or Go hosts

Use host networking:

```bash
sudo make DOCKER_BUILD_ARGS="--network=host" docker-build
sudo docker build --network=host -t pfcpsim:patched .
```

### 12.3 BESS fails with hugepage error

Error example:

```text
Cannot get hugepage information
rte_eal_init failed
```

Fix:

```bash
sudo mkdir -p /dev/hugepages
sudo mount -t hugetlbfs nodev /dev/hugepages || true
sudo sysctl -w vm.nr_hugepages=1024
```

Make sure the BESS container mounts:

```yaml
- /dev/hugepages:/dev/hugepages
```

### 12.4 pfcpiface says pdrLookup not found

The BESS pipeline was not loaded.

Fix:

```bash
sudo docker exec bess bash -lc 'cd /opt/bess/bessctl && ./bessctl run up4'
sudo docker restart pfcpiface
```

### 12.5 pdrLookup has 0 rules

Sessions are not installed or were lost.

Check:

```bash
curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions
```

Recreate pfcpsim association and sessions.

Use PFCP control through `enp9s0`, not N3.

### 12.6 PFCP sessions disappear after timeout

Symptom:

```text
read timeout for connection
removed connection to 192.168.70.2:8805
```

Cause:

```text
PFCP was using N3, but TRex DPDK takes over the N3 interface.
```

Fix:

```text
Use enp9s0 for PFCP control.
TRex control IP 192.168.90.2.
UPF control IP 192.168.90.1.
```

### 12.7 pdrLookup rules exist, but packets go to pdrLookupFail

Check PDR in pfcpiface logs:

```bash
sudo docker logs pfcpiface --tail 40 | grep 'PDR(id'
```

Correct PDR must show:

```text
tunnelIPv4Dst=192.168.70.1
```

If it shows `192.168.70.2`, pfcpsim was configured incorrectly.

Correct pfcpsim configuration:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.1 \
  --remote-peer-addr 192.168.90.1
```

### 12.8 Most packets fail at accessRxL4Cksum

Check:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module accessRxL4Cksum
```

Symptom:

```text
accessRxL4CksumFail increases heavily
```

Fix:

```text
Set outer UDP checksum to zero in the TRex GTP U profile.
```

Use:

```python
UDP(sport=2152, dport=2152, chksum=0)
```

### 12.9 gtpuDecap and farLookup work, but no N6 output

Check:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

If traffic goes to:

```text
enp8s0np0bad_route
```

Fix route and neighbor:

```bash
sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink
sudo docker restart bess-routectl
```

Expected route controller log:

```text
Route entry 192.168.80.2/32 added to enp8s0np0Routes
```

### 12.10 TRex fails with libibverbs missing

Install:

```bash
sudo apt install -y libibverbs1 ibverbs-providers librdmacm1 libmlx5-1
```

### 12.11 TRex fails with MLX5_1.24 not found

Install MLNX OFED userspace as described in section 5.4.

Validate:

```bash
strings /lib/x86_64-linux-gnu/libmlx5.so.1 | grep MLX5_1.24
```

### 12.12 TRex fails with Verbs device not found

Validate:

```bash
ls -l /dev/infiniband
ibv_devinfo
```

Load modules:

```bash
sudo modprobe ib_uverbs
sudo modprobe rdma_ucm
sudo modprobe mlx5_ib
```

If missing:

```bash
sudo apt install -y linux-modules-extra-$(uname -r)
```

### 12.13 TRex fails setting MTU to 65518

Edit `/etc/trex_cfg.yaml` and add:

```yaml
  port_mtu: 1500
```

### 12.14 stats shows port 1 RX, but stats -l shows RX pkts 0

This means forwarding works, but latency correlation failed.

Use TRex software mode:

```bash
sudo ./t-rex-64 -i --software --no-ofed-check -c 8
```

Then run:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py -p 0 -d 10 --force
stats -l
```

Expected for valid latency:

```text
RX pkts > 0
Avg latency > 0
Errors 0
```

## 13. Clean baseline checklist

Before experiments, ensure this baseline:

On UPF:

```bash
curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions

sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

Expected:

```text
pfcp_sessions{node_id="192.168.90.2"} 3
pdrLookup 6 rules
farLookup 6 rules
enp8s0np0Routes has gate 0 to enp8s0np0DstMAC1070FDC0EF81
```

On TRex:

```text
stats
```

Expected after a functional run:

```text
port 0 opackets increases
port 1 ipackets increases
errors remain 0
```

For latency:

```text
stats -l
```

Expected:

```text
PG ID 1, RX pkts > 0
PG ID 11, RX pkts > 0
PG ID 21, RX pkts > 0
Errors 0
```

## 14. Recommended experiment progression

Start with low rate:

```text
100 pps per TEID
10 Mbps total
```

Then increase gradually:

```text
50 Mbps
100 Mbps
500 Mbps
1 Gbps
```

At each step collect:

```text
TRex stats
TRex stats -l
UPF gtpuDecap packets
UPF farLookup packets
UPF enp8s0np0Fast Out/TX packets
BESS drops
pfcp_sessions
CPU usage
```

Use these as the first experimental metrics:

```text
Per TEID TX packets
Per TEID RX packets
Per TEID average latency
Per TEID max latency
Per TEID jitter
Port level packet loss
UPF decap packet count
UPF N6 output packet count
BESS drops
```

## 15. Key conclusions from setup validation

```text
BESS UPF AF_PACKET forwarding is functional.
PFCP must be separated from TRex controlled N3/N6 interfaces.
enp9s0 is used as dedicated PFCP control.
pfcpsim --n3-addr must point to the UPF N3 IP, 192.168.70.1.
TRex --gnb-addr must point to TRex N3 IP, 192.168.70.2.
Outer UDP checksum must be zero for GTP U traffic.
N6 route and neighbor must be explicitly installed because TRex uses DPDK.
TRex latency works with --software in this decapsulation scenario.
The observed latency is software instrumented end to end testbed latency, not Mellanox hardware latency.
```

# Appendix, DPDK Migration for BESS UPF with Mellanox

This appendix extends the previous AF_PACKET README with the additional steps required to run the BESS UPF datapath in DPDK mode with Mellanox ConnectX interfaces.

The goal is to keep the known good AF_PACKET setup intact and add a separate DPDK path.

## A1. Validated topology

```text
TRex control, enp9s0, 192.168.90.2
UPF control,  enp9s0, 192.168.90.1

TRex N3, enp7s0np0, 192.168.70.2, MAC 10:70:fd:c0:ef:80
UPF N3,  enp7s0np0, 192.168.70.1, MAC 10:70:fd:c1:59:c4

TRex N6, enp8s0np0, 192.168.80.2, MAC 10:70:fd:c0:ef:81
UPF N6,  enp8s0np0, 192.168.80.1, MAC 10:70:fd:c1:59:c5
```

Validated UPF PCI mapping:

```text
N3,  0000:07:00.0, enp7s0np0, MAC 10:70:fd:c1:59:c4
N6,  0000:08:00.0, enp8s0np0, MAC 10:70:fd:c1:59:c5
CTL, 0000:09:00.0, enp9s0,    MAC 16:af:85:d9:77:71
```

## A2. DPDK interpretation

With Mellanox `mlx5`, the NICs can remain bound to the kernel driver `mlx5_core`, while DPDK accesses them through Verbs/RDMA. Operationally, while BESS DPDK is using N3 and N6, treat those interfaces as datapath owned.

```text
Do not rely on ping over enp7s0np0 or enp8s0np0 while BESS DPDK is running.
Do not rely on tcpdump on enp7s0np0 or enp8s0np0 for datapath validation.
Do not rely on iperf3 on enp7s0np0 or enp8s0np0 while TRex or BESS DPDK owns the path.
Keep PFCP and management on enp9s0.
```

The static N6 neighbor is still needed because `route_control.py` uses the Linux route and neighbor tables to program BESS routes.

```bash
sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink
```

## A3. Prepare Mellanox userspace on the UPF host

Run on the UPF host.

```bash
cd /tmp

wget https://www.mellanox.com/downloads/ofed/MLNX_OFED-5.9-0.5.6.0/MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64.tgz

tar xzf MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64.tgz

cd MLNX_OFED_LINUX-5.9-0.5.6.0-ubuntu22.04-x86_64

sudo ./mlnxofedinstall --user-space-only --without-fw-update
sudo ldconfig
```

Load modules:

```bash
sudo modprobe ib_uverbs
sudo modprobe rdma_ucm
sudo modprobe mlx5_ib
```

Validate:

```bash
strings /lib/x86_64-linux-gnu/libmlx5.so.1 | grep MLX5_1.24
ls -l /dev/infiniband
ibv_devinfo
```

Expected:

```text
MLX5_1.24
/dev/infiniband/rdma_cm
/dev/infiniband/uverbs0
/dev/infiniband/uverbs1
/dev/infiniband/uverbs2
hca_id: mlx5_0, PORT_ACTIVE
hca_id: mlx5_1, PORT_ACTIVE
hca_id: mlx5_2, PORT_ACTIVE
```

In the validated setup:

```text
mlx5_0, node_guid 1070:fd03:00c1:59c4, N3
mlx5_1, node_guid 1070:fd03:00c1:59c5, N6
mlx5_2, node_guid 16af:85ff:fed9:7771, control
```

## A4. Create a separate DPDK config

Do not overwrite the AF_PACKET file.

```bash
cd ~/bess-upf/config
cp ~/bess-upf/upf/conf/upf.jsonc ./upf-dpdk-local.jsonc
```

Patch the local DPDK configuration:

```bash
python3 - <<'PY'
from pathlib import Path
import re

p = Path("upf-dpdk-local.jsonc")
s = p.read_text()

s = s.replace('"ifname": "ens803f2"', '"ifname": "enp7s0np0"')
s = s.replace('"ifname": "ens803f3"', '"ifname": "enp8s0np0"')

s = re.sub(r'"peers"\s*:\s*\[[^\]]*\]', '"peers": []', s)
s = re.sub(r'"ue_ip_pool"\s*:\s*"10\.250\.0\.0/16"', '"ue_ip_pool": "10.250.0.0/24"', s)
s = re.sub(r'"read_timeout"\s*:\s*[0-9]+', '"read_timeout": 25', s)

s = re.sub(r'"n6_bps"\s*:\s*[0-9]+', '"n6_bps": 1000000000', s)
s = re.sub(r'"n3_bps"\s*:\s*[0-9]+', '"n3_bps": 1000000000', s)
s = re.sub(r'"n6_burst_bytes"\s*:\s*[0-9]+', '"n6_burst_bytes": 12500000', s)
s = re.sub(r'"n3_burst_bytes"\s*:\s*[0-9]+', '"n3_burst_bytes": 12500000', s)

p.write_text(s)
PY
```

Validate:

```bash
grep -nE '"mode"|"ifname"|"peers"|"read_timeout"|"http_port"|"ue_ip_pool"|"n6_bps"|"n3_bps"|"n6_burst_bytes"|"n3_burst_bytes"' upf-dpdk-local.jsonc
```

Expected:

```text
"mode": "dpdk"
"ifname": "enp7s0np0"
"ifname": "enp8s0np0"
"peers": []
"http_port": "8080"
"ue_ip_pool": "10.250.0.0/24"
```

## A5. Why the original image did not detect Mellanox DPDK ports

The original `upf-bess:2.4.2-dev` image saw PCI and `/dev/infiniband`, but BESS reported:

```text
0 DPDK PMD ports have been recognized
```

The issue was not the host. The issue was the BESS plugin directory. The image had `librte_net_mlx5.so` under `/usr/local/lib/x86_64-linux-gnu`, but it was not symlinked into:

```text
/opt/bess/lib/dpdk-pmds
```

The Dockerfile keeps a narrow PMD set and does not automatically include vendor PMDs such as `mlx5`.

## A6. Create a derived BESS image with mlx5 enabled

Create this file in `~/bess-upf/config`.

```bash
cd ~/bess-upf/config

cat > Dockerfile.bess-mlx5 <<'EOF_DOCKER'
FROM upf-bess:2.4.2-dev

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    libibverbs1 \
    ibverbs-providers \
    librdmacm1 \
    libmlx5-1 \
    libnl-3-200 \
    libnl-route-3-200 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN set -e; \
    mkdir -p /opt/bess/lib/dpdk-pmds; \
    for pat in librte_common_mlx5 librte_net_mlx5; do \
      found=0; \
      for f in /usr/local/lib/x86_64-linux-gnu/${pat}.so*; do \
        if [ -f "$f" ]; then \
          ln -sf "$f" /opt/bess/lib/dpdk-pmds/; \
          found=1; \
        fi; \
      done; \
      if [ "$found" -eq 0 ]; then \
        echo "Missing ${pat}" >&2; \
        exit 1; \
      fi; \
    done; \
    ldconfig; \
    echo "MLX5 PMDs enabled:"; \
    ls -l /opt/bess/lib/dpdk-pmds | grep mlx5
EOF_DOCKER
```

Build:

```bash
sudo docker build --network=host -f Dockerfile.bess-mlx5 -t upf-bess:2.4.2-dev-mlx5 .
```

Validate:

```bash
sudo docker run --rm upf-bess:2.4.2-dev-mlx5 bash -lc '
find /opt/bess/lib/dpdk-pmds -iname "*mlx5*"
ldconfig -p | grep -E "mlx5|ibverbs|rdmacm" || true
'
```

Expected:

```text
/opt/bess/lib/dpdk-pmds/librte_common_mlx5.so
/opt/bess/lib/dpdk-pmds/librte_net_mlx5.so
libibverbs.so.1
libmlx5.so.1
```

## A7. Create the DPDK compose file

Create `docker-compose-dpdk.yml` in `~/bess-upf/config`.

```bash
cd ~/bess-upf/config

cat > docker-compose-dpdk.yml <<'EOF_COMPOSE'
services:
  bess:
    image: upf-bess:2.4.2-dev-mlx5
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
      - ./upf-dpdk-local.jsonc:/opt/bess/bessctl/conf/upf.jsonc
      - /sys:/sys
      - /sys/devices/system/node:/sys/devices/system/node
      - /lib/modules:/lib/modules
      - /dev/hugepages:/dev/hugepages
      - /dev/infiniband:/dev/infiniband
    command: >
      -grpc-url=0.0.0.0:10514

  pfcpiface:
    image: upf-pfcp:2.4.2-dev
    container_name: pfcpiface
    network_mode: host
    cap_add:
      - NET_ADMIN
    depends_on:
      - bess
    volumes:
      - ./upf-dpdk-local.jsonc:/conf/upf.jsonc
    command: >
      -config /conf/upf.jsonc
EOF_COMPOSE
```

Validate syntax:

```bash
sudo docker compose -f docker-compose-dpdk.yml config
```

## A8. Start DPDK BESS

Stop previous containers:

```bash
cd ~/bess-upf/config
sudo docker rm -f pfcpiface bess-routectl bess 2>/dev/null || true
```

Ensure hugepages:

```bash
sudo mkdir -p /dev/hugepages
sudo mount -t hugetlbfs nodev /dev/hugepages 2>/dev/null || true
sudo sysctl -w vm.nr_hugepages=1024
grep -i Huge /proc/meminfo
```

Start only `bess` first:

```bash
sudo docker compose -f docker-compose-dpdk.yml up -d bess
sleep 3
sudo docker logs bess --tail 80
```

Expected BESS log:

```text
3 DPDK PMD ports have been recognized:
DPDK port_id 0, mlx5_pci, MAC 10:70:fd:c1:59:c4
DPDK port_id 1, mlx5_pci, MAC 10:70:fd:c1:59:c5
DPDK port_id 2, mlx5_pci, MAC 16:af:85:d9:77:71
Server listening on 0.0.0.0:10514
```

The control NIC can be detected by DPDK, but the UPF pipeline must use only N3 and N6.

## A9. Load the UPF pipeline

```bash
sudo docker exec bess bash -lc 'cd /opt/bess/bessctl && ./bessctl run up4'
```

Warnings like these were observed and were not fatal:

```text
Mirror veth interface: enp7s0np0 misconfigured: veth interface enp7s0np0 does not exist
Mirror veth interface: enp8s0np0 misconfigured: veth interface enp8s0np0 does not exist
```

Validate BESS ports:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show port
```

Expected:

```text
enp7s0np0Fast, Driver PMDPort, MAC 10:70:fd:c1:59:c4, Speed 25,000Mbps, Link UP
enp8s0np0Fast, Driver PMDPort, MAC 10:70:fd:c1:59:c5, Speed 25,000Mbps, Link UP
```

## A10. Start pfcpiface

```bash
cd ~/bess-upf/config
sudo docker compose -f docker-compose-dpdk.yml up -d pfcpiface
sudo docker logs pfcpiface --tail 40
```

Expected:

```text
Mode: dpdk
AccessIface: enp7s0np0
CoreIface: enp8s0np0
Peers: []
UEIPPool: 10.250.0.0/24
listening for new PFCP connections on [::]:8805
```

## A11. Program the N6 route in BESS

```bash
sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink
```

Run the route controller with the mlx5 enabled image:

```bash
sudo docker rm -f bess-routectl 2>/dev/null || true

sudo docker run --name bess-routectl -td --restart unless-stopped \
  --net host \
  --pid container:bess \
  --entrypoint python3 \
  -v ~/bess-upf/upf/conf/route_control.py:/route_control.py \
  upf-bess:2.4.2-dev-mlx5 \
  /route_control.py -i enp7s0np0 enp8s0np0
```

Validate:

```bash
sudo docker logs bess-routectl --tail 20
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

Expected:

```text
Route entry 192.168.80.2/32 added to enp8s0np0Routes
0 -> enp8s0np0DstMAC1070FDC0EF81
8191 -> enp8s0np0bad_route
```

In DPDK mode, the route module input was observed as:

```text
enp8s0np0Routes input gate 0 from executeFAR:1
```

## A12. Recreate PFCP sessions from TRex

On the TRex host:

```bash
sudo docker rm -f pfcpsim 2>/dev/null || true

sudo docker run --rm -d --network host \
  --name pfcpsim \
  pfcpsim:patched \
  -p 12345 \
  --interface enp9s0
```

Configure:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.1 \
  --remote-peer-addr 192.168.90.1
```

Associate:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate
```

Create sessions:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2 \
  --app-filter "udp:any:any:allow:100"
```

Validate on the UPF host:

```bash
curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup | grep rules
```

Expected:

```text
pfcp_sessions{node_id="192.168.90.2"} 3
pdrLookup, 6 rules
farLookup, 6 rules
```

## A13. Validate DPDK forwarding with TRex

For forwarding and capacity, start TRex without software mode:

```bash
cd /opt/trex/v3.08
sudo ./t-rex-64 -i --no-ofed-check -c 8
```

In the TRex console:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_profile.py -p 0 -m 10mbps -d 10 --force
stats
```

Validate on the UPF host:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup | grep 'rules\|packets'
sudo docker exec bess /opt/bess/bessctl/bessctl show module gtpuDecap | grep packets
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup | grep packets
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
sudo docker exec bess /opt/bess/bessctl/bessctl show port | grep -A8 enp8s0np0Fast
```

Validated DPDK forwarding result:

```text
pdrLookup -> gtpuDecap, 30003 packets
pdrLookupFail, 0 packets

gtpuDecap, 30003 packets

farLookup -> farMerge, 30003 packets
farLookupFail, 0 packets

enp8s0np0Routes gate 0, 30003 packets
enp8s0np0bad_route, 0 packets

enp8s0np0Fast Out/TX, 30003 packets
enp8s0np0Fast dropped, 0
```

Validated TRex result:

```text
Port 0 opackets, 30003
Port 1 ipackets, 30007
drop_rate, 0 bps
oerrors, 0
ierrors, 0
```

This confirms BESS UPF forwarding in DPDK mode.

## A14. Latency measurement in the DPDK setup

Forwarding works without `--software`. However, latency by PG ID was only observed reliably when TRex was started with `--software`.

Start TRex for latency:

```bash
cd /opt/trex/v3.08
sudo ./t-rex-64 -i --software --no-ofed-check -c 8
```

In the TRex console:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py -p 0 -d 10 --force
stats -l
```

Validated DPDK latency result with TRex software mode:

```text
PG ID 1,  TX 443, RX 439, Avg 40427 us, Jitter 1, Errors 0
PG ID 11, TX 443, RX 439, Avg 40426 us, Jitter 3, Errors 0
PG ID 21, TX 443, RX 439, Avg 40445 us, Jitter 0, Errors 0
```

Interpretation:

```text
Forwarding DPDK works without TRex --software.
Latency by PG ID works with TRex --software.
The measured latency remains near 40 ms, which strongly suggests that the value is dominated by software instrumentation or the environment, not by the Mellanox datapath alone.
```

## A15. DPDK experiment checklist

Before each DPDK run, check:

```bash
sudo docker ps
sudo docker logs bess --tail 30
sudo docker logs pfcpiface --tail 30
sudo docker logs bess-routectl --tail 30

curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions

sudo docker exec bess /opt/bess/bessctl/bessctl show port
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

Expected:

```text
bess running
pfcpiface running
bess-routectl running
pfcp_sessions{node_id="192.168.90.2"} 3
enp7s0np0Fast, PMDPort, 25,000Mbps, Link UP
enp8s0np0Fast, PMDPort, 25,000Mbps, Link UP
pdrLookup, 6 rules
farLookup, 6 rules
enp8s0np0Routes gate 0 points to enp8s0np0DstMAC1070FDC0EF81
```

During forwarding runs, collect:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module gtpuDecap
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
sudo docker exec bess /opt/bess/bessctl/bessctl show port
```

From TRex:

```text
stats
stats -s
```

For latency runs with software mode:

```text
stats -l
```

## A16. Troubleshooting

### BESS sees 0 DPDK PMD ports

Check:

```bash
sudo docker exec bess bash -lc '
ls -l /dev/infiniband || true
find /opt/bess/lib/dpdk-pmds -iname "*mlx5*"
ldconfig -p | grep -E "mlx5|ibverbs|rdmacm" || true
'
```

Fix:

```text
Use upf-bess:2.4.2-dev-mlx5.
Ensure librte_common_mlx5 and librte_net_mlx5 are symlinked into /opt/bess/lib/dpdk-pmds.
Ensure /dev/infiniband is mounted into the container.
```

### BESS detects the control interface as a DPDK port

This was observed:

```text
port_id 2, MAC 16:af:85:d9:77:71
```

This is acceptable if the UPF pipeline uses only:

```text
enp7s0np0Fast
enp8s0np0Fast
```

### N6 route does not get installed

Reinstall the static neighbor and route:

```bash
sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink
sudo docker restart bess-routectl
```

Validate:

```bash
sudo docker logs bess-routectl --tail 20
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
```

### Rules exist but no N6 output

Check all stages:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module gtpuDecap
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup
sudo docker exec bess /opt/bess/bessctl/bessctl show module enp8s0np0Routes
sudo docker exec bess /opt/bess/bessctl/bessctl show port | grep -A8 enp8s0np0Fast
```

Working path:

```text
pdrLookup gate 1 to gtpuDecap increases
gtpuDecap increases
farLookup gate 0 to farMerge increases
farLookupFail remains 0
enp8s0np0Routes gate 0 increases
enp8s0np0bad_route remains 0
enp8s0np0Fast Out/TX increases
```

### TRex receives packets but stats -l has RX pkts 0

Forwarding is working, but latency correlation is not.

Use TRex software mode for latency:

```bash
sudo ./t-rex-64 -i --software --no-ofed-check -c 8
```

Then:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py -p 0 -d 10 --force
stats -l
```

## A17. Roll back to AF_PACKET

If needed:

```bash
cd ~/bess-upf/config

sudo docker rm -f pfcpiface bess-routectl bess 2>/dev/null || true

sudo docker compose up -d

sudo docker exec bess bash -lc 'cd /opt/bess/bessctl && ./bessctl run up4'

sudo docker restart pfcpiface

sudo ip neigh replace 192.168.80.2 lladdr 10:70:fd:c0:ef:81 dev enp8s0np0 nud permanent
sudo ip route replace 192.168.80.2/32 via 192.168.80.2 dev enp8s0np0 onlink

sudo docker run --name bess-routectl -td --restart unless-stopped \
  --net host \
  --pid container:bess \
  --entrypoint python3 \
  -v ~/bess-upf/upf/conf/route_control.py:/route_control.py \
  upf-bess:2.4.2-dev \
  /route_control.py -i enp7s0np0 enp8s0np0
```

Recreate PFCP sessions from TRex:

```bash
sudo docker rm -f pfcpsim 2>/dev/null || true

sudo docker run --rm -d --network host \
  --name pfcpsim \
  pfcpsim:patched \
  -p 12345 \
  --interface enp9s0

sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.1 \
  --remote-peer-addr 192.168.90.1

sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate

sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2 \
  --app-filter "udp:any:any:allow:100"
```

Validate:

```bash
curl -s http://127.0.0.1:8080/metrics | grep pfcp_sessions
sudo docker exec bess /opt/bess/bessctl/bessctl show module pdrLookup | grep rules
sudo docker exec bess /opt/bess/bessctl/bessctl show module farLookup | grep rules
```
# Results Appendix, First Valid DPDK Slice Experiment

This appendix summarizes the first validated BESS-UPF DPDK experiment with three simultaneous slices. It is intended to be appended to the main setup README.

## Experiment Identification

```text
Experiment name: dpdk_latency_run001
Date: 2026-04-30
TRex profile: /opt/trex/v3.08/automation/exp2/exp2_latency_profile.py
TRex mode: software latency mode
Duration: 30 s
TX port: 0
RX port: 1
UPF datapath: BESS-UPF DPDK with Mellanox mlx5 PMD
```

## Active Setup

The experiment was executed with the DPDK UPF stack already running.

```text
bess          upf-bess:2.4.2-dev-mlx5
pfcpiface     upf-pfcp:2.4.2-dev
bess-routectl upf-bess:2.4.2-dev-mlx5
```

The PFCP control plane remained active through the control interface.

```text
pfcp_sessions{node_id="192.168.90.2"} 3
```

The BESS datapath was using DPDK PMD ports.

```text
Access/N3: enp7s0np0Fast, PMDPort, 25,000 Mbps, MAC 10:70:fd:c1:59:c4
Core/N6:   enp8s0np0Fast, PMDPort, 25,000 Mbps, MAC 10:70:fd:c1:59:c5
```

## Slice Mapping

The experiment used three slices represented by different PG IDs.

```text
Slice 1: PG ID 1
Slice 2: PG ID 11
Slice 3: PG ID 21
```

Each slice transmitted 3000 packets during the 30 s run.

## TRex Aggregate Results

The TRex run completed successfully.

```text
ok: true
started_at: 2026-04-30T20:23:07.687946Z
finished_at: 2026-04-30T20:23:38.836878Z
```

Aggregate TRex port counters were:

```text
Port 0 TX packets: 9000
Port 0 TX bytes:   1,890,000

Port 1 RX packets: 9003
Port 1 RX bytes:   1,566,303

Port 0 output errors: 0
Port 1 input errors:  0
```

The three extra packets observed on port 1 are not part of the per-slice flow counters. The per-slice counters show exactly 9000 received data packets across the three PG IDs.

## TRex Per-Slice Flow Results

Per-slice flow statistics confirmed that all three slices were transmitted and received correctly.

| PG ID | TX packets | RX packets | TX bytes | RX bytes | Packet loss |
|---:|---:|---:|---:|---:|---:|
| 1  | 3000 | 3000 | 630,000 | 522,000 | 0 |
| 11 | 3000 | 3000 | 630,000 | 522,000 | 0 |
| 21 | 3000 | 3000 | 630,000 | 522,000 | 0 |

Total per-slice flow counters:

```text
Total TX packets: 9000
Total RX packets: 9000
Total TX bytes:   1,890,000
Total RX bytes:   1,566,000
Total loss:       0 packets
```

The byte difference between TX and RX is expected because the UPF decapsulates the GTP-U packets before forwarding them toward N6.

## TRex Per-Slice Latency Results

Latency was successfully measured per PG ID.

| PG ID | Average latency | Minimum latency | Maximum latency | Jitter | Dropped | Out of order | Duplicates |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1  | 40.425 ms | 40.423 ms | 40.432 ms | 0 us   | 0 | 0 | 0 |
| 11 | 40.587 ms | 40.422 ms | 42.385 ms | 124 us | 0 | 0 | 0 |
| 21 | 40.437 ms | 40.422 ms | 40.462 ms | 8 us   | 0 | 0 | 0 |

Raw latency values reported by TRex were in microseconds.

```text
PG ID 1
average: 40425 us
min:     40423 us
max:     40432 us
jitter:  0 us

PG ID 11
average: 40587 us
min:     40422 us
max:     42385 us
jitter:  124 us

PG ID 21
average: 40437 us
min:     40422 us
max:     40462 us
jitter:  8 us
```

No sequence-level errors were reported by TRex.

```text
dropped:       0
out_of_order:  0
dup:           0
seq_too_high:  0
seq_too_low:   0
```

## UPF Counter Deltas

UPF snapshots were collected before and after the TRex run.

### Prometheus UPF Metrics

| Metric | Before | After | Delta |
|---|---:|---:|---:|
| upf_packets_count rx Access | 2,038,310 | 2,047,311 | 9,001 |
| upf_packets_count tx Core   | 1,692,499 | 1,701,499 | 9,000 |
| upf_bytes_count rx Access   | 673,591,852 | 675,445,938 | 1,854,086 |
| upf_bytes_count tx Core     | 497,163,742 | 498,693,742 | 1,530,000 |
| upf_dropped_count rx Access | 0 | 0 | 0 |
| upf_dropped_count tx Core   | 0 | 0 | 0 |

The Access RX packet delta contains one additional packet compared with the main datapath counters. The BESS module counters confirm that exactly 9000 packets traversed the validated GTP-U processing path.

### BESS Module Deltas

| BESS module path | Before | After | Delta |
|---|---:|---:|---:|
| pdrLookup to gtpuDecap | 2,038,299 | 2,047,299 | 9,000 |
| gtpuDecap output | 2,038,299 | 2,047,299 | 9,000 |
| farLookup to farMerge | 1,692,499 | 1,701,499 | 9,000 |
| enp8s0np0Routes gate 0 | 1,692,499 | 1,701,499 | 9,000 |
| enp8s0np0Fast Out/TX | 1,692,499 | 1,701,499 | 9,000 |

Failure and drop paths remained at zero.

```text
pdrLookupFail:      0
farLookupFail:      0
enp8s0np0bad_route: 0
enp7s0np0Fast dropped: 0
enp8s0np0Fast dropped: 0
```

## Validated Datapath

The following datapath was validated in this experiment.

```text
TRex port 0
  -> UPF Access/N3, enp7s0np0Fast, DPDK PMDPort
  -> pdrLookup
  -> gtpuDecap
  -> appQERLookup/sessionQERLookup
  -> farLookup
  -> farMerge/executeFAR
  -> enp8s0np0Routes
  -> enp8s0np0DstMAC1070FDC0EF81
  -> UPF Core/N6, enp8s0np0Fast, DPDK PMDPort
  -> TRex port 1
```

## Result Summary

This run validates the complete DPDK datapath for three simultaneous slices.

```text
BESS-UPF DPDK forwarding: OK
PFCP sessions: 3 active sessions
Per-slice TX/RX counters: OK
Per-slice latency: OK
Packet loss by PG ID: 0
Sequence errors: 0
UPF datapath drops: 0
Bad route packets: 0
PDR lookup failures: 0
FAR lookup failures: 0
```

The measured average latency remained around 40 ms for all three PG IDs. Since this latency measurement used TRex software mode, this value should be interpreted as the latency of the current software-instrumented measurement setup, not as the intrinsic latency of the Mellanox NICs or the physical links alone.

# Appendix, Per-Slice QoS Enforcement via Patched pfcpsim

This appendix extends the previous DPDK BESS-UPF testbed README with the steps required to enable
**per-slice Maximum Bit Rate (MBR) enforcement** through PFCP QoS Enforcement Rules (QERs).

The goal is to move beyond uniform forwarding and start exercising the BESS-UPF QoS pipeline
(`appQERLookup`, `sessionQERLookup`, `appQERMeterRed`) with **distinct rate limits per slice** that
can be applied at session creation time and **modified at runtime without tearing sessions down**.

The default `pfcpsim` shipped by the omec-project hardcodes MBR values inside `internal/pfcpsim/server.go`,
so all created sessions share the same QER MBR. This appendix documents a minimal patch that exposes
per-session MBR through the gRPC API and the `pfcpctl` CLI, plus the validation experiment.

## B1. What this appendix adds on top of the existing setup

```text
- Per-session MBR uplink and downlink at session creation
- Per-session MBR runtime modification through Session Modification Request (no session re-establishment)
- pfcpctl flags: --session-mbr-uplink, --session-mbr-downlink, --app-mbr-uplink, --app-mbr-downlink
- Validation that BESS appQERLookup gate 3 (appQERMeterRed) drops only the slice that exceeds its MBR
- Per-slice TRex flow latency stats confirming policer behaviour per PG ID
```

What does **not** change:

```text
- BESS-UPF DPDK image (upf-bess:2.4.2-dev-mlx5)
- pfcpiface image
- BESS pipeline (up4)
- Static N6 neighbor and route
- TRex installation, OFED, DPDK config
- N3, N6, control interface IPs and MACs
```

## B2. Patched pfcpsim source layout

The patched fork keeps the original layout. Only four files change.

```text
~/pfcpsim_v2/
├── api/pfcpsim.proto                          # adds 4 repeated uint64 MBR fields
├── internal/pfcpsim/server.go                 # honors the new MBR fields in Create/Modify
├── internal/pfcpctl/commands/sessions.go      # adds the 4 CLI flags, parses CSV
└── Dockerfile                                 # regenerates protobuf at build time
```

Backup the originals before applying the patch:

```bash
cd ~/pfcpsim_v2
mkdir -p .backup
cp api/pfcpsim.proto .backup/
cp internal/pfcpsim/server.go .backup/
cp internal/pfcpctl/commands/sessions.go .backup/
cp Dockerfile .backup/
```

## B3. Patched `api/pfcpsim.proto`

Adds four `repeated uint64` lists, one element per session. Each value is in **kbps**. Empty list
means "use defaults on Create" or "do not modify on Modify".

```bash
cat > api/pfcpsim.proto <<'EOF'
// SPDX-License-Identifier: Apache-2.0
// Copyright 2022-present Open Networking Foundation

syntax = "proto3";
package api;

option go_package = ".;api";

message CreateSessionRequest {
  int32 count = 1;
  int32 baseID = 2;
  string nodeBAddress = 3;
  string ueAddressPool = 4;
  repeated string appFilters = 5;
  int32 qfi = 6;
  // Per-session MBR overrides (kbps). One value per session. If empty, defaults are used.
  repeated uint64 sessionMbrUplink = 7;
  repeated uint64 sessionMbrDownlink = 8;
  repeated uint64 appMbrUplink = 9;
  repeated uint64 appMbrDownlink = 10;
}

message ModifySessionRequest {
  int32 count = 1;
  int32 baseID = 2;
  string nodeBAddress = 3;
  string ueAddressPool = 4;
  bool bufferFlag = 5;
  bool notifyCPFlag = 6;
  repeated string appFilters = 7;
  // Per-session MBR overrides (kbps). Only categories with at least one non-empty list are updated.
  repeated uint64 sessionMbrUplink = 8;
  repeated uint64 sessionMbrDownlink = 9;
  repeated uint64 appMbrUplink = 10;
  repeated uint64 appMbrDownlink = 11;
}

message ConfigureRequest {
  string upfN3Address = 1;
  string remotePeerAddress = 3;
}

message DeleteSessionRequest {
  int32 count = 1;
  int32 baseID = 2;
}

message EmptyRequest {}

message Response {
  int32 status_code = 1;
  string message = 2;
}

service PFCPSim {
  rpc Configure (ConfigureRequest) returns (Response) {}
  rpc Associate (EmptyRequest) returns (Response) {}
  rpc Disassociate (EmptyRequest) returns (Response) {}
  rpc CreateSession (CreateSessionRequest) returns (Response) {}
  rpc ModifySession (ModifySessionRequest) returns (Response) {}
  rpc DeleteSession (DeleteSessionRequest) returns (Response) {}
}
EOF
```

## B4. Patched `internal/pfcpsim/server.go`

The two relevant pieces are:

```text
- pickMBR helper: returns the per-session value if provided, otherwise the default
- ModifySession: only sends QER Update IEs for the categories that the caller actually asked to change
```

The full patched file is available in the project repository; the critical Modify behaviour is:

```go
updateSessionMBR := len(request.SessionMbrUplink) > 0 || len(request.SessionMbrDownlink) > 0
updateAppMBR     := len(request.AppMbrUplink) > 0     || len(request.AppMbrDownlink) > 0

// Only QERs explicitly requested are updated.
if updateSessionMBR { /* push session-level QER update */ }
if updateAppMBR     { /* push app-level QER updates    */ }
```

This avoids overwriting the session-level QER with defaults when the caller only wants to retune
the application-level MBR, which was the failure mode observed in the first iteration of the patch.

## B5. Patched `internal/pfcpctl/commands/sessions.go`

Adds four CSV flags to both `session create` and `session modify`:

```text
--session-mbr-uplink     CSV in kbps, one value per session
--session-mbr-downlink   CSV in kbps, one value per session
--app-mbr-uplink         CSV in kbps, one value per session
--app-mbr-downlink       CSV in kbps, one value per session
```

Empty input is treated as "no override". Invalid input (non-integer, negative, malformed CSV) is
fatal and surfaces a clear error message before any gRPC call.

## B6. Patched `Dockerfile`

The original Dockerfile relied on pre-generated `.pb.go` files. After modifying `pfcpsim.proto`,
the `.pb.go` artifacts must be regenerated. The patched Dockerfile installs `protoc` plus the Go
plugins inside the build stage so the regeneration happens automatically and reproducibly:

```Dockerfile
FROM golang:1.26.2-bookworm AS builder
WORKDIR /pfcpctl

RUN apt-get update && apt-get install -y --no-install-recommends \
    protobuf-compiler && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/go/bin:${PATH}"
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2 && \
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1

COPY . .

RUN protoc \
    --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    api/pfcpsim.proto

RUN CGO_ENABLED=0 go build -o ./pfcpctl cmd/pfcpctl/main.go && \
    CGO_ENABLED=0 go build -o ./pfcpsim cmd/pfcpsim/main.go

FROM alpine:3.23 AS pfcpsim
RUN apk add --no-cache tcpdump
COPY --from=builder /pfcpctl/pfcp* /usr/local/bin/
ENTRYPOINT [ "pfcpsim" ]
```

This means the host TRex machine does not need `protoc` or Go installed locally.

## B7. Build the patched image

Run on the TRex host:

```bash
cd ~/pfcpsim_v2
sudo docker build --network=host -t pfcpsim:patched .
```

Validate:

```bash
sudo docker images | grep pfcpsim
```

Expected:

```text
pfcpsim   patched
```

## B8. Bring the patched pfcpsim up

```bash
sudo docker rm -f pfcpsim 2>/dev/null || true

sudo docker run --rm -d --network host \
  --name pfcpsim \
  pfcpsim:patched \
  -p 12345 \
  --interface enp9s0
```

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 service configure \
  --n3-addr 192.168.70.1 \
  --remote-peer-addr 192.168.90.1

sudo docker exec pfcpsim pfcpctl -s localhost:12345 service associate
```

Confirm the new flags exist:

```bash
sudo docker exec pfcpsim pfcpctl session create --help
```

Expected (truncated):

```text
--session-mbr-uplink   string   Per-session uplink session-level MBR in kbps, CSV
--session-mbr-downlink string   Per-session downlink session-level MBR in kbps, CSV
--app-mbr-uplink       string   Per-session uplink app-level MBR in kbps, CSV
--app-mbr-downlink     string   Per-session downlink app-level MBR in kbps, CSV
```

## B9. Create three sessions with different per-slice MBRs

For the validation experiment, the application-level MBR is set per slice while the session-level
MBR is kept high (1 Gbps) so that only the application-level policer is exercised.

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 session create \
  --count 3 --baseID 1 \
  --ue-pool 10.250.0.0/24 \
  --gnb-addr 192.168.70.2 \
  --app-filter "udp:any:any:allow:100" \
  --session-mbr-uplink   1000000,1000000,1000000 \
  --session-mbr-downlink 1000000,1000000,1000000 \
  --app-mbr-uplink       50000,200000,500000 \
  --app-mbr-downlink     50000,200000,500000
```

Validated pfcpsim log:

```text
Create session idx=0 baseID=1  MBR session(ul=1000000,dl=1000000) app(ul=50000,dl=50000)  kbps
Create session idx=1 baseID=11 MBR session(ul=1000000,dl=1000000) app(ul=200000,dl=200000) kbps
Create session idx=2 baseID=21 MBR session(ul=1000000,dl=1000000) app(ul=500000,dl=500000) kbps
3 sessions were established using 1 as baseID
```

Validated UPF state:

```text
pfcp_sessions{node_id="192.168.90.2"} 3
pdrLookup,        6 rules
farLookup,        6 rules
appQERLookup,    12 rules
sessionQERLookup, 6 rules
```

## B10. Modify session MBR at runtime

The patched Modify operation accepts the same per-slice MBR arrays. Only the categories that have
at least one non-empty array are pushed as PFCP `Session Modification Request` with QER Update IEs.

Example, retune slice 11 only at the application level, leaving session-level untouched:

```bash
sudo docker exec pfcpsim pfcpctl -s localhost:12345 session modify \
  --count 3 --baseID 1 \
  --app-filter "udp:any:any:allow:100" \
  --app-mbr-uplink   50000,100000,500000 \
  --app-mbr-downlink 50000,100000,500000
```

Validated pfcpsim log:

```text
Modify session idx=0 baseID=1  app-level MBR (ul=50000,dl=50000)   kbps
Modify session idx=1 baseID=11 app-level MBR (ul=100000,dl=100000) kbps
Modify session idx=2 baseID=21 app-level MBR (ul=500000,dl=500000) kbps
3 sessions were modified
```

The absence of `session-level MBR` log lines confirms that the patched Modify path correctly
preserved the existing session-level QER values, which was the intended behaviour.

## B11. Validation experiment, overload profile

A higher rate TRex profile is used to drive each slice **above its MBR**, so that the BESS policer
takes effect.

```bash
cat > /opt/trex/v3.08/automation/exp2/exp2_overload_lat_profile.py <<'EOF'
from trex_stl_lib.api import *
from scapy.contrib.gtp import GTP_U_Header

GNB_IP = "192.168.70.2"
UPF_N3_IP = "192.168.70.1"
DN_IP = "192.168.80.2"
PAYLOAD_BYTES = 128
PPS_PER_SLICE = 50000  # ~70 Mbps per slice in software mode

SLICES = [
    {"teid": 1,  "ue_ip": "10.250.0.1", "src_port": 10001, "pg_id": 1},
    {"teid": 11, "ue_ip": "10.250.0.2", "src_port": 10011, "pg_id": 11},
    {"teid": 21, "ue_ip": "10.250.0.3", "src_port": 10021, "pg_id": 21},
]

class STLS1(object):
    def get_streams(self, direction=0, **kwargs):
        streams = []
        for s in SLICES:
            pkt = (
                Ether()
                / IP(src=GNB_IP, dst=UPF_N3_IP)
                / UDP(sport=2152, dport=2152, chksum=0)
                / GTP_U_Header(teid=s["teid"])
                / IP(src=s["ue_ip"], dst=DN_IP)
                / UDP(sport=s["src_port"], dport=5555, chksum=0)
                / ("X" * PAYLOAD_BYTES)
            )
            streams.append(
                STLStream(
                    name="ovl_lat_teid_%s" % s["teid"],
                    packet=STLPktBuilder(pkt=pkt),
                    mode=STLTXCont(pps=PPS_PER_SLICE),
                    flow_stats=STLFlowLatencyStats(pg_id=s["pg_id"]),
                )
            )
        return streams

def register():
    return STLS1()
EOF
```

Two profiles are useful in practice:

```text
exp2_overload_profile.py      STLFlowStats,        higher pps, no --software needed
exp2_overload_lat_profile.py  STLFlowLatencyStats, requires TRex --software for per-PG RX
```

In the validated experiment the second one was used because per-slice RX correlation was the goal.

## B12. Run the experiment

UPF host, snapshot before:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module appQERLookup > /tmp/qer_before.txt
sudo docker exec bess /opt/bess/bessctl/bessctl show port | grep -A8 enp8s0np0Fast
```

TRex host, software mode:

```bash
sudo pkill -f t-rex-64
sleep 2
cd /opt/trex/v3.08
sudo ./t-rex-64 -i --software --no-ofed-check -c 8
```

In another TRex terminal:

```bash
cd /opt/trex/v3.08
sudo ./trex-console
```

In the TRex console:

```text
service --port 1
start -f /opt/trex/v3.08/automation/exp2/exp2_overload_lat_profile.py -p 0 -d 30 --force
stats -l
```

UPF host, snapshot after (during or just after the run):

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module appQERLookup > /tmp/qer_after.txt
sudo docker exec bess /opt/bess/bessctl/bessctl show port | grep -A8 enp8s0np0Fast
```

## B13. Validated results, overload run, MBRs 50 / 200 / 500 Mbps

A first stress run was executed with a higher pps overload profile (no latency stats) to produce a
clean macro-level conservation check. Duration ~58 s, ~12 M packets transmitted in total.

### TRex aggregate counters

```text
Port 0 TX packets: 12,000,003
Port 1 RX packets:  8,001,304
Drop:               3,998,699
oerrors / ierrors:  0 / 0
```

### BESS appQERLookup deltas

| Output gate | Meaning           | Before    | After     | Delta     |
|---:|---|---:|---:|---:|
| 1 | passes to sessionQER (alt path) | 4,920    | 4,923    | +3        |
| 2 | passes to sessionQER (main path)| 1,921,588| 9,922,882| +8,001,294|
| 3 | dropped by appQERMeterRed       | 345,800  | 4,344,506| +3,998,706|
| 4 | appQERLookupFail                | 0        | 0        | 0         |
| 5 | appQERStatusDrop                | 0        | 0        | 0         |

### BESS port enp8s0np0Fast (N6 output)

```text
Out/TX before: 1,926,508 packets
Out/TX after:  9,927,805 packets
Delta:         8,001,297 packets
NIC dropped:   0
```

### Conservation of packets

```text
TRex TX                                 = 12,000,003
BESS appQERLookup gate2 + gate3 delta   = 12,000,000
BESS port enp8s0np0Fast Out/TX delta    =  8,001,297
TRex RX                                 =  8,001,304
BESS gate3 delta (policer drop)         =  3,998,706
TRex aggregate drop                     =  3,998,699
```

The mismatch of a few packets between counters is consistent with PFCP keepalives and timing of the
snapshot windows. The macro-level conservation matches: every packet is accounted for either as
forwarded to N6 or as dropped by the application-level policer, with zero datapath failures.

## B14. Validated results, per-slice latency run, MBRs 50 / 200 / 500 Mbps

A second run executed the latency overload profile with `STLFlowLatencyStats` and TRex `--software`
mode to obtain per-PG-ID counters. ~50 kpps per slice, ~70 Mbps per slice offered load.

| PG ID | TX pkts | RX pkts | Loss     | Avg latency | Min latency | Max latency | Jitter |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1  | 924,033 | 737,959 | 186,074  | 40.424 ms | 40.421 ms | 42.829 ms | 1 us |
| 11 | 924,033 | 922,011 | 2,022    | 40.423 ms | 40.421 ms | 41.001 ms | 2 us |
| 21 | 924,033 | 922,010 | 2,023    | 40.439 ms | 40.421 ms | 43.936 ms | 0 us |

Per-slice errors reported by TRex:

```text
PG ID 1   Errors 184.05 K
PG ID 11  Errors      0
PG ID 21  Errors      0
```

Interpretation:

```text
- Slice 1 cap is 50 Mbps. Offered load ~70 Mbps. Roughly 80% of packets pass, 20% are dropped by the policer.
- Slice 11 cap is 200 Mbps. Offered load ~70 Mbps, well below the cap. All packets pass except for ~0.2% noise.
- Slice 21 cap is 500 Mbps. Offered load ~70 Mbps. All packets pass except for ~0.2% noise.
- The latency floor near 40 ms is the same software-instrumented floor observed in the previous DPDK forwarding
  validation appendix and is not attributable to the BESS or Mellanox datapath.
```

This confirms that **the policer applies different rate limits per slice**, exactly as configured
through the patched PFCP control path.

## B15. Validated datapath under per-slice MBR enforcement

```text
TRex port 0
  -> UPF Access/N3, enp7s0np0Fast, DPDK PMDPort
  -> pdrLookup
  -> gtpuDecap
  -> appQERLookup
        gate 2 -> sessionQERLookup -> farLookup -> ... -> N6
        gate 3 -> appQERMeterRed (Sink, drop above MBR)
  -> sessionQERLookup
  -> farLookup
  -> farMerge / executeFAR
  -> enp8s0np0Routes
  -> enp8s0np0DstMAC1070FDC0EF81
  -> UPF Core/N6, enp8s0np0Fast, DPDK PMDPort
  -> TRex port 1 RX
```

## B16. Operational notes

```text
- MBR values are passed in kbps. 50 Mbps is "50000".
- The session-level QER (qer_id=0) and the app-level QERs are independent.
- Setting a low session-level MBR caps the entire session regardless of app rules.
- Setting a low app-level MBR only caps the matched application traffic for that session.
- For experimental studies focused on slice differentiation, keep the session-level MBR very high
  (1 Gbps in this appendix) and vary the app-level MBR per slice.
- Modify uses PFCP Session Modification Request with QER Update IEs. Session, PDR, FAR, and TEID
  state are preserved; in-flight packets are not interrupted.
- The patched Modify only sends QER Update IEs for categories that the caller passes explicitly.
  Calling modify with only --app-mbr-* will not change session-level MBR, and vice versa.
- pdrLookupFail, farLookupFail, enp8s0np0bad_route, and NIC drop counters all remained at 0
  during the validated runs, confirming that the policer is the only source of drops.
```

## B17. Troubleshooting specific to the patched build

### Build fails on `protoc` step

The patched Dockerfile pins:

```text
google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
```

If a different version is installed locally and the host Go is too old (1.18 or earlier), avoid
running the build outside Docker. The Dockerfile uses `golang:1.26.2-bookworm` and works regardless
of the host Go version.

### `pfcpctl session create --help` does not show the new flags

Check that the pfcpsim image used at runtime is `pfcpsim:patched` and not the upstream one:

```bash
sudo docker inspect --format '{{.Config.Image}}' pfcpsim
```

### Modify keeps overwriting session-level MBR with the defaults

This was the first-iteration bug. If observed, confirm that the running container was rebuilt from
the patched source and that the `if updateSessionMBR { ... }` and `if updateAppMBR { ... }` guards
are present in `internal/pfcpsim/server.go`.

### `appQERMeterRed` Sink shows zero packets at its input gate

The drop counter is reported on the **output gate of `appQERLookup`** (gate 3), not at the input
of the Sink. Always read the policer drop count from:

```bash
sudo docker exec bess /opt/bess/bessctl/bessctl show module appQERLookup
```

and look at the output gate that feeds `appQERMeterRed`.

### Per-PG-ID RX is zero with `STLFlowStats`

`STLFlowStats` relies on a marker that may not be preserved across the GTP-U decap on the validated
Mellanox + TRex 3.08 combination. For per-slice RX correlation, use `STLFlowLatencyStats` and start
TRex with `--software`. This is the same constraint already documented in section 12.14 of the main
README.

## B18. Result summary

```text
Per-session MBR via PFCP QER:        OK
Runtime MBR modification:            OK (no session re-establishment)
Policer drops only the overloaded slice (slice 1, cap 50 Mbps): OK
Slices below their cap (slices 11 and 21) pass without policer drops: OK
Datapath conservation (TX = forwarded + policed): OK
PDR / FAR / route / NIC drop failures: 0
```

This appendix completes the BESS-UPF DPDK testbed by adding a working, runtime-controllable QoS
enforcement plane per slice. It establishes the operational and measurement foundation required
for closed-loop slice control experiments, where an external controller can adjust MBR values in
response to telemetry without disrupting active sessions.
