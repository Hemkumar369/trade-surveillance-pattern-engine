-- LAYERING / SPOOFING: an account stacks several same-side orders, then trades on
-- the opposite side, then cancels the stacked orders. The stacked orders were never
-- meant to execute; they exist to move the market.
-- Parameters: :min_orders    min stacked orders in the cluster
--             :window_s      orders must be placed within this many seconds
--             :max_cancel_s  each order must be cancelled within this many seconds
--             :require_exec  1 = require an opposite-side execution during the cluster
--             :exec_gap_s    grace after the last cancel for the opposite execution
WITH canc AS (
    SELECT order_id, account_id, symbol, side, trade_date, order_ts, cancel_ts,
           quantity, limit_price
    FROM orders
    WHERE status = 'CANCELLED' AND cancel_ts - order_ts <= :max_cancel_s
),
clusters AS (                      -- anchor on each order, gather those placed shortly after
    SELECT a.order_id AS anchor_id, a.account_id, a.symbol, a.side, a.trade_date,
           COUNT(*)                          AS n_orders,
           MIN(b.order_ts)                   AS first_ts,
           MAX(b.cancel_ts)                  AS last_cancel_ts,
           SUM(b.quantity)                   AS layered_qty,
           SUM(b.quantity * b.limit_price)   AS layered_notional
    FROM canc a
    JOIN canc b
      ON  b.account_id = a.account_id AND b.symbol = a.symbol
      AND b.side       = a.side       AND b.trade_date = a.trade_date
      AND b.order_ts BETWEEN a.order_ts AND a.order_ts + :window_s
    GROUP BY a.order_id
),
best AS (                          -- keep the biggest cluster per account/symbol/day/side
    SELECT *, ROW_NUMBER() OVER (
               PARTITION BY account_id, symbol, side, trade_date
               ORDER BY n_orders DESC, first_ts) AS rn
    FROM clusters
),
enriched AS (
    SELECT b.*,
           (SELECT COALESCE(SUM(t.quantity), 0)
              FROM trades_clean t
             WHERE t.account_id = b.account_id AND t.symbol = b.symbol
               AND t.side <> b.side
               AND t.trade_ts BETWEEN b.first_ts AND b.last_cancel_ts + :exec_gap_s
           ) AS opp_exec_qty
    FROM best b
    WHERE rn = 1 AND n_orders >= :min_orders
)
SELECT account_id, symbol, trade_date, side, n_orders, layered_qty, opp_exec_qty,
       ROUND(layered_notional, 2) AS notional,
       -- score: more layers and an opposite-side execution = higher
       MIN(100.0, 40 + 6 * n_orders + CASE WHEN opp_exec_qty > 0 THEN 20 ELSE 0 END) AS score
FROM enriched
WHERE (:require_exec = 0 OR opp_exec_qty > 0);
