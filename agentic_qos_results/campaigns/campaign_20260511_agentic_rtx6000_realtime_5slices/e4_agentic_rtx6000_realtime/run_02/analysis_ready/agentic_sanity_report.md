# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_02`

Total windows `24`
Total decisions `24`
Total actions `13`
Total fallbacks `4`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 4090.06 | clean |
| B | WARN | 6 | 6 | 0 | 531.48 | 9477556 | 0 | 0 | 0 | 4374.29 | tiny NIC drops 0.000000 |
| C | OK | 6 | 6 | 0 | 585.73 | 11292998 | 0 | 0 | 0 | 4580.76 | clean |
| D | WARN | 6 | 1 | 4 | 518.09 | 0 | 0 | 0 | 0 | 4005.27 | fallback used |
