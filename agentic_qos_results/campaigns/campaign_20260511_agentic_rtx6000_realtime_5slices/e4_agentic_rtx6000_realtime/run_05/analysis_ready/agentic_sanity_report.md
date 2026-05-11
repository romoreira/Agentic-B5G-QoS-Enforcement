# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_05`

Total windows `24`
Total decisions `24`
Total actions `12`
Total fallbacks `6`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | WARN | 6 | 0 | 0 | 518.07 | 0 | 0 | 0 | 0 | 3763.78 | tiny NIC drops 0.000022 |
| B | OK | 6 | 6 | 0 | 531.50 | 9476503 | 0 | 0 | 0 | 4453.66 | clean |
| C | OK | 6 | 6 | 0 | 585.66 | 11295974 | 0 | 0 | 0 | 4598.49 | clean |
| D | WARN | 6 | 0 | 6 | 518.09 | 0 | 0 | 0 | 0 | 3959.04 | fallback used |
