# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_03`

Total windows `24`
Total decisions `24`
Total actions `12`
Total fallbacks `6`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | WARN | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3945.69 | tiny NIC drops 0.000003 |
| B | OK | 6 | 6 | 0 | 531.44 | 9479798 | 0 | 0 | 0 | 4504.75 | clean |
| C | OK | 6 | 6 | 0 | 585.85 | 11287813 | 0 | 0 | 0 | 4562.89 | clean |
| D | WARN | 6 | 0 | 6 | 518.09 | 0 | 0 | 0 | 0 | 3955.89 | fallback used |
