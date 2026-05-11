# E4 Agentic RTX6000 Realtime Campaign Status

Status: completed

Runs: 10
Windows per run: 24
Total decisions: 240
Tool failures: 0
Incomplete runs: 0
vLLM backend: RTX A4000 through reverse SSH tunnel
Model: Qwen/Qwen2.5-7B-Instruct
Prefix cache: disabled
Window size: 10 s
Windows per phase: 6

Main finding:
The realtime agentic loop executed successfully, with no tool failures and no incomplete runs.
All runs were marked WARN due to fallbacks and oscillatory MBR decisions.

Interpretation:
The pipeline is operationally valid, but the controller requires hysteresis or stateful damping before being considered stable.
