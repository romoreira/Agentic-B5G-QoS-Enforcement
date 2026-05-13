# Combined baseline and agentic phase metrics

Output CSV `/home/ubuntu/agentic_qos_results/campaigns/combined_baseline_agentic_phase_metrics.csv`

Total rows `160`

| experiment | phase | n | delivered Mbps mean | delivered Mbps std | app QER red mean | actions mean | fallbacks mean | oscillations mean | LLM latency mean ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| e1_static | A | 10 | 518.09 | 0.00 | 0.00 |  |  |  |  |
| e1_static | B | 10 | 562.14 | 0.01 | 9485328.80 |  |  |  |  |
| e1_static | C | 10 | 650.21 | 0.02 | 11313651.50 |  |  |  |  |
| e1_static | D | 10 | 518.09 | 0.00 | 0.00 |  |  |  |  |
| e2_threshold | A | 10 | 518.09 | 0.00 | 0.00 |  |  |  |  |
| e2_threshold | B | 10 | 507.73 | 0.01 | 9485495.00 |  |  |  |  |
| e2_threshold | C | 10 | 574.58 | 0.03 | 11313518.80 |  |  |  |  |
| e2_threshold | D | 10 | 518.09 | 0.00 | 0.00 |  |  |  |  |
| e3_greedy | A | 10 | 518.09 | 0.00 | 0.00 |  |  |  |  |
| e3_greedy | B | 10 | 562.14 | 0.01 | 9485206.30 |  |  |  |  |
| e3_greedy | C | 10 | 650.22 | 0.02 | 11313691.30 |  |  |  |  |
| e3_greedy | D | 10 | 518.09 | 0.00 | 0.00 |  |  |  |  |
| e4_agentic_rtx6000_realtime | A | 10 | 518.09 | 0.01 | 0.00 | 0.0 | 0.0 | 0.0 | 3816.2516355514526 |
| e4_agentic_rtx6000_realtime | B | 10 | 531.47 | 0.03 | 9478085.60 | 6.0 | 0.0 | 4.0 | 4453.273443380992 |
| e4_agentic_rtx6000_realtime | C | 10 | 585.69 | 0.07 | 11294803.40 | 6.0 | 0.0 | 4.0 | 4611.002131303151 |
| e4_agentic_rtx6000_realtime | D | 10 | 518.09 | 0.00 | 0.00 | 0.4 | 5.0 | 0.0 | 3958.302692572276 |
