# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime/smoke_01`

Total windows `24`
Total decisions `24`
Total actions `6`
Total fallbacks `7`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3742.52 | clean |
| B | WARN | 6 | 3 | 3 | 522.42 | 9475363 | 0 | 0 | 0 | 4304.41 | fallback used |
| C | WARN | 6 | 2 | 4 | 561.99 | 11292998 | 0 | 0 | 0 | 4653.07 | fallback used |
| D | OK | 6 | 1 | 0 | 518.09 | 0 | 0 | 0 | 0 | 4048.36 | clean |
