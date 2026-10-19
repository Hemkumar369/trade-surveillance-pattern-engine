"""Generate a synthetic equity/ETF order and trade book.

Output (SQLite, data/surveillance.db):
  orders, trades               - the "production" tables (with injected defects)
  gt_case_labels               - ground truth: injected surveillance scenarios
  gt_injected_defects          - ground truth: injected data-quality defects

Everything is synthetic. Prices follow a random walk; behaviour is NOT calibrated
to real markets. The point is a controlled test bed where the right answer is known,
so alert precision/recall can be measured.
"""
import json
import sqlite3

import numpy as np
import pandas as pd

from config import *  # noqa: F401,F403

rng = np.random.default_rng(SEED)
DAYS = pd.bdate_range(START_DATE, periods=N_DAYS)
EPOCH0 = pd.Timestamp("1970-01-01")
N_MIN = (CLOSE_SOD - OPEN_SOD) // 60  # 390 minutes

ACCOUNTS = [f"ACC{i:04d}" for i in range(1, N_ACCOUNTS + 1)]
MMS = [f"MM{i:02d}" for i in range(1, N_MARKET_MAKERS + 1)]
ALL_ACCOUNTS = ACCOUNTS + MMS


def ts(di: int, sod: float) -> int:
    """Epoch seconds for business-day index `di` and seconds-of-day `sod`."""
    return int((DAYS[di] - EPOCH0).days) * 86400 + int(sod)


# ---------------------------------------------------------------- price paths
base_px = rng.uniform(25, 450, len(SYMBOLS))
paths = {}
for si, sym in enumerate(SYMBOLS):
    px = base_px[si]
    for di in range(N_DAYS):
        px *= 1 + rng.normal(0, 0.008)
        path = px * np.cumprod(1 + rng.normal(0, 0.0003, N_MIN + 1))
        paths[(sym, di)] = path
        px = path[-1]


def mid(sym, di, sod):
    idx = int(min(max((sod - OPEN_SOD) // 60, 0), N_MIN))
    return float(paths[(sym, di)][idx])


def apply_close_drift(sym, di, bps):
    """Push the last CLOSE_PUSH_MIN minutes of the price path by `bps`."""
    n = CLOSE_PUSH_MIN + 1
    paths[(sym, di)][-n:] *= 1 + (bps / 1e4) * np.linspace(0, 1, n)


# ------------------------------------------------------------------- the book
class Book:
    def __init__(self):
        self.orders, self.trades, self.labels = [], [], []
        self._k = 0

    def add(self, account, sym, di, side, qty, sod, limit_px, status, fills=(),
            cancel_sod=None, scenario=False):
        """fills = [(delay_s, qty, price), ...]; filled_qty is derived from fills."""
        self._k += 1
        key = self._k
        filled = int(sum(f[1] for f in fills))
        self.orders.append(dict(
            okey=key, account_id=account, symbol=sym, side=side,
            order_type="LIMIT", limit_price=round(limit_px, 2), quantity=int(qty),
            filled_qty=filled, status=status, order_ts=ts(di, sod),
            cancel_ts=ts(di, cancel_sod) if cancel_sod is not None else None,
            trade_date=DAYS[di].strftime("%Y-%m-%d"), sod=int(sod), scenario=scenario,
        ))
        for delay, q, px in fills:
            t_sod = min(sod + delay, CLOSE_SOD - 1)
            self.trades.append(dict(
                okey=key, account_id=account, symbol=sym, side=side,
                price=round(px, 2), quantity=int(q), trade_ts=ts(di, t_sod),
                trade_date=DAYS[di].strftime("%Y-%m-%d"), sod=int(t_sod),
            ))
        return key

    def label(self, pattern, account, sym, di, kind, difficulty, note):
        self.labels.append(dict(
            pattern=pattern, account_id=account, symbol=sym,
            trade_date=DAYS[di].strftime("%Y-%m-%d"),
            label=kind, difficulty=difficulty, note=note,
        ))


book = Book()
used = {p: set() for p in PATTERNS}


def pick(pattern, pool, sym=None, di=None):
    """Pick a unique (account, symbol, day) for a scenario."""
    while True:
        a = pool[rng.integers(len(pool))]
        s = sym or SYMBOLS[rng.integers(len(SYMBOLS))]
        d = di if di is not None else int(rng.integers(N_DAYS))
        if (a, s, d) not in used[pattern]:
            used[pattern].add((a, s, d))
            return a, s, d


# ------------------------------------------- 1) plan close-marking symbol-days
cm = SCENARIOS["marking_the_close"]
n_close = cm["easy"] + cm["hard"] + cm["benign"] + cm["benign_v2_fp"]
combos = [(s, d) for s in SYMBOLS for d in range(N_DAYS)]
close_idx = rng.choice(len(combos), n_close, replace=False)
close_plan = [combos[i] for i in close_idx]
close_drift = {}
for i, (s, d) in enumerate(close_plan):
    if i < cm["easy"] + cm["hard"]:                       # positives: pushed price
        close_drift[(s, d)] = float(rng.choice([-1, 1]) * rng.uniform(25, 60))
    elif i >= cm["easy"] + cm["hard"] + cm["benign"]:     # benign trend-follower
        close_drift[(s, d)] = float(rng.uniform(14, 18))
    else:
        close_drift[(s, d)] = 0.0
    apply_close_drift(s, d, close_drift[(s, d)])

# ------------------------------------------------------ 2) background orders
N = BG_ORDERS
weights = np.r_[np.ones(N_ACCOUNTS), np.full(N_MARKET_MAKERS, 4.0)]
weights /= weights.sum()
acct = rng.choice(ALL_ACCOUNTS, N, p=weights)
sym_i = rng.integers(len(SYMBOLS), size=N)
day_i = rng.integers(N_DAYS, size=N)
u = rng.random(N)
sod = np.where(u < 0.30, OPEN_SOD + rng.beta(1, 4, N) * 3600,
               np.where(u < 0.80, rng.uniform(OPEN_SOD, CLOSE_SOD - 1, N),
                        CLOSE_SOD - 1 - rng.beta(1, 3, N) * 3600))
sod = np.clip(sod.astype(int), OPEN_SOD, CLOSE_SOD - 2)
side = rng.choice(["BUY", "SELL"], N)
qty = np.maximum(10, (rng.lognormal(np.log(380), 0.8, N) / 10).astype(int) * 10)
r = rng.random(N)
status = np.where(r < 0.48, "FILLED", np.where(r < 0.54, "PARTIAL", "CANCELLED"))

for i in range(N):
    sym, di, s0 = SYMBOLS[sym_i[i]], int(day_i[i]), int(sod[i])
    m = mid(sym, di, s0)
    sgn = 1 if side[i] == "BUY" else -1
    lim = m * (1 - sgn * 0.0003)
    q = int(qty[i])
    if status[i] == "FILLED":
        fills = [(1 + rng.exponential(8), q, m * (1 + rng.normal(0, 0.0003)))]
        book.add(acct[i], sym, di, side[i], q, s0, lim, "FILLED", fills)
    elif status[i] == "PARTIAL":
        q = max(q, 40)
        f1 = max(10, int(q * rng.uniform(0.3, 0.6) / 10) * 10)
        f2 = max(10, int(q * rng.uniform(0.1, 0.3) / 10) * 10)
        d1 = 1 + rng.exponential(8)
        fills = [(d1, f1, m * (1 + rng.normal(0, 0.0003))),
                 (d1 + 1 + rng.exponential(15), f2, m * (1 + rng.normal(0, 0.0003)))]
        book.add(acct[i], sym, di, side[i], max(q, f1 + f2 + 10), s0, lim, "PARTIAL",
                 fills, cancel_sod=min(s0 + 120 + rng.exponential(90), CLOSE_SOD - 1))
    else:
        c = min(s0 + 1 + rng.exponential(120), CLOSE_SOD - 1)
        book.add(acct[i], sym, di, side[i], q, s0, lim, "CANCELLED", (), cancel_sod=c)

bg_trades = pd.DataFrame(book.trades)
day_vol = bg_trades.groupby(["symbol", "trade_date"])["quantity"].sum().to_dict()


# ----------------------------------------------------------- 3) scenarios
def wash_case(acct_, sym, di, s0, qty_, gap, qty_diff, px_diff):
    m = mid(sym, di, s0)
    q2 = int(round(qty_ * (1 + qty_diff) / 10) * 10)
    book.add(acct_, sym, di, "BUY", qty_, s0, m, "FILLED", [(1, qty_, m)], scenario=True)
    book.add(acct_, sym, di, "SELL", q2, s0 + gap, m, "FILLED",
             [(1, q2, m * (1 + px_diff))], scenario=True)


sc = SCENARIOS["wash_trade"]
for kind, n in [("easy", sc["easy"]), ("hard", sc["hard"])]:
    for _ in range(n):
        a, s, d = pick("wash_trade", ACCOUNTS)
        s0 = int(rng.integers(OPEN_SOD + 600, CLOSE_SOD - 3600))
        qq = int(rng.choice([500, 1000, 1500, 2000, 5000]))
        if kind == "easy":
            wash_case(a, s, d, s0, qq, int(rng.integers(10, 80)),
                      rng.uniform(-0.02, 0.02), rng.uniform(0, 0.0002))
        else:   # slightly mismatched wash: real but evades tuned thresholds
            wash_case(a, s, d, s0, qq, int(rng.integers(150, 230)),
                      rng.uniform(0.07, 0.09), rng.uniform(0.0003, 0.0005))
        book.label("wash_trade", a, s, d, "POSITIVE", kind,
                   "same account buys and sells same symbol within minutes")
for k in range(sc["benign"] + sc["benign_v2_fp"]):
    a, s, d = pick("wash_trade", MMS)
    s0 = int(rng.integers(OPEN_SOD + 600, CLOSE_SOD - 3600))
    qq = int(rng.choice([300, 600, 1000, 2000]))
    if k < sc["benign"]:    # market maker flipping inventory, loosely matched
        wash_case(a, s, d, s0, qq, int(rng.integers(130, 280)),
                  rng.choice([-1, 1]) * rng.uniform(0.10, 0.22),
                  rng.uniform(0.0015, 0.004))
        note = "market-maker inventory flip, loose size/price match"
    else:                   # near-identical MM round trip: still benign, still flagged
        wash_case(a, s, d, s0, qq, 70, 0.03, 0.0005)
        note = "market-maker round trip that looks like a wash (unavoidable FP)"
    book.label("wash_trade", a, s, d, "BENIGN_LOOKALIKE", "benign", note)


def layering_case(acct_, sym, di, s0, n, size, side_, hard):
    opp = "SELL" if side_ == "BUY" else "BUY"
    m = mid(sym, di, s0)
    sgn = 1 if side_ == "BUY" else -1
    exec_sod = s0 + n * 1.5 + 2
    lat = rng.uniform(36, 45) if hard else rng.uniform(2, 8)
    for i in range(n):
        o = s0 + i * 1.5
        book.add(acct_, sym, di, side_, size, o, m * (1 - sgn * 0.0005 * (i + 1)),
                 "CANCELLED", cancel_sod=exec_sod + lat, scenario=True)
    q = int(rng.choice([300, 500, 800]))
    book.add(acct_, sym, di, opp, q, exec_sod, m * (1 + sgn * 0.0003), "FILLED",
             [(1, q, m * (1 + sgn * 0.0003))], scenario=True)


sc = SCENARIOS["layering_spoofing"]
for kind, n_cases in [("easy", sc["easy"]), ("hard", sc["hard"])]:
    for _ in range(n_cases):
        a, s, d = pick("layering_spoofing", ACCOUNTS)
        n_orders = int(rng.integers(5, 9)) if kind == "easy" else 4
        layering_case(a, s, d, int(rng.integers(OPEN_SOD + 600, CLOSE_SOD - 3600)),
                      n_orders, int(rng.choice([1500, 2000, 3000])),
                      str(rng.choice(["BUY", "SELL"])), hard=(kind == "hard"))
        book.label("layering_spoofing", a, s, d, "POSITIVE", kind,
                   "stacked orders on one side cancelled right after opposite-side execution")
for k in range(sc["benign"] + sc["benign_v2_fp"]):
    a, s, d = pick("layering_spoofing", MMS)
    s0 = int(rng.integers(OPEN_SOD + 600, CLOSE_SOD - 3600))
    side_ = str(rng.choice(["BUY", "SELL"]))
    m = mid(s, d, s0)
    sgn = 1 if side_ == "BUY" else -1
    if k < sc["benign"]:    # quote repricing: several quotes cancelled, no opposite fill
        n_orders = int(rng.integers(3, 7))
        for i in range(n_orders):
            o = s0 + i * rng.uniform(4, 9)
            book.add(a, s, d, side_, int(rng.choice([200, 400, 600])), o,
                     m * (1 - sgn * 0.0004 * (i + 1)), "CANCELLED",
                     cancel_sod=o + rng.uniform(5, 50), scenario=True)
        note = "market-maker quote repricing, no opposite-side execution"
    else:                   # repricing that happens to coincide with a hedge fill
        layering_case(a, s, d, s0, 5, 400, side_, hard=False)
        note = "quote repricing coinciding with a hedge fill (unavoidable FP)"
    book.label("layering_spoofing", a, s, d, "BENIGN_LOOKALIKE", "benign", note)


def close_case(acct_, sym, di, share, sides, window_lo, n_trades=5):
    """Place trades in the closing window sized to `share` of the day's volume."""
    v = day_vol[(sym, DAYS[di].strftime("%Y-%m-%d"))]
    x = share * v / (1 - share)
    q = max(100, int(x / n_trades / 10) * 10)
    for k in range(n_trades):
        s0 = int(rng.integers(window_lo, CLOSE_SOD - 30))
        m = mid(sym, di, s0)
        sd = sides[k % len(sides)]
        book.add(acct_, sym, di, sd, q, s0, m, "FILLED", [(1, q, m)], scenario=True)


sc = SCENARIOS["marking_the_close"]
plan = iter(close_plan)
for kind, n_cases in [("easy", sc["easy"]), ("hard", sc["hard"])]:
    for _ in range(n_cases):
        s, d = next(plan)
        a, _, _ = pick("marking_the_close", ACCOUNTS, sym=s, di=d)
        share = rng.uniform(0.30, 0.42) if kind == "easy" else rng.uniform(0.18, 0.21)
        direction = "BUY" if close_drift[(s, d)] > 0 else "SELL"
        close_case(a, s, d, share, [direction], CLOSE_SOD - CLOSE_PUSH_MIN * 60 + 30)
        book.label("marking_the_close", a, s, d, "POSITIVE", kind,
                   "large one-sided volume in last minutes pushing the closing price")
for k in range(sc["benign"] + sc["benign_v2_fp"]):
    s, d = next(plan)
    if k < sc["benign"]:    # two-sided closing activity, no price push
        a, _, _ = pick("marking_the_close", MMS + ACCOUNTS[:20], sym=s, di=d)
        close_case(a, s, d, rng.uniform(0.16, 0.28), ["BUY", "SELL"],
                   CLOSE_SOD - 840, n_trades=6)
        note = "two-sided closing activity, no directional price impact"
    else:                   # one-sided buyer into a market-wide move
        a, _, _ = pick("marking_the_close", ACCOUNTS, sym=s, di=d)
        close_case(a, s, d, 0.28, ["BUY"], CLOSE_SOD - CLOSE_PUSH_MIN * 60 + 30)
        note = "one-sided closing buyer during a genuine market-wide move (unavoidable FP)"
    book.label("marking_the_close", a, s, d, "BENIGN_LOOKALIKE", "benign", note)

# ------------------------------------------------- 4) assemble + sort + IDs
orders = pd.DataFrame(book.orders).sort_values(["order_ts", "okey"]).reset_index(drop=True)
orders["order_id"] = [f"ORD{i:07d}" for i in range(1, len(orders) + 1)]
okey_to_id = dict(zip(orders["okey"], orders["order_id"]))
trades = pd.DataFrame(book.trades)
trades["order_id"] = trades["okey"].map(okey_to_id)
trades = trades.sort_values(["trade_ts", "okey"]).reset_index(drop=True)
trades["trade_id"] = [f"TRD{i:07d}" for i in range(1, len(trades) + 1)]
scenario_ids = set(orders.loc[orders["scenario"], "order_id"])

# -------------------------------------------- 5) inject data-quality defects
defects = []
eligible = (trades[~trades["order_id"].isin(scenario_ids)]
            .merge(orders[orders["status"] == "FILLED"][["order_id"]], on="order_id")
            .sample(frac=1, random_state=SEED))
cursor = iter(eligible.itertuples(index=False))
dup_rows = []
for kind, n in DEFECTS.items():
    for _ in range(n):
        t = next(cursor)
        if kind == "missing_trade":
            trades = trades[trades["trade_id"] != t.trade_id]
            key = t.order_id
        elif kind == "quantity_mismatch":
            trades.loc[trades["trade_id"] == t.trade_id, "quantity"] += int(rng.choice([10, 50, 100]))
            key = t.order_id
        else:
            dup_rows.append(trades[trades["trade_id"] == t.trade_id])
            key = t.trade_id
        defects.append(dict(defect_id=len(defects) + 1, defect_type=kind, record_key=key))
trades = pd.concat([trades] + dup_rows, ignore_index=True)
trades = trades.sort_values(["trade_ts", "trade_id"]).reset_index(drop=True)

# ----------------------------------------------------------------- 6) write DB
DB_PATH.parent.mkdir(exist_ok=True)
if DB_PATH.exists():
    DB_PATH.unlink()
con = sqlite3.connect(DB_PATH)
ocols = ["order_id", "account_id", "symbol", "side", "order_type", "limit_price", "quantity",
         "filled_qty", "status", "order_ts", "cancel_ts", "trade_date", "sod"]
tcols = ["trade_id", "order_id", "account_id", "symbol", "side", "price", "quantity",
         "trade_ts", "trade_date", "sod"]
orders[ocols].to_sql("orders", con, index=False)
trades[tcols].to_sql("trades", con, index=False)
pd.DataFrame(book.labels).assign(case_id=lambda x: range(1, len(x) + 1)).to_sql(
    "gt_case_labels", con, index=False)
pd.DataFrame(defects).to_sql("gt_injected_defects", con, index=False)
con.execute("CREATE INDEX ix_orders_acct ON orders(account_id, symbol, trade_date)")
con.execute("CREATE INDEX ix_trades_order ON trades(order_id)")
con.commit()
con.close()

summary = dict(
    orders=len(orders), trades=len(trades), accounts=len(ALL_ACCOUNTS),
    symbols=len(SYMBOLS), trading_days=N_DAYS,
    scenario_cases=len(book.labels), injected_defects=len(defects),
)
print(json.dumps(summary, indent=2))
