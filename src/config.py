"""Central configuration: data-generation constants and surveillance thresholds.

Two threshold sets are kept side by side so the tuning exercise is reproducible:
  v1 = deliberately loose first-pass thresholds (high recall, noisy)
  v2 = tuned thresholds (fewer false positives, documented recall trade-off)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "surveillance.db"
SQL_DIR = ROOT / "sql"
REPORT_DIR = ROOT / "reports"

# ---- synthetic market ------------------------------------------------------
SEED = 42
START_DATE = "2025-03-03"
N_DAYS = 20                      # business days
OPEN_SOD = 9 * 3600 + 30 * 60    # 09:30 in seconds-of-day
CLOSE_SOD = 16 * 3600            # 16:00
N_ACCOUNTS = 400
N_MARKET_MAKERS = 12             # legitimate two-sided liquidity providers
BG_ORDERS = 59_820               # background (normal) orders; scenarios add more
CLOSE_PUSH_MIN = 10              # minutes of price drift injected before close

SYMBOLS = [
    "SPY", "QQQ", "IWM", "DIA", "XLF", "XLE", "XLK", "XLV", "GLD", "TLT",
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "BAC", "WFC",
    "GS", "MS", "C", "V", "MA", "KO", "PEP", "WMT", "HD", "DIS",
    "NFLX", "INTC", "AMD", "CSCO", "ORCL", "IBM", "XOM", "CVX", "PFE", "MRK",
]

# ---- injected data-quality defects (for the reconciliation exercise) --------
DEFECTS = {"missing_trade": 8, "quantity_mismatch": 8, "duplicate_trade_id": 7}

# ---- injected surveillance scenarios ---------------------------------------
SCENARIOS = {
    "wash_trade":        {"easy": 8, "hard": 1, "benign": 9, "benign_v2_fp": 1},
    "layering_spoofing": {"easy": 6, "hard": 1, "benign": 7, "benign_v2_fp": 1},
    "marking_the_close": {"easy": 6, "hard": 1, "benign": 7, "benign_v2_fp": 1},
}

# ---- surveillance thresholds -----------------------------------------------
PARAMS = {
    "v1": {
        "wash_trade": {"window_s": 300, "qty_tol": 0.25, "price_tol": 0.005},
        "layering_spoofing": {
            "min_orders": 3, "window_s": 60, "max_cancel_s": 60,
            "require_exec": 0, "exec_gap_s": 15,
        },
        "marking_the_close": {
            "window_s": 900, "min_share": 0.15,
            "min_one_sided": 0.0, "min_impact_bps": -10000.0,
        },
    },
    "v2": {
        "wash_trade": {"window_s": 120, "qty_tol": 0.05, "price_tol": 0.001},
        "layering_spoofing": {
            "min_orders": 5, "window_s": 45, "max_cancel_s": 30,
            "require_exec": 1, "exec_gap_s": 15,
        },
        "marking_the_close": {
            "window_s": 600, "min_share": 0.25,
            "min_one_sided": 0.80, "min_impact_bps": 10.0,
        },
    },
}
PATTERNS = ["wash_trade", "layering_spoofing", "marking_the_close"]

SEVERITY_BANDS = [(80, "HIGH"), (60, "MEDIUM"), (0, "LOW")]
