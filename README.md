# Trade Surveillance Pattern Engine (synthetic data)

A learning project: SQL + Python surveillance patterns for three classic forms of
market manipulation, with alert validation, precision/recall measurement and
threshold tuning, built on a **fully synthetic** equity/ETF order book.

> **Scope note.** All data is synthetic (random-walk prices, generated accounts).
> Nothing here is calibrated to real markets or based on any employer's or regulator's
> surveillance logic. It is a controlled test bed where the correct answer is known, so
> alert quality can be measured honestly.

## What it does

| Step | Script | What happens |
|---|---|---|
| 1 | `src/generate_data.py` | Generates 60K+ orders and 36K+ trades (400 accounts + 12 market makers, 40 symbols, 20 days). Injects labeled manipulation cases, labeled *benign look-alikes*, and 23 data-quality defects. |
| 2 | `src/reconcile.py` | Orders-to-trades reconciliation: missing trades, quantity mismatches, duplicate trade IDs. Builds a de-duplicated `trades_clean` staging table. |
| 3 | `src/patterns.py` + `sql/*.sql` | Runs three SQL patterns, normalises output to one alert schema, scores and ranks by severity, rolls up per account. |
| 4 | `src/evaluate.py` | Precision/recall per pattern against labeled cases; v1-to-v2 regression diff. |
| 5 | `src/tune.py` | Threshold sensitivity sweeps (how each threshold trades precision for recall). |

## Patterns (`sql/`)

- **Wash trade** - same account buys and sells the same symbol within seconds/minutes, with near-identical size and price.
- **Layering / spoofing** - a cluster of same-side orders placed in quick succession, an opposite-side execution, then the stacked orders cancelled.
- **Marking the close** - a large, one-directional share of the day's volume in the closing window that moves the closing price in the account's favour.

## Run it

```bash
pip install -r requirements.txt
python src/run_all.py          # ~1 minute; writes data/surveillance.db and reports/
python -m pytest tests         # sanity checks
```

## Results (seed 42; regenerate to reproduce)

**Reconciliation:** all 23 injected defects detected (8 missing trades, 8 quantity mismatches, 7 duplicate trade IDs), 0 false alarms.

**Alert tuning, v1 (loose) vs v2 (tuned):**

| | Alerts | Precision | Recall |
|---|---|---|---|
| v1 | 77 | 29.9% | 100% |
| v2 | 28 | 71.4% | 87.0% |

Per pattern (precision / recall): wash trade 25.7% / 100% -> 53.3% / 88.9%; layering 46.7% / 100% -> 85.7% / 85.7%; marking the close 25.9% / 100% -> 100% / 85.7%.

**Trade-off, documented:** tuning suppressed 46 false positives and lost 3 true positives
(one per pattern, all deliberately "hard" cases: slightly mismatched wash trade, a 4-order
layering cluster with slow cancels, a closing share just under the new threshold).
`reports/alert_validation_report.md` lists them.

**Remaining false positives** are mostly market-maker accounts, whose legitimate two-sided
flow looks like wash trading. That is the realistic next step: an account-type
exclusion or a market-maker baseline, rather than ever-tighter thresholds.

## Limitations

- Synthetic data; real surveillance deals with far larger volumes, order-book depth, quotes, multiple venues and linked accounts.
- Ground truth is injected by me, so recall/precision describe this test bed, not real-world detection performance.
- Wash-trade detection is same-account only (no cross-account or related-party linkage).
- Thresholds are tuned on the same data they are evaluated on (no hold-out set).

## Layout

```
src/      config, generator, reconcile, patterns, evaluate, tune, run_all
sql/      one SQL file per pattern (parameterised)
reports/  reconciliation, validation, and threshold-sweep outputs
docs/     interview walkthrough notes
tests/    sanity tests
```
