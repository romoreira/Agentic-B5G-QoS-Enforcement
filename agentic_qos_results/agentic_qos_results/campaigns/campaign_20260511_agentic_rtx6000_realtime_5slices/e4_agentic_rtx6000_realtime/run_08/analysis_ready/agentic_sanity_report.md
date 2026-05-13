# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_08`

Total windows `24`
Total decisions `24`
Total actions `12`
Total fallbacks `6`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3734.98 | clean |
| B | OK | 6 | 6 | 0 | 531.47 | 9479020 | 0 | 0 | 0 | 4491.74 | clean |
| C | WARN | 6 | 6 | 0 | 585.70 | 11294079 | 0 | 0 | 0 | 4607.42 | tiny NIC drops 0.000007 |
| D | WARN | 6 | 0 | 6 | 518.09 | 0 | 0 | 0 | 0 | 3866.14 | fallback used |
