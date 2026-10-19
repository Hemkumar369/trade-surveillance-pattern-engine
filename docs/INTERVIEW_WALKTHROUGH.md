# Interview walkthrough: how to present this project

## Be upfront (say this first)
"This is a self-directed learning project on synthetic data. I don't have direct
surveillance experience at a regulator or broker-dealer. I built it to learn how
surveillance patterns are structured and to apply my validation and SQL background
to that domain."

## 5-minute script
1. **Problem (30s).** Surveillance systems generate alerts from rules. The hard part is not
   writing a rule; it is showing the alerts are accurate, complete and defensible.
2. **Data (45s).** 60K orders, 36K trades, synthetic. I injected labeled manipulation cases,
   labeled benign look-alikes, and 23 data defects so I know the right answer.
3. **Data quality first (45s).** Reconciled orders to trades: missing trades, quantity
   mismatches, duplicate IDs. Found 23/23. Built a de-duplicated staging table so patterns
   don't run on bad data.
4. **Patterns (90s).** Walk through the three SQL files (below).
5. **Validation + tuning (90s).** v1 loose: 77 alerts, 30% precision, 100% recall. v2 tuned:
   28 alerts, 71% precision, 87% recall. Lost 3 cases, I can show which and why.

## The three patterns in plain language
**Wash trade.** Buying and selling to yourself to fake volume. Logic: self-join trades for the
same account/symbol/day, BUY vs SELL, within `window_s`, quantity within `qty_tol`, price within
`price_tol`. Score rises as time/size/price gaps shrink. False positives: market makers who
legitimately buy and sell the same name all day.

**Layering / spoofing.** Placing orders you intend to cancel to push the price, trading the other
side, then cancelling. Logic: cluster same-side cancelled orders placed within `window_s` and
cancelled quickly; v2 also requires an opposite-side execution while the cluster is live.
False positives: quote repricing by market makers.

**Marking the close.** Pushing the closing price with late, one-way volume. Logic: account's
share of the day's volume in the final N minutes, how one-sided it is, and price move in
its direction. False positives: two-sided closing activity; a buyer in a genuine market move.

## Likely follow-ups
- **Why those thresholds?** `reports/threshold_sweep.md`: e.g. wash window 60s loses recall,
  300s adds noise, 120s was the knee. Closing share 0.18-0.25 is where recall steps down.
- **What did you miss and why?** 3 deliberate hard cases; accepted trade-off, and in real life
  that decision belongs with compliance (cost of a missed case vs analyst workload).
- **Why is wash-trade precision still only 53%?** Market-maker accounts. Next step: account-type
  baselines or exclusions, not tighter thresholds.
- **How would this scale?** Self-join on a window is O(n^2) per account/symbol/day: partition by
  date/symbol on a distributed engine (Snowflake/Redshift/Spark), index/sort by account and time.
- **What would change on real data?** Order-book/quote data, multiple venues, related accounts,
  corporate actions, clock sync, and thresholds per security liquidity tier.
- **Limits of the test bed?** I injected the ground truth, so metrics describe the test bed, not
  real-world performance; no hold-out set.
- **How did you use AI?** [Be honest: e.g. AI helped scaffold code; you reviewed, ran and
  validated it, and can explain every query.] Validating AI output is a stated JD skill.

## Things to be ready to do live
- Open `sql/wash_trade.sql` and explain each CTE line by line.
- Run `python src/run_all.py` and read the output.
- Change a threshold in `src/config.py`, rerun, explain the effect.
