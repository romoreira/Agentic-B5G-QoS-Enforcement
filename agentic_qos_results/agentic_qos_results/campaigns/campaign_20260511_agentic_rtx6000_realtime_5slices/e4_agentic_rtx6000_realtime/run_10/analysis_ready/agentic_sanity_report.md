# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_10`

Total windows `24`
Total decisions `24`
Total actions `12`
Total fallbacks `6`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3803.81 | clean |
| B | OK | 6 | 6 | 0 | 531.52 | 9476301 | 0 | 0 | 0 | 4466.35 | clean |
| C | OK | 6 | 6 | 0 | 585.68 | 11295443 | 0 | 0 | 0 | 4609.54 | clean |
| D | WARN | 6 | 0 | 6 | 518.09 | 0 | 0 | 0 | 0 | 3950.83 | fallback used |
