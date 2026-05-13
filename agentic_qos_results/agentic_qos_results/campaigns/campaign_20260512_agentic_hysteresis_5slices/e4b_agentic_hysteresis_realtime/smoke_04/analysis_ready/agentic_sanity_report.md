# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime/smoke_04`

Total windows `24`
Total decisions `24`
Total actions `4`
Total fallbacks `0`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2463.93 | clean |
| B | WARN | 6 | 2 | 0 | 538.74 | 9478207 | 0 | 0 | 0 | 3088.98 | tiny NIC drops 0.000001 |
| C | WARN | 6 | 1 | 0 | 578.75 | 11291495 | 0 | 0 | 0 | 2863.50 | tiny NIC drops 0.000003 |
| D | OK | 6 | 1 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2576.96 | clean |
