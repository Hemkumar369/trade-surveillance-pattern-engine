"""Sanity tests. Run the pipeline first:  python src/run_all.py  then  pytest"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import DB_PATH  # noqa: E402
from evaluate import load, metrics  # noqa: E402


def _con():
    return sqlite3.connect(DB_PATH)


def test_volume_targets():
    c = _con()
    assert c.execute("SELECT COUNT(*) FROM orders").fetchone()[0] >= 60_000
    assert c.execute("SELECT COUNT(*) FROM trades").fetchone()[0] >= 36_000


def test_all_injected_defects_detected():
    from reconcile import main
    hit, total = main()
    assert hit == total == 23


def test_tuning_improves_precision_without_collapsing_recall():
    c = _con()
    alerts, labels = load(c)
    m = metrics(alerts, labels)
    all_ = m[m["pattern"] == "ALL"].set_index("version")
    assert all_.loc["v2", "alerts"] < all_.loc["v1", "alerts"]
    assert all_.loc["v2", "precision"] > all_.loc["v1", "precision"]
    assert all_.loc["v2", "recall"] >= 0.8


def test_alerts_have_common_schema():
    a = pd.read_sql_query("SELECT * FROM alerts", _con())
    for col in ["alert_id", "version", "pattern", "account_id", "symbol",
                "trade_date", "score", "severity"]:
        assert col in a.columns
    assert set(a["severity"]) <= {"HIGH", "MEDIUM", "LOW"}
