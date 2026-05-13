# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_01`

Total windows `24`
Total decisions `24`
Total actions `13`
Total fallbacks `2`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3751.72 | clean |
| B | WARN | 6 | 6 | 0 | 531.47 | 9477754 | 0 | 0 | 0 | 4418.60 | tiny NIC drops 0.000006 |
| C | WARN | 6 | 6 | 0 | 585.72 | 11293298 | 0 | 0 | 0 | 4562.38 | tiny NIC drops 0.000002 |
| D | WARN | 6 | 1 | 2 | 518.09 | 0 | 0 | 0 | 0 | 3931.14 | fallback used |
