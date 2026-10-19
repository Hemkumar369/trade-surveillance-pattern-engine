"""Surveillance patterns: SQL detection + Python scoring/aggregation. Each pattern emits a common alert schema."""
import sqlite3
import numpy as np
import pandas as pd

SESSION = 23400
ALERT_COLS = ["pattern", "account", "symbol", "trade_date", "score", "severity", "details"]

# v1 = loose first-pass thresholds; v2 = tuned thresholds
V1 = dict(wash=dict(min_trades=1),
          layering=dict(min_orders=2, min_qty=1000, max_cancel_s=10, gap_s=60, follow_s=60),
          marking=dict(min_trades=3, min_share=0.30, min_move=0.003, window_s=600))
V2 = dict(wash=dict(min_trades=3),
          layering=dict(min_orders=4, min_qty=10000, max_cancel_s=5, gap_s=60, follow_s=30),
          marking=dict(min_trades=5, min_share=0.40, min_move=0.010, window_s=600))


def load(orders, trades):
    con = sqlite3.connect(":memory:")
    orders.to_sql("orders", con, index=False)
    trades.to_sql("trades", con, index=False)
    return con


def wash_trades(con, p):
    q = """SELECT buy_account AS account, symbol, trade_date, COUNT(*) AS n_trades, SUM(qty) AS total_qty
           FROM trades WHERE buy_account = sell_account
           GROUP BY buy_account, symbol, trade_date HAVING COUNT(*) >= ?"""
    df = pd.read_sql(q, con, params=(p["min_trades"],))
    df["pattern"] = "WASH_TRADE"
    df["score"] = np.minimum(100, 25 * df.n_trades)
    df["details"] = df.apply(lambda r: f"{r.n_trades} self-matched trades, {r.total_qty} shares", axis=1)
    return df


def layering(con, p):
    qc = pd.read_sql("""SELECT account, symbol, trade_date, side, ts, qty FROM orders
                        WHERE status='CANCELLED' AND cancel_ts - ts <= ?""", con, params=(p["max_cancel_s"],))
    fl = pd.read_sql("SELECT account, symbol, trade_date, side, ts FROM orders WHERE status='FILLED'", con)
    fidx = {k: g.ts.values for k, g in fl.groupby(["account", "symbol", "trade_date", "side"])}
    rows = []
    for (a, s, d, side), g in qc.sort_values("ts").groupby(["account", "symbol", "trade_date", "side"]):
        cluster = (g.ts.diff().fillna(0) > p["gap_s"]).cumsum()
        for _, c in g.groupby(cluster):
            if len(c) < p["min_orders"] or c.qty.sum() < p["min_qty"]:
                continue
            opp = "SELL" if side == "BUY" else "BUY"
            f = fidx.get((a, s, d, opp), np.array([]))
            followed = bool(((f >= c.ts.min()) & (f <= c.ts.max() + p["follow_s"])).any())
            if not followed:
                continue
            rows.append(dict(account=a, symbol=s, trade_date=d, pattern="LAYERING_SPOOFING",
                             score=min(100, 10 * len(c) + c.qty.sum() / 500),
                             details=f"{len(c)} {side} orders cancelled <= {p['max_cancel_s']}s, {c.qty.sum()} shares, opposite fill followed"))
    return pd.DataFrame(rows)


def marking_close(con, p):
    t = pd.read_sql("SELECT symbol, trade_date, ts, price, qty, buy_account FROM trades WHERE ts >= ?",
                    con, params=(SESSION - p["window_s"],)).sort_values("ts")
    rows = []
    for (s, d), g in t.groupby(["symbol", "trade_date"]):
        first = g.price.iloc[0]; move = (g.price.max() - first) / first; tot = g.qty.sum()
        if move < p["min_move"]:
            continue
        for a, x in g.groupby("buy_account"):
            share = x.qty.sum() / tot
            if len(x) >= p["min_trades"] and share >= p["min_share"]:
                rows.append(dict(account=a, symbol=s, trade_date=d, pattern="MARKING_THE_CLOSE",
                                 score=min(100, 50 * share + 2500 * move),
                                 details=f"{len(x)} late buys, {share:.0%} of closing-window volume, price +{move:.2%}"))
    return pd.DataFrame(rows)


def run_all(con, params):
    parts = [f(con, params[k]) for f, k in [(wash_trades, "wash"), (layering, "layering"), (marking_close, "marking")]]
    parts = [x for x in parts if len(x)]
    al = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=ALERT_COLS)
    al["score"] = al.score.round(1)
    al["severity"] = pd.cut(al.score, [-1, 49.99, 79.99, 101], labels=["LOW", "MEDIUM", "HIGH"])
    al = al[ALERT_COLS].sort_values("score", ascending=False, ignore_index=True)
    al.insert(0, "alert_id", [f"AL{i+1:05d}" for i in range(len(al))])
    return al
