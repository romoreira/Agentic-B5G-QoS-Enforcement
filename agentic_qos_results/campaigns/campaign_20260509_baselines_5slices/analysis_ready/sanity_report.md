# Baseline campaign sanity report

Campaign root `/home/ubuntu/agentic_qos_results/campaigns/campaign_20260509_baselines_5slices`

## Overall status

Total phase records `120`
OK `100`
WARN `20`
FAIL `0`

## Recommendation

Review the warnings before running the 10 repetitions.

## Phase summary

| experiment | run | phase | status | elapsed s | access RX pkts | core TX pkts | core TX Mbps expected window | app QER drop | pdr fail | far fail | bad route | notes |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| e1_static | run_01 | A | OK | 86.0 | 22857061 | 22857060 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_01 | B | OK | 88.0 | 34285623 | 24799685 | 562.13 | 9485937 | 0 | 0 | 0 | clean |
| e1_static | run_01 | C | OK | 89.0 | 39999901 | 28688154 | 650.26 | 11311744 | 0 | 0 | 0 | clean |
| e1_static | run_01 | D | WARN | 87.0 | 22857004 | 22857004 | 518.09 | 0 | 0 | 0 | 0 | tiny NIC drops n3_rx=58, n6_tx=0, rate=0.000001 |
| e1_static | run_02 | A | OK | 84.0 | 22857063 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_02 | B | WARN | 84.0 | 34284859 | 24799529 | 562.12 | 9485329 | 0 | 0 | 0 | tiny NIC drops n3_rx=762, n6_tx=0, rate=0.000013 |
| e1_static | run_02 | C | OK | 85.0 | 39999904 | 28685351 | 650.20 | 11314550 | 0 | 0 | 0 | clean |
| e1_static | run_02 | D | OK | 85.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_03 | A | OK | 84.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_03 | B | OK | 92.0 | 34285621 | 24800827 | 562.15 | 9484793 | 0 | 0 | 0 | clean |
| e1_static | run_03 | C | OK | 85.0 | 39999904 | 28686562 | 650.23 | 11313339 | 0 | 0 | 0 | clean |
| e1_static | run_03 | D | OK | 84.0 | 22857062 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_04 | A | OK | 84.0 | 22857063 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_04 | B | OK | 85.0 | 34285622 | 24800515 | 562.15 | 9485106 | 0 | 0 | 0 | clean |
| e1_static | run_04 | C | OK | 85.0 | 39999903 | 28686614 | 650.23 | 11313286 | 0 | 0 | 0 | clean |
| e1_static | run_04 | D | OK | 84.0 | 22857062 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_05 | A | OK | 84.0 | 22857062 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_05 | B | OK | 85.0 | 34285622 | 24800298 | 562.14 | 9485323 | 0 | 0 | 0 | clean |
| e1_static | run_05 | C | WARN | 85.0 | 39999431 | 28684570 | 650.18 | 11314858 | 0 | 0 | 0 | tiny NIC drops n3_rx=472, n6_tx=0, rate=0.000007 |
| e1_static | run_05 | D | OK | 84.0 | 22857062 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_06 | A | OK | 84.0 | 22857062 | 22857062 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_06 | B | OK | 84.0 | 34285623 | 24799964 | 562.13 | 9485657 | 0 | 0 | 0 | clean |
| e1_static | run_06 | C | WARN | 84.0 | 39999551 | 28686735 | 650.23 | 11312814 | 0 | 0 | 0 | tiny NIC drops n3_rx=352, n6_tx=0, rate=0.000005 |
| e1_static | run_06 | D | OK | 83.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_07 | A | OK | 84.0 | 22857063 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_07 | B | OK | 84.0 | 34285624 | 24801063 | 562.16 | 9484559 | 0 | 0 | 0 | clean |
| e1_static | run_07 | C | WARN | 84.0 | 39999451 | 28685466 | 650.20 | 11313983 | 0 | 0 | 0 | tiny NIC drops n3_rx=452, n6_tx=0, rate=0.000007 |
| e1_static | run_07 | D | OK | 84.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_08 | A | OK | 84.0 | 22857063 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_08 | B | OK | 84.0 | 34285624 | 24800611 | 562.15 | 9485011 | 0 | 0 | 0 | clean |
| e1_static | run_08 | C | WARN | 84.0 | 39998099 | 28685366 | 650.20 | 11312731 | 0 | 0 | 0 | tiny NIC drops n3_rx=1804, n6_tx=0, rate=0.000026 |
| e1_static | run_08 | D | OK | 84.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_09 | A | OK | 86.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_09 | B | OK | 85.0 | 34285623 | 24799760 | 562.13 | 9485862 | 0 | 0 | 0 | clean |
| e1_static | run_09 | C | OK | 85.0 | 39999903 | 28684806 | 650.19 | 11315095 | 0 | 0 | 0 | clean |
| e1_static | run_09 | D | OK | 86.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_10 | A | OK | 85.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e1_static | run_10 | B | WARN | 84.0 | 34285499 | 24799787 | 562.13 | 9485711 | 0 | 0 | 0 | tiny NIC drops n3_rx=124, n6_tx=0, rate=0.000002 |
| e1_static | run_10 | C | WARN | 84.0 | 39999896 | 28685778 | 650.21 | 11314115 | 0 | 0 | 0 | tiny NIC drops n3_rx=8, n6_tx=0, rate=0.000000 |
| e1_static | run_10 | D | OK | 84.0 | 22857063 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_01 | A | OK | 84.0 | 22857064 | 22857063 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_01 | B | OK | 84.0 | 34285623 | 22399916 | 507.73 | 9485788 | 0 | 0 | 0 | clean |
| e2_threshold | run_01 | C | OK | 84.0 | 39999904 | 25348193 | 574.56 | 11314624 | 0 | 0 | 0 | clean |
| e2_threshold | run_01 | D | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_02 | A | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_02 | B | OK | 85.0 | 34285625 | 22400470 | 507.74 | 9484734 | 0 | 0 | 0 | clean |
| e2_threshold | run_02 | C | OK | 84.0 | 39999903 | 25349820 | 574.60 | 11313125 | 0 | 0 | 0 | clean |
| e2_threshold | run_02 | D | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_03 | A | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_03 | B | OK | 84.0 | 34285625 | 22399876 | 507.73 | 9485884 | 0 | 0 | 0 | clean |
| e2_threshold | run_03 | C | WARN | 85.0 | 39999451 | 25348598 | 574.57 | 11313882 | 0 | 0 | 0 | tiny NIC drops n3_rx=452, n6_tx=0, rate=0.000007 |
| e2_threshold | run_03 | D | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_04 | A | OK | 85.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_04 | B | WARN | 85.0 | 34284964 | 22399555 | 507.72 | 9485574 | 0 | 0 | 0 | tiny NIC drops n3_rx=661, n6_tx=0, rate=0.000012 |
| e2_threshold | run_04 | C | OK | 84.0 | 39999903 | 25350149 | 574.60 | 11312842 | 0 | 0 | 0 | clean |
| e2_threshold | run_04 | D | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_05 | A | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_05 | B | OK | 84.0 | 34285625 | 22399958 | 507.73 | 9485739 | 0 | 0 | 0 | clean |
| e2_threshold | run_05 | C | OK | 85.0 | 39999903 | 25348075 | 574.56 | 11314733 | 0 | 0 | 0 | clean |
| e2_threshold | run_05 | D | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_06 | A | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_06 | B | WARN | 85.0 | 34285383 | 22399658 | 507.73 | 9485884 | 0 | 0 | 0 | tiny NIC drops n3_rx=241, n6_tx=0, rate=0.000004 |
| e2_threshold | run_06 | C | OK | 84.0 | 39999903 | 25348755 | 574.57 | 11314078 | 0 | 0 | 0 | clean |
| e2_threshold | run_06 | D | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_07 | A | OK | 86.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_07 | B | OK | 87.0 | 34285625 | 22400361 | 507.74 | 9484984 | 0 | 0 | 0 | clean |
| e2_threshold | run_07 | C | OK | 85.0 | 39999903 | 25350157 | 574.60 | 11312731 | 0 | 0 | 0 | clean |
| e2_threshold | run_07 | D | OK | 86.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_08 | A | OK | 86.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_08 | B | OK | 84.0 | 34285624 | 22400342 | 507.74 | 9485330 | 0 | 0 | 0 | clean |
| e2_threshold | run_08 | C | WARN | 84.0 | 39999523 | 25351367 | 574.63 | 11311182 | 0 | 0 | 0 | tiny NIC drops n3_rx=381, n6_tx=0, rate=0.000006 |
| e2_threshold | run_08 | D | OK | 85.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_09 | A | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_09 | B | WARN | 85.0 | 34285378 | 22399797 | 507.73 | 9485680 | 0 | 0 | 0 | tiny NIC drops n3_rx=246, n6_tx=0, rate=0.000004 |
| e2_threshold | run_09 | C | OK | 84.0 | 39999904 | 25347712 | 574.55 | 11315099 | 0 | 0 | 0 | clean |
| e2_threshold | run_09 | D | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_10 | A | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e2_threshold | run_10 | B | WARN | 84.0 | 34285189 | 22399801 | 507.73 | 9485353 | 0 | 0 | 0 | tiny NIC drops n3_rx=435, n6_tx=0, rate=0.000008 |
| e2_threshold | run_10 | C | OK | 85.0 | 39999904 | 25350062 | 574.60 | 11312892 | 0 | 0 | 0 | clean |
| e2_threshold | run_10 | D | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_01 | A | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_01 | B | OK | 84.0 | 34285625 | 24800289 | 562.14 | 9485335 | 0 | 0 | 0 | clean |
| e3_greedy | run_01 | C | WARN | 85.0 | 39999374 | 28685594 | 650.21 | 11313780 | 0 | 0 | 0 | tiny NIC drops n3_rx=529, n6_tx=0, rate=0.000008 |
| e3_greedy | run_01 | D | OK | 84.0 | 22857066 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_02 | A | OK | 84.0 | 22857065 | 22857065 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_02 | B | OK | 84.0 | 34285625 | 24800656 | 562.15 | 9484968 | 0 | 0 | 0 | clean |
| e3_greedy | run_02 | C | WARN | 86.0 | 39999789 | 28685001 | 650.19 | 11314788 | 0 | 0 | 0 | tiny NIC drops n3_rx=114, n6_tx=0, rate=0.000002 |
| e3_greedy | run_02 | D | OK | 86.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_03 | A | OK | 84.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_03 | B | OK | 84.0 | 34285620 | 24799874 | 562.13 | 9485746 | 0 | 0 | 0 | clean |
| e3_greedy | run_03 | C | OK | 84.0 | 39999903 | 28686152 | 650.22 | 11313751 | 0 | 0 | 0 | clean |
| e3_greedy | run_03 | D | OK | 85.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_04 | A | OK | 85.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_04 | B | OK | 86.0 | 34285620 | 24800228 | 562.14 | 9485392 | 0 | 0 | 0 | clean |
| e3_greedy | run_04 | C | OK | 87.0 | 39999904 | 28686461 | 650.23 | 11313442 | 0 | 0 | 0 | clean |
| e3_greedy | run_04 | D | OK | 85.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_05 | A | OK | 84.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_05 | B | OK | 84.0 | 34285620 | 24800382 | 562.14 | 9485238 | 0 | 0 | 0 | clean |
| e3_greedy | run_05 | C | OK | 84.0 | 39999904 | 28685205 | 650.20 | 11314698 | 0 | 0 | 0 | clean |
| e3_greedy | run_05 | D | OK | 85.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_06 | A | OK | 87.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_06 | B | WARN | 85.0 | 34285492 | 24800768 | 562.15 | 9484724 | 0 | 0 | 0 | tiny NIC drops n3_rx=128, n6_tx=0, rate=0.000002 |
| e3_greedy | run_06 | C | OK | 84.0 | 39999904 | 28688124 | 650.26 | 11311779 | 0 | 0 | 0 | clean |
| e3_greedy | run_06 | D | OK | 84.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_07 | A | OK | 85.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_07 | B | WARN | 86.0 | 34285012 | 24799813 | 562.13 | 9485199 | 0 | 0 | 0 | tiny NIC drops n3_rx=608, n6_tx=0, rate=0.000010 |
| e3_greedy | run_07 | C | OK | 86.0 | 39999904 | 28686613 | 650.23 | 11313290 | 0 | 0 | 0 | clean |
| e3_greedy | run_07 | D | OK | 84.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_08 | A | OK | 86.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_08 | B | OK | 84.0 | 34285620 | 24800733 | 562.15 | 9484887 | 0 | 0 | 0 | clean |
| e3_greedy | run_08 | C | OK | 84.0 | 39999904 | 28687015 | 650.24 | 11312888 | 0 | 0 | 0 | clean |
| e3_greedy | run_08 | D | OK | 85.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_09 | A | OK | 84.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_09 | B | OK | 84.0 | 34285620 | 24800449 | 562.14 | 9485171 | 0 | 0 | 0 | clean |
| e3_greedy | run_09 | C | WARN | 84.0 | 39999155 | 28684948 | 650.19 | 11314206 | 0 | 0 | 0 | tiny NIC drops n3_rx=749, n6_tx=0, rate=0.000011 |
| e3_greedy | run_09 | D | OK | 85.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_10 | A | OK | 84.0 | 22857061 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |
| e3_greedy | run_10 | B | OK | 84.0 | 34285621 | 24800217 | 562.14 | 9485403 | 0 | 0 | 0 | clean |
| e3_greedy | run_10 | C | WARN | 84.0 | 39998935 | 28684644 | 650.19 | 11314291 | 0 | 0 | 0 | tiny NIC drops n3_rx=968, n6_tx=0, rate=0.000014 |
| e3_greedy | run_10 | D | OK | 84.0 | 22857062 | 22857061 | 518.09 | 0 | 0 | 0 | 0 | clean |