"""Run the SQL surveillance patterns and write scored, severity-ranked alerts.

Every pattern returns a different shape, but all alerts are normalised to a common
schema: (alert_id, version, pattern, account_id, symbol, trade_date, score, severity,
notional, detail) and then rolled up per account.
"""
import json
import sqlite3

import pandas as pd

from config import (CLOSE_SOD, DB_PATH, PARAMS, PATTERNS, SEVERITY_BANDS, SQL_DIR)

KEYS = ["account_id", "symbol", "trade_date"]


def severity(score: float) -> str:
    for floor, label in SEVERITY_BANDS:
        if score >= floor:
            return label
    return "LOW"


def run_pattern(con, pattern: str, params: dict) -> pd.DataFrame:
    sql = (SQL_DIR / f"{pattern}.sql").read_text()
    p = dict(params)
    if pattern == "marking_the_close":
        p["close_sod"] = CLOSE_SOD
    return pd.read_sql_query(sql, con, params=p)


def to_alerts(df: pd.DataFrame, pattern: str, version: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    extra = [c for c in df.columns if c not in KEYS + ["score", "notional"]]
    out = df[KEYS + ["score", "notional"]].copy()
    out["pattern"], out["version"] = pattern, version
    out["detail"] = df[extra].apply(lambda r: json.dumps(r.to_dict(), default=float), axis=1)
    out["severity"] = out["score"].map(severity)
    return out


def run_version(con, version: str, params: dict = None) -> pd.DataFrame:
    params = params or PARAMS[version]
    frames = [to_alerts(run_pattern(con, p, params[p]), p, version) for p in PATTERNS]
    alerts = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    alerts = alerts.sort_values(["score", "notional"], ascending=False).reset_index(drop=True)
    alerts.insert(0, "alert_id",
                  [f"{version.upper()}-{i:04d}" for i in range(1, len(alerts) + 1)])
    return alerts


def account_rollup(alerts: pd.DataFrame) -> pd.DataFrame:
    g = alerts.groupby(["version", "account_id"])
    roll = g.agg(alert_count=("alert_id", "count"),
                 patterns=("pattern", lambda s: ", ".join(sorted(set(s)))),
                 distinct_patterns=("pattern", "nunique"),
                 max_score=("score", "max"),
                 total_notional=("notional", "sum")).reset_index()
    # multi-pattern accounts are escalated: behaviour across patterns is more suspicious
    roll["risk_tier"] = roll.apply(
        lambda r: "ESCALATE" if r.distinct_patterns > 1 or r.max_score >= 80
        else ("REVIEW" if r.max_score >= 60 else "MONITOR"), axis=1)
    return roll.sort_values(["version", "max_score"], ascending=[True, False])


def main():
    con = sqlite3.connect(DB_PATH)
    all_alerts = [run_version(con, v) for v in ("v1", "v2")]
    alerts = pd.concat(all_alerts, ignore_index=True)
    roll = account_rollup(alerts)
    alerts.to_sql("alerts", con, if_exists="replace", index=False)
    roll.to_sql("account_rollup", con, if_exists="replace", index=False)
    con.close()
    print(alerts.groupby(["version", "pattern"]).size().unstack(0))
    return alerts


if __name__ == "__main__":
    main()
