# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime/run_01`

Total windows `24`
Total decisions `24`
Total actions `3`
Total fallbacks `0`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2459.53 | clean |
| B | OK | 6 | 1 | 0 | 535.14 | 9477480 | 0 | 0 | 0 | 3314.93 | clean |
| C | WARN | 6 | 1 | 0 | 578.72 | 11292831 | 0 | 0 | 0 | 3010.94 | tiny NIC drops 0.000001 |
| D | OK | 6 | 1 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2633.38 | clean |
