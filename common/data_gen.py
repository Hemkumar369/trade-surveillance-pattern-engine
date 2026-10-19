"""Synthetic US equity/ETF order and trade data with injected, labeled surveillance scenarios.
All data is simulated - no real market data or accounts are used."""
import numpy as np
import pandas as pd

SESSION = 23400  # seconds in a 9:30-16:00 session


def generate(seed=42, days=5, n_symbols=20, n_accounts=300, orders_per_sym_day=600, inject_defects=True):
    rng = np.random.default_rng(seed)
    symbols = [f"SYM{i:02d}" for i in range(n_symbols)]
    base = dict(zip(symbols, rng.uniform(20, 400, n_symbols).round(2)))
    dates = list(pd.bdate_range("2026-03-02", periods=days).strftime("%Y-%m-%d"))
    accounts = np.array([f"ACC{i:04d}" for i in range(n_accounts)])
    O, T, truth, normal_tids = [], [], [], []
    cnt = {"o": 0, "t": 0}

    def px(s, mult=1.0):
        return round(base[s] * mult * (1 + rng.normal(0, 0.0005)), 2)

    def order(d, ts, a, s, side, price, qty, status, cancel_ts=None):
        cnt["o"] += 1
        O.append(dict(order_id=cnt["o"], trade_date=d, ts=int(ts), account=a, symbol=s, side=side,
                      price=price, qty=int(qty), status=status,
                      cancel_ts=None if cancel_ts is None else int(min(cancel_ts, SESSION))))
        return cnt["o"]

    def trade(d, ts, s, price, qty, buy, sell, oid):
        cnt["t"] += 1
        T.append(dict(trade_id=cnt["t"], order_id=oid, trade_date=d, ts=int(min(ts, SESSION - 1)), symbol=s,
                      price=price, qty=int(qty), buy_account=buy, sell_account=sell))
        return cnt["t"]

    def other(a):
        b = rng.choice(accounts)
        while b == a:
            b = rng.choice(accounts)
        return b

    # ---- normal flow ----
    for d in dates:
        for s in symbols:
            n = orders_per_sym_day
            ts = rng.integers(0, SESSION - 1, n); acc = rng.choice(accounts, n)
            side = rng.choice(["BUY", "SELL"], n); qty = rng.choice([100, 200, 300, 500, 1000], n)
            filled = rng.random(n) < 0.6
            delay = np.maximum(1, rng.lognormal(4.0, 1.2, n)).astype(int)
            for i in range(n):
                p = px(s)
                if filled[i]:
                    oid = order(d, ts[i], acc[i], s, side[i], p, qty[i], "FILLED")
                    cp = acc[i] if rng.random() < 0.0005 else other(acc[i])  # rare accidental self-match
                    buy, sell = (acc[i], cp) if side[i] == "BUY" else (cp, acc[i])
                    normal_tids.append(trade(d, ts[i] + rng.integers(0, 3), s, p, qty[i], buy, sell, oid))
                else:
                    order(d, ts[i], acc[i], s, side[i], p, qty[i], "CANCELLED", ts[i] + delay[i])

    def pick():
        return rng.choice(dates), rng.choice(symbols), rng.choice(accounts)

    # ---- injected wash trades ----
    for k in range(12):
        d, s, a = pick(); t0 = int(rng.integers(1000, SESSION - 2000))
        for j in range(int(rng.integers(4, 9))):
            t = t0 + j * int(rng.integers(20, 120)); q = int(rng.integers(5, 20)) * 100; p = px(s)
            oid = order(d, t, a, s, "BUY", p, q, "FILLED"); trade(d, t, s, p, q, a, a, oid)
        truth.append(("WASH_TRADE", a, s, d))

    # ---- injected layering / spoofing ----
    for k in range(12):
        d, s, a = pick(); side = rng.choice(["BUY", "SELL"]); t = int(rng.integers(1000, SESSION - 2000))
        for j in range(int(rng.integers(4, 7))):
            t += int(rng.integers(1, 3)); step = 1 - 0.0005 * j if side == "BUY" else 1 + 0.0005 * j
            order(d, t, a, s, side, px(s, step), int(rng.integers(20, 50)) * 100, "CANCELLED", t + int(rng.integers(1, 5)))
        opp = "SELL" if side == "BUY" else "BUY"; t += int(rng.integers(1, 6)); p = px(s); q = int(rng.integers(3, 6)) * 100
        oid = order(d, t, a, s, opp, p, q, "FILLED"); cp = other(a)
        trade(d, t, s, p, q, *((cp, a) if opp == "SELL" else (a, cp)), oid)
        truth.append(("LAYERING_SPOOFING", a, s, d))

    # benign decoys: two small quick cancels (should NOT alert under tuned rules)
    for k in range(15):
        d, s, a = pick(); side = rng.choice(["BUY", "SELL"]); t = int(rng.integers(1000, SESSION - 2000))
        for j in range(2):
            order(d, t + j * 2, a, s, side, px(s), 500, "CANCELLED", t + j * 2 + int(rng.integers(1, 4)))

    # ---- injected marking the close ----
    for k in range(10):
        d, s, a = pick(); ramp = rng.uniform(0.015, 0.03); n = int(rng.integers(8, 13))
        times = np.sort(rng.integers(SESSION - 590, SESSION - 5, n))
        for j, t in enumerate(times):
            p = px(s, 1 + ramp * (j + 1) / n); q = int(rng.integers(5, 20)) * 100
            oid = order(d, t, a, s, "BUY", p, q, "FILLED"); trade(d, t, s, p, q, a, other(a), oid)
        truth.append(("MARKING_THE_CLOSE", a, s, d))

    # benign decoys: heavy late buying with no price impact (should NOT alert under tuned rules)
    for k in range(10):
        d, s, a = pick(); times = np.sort(rng.integers(SESSION - 590, SESSION - 5, 8))
        for t in times:
            p = px(s); oid = order(d, t, a, s, "BUY", p, 1000, "FILLED"); trade(d, t, s, p, 1000, a, other(a), oid)

    odf, tdf = pd.DataFrame(O), pd.DataFrame(T)
    meta = {}
    if inject_defects:  # known data-quality defects so reconciliation checks can be verified
        ids = rng.choice(normal_tids, 23, replace=False)
        drop, alt, dup = ids[:10], ids[10:18], ids[18:]
        tdf.loc[tdf.trade_id.isin(alt), "qty"] += 100
        tdf = pd.concat([tdf[~tdf.trade_id.isin(drop)], tdf[tdf.trade_id.isin(dup)]], ignore_index=True)
        meta = dict(missing_trades=len(drop), qty_mismatches=len(alt), duplicate_trades=len(dup))
    truth_df = pd.DataFrame(truth, columns=["pattern", "account", "symbol", "trade_date"])
    return odf, tdf, truth_df, meta
