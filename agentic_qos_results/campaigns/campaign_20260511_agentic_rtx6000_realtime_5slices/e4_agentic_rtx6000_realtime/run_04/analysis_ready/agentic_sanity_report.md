# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime/run_04`

Total windows `24`
Total decisions `24`
Total actions `13`
Total fallbacks `3`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 3743.96 | clean |
| B | WARN | 6 | 6 | 0 | 531.40 | 9477454 | 0 | 0 | 0 | 4460.45 | tiny NIC drops 0.000078 |
| C | OK | 6 | 6 | 0 | 585.67 | 11295470 | 0 | 0 | 0 | 4665.96 | clean |
| D | WARN | 6 | 1 | 3 | 518.09 | 0 | 0 | 0 | 0 | 3950.35 | fallback used |
