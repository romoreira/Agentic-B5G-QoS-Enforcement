# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_09`

Total windows `24`
Total decisions `24`
Total actions `13`
Total fallbacks `5`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3782.92 | clean |
| B | WARN | 6 | 6 | 0 | 531.45 | 9479381 | 0 | 0 | 0 | 4478.51 | tiny NIC drops 0.000004 |
| C | OK | 6 | 6 | 0 | 585.62 | 11297867 | 0 | 0 | 0 | 4707.02 | clean |
| D | WARN | 6 | 1 | 5 | 518.09 | 0 | 0 | 0 | 0 | 4045.92 | fallback used |
