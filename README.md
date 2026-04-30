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

