# Project 1 - Surveillance Pattern Engine

## Business requirement
Detect three potential market-abuse behaviors in order/trade data, generate scored alerts in a common schema, and
aggregate alerts by account so reviewers can see repeat subjects.

## Patterns (tuned v2 thresholds)
| Pattern | Logic | Key thresholds |
|---|---|---|
| Wash trade | Trades where buyer = seller, grouped by account/symbol/day (SQL) | >= 3 self-matched trades |
| Layering / spoofing | Cluster of same-side orders cancelled within seconds, followed by an opposite-side fill by the same account | >= 4 orders, >= 10,000 shares, cancel <= 5s, fill within 30s |
| Marking the close | Account buys a large share of last-10-minute volume while price rises | >= 5 buys, >= 40% of window volume, >= 1.0% price move |

Alert schema: `alert_id, pattern, account, symbol, trade_date, score (0-100), severity (LOW/MEDIUM/HIGH), details`.

## Architecture
Orders + trades -> SQLite (SQL detection queries) -> pandas clustering/scoring -> unified alerts -> account roll-up.
Exception generation, scoring, and aggregation are separate steps so each can be tested on its own.

## Result (seed 42)
60,370 orders, 36,267 trades -> 31 alerts (12 wash, 11 layering/spoofing, 8 marking the close), 26 HIGH severity.

## Limitations
Simulated data, simplified rules, no cross-market or cross-account coordination logic. Not a compliance tool.
