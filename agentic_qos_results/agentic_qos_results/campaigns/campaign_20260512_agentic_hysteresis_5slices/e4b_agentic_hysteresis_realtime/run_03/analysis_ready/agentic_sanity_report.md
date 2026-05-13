# Agentic realtime run sanity report

Run directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260512_agentic_hysteresis_5slices/e4b_agentic_hysteresis_realtime/run_03`

Total windows `24`
Total decisions `24`
Total actions `4`
Total fallbacks `0`
Total tool failures `0`

| phase | status | windows | actions | fallbacks | mean delivered Mbps | app QER red packets | pdr fail | far fail | bad route | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A | OK | 6 | 0 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2433.09 | clean |
| B | OK | 6 | 2 | 0 | 527.85 | 9476056 | 0 | 0 | 0 | 3199.94 | clean |
| C | WARN | 6 | 1 | 0 | 578.66 | 11295671 | 0 | 0 | 0 | 2907.71 | tiny NIC drops 0.000002 |
| D | OK | 6 | 1 | 0 | 518.09 | 0 | 0 | 0 | 0 | 2528.79 | clean |
