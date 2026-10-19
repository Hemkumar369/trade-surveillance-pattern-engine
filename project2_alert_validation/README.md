# Project 2 - Surveillance Alert Validation and Tuning

## Business requirement
Show that pattern output is accurate, complete, and defensible: verify input data, measure alert quality against known
cases, and document what changes when rules are tuned.

## Method
1. **Data reconciliation** - orders vs trades: filled orders with no trade, quantity mismatches, duplicate trade IDs,
   orphan trades, invalid prices/times. Known defects were injected; all 23 were found (10 missing, 8 qty mismatches, 5 duplicates).
2. **Precision/recall** - alerts matched to labeled ground truth on pattern + account + symbol + date.
3. **Regression diff** - v1 (loose) vs v2 (tuned) alerts: removed, added, unchanged.

## Results (seed 42)
| Pattern | v1 precision / recall | v2 precision / recall |
|---|---|---|
| Wash trade | 0.48 / 1.00 | 1.00 / 1.00 |
| Layering / spoofing | 1.00 / 1.00 | 1.00 / 0.92 |
| Marking the close | 1.00 / 1.00 | 1.00 / 0.80 |

Total alerts fell from 47 to 31. Raising the wash-trade threshold removed 13 false positives (precision 48% to 100%),
but the stricter layering and marking thresholds missed 3 labeled cases - a real precision/recall trade-off that a
reviewer would need to accept or revisit.

## Limitations
Labeled cases are injected by the same generator that defines the patterns, so recall here is optimistic versus real data.
