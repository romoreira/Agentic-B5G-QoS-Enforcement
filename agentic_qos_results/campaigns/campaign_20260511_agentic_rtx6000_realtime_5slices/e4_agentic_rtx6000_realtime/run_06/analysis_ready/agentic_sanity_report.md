# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_06`

Total windows `24`
Total decisions `24`
Total actions `12`
Total fallbacks `6`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3770.51 | clean |
| B | OK | 6 | 6 | 0 | 531.48 | 9478087 | 0 | 0 | 0 | 4425.01 | clean |
| C | OK | 6 | 6 | 0 | 585.57 | 11300113 | 0 | 0 | 0 | 4605.85 | clean |
| D | WARN | 6 | 0 | 6 | 518.09 | 0 | 0 | 0 | 0 | 3970.55 | fallback used |
