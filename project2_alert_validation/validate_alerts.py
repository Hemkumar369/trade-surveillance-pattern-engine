"""Project 2: Surveillance alert validation - data reconciliation, precision/recall tuning, version regression diff."""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from data_gen import generate, SESSION
from patterns import load, run_all, V1, V2

out = os.path.join(os.path.dirname(__file__), "output"); os.makedirs(out, exist_ok=True)
orders, trades, truth, meta = generate()
KEY = ["pattern", "account", "symbol", "trade_date"]

# 1) Input data reconciliation (orders vs trades)
t_unique = trades.drop_duplicates("trade_id")
filled = orders[orders.status == "FILLED"]
m = filled.merge(t_unique, on="order_id", how="left", suffixes=("_o", "_t"))
checks = {
    "missing_trades (filled order, no trade)": int(m.trade_id.isna().sum()),
    "qty_mismatches (order qty != trade qty)": int((m.trade_id.notna() & (m.qty_o != m.qty_t)).sum()),
    "duplicate_trades (repeated trade_id)": int(trades.trade_id.duplicated().sum()),
    "orphan_trades (trade, no order)": int((~t_unique.order_id.isin(orders.order_id)).sum()),
    "invalid_price_or_time": int(((trades.price <= 0) | (trades.ts < 0) | (trades.ts >= SESSION)).sum()),
}
expected = {"missing_trades (filled order, no trade)": meta["missing_trades"],
            "qty_mismatches (order qty != trade qty)": meta["qty_mismatches"],
            "duplicate_trades (repeated trade_id)": meta["duplicate_trades"]}
recon = pd.DataFrame([dict(check=k, found=v, injected=expected.get(k, 0), match=(v == expected.get(k, 0))) for k, v in checks.items()])
recon.to_csv(f"{out}/data_reconciliation.csv", index=False)

# 2) Precision / recall per pattern for each rule version, against labeled ground truth
con = load(orders, trades)
res, runs = [], {}
for name, params in [("v1_loose", V1), ("v2_tuned", V2)]:
    al = run_all(con, params); runs[name] = al; al.to_csv(f"{out}/alerts_{name}.csv", index=False)
    for pat in truth.pattern.unique():
        a = al[al.pattern == pat][KEY].drop_duplicates(); g = truth[truth.pattern == pat]
        tp = len(a.merge(g, on=KEY)); fp = len(a) - tp; fn = len(g) - tp
        p = tp / (tp + fp) if tp + fp else 0; r = tp / (tp + fn) if tp + fn else 0
        res.append(dict(version=name, pattern=pat, alerts=len(a), true_pos=tp, false_pos=fp, false_neg=fn,
                        precision=round(p, 3), recall=round(r, 3), f1=round(2 * p * r / (p + r), 3) if p + r else 0))
perf = pd.DataFrame(res); perf.to_csv(f"{out}/pattern_performance.csv", index=False)

# 3) Regression diff between versions (what changed when thresholds were tuned)
k1, k2 = runs["v1_loose"][KEY].drop_duplicates(), runs["v2_tuned"][KEY].drop_duplicates()
diff = k1.merge(k2, on=KEY, how="outer", indicator=True)
diff["change"] = diff._merge.map({"left_only": "REMOVED_IN_V2", "right_only": "ADDED_IN_V2", "both": "UNCHANGED"})
diff.drop(columns="_merge").to_csv(f"{out}/version_diff.csv", index=False)

print("DATA RECONCILIATION"); print(recon.to_string(index=False))
print("\nPATTERN PERFORMANCE"); print(perf.to_string(index=False))
print("\nVERSION DIFF"); print(diff.change.value_counts().to_string())
print(f"\nOverall alerts: v1={len(k1)} v2={len(k2)}")
