"""Data-quality reconciliation: orders <-> trades.

Surveillance output is only as good as its inputs, so this runs first. It detects:
  1. filled/partial orders with NO trade            (missing trade)
  2. orders whose filled_qty != SUM(trade quantity) (quantity mismatch)
  3. trade_ids that appear more than once           (duplicate trade id)
  4. integrity checks: orphan trades, cancelled orders with fills
Then it builds `trades_clean` (de-duplicated, indexed) for the surveillance patterns
and compares what it found to the injected-defect ground truth.
"""
import sqlite3

import pandas as pd

from config import DB_PATH, REPORT_DIR

Q_MISSING = """
SELECT o.order_id FROM orders o
LEFT JOIN trades t ON t.order_id = o.order_id
WHERE o.status IN ('FILLED','PARTIAL') AND t.trade_id IS NULL
"""
Q_QTY = """
SELECT o.order_id, o.filled_qty, SUM(t.quantity) AS trade_qty
FROM orders o JOIN (SELECT DISTINCT trade_id, order_id, quantity FROM trades) t
  ON t.order_id = o.order_id
GROUP BY o.order_id, o.filled_qty
HAVING o.filled_qty <> SUM(t.quantity)
"""
Q_DUP = "SELECT trade_id, COUNT(*) AS n FROM trades GROUP BY trade_id HAVING COUNT(*) > 1"
Q_ORPHAN = "SELECT COUNT(*) FROM trades t LEFT JOIN orders o ON o.order_id=t.order_id WHERE o.order_id IS NULL"
Q_CANC_FILL = """SELECT COUNT(*) FROM orders o JOIN trades t ON t.order_id=o.order_id
                 WHERE o.status='CANCELLED'"""


def main():
    con = sqlite3.connect(DB_PATH)
    missing = pd.read_sql_query(Q_MISSING, con)
    qty = pd.read_sql_query(Q_QTY, con)
    dup = pd.read_sql_query(Q_DUP, con)
    orphans = con.execute(Q_ORPHAN).fetchone()[0]
    canc_fill = con.execute(Q_CANC_FILL).fetchone()[0]

    found = {
        "missing_trade": set(missing["order_id"]),
        "quantity_mismatch": set(qty["order_id"]),
        "duplicate_trade_id": set(dup["trade_id"]),
    }
    gt = pd.read_sql_query("SELECT * FROM gt_injected_defects", con)
    rows, total_hit = [], 0
    for kind, grp in gt.groupby("defect_type"):
        injected = set(grp["record_key"])
        hit = injected & found[kind]
        total_hit += len(hit)
        rows.append(dict(defect_type=kind, injected=len(injected), detected=len(hit),
                         false_alarms=len(found[kind] - injected)))
    summary = pd.DataFrame(rows)

    # Staging layer for surveillance: de-duplicated trades + indexes
    con.execute("DROP TABLE IF EXISTS trades_clean")
    con.execute("CREATE TABLE trades_clean AS SELECT DISTINCT * FROM trades")
    con.execute("CREATE INDEX ix_tc_acct ON trades_clean(account_id, symbol, trade_date)")
    con.execute("CREATE INDEX ix_tc_sym ON trades_clean(symbol, trade_date, sod)")
    n_clean = con.execute("SELECT COUNT(*) FROM trades_clean").fetchone()[0]
    n_raw = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    con.commit()
    con.close()

    REPORT_DIR.mkdir(exist_ok=True)
    md = ["# Orders-to-trades reconciliation", "",
          summary.to_markdown(index=False), "",
          f"- Detected **{total_hit} of {len(gt)}** injected defects",
          f"- Orphan trades (trade with no order): {orphans}",
          f"- Cancelled orders that have fills: {canc_fill}",
          f"- Raw trades: {n_raw:,} -> `trades_clean` after de-duplication: {n_clean:,}", ""]
    (REPORT_DIR / "reconciliation_report.md").write_text("\n".join(md))
    print("\n".join(md))
    return total_hit, len(gt)


if __name__ == "__main__":
    main()
