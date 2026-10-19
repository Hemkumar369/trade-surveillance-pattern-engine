# Orders-to-trades reconciliation

| defect_type        |   injected |   detected |   false_alarms |
|:-------------------|-----------:|-----------:|---------------:|
| duplicate_trade_id |          7 |          7 |              0 |
| missing_trade      |          8 |          8 |              0 |
| quantity_mismatch  |          8 |          8 |              0 |

- Detected **23 of 23** injected defects
- Orphan trades (trade with no order): 0
- Cancelled orders that have fills: 0
- Raw trades: 36,174 -> `trades_clean` after de-duplication: 36,167
