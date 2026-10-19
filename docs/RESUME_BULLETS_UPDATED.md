# Resume bullets matched to what the code actually produces

The numbers in the earlier resume draft (alerts 47 -> 31, wash-trade precision 48% -> 100%)
do NOT match this project's output. Use these instead, or the interviewer may catch it.

**Trade Surveillance Pattern Engine (Python, SQL, SQLite, pandas)**
- Built SQL and Python surveillance patterns for wash trades, layering/spoofing and marking the
  close on 60K+ synthetic equity/ETF orders and 36K+ trades, producing scored, severity-ranked
  alerts in a common schema with account-level roll-up.

**Surveillance Alert Validation and Tuning (Python, SQL, pandas)**
- Reconciled orders to trades and detected all 23 injected data defects (missing trades,
  quantity mismatches, duplicate trade IDs); built a de-duplicated staging layer for detection.
- Measured precision and recall per pattern against labeled cases; tuned thresholds and ran a
  v1-to-v2 regression diff, cutting alerts from 77 to 28 and raising precision from 30% to 71%
  at 87% recall, with 3 missed cases documented as a precision/recall trade-off.

Also: replace `github.com/YOUR-USERNAME/trade-surveillance-portfolio` with your real repo URL.
