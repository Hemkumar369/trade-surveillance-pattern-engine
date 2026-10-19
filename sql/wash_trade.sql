-- WASH TRADE: the same account buys and sells the same symbol on the same day,
-- close together in time, with near-identical size and price (no change in
-- beneficial ownership; artificially inflates volume).
-- Parameters: :window_s  max seconds between the buy and the sell
--             :qty_tol   max relative quantity difference
--             :price_tol max relative price difference
WITH pairs AS (
    SELECT b.account_id, b.symbol, b.trade_date,
           ABS(s.trade_ts - b.trade_ts) * 1.0                                AS gap_s,
           ABS(b.quantity - s.quantity) * 1.0 / MAX(b.quantity, s.quantity)  AS qty_diff,
           ABS(b.price - s.price) / ((b.price + s.price) / 2.0)              AS price_diff,
           MIN(b.quantity, s.quantity) * (b.price + s.price) / 2.0           AS notional
    FROM trades_clean b
    JOIN trades_clean s
      ON  s.account_id = b.account_id
      AND s.symbol     = b.symbol
      AND s.trade_date = b.trade_date
    WHERE b.side = 'BUY' AND s.side = 'SELL'
      AND ABS(s.trade_ts - b.trade_ts) <= :window_s
)
SELECT account_id, symbol, trade_date,
       COUNT(*)                         AS pair_count,
       ROUND(SUM(notional), 2)          AS notional,
       -- score: closer in time, size and price = higher
       ROUND(MAX(100 * (0.4 * (1 - gap_s / :window_s)
                      + 0.4 * (1 - qty_diff / :qty_tol)
                      + 0.2 * (1 - price_diff / :price_tol))), 1) AS score,
       MIN(gap_s)                       AS min_gap_s,
       ROUND(MIN(qty_diff), 4)          AS min_qty_diff,
       ROUND(MIN(price_diff), 6)        AS min_price_diff
FROM pairs
WHERE qty_diff <= :qty_tol AND price_diff <= :price_tol
GROUP BY account_id, symbol, trade_date;
