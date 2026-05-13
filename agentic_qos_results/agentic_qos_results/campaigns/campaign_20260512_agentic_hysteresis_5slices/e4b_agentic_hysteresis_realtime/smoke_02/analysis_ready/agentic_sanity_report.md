# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime/smoke_02`

Total windows `24`
Total decisions `24`
Total actions `4`
Total fallbacks `0`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | WARN | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2504.31 | tiny NIC drops 0.000006 |
| B | WARN | 6 | 3 | 0 | 522.43 | 9474734 | 0 | 0 | 0 | 3027.67 | tiny NIC drops 0.000001 |
| C | OK | 6 | 1 | 0 | 576.92 | 11296811 | 0 | 0 | 0 | 3940.78 | clean |
| D | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2514.84 | clean |
