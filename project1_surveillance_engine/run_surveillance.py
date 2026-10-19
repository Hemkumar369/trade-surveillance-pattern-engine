"""Project 1: Trade surveillance pattern engine (wash trades, layering/spoofing, marking the close)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from data_gen import generate
from patterns import load, run_all, V2

out = os.path.join(os.path.dirname(__file__), "output"); os.makedirs(out, exist_ok=True)
orders, trades, truth, meta = generate()
orders.to_csv(f"{out}/orders.csv", index=False); trades.to_csv(f"{out}/trades.csv", index=False)
alerts = run_all(load(orders, trades), V2)
alerts.to_csv(f"{out}/alerts.csv", index=False)

# aggregation: roll alerts up by account to surface repeat subjects
roll = (alerts.groupby("account").agg(alerts=("alert_id", "count"), patterns=("pattern", "nunique"),
        max_score=("score", "max")).sort_values(["alerts", "max_score"], ascending=False))
roll.to_csv(f"{out}/account_rollup.csv")

print(f"Orders: {len(orders):,} | Trades: {len(trades):,} | Alerts: {len(alerts)}")
print(alerts.groupby(["pattern", "severity"], observed=True).size().unstack(fill_value=0))
print("\nTop 5 alerts:"); print(alerts.head(5)[["alert_id", "pattern", "account", "symbol", "score", "details"]].to_string(index=False))
