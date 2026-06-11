# 🚀 Agentic Orchestration for SLA-Constrained Network Slicing in Programmable Mobile Data Planes

[![Status](https://img.shields.io/badge/status-submitted-blue)]()
[![Venue](https://img.shields.io/badge/venue-IEEE%20CCNC%202027-purple)]()
[![Reproducibility](https://img.shields.io/badge/reproducibility-available-brightgreen)]()
[![Platform](https://img.shields.io/badge/platform-BESS--UPF%20%7C%20TRex%20%7C%20DPDK-orange)]()
[![License](https://img.shields.io/badge/license-research--only-lightgrey)]()

This repository provides the experimental artifacts for the paper:

> **Agentic Orchestration for SLA-Constrained Network Slicing in Programmable Mobile Data Planes**

Submitted to **IEEE Consumer Communications & Networking Conference 2027 (CCNC 2027)**.

---

## 👥 Authors

**Rodrigo Moreira**  
**Larissa Ferreira Rodrigues Moreira**  
**Joberto S. B. Martins**  
**Tereza C. Carvalho**  
**Flávio de Oliveira Silva**

---

## 📌 Overview

This repository supports the reproducibility of an agentic control-loop architecture for runtime QoS enforcement in programmable mobile data planes.

The proposed system combines:

- 📡 **BESS-UPF telemetry**
- ⚙️ **PFCP-based runtime MBR modification**
- 🧠 **Local LLM-based candidate selection**
- 🛡️ **SLA-monotone validation**
- 📊 **Structured audit logs**
- 🚦 **Static, threshold, greedy, and agentic QoS controllers**
- 🧪 **TRex-based overload experiments over a real UPF datapath**

The goal is to evaluate whether an agentic controller can adapt per-session Maximum Bit Rate (MBR) values under overload while preserving SLA priority across coexisting network slices.

---

## 🧠 Paper Contribution in One Sentence

We show that a locally hosted LLM can participate in a telemetry-aware PFCP control loop for UPF QoS enforcement, provided that the model is constrained to select among deterministic, SLA-safe MBR candidates rather than generating actions freely.

---

## 🧪 Reproducibility Guide

The complete step-by-step reproducibility guide is available here:

➡️ **[TUTORIAL.md](./TUTORIAL.md)**

The tutorial includes:

- Two-host BESS-UPF and TRex topology
- UPF host installation
- TRex host installation
- BESS-UPF in AF_PACKET and DPDK modes
- Mellanox `mlx5` DPDK configuration
- Patched `pfcpsim` with runtime MBR modification
- PFCP session creation and modification
- Per-slice QoS enforcement validation
- Agentic experiment planning
- Monitoring and troubleshooting commands

---

## 🏗️ Experimental Platform

The experiments use a two-host testbed:

```text
TRex Host                              UPF Host
─────────                              ────────

TRex traffic generator     N3      ->  BESS-UPF access interface
TRex receiver              N6      <-  BESS-UPF core interface
pfcpsim / pfcpctl          PFCP    ->  pfcpiface / BESS-UPF
Agentic controller         API     ->  telemetry + PFCP actuation
```

The validated datapath is:

```text
TRex port 0
  -> UPF N3
  -> pdrLookup
  -> GTP-U decapsulation
  -> appQERLookup / sessionQERLookup
  -> farLookup
  -> N6 route
  -> UPF N6
  -> TRex port 1
```

---

## 🔬 Controllers Evaluated

| ID | Controller | Description |
|---|---|---|
| **E1** | Static | Fixed MBR vector, no runtime adaptation |
| **E2** | Threshold | Rule-based reaction to utilization or overload |
| **E3** | Greedy | Utilization-oriented headroom allocation |
| **E4** | Agentic | LLM-assisted telemetry-aware control loop |
| **E4b** | Constrained Agentic | SLA-monotone candidate selection with deterministic validation |

---

## 📊 Main Metrics

The experiments collect:

- Delivered throughput
- Policing ratio
- Per-slice packet loss
- MBR trajectory
- Number of `modify_mbr` actions
- Fallback events
- Oscillation events
- LLM decision latency
- Token usage
- PFCP actuation outcome
- Structured JSONL audit logs

---

## 📁 Suggested Repository Structure

```text
.
├── README.md
├── TUTORIAL.md
├── LICENSE
├── requirements.txt
├── scripts/
│   ├── run_campaign.py
│   ├── plot_agentic_qos.py
│   └── analyze_audit_logs.py
├── controller/
│   ├── agentic_controller.py
│   ├── candidate_policy.py
│   ├── pfcp_actuator.py
│   └── telemetry.py
├── trex_profiles/
│   ├── exp2_profile.py
│   ├── exp2_latency_profile.py
│   └── exp2_overload_profile.py
├── pfcpsim_patch/
│   ├── api/
│   ├── internal/
│   └── Dockerfile
├── figures/
│   └── README.md
├── results/
│   └── README.md
└── docs/
    └── architecture.md
```

---

## ⚡ Quick Start

For the full reproducibility workflow, follow:

```bash
cat TUTORIAL.md
```

A typical execution flow is:

```text
1. Configure the UPF host
2. Configure the TRex host
3. Build BESS-UPF and patched pfcpsim images
4. Start BESS-UPF, pfcpiface, and route controller
5. Create PFCP sessions
6. Validate GTP-U forwarding
7. Validate per-slice MBR enforcement
8. Run baseline and agentic campaigns
9. Generate figures and statistics
```

Detailed commands are provided in **[TUTORIAL.md](./TUTORIAL.md)**.

---

## 🧾 Citation

If you use this repository, please cite the associated paper:

```bibtex
@inproceedings{moreira2027agentic,
  title     = {Agentic Orchestration for SLA-Constrained Network Slicing in Programmable Mobile Data Planes},
  author    = {Moreira, Rodrigo and Rodrigues Moreira, Larissa Ferreira and Martins, Joberto S. B. and Carvalho, Tereza C. and Silva, Flávio de Oliveira},
  booktitle = {IEEE Consumer Communications & Networking Conference},
  year      = {2027},
  note      = {Submitted}
}
```

---

## ⚠️ Notes

This repository is intended for research reproducibility.

The experiments depend on a specific two-host networking setup with BESS-UPF, TRex, Mellanox interfaces, DPDK, PFCP, and patched `pfcpsim`. Hardware, driver, and interface names may need to be adapted to each environment.

---

## 📜 License

This repository is released for academic and research use.

Please check the licenses of third-party components such as OMEC BESS-UPF, TRex, DPDK, and pfcpsim before redistribution or commercial use.
