# Alert validation and tuning results

## Precision / recall by pattern and threshold version

| version   | pattern           |   alerts |   true_pos |   false_pos |   labeled_cases |   precision |   recall |
|:----------|:------------------|---------:|-----------:|------------:|----------------:|------------:|---------:|
| v1        | wash_trade        |       35 |          9 |          26 |               9 |       0.257 |    1     |
| v1        | layering_spoofing |       15 |          7 |           8 |               7 |       0.467 |    1     |
| v1        | marking_the_close |       27 |          7 |          20 |               7 |       0.259 |    1     |
| v1        | ALL               |       77 |         23 |          54 |              23 |       0.299 |    1     |
| v2        | wash_trade        |       15 |          8 |           7 |               9 |       0.533 |    0.889 |
| v2        | layering_spoofing |        7 |          6 |           1 |               7 |       0.857 |    0.857 |
| v2        | marking_the_close |        6 |          6 |           0 |               7 |       1     |    0.857 |
| v2        | ALL               |       28 |         20 |           8 |              23 |       0.714 |    0.87  |

## v1 -> v2 regression diff

- Total alerts: **77 -> 28**
- Alerts in both versions: 28
- Removed by tuning: 49 (46 false positives suppressed, 3 true positives lost)
- New in v2: 0

### Missed by v2 (recall trade-off)

| pattern           | account_id   | symbol   | trade_date   | difficulty   |
|:------------------|:-------------|:---------|:-------------|:-------------|
| wash_trade        | ACC0144      | NVDA     | 2025-03-07   | hard         |
| layering_spoofing | ACC0361      | SPY      | 2025-03-03   | hard         |
| marking_the_close | ACC0107      | MRK      | 2025-03-20   | hard         |

### False positives still present in v2

| pattern           | account_id   | symbol   | trade_date   |   score | note                                                            |
|:------------------|:-------------|:---------|:-------------|--------:|:----------------------------------------------------------------|
| wash_trade        | MM09         | JPM      | 2025-03-14   |    95.7 | unlabeled (background noise)                                    |
| wash_trade        | MM10         | JPM      | 2025-03-03   |    95.3 | unlabeled (background noise)                                    |
| wash_trade        | MM05         | CSCO     | 2025-03-21   |    95   | unlabeled (background noise)                                    |
| layering_spoofing | MM01         | CSCO     | 2025-03-20   |    90   | quote repricing coinciding with a hedge fill (unavoidable FP)   |
| wash_trade        | MM04         | CVX      | 2025-03-12   |    84   | unlabeled (background noise)                                    |
| wash_trade        | MM01         | XOM      | 2025-03-07   |    73.5 | unlabeled (background noise)                                    |
| wash_trade        | ACC0010      | SPY      | 2025-03-28   |    54.7 | unlabeled (background noise)                                    |
| wash_trade        | MM02         | KO       | 2025-03-25   |    43.7 | market-maker round trip that looks like a wash (unavoidable FP) |
