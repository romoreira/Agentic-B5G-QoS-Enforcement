# Agentic RTX6000 campaign summary

Experiment directory `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260511_agentic_rtx6000_realtime_5slices/e4_agentic_rtx6000_realtime`

Runs found `10`
OK `0`
WARN `10`
FAIL `0`
INCOMPLETE `0`

## Run summary

| run | status | windows | decisions | actions | fallbacks | tool failures | oscillations | mean LLM latency ms | notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| run_01 | WARN | 24 | 24 | 13 | 2 | 0 | 8 | 4165.96 | fallbacks=2; oscillations=8 |
| run_02 | WARN | 24 | 24 | 13 | 4 | 0 | 8 | 4262.59 | fallbacks=4; oscillations=8 |
| run_03 | WARN | 24 | 24 | 12 | 6 | 0 | 8 | 4242.30 | fallbacks=6; oscillations=8 |
| run_04 | WARN | 24 | 24 | 13 | 3 | 0 | 8 | 4205.18 | fallbacks=3; oscillations=8 |
| run_05 | WARN | 24 | 24 | 12 | 6 | 0 | 8 | 4193.74 | fallbacks=6; oscillations=8 |
| run_06 | WARN | 24 | 24 | 12 | 6 | 0 | 8 | 4192.98 | fallbacks=6; oscillations=8 |
| run_07 | WARN | 24 | 24 | 12 | 6 | 0 | 8 | 4198.02 | fallbacks=6; oscillations=8 |
| run_08 | WARN | 24 | 24 | 12 | 6 | 0 | 8 | 4175.07 | fallbacks=6; oscillations=8 |
| run_09 | WARN | 24 | 24 | 13 | 5 | 0 | 8 | 4253.59 | fallbacks=5; oscillations=8 |
| run_10 | WARN | 24 | 24 | 12 | 6 | 0 | 8 | 4207.63 | fallbacks=6; oscillations=8 |

## Phase aggregate

| phase | runs | delivered Mbps mean | delivered Mbps std | app QER red mean | actions mean | fallbacks mean | LLM latency mean ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 10 | 518.09 | 0.01 | 0.00 | 0.00 | 0.00 | 3816.25 |
| B | 10 | 531.47 | 0.03 | 9478085.60 | 6.00 | 0.00 | 4453.27 |
| C | 10 | 585.69 | 0.07 | 11294803.40 | 6.00 | 0.00 | 4611.00 |
| D | 10 | 518.09 | 0.00 | 0.00 | 0.40 | 5.00 | 3958.30 |
