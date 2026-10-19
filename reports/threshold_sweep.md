# Threshold sensitivity (all other v2 thresholds held fixed)

| pattern           | parameter   |   value |   alerts |   true_pos |   precision |   recall |
|:------------------|:------------|--------:|---------:|-----------:|------------:|---------:|
| wash_trade        | qty_tol     |    0.02 |       14 |          8 |       0.571 |    0.889 |
| wash_trade        | qty_tol     |    0.03 |       15 |          8 |       0.533 |    0.889 |
| wash_trade        | qty_tol     |    0.05 |       15 |          8 |       0.533 |    0.889 |
| wash_trade        | qty_tol     |    0.08 |       15 |          8 |       0.533 |    0.889 |
| wash_trade        | qty_tol     |    0.1  |       17 |          8 |       0.471 |    0.889 |
| wash_trade        | qty_tol     |    0.15 |       17 |          8 |       0.471 |    0.889 |
| wash_trade        | qty_tol     |    0.25 |       18 |          8 |       0.444 |    0.889 |
| wash_trade        | window_s    |   30    |        3 |          0 |       0     |    0     |
| wash_trade        | window_s    |   60    |       10 |          6 |       0.6   |    0.667 |
| wash_trade        | window_s    |  120    |       15 |          8 |       0.533 |    0.889 |
| wash_trade        | window_s    |  180    |       17 |          8 |       0.471 |    0.889 |
| wash_trade        | window_s    |  240    |       17 |          8 |       0.471 |    0.889 |
| wash_trade        | window_s    |  300    |       17 |          8 |       0.471 |    0.889 |
| layering_spoofing | min_orders  |    3    |        7 |          6 |       0.857 |    0.857 |
| layering_spoofing | min_orders  |    4    |        7 |          6 |       0.857 |    0.857 |
| layering_spoofing | min_orders  |    5    |        7 |          6 |       0.857 |    0.857 |
| layering_spoofing | min_orders  |    6    |        5 |          5 |       1     |    0.714 |
| layering_spoofing | min_orders  |    7    |        3 |          3 |       1     |    0.429 |
| marking_the_close | min_share   |    0.1  |       17 |          7 |       0.412 |    1     |
| marking_the_close | min_share   |    0.15 |        9 |          7 |       0.778 |    1     |
| marking_the_close | min_share   |    0.18 |        7 |          7 |       1     |    1     |
| marking_the_close | min_share   |    0.2  |        6 |          6 |       1     |    0.857 |
| marking_the_close | min_share   |    0.25 |        6 |          6 |       1     |    0.857 |
| marking_the_close | min_share   |    0.3  |        6 |          6 |       1     |    0.857 |
| marking_the_close | min_share   |    0.35 |        4 |          4 |       1     |    0.571 |
