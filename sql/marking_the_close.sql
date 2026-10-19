-- MARKING THE CLOSE: an account trades a large, one-directional share of the day's
-- volume in the final minutes, pushing the closing price in its favour.
-- Parameters: :close_sod        market close, seconds-of-day (16:00 = 57600)
--             :window_s         length of the closing window
--             :min_share        min share of the symbol's daily volume inside the window
--             :min_one_sided    min fraction of the account's window volume on one side
--             :min_impact_bps   min price move (bps) in the account's direction
WITH win AS (
    SELECT account_id, symbol, trade_date,
           SUM(quantity)                                          AS win_qty,
           SUM(CASE WHEN side = 'BUY'  THEN quantity ELSE 0 END)  AS buy_qty,
           SUM(CASE WHEN side = 'SELL' THEN quantity ELSE 0 END)  AS sell_qty,
           SUM(quantity * price)                                  AS win_notional
    FROM trades_clean
    WHERE sod >= :close_sod - :window_s AND sod < :close_sod
    GROUP BY account_id, symbol, trade_date
),
day AS (
    SELECT symbol, trade_date, SUM(quantity) AS day_vol
    FROM trades_clean GROUP BY symbol, trade_date
),
px AS (                            -- reference price before the window vs last price of day
    SELECT d.symbol, d.trade_date,
      (SELECT price FROM trades_clean t
        WHERE t.symbol = d.symbol AND t.trade_date = d.trade_date
          AND t.sod < :close_sod - :window_s
        ORDER BY t.trade_ts DESC, t.trade_id DESC LIMIT 1) AS start_px,
      (SELECT price FROM trades_clean t
        WHERE t.symbol = d.symbol AND t.trade_date = d.trade_date
          AND t.sod < :close_sod
        ORDER BY t.trade_ts DESC, t.trade_id DESC LIMIT 1) AS end_px
    FROM day d
),
scored AS (
    SELECT w.account_id, w.symbol, w.trade_date, w.win_qty, d.day_vol,
           w.win_qty * 1.0 / d.day_vol                               AS share,
           MAX(w.buy_qty, w.sell_qty) * 1.0 / w.win_qty              AS one_sided,
           CASE WHEN w.buy_qty >= w.sell_qty THEN 1 ELSE -1 END
             * (p.end_px - p.start_px) / p.start_px * 10000.0        AS impact_bps,
           w.win_notional
    FROM win w
    JOIN day d ON d.symbol = w.symbol AND d.trade_date = w.trade_date
    JOIN px  p ON p.symbol = w.symbol AND p.trade_date = w.trade_date
)
SELECT account_id, symbol, trade_date,
       win_qty, day_vol,
       ROUND(share, 4)        AS share,
       ROUND(one_sided, 3)    AS one_sided,
       ROUND(impact_bps, 1)   AS impact_bps,
       ROUND(win_notional, 2) AS notional,
       -- score: bigger share, more one-sided, more price impact = higher
       ROUND(MIN(100.0, 30 + 100 * share + 0.5 * MAX(impact_bps, 0) + 20 * one_sided), 1) AS score
FROM scored
WHERE share >= :min_share
  AND one_sided >= :min_one_sided
  AND impact_bps >= :min_impact_bps;
