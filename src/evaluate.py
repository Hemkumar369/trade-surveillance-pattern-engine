"""Measure precision/recall per pattern against the labeled scenarios, and diff v1 vs v2.

An alert is a TRUE POSITIVE if it matches a labeled POSITIVE case on
(pattern, account, symbol, trade_date). Every other alert is a false positive.
Recall = labeled positives alerted / labeled positives.
"""
import sqlite3

import pandas as pd

from config import DB_PATH, PATTERNS, REPORT_DIR

K = ["pattern", "account_id", "symbol", "trade_date"]


def load(con):
    alerts = pd.read_sql_query("SELECT * FROM alerts", con)
    labels = pd.read_sql_query("SELECT * FROM gt_case_labels", con)
    return alerts, labels


def metrics(alerts: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    pos = labels[labels["label"] == "POSITIVE"]
    rows = []
    for version, a in alerts.groupby("version"):
        for pattern in PATTERNS + ["ALL"]:
            ap = a if pattern == "ALL" else a[a["pattern"] == pattern]
            pp = pos if pattern == "ALL" else pos[pos["pattern"] == pattern]
            tp_alerts = ap.merge(pp[K], on=K).shape[0]
            rows.append(dict(
                version=version, pattern=pattern, alerts=len(ap), true_pos=tp_alerts,
                false_pos=len(ap) - tp_alerts, labeled_cases=len(pp),
                precision=round(tp_alerts / len(ap), 3) if len(ap) else None,
                recall=round(tp_alerts / len(pp), 3) if len(pp) else None))
    return pd.DataFrame(rows)


def regression_diff(alerts, labels):
    v1 = alerts[alerts["version"] == "v1"][K + ["alert_id", "score"]]
    v2 = alerts[alerts["version"] == "v2"][K + ["alert_id", "score"]]
    pos = labels[labels["label"] == "POSITIVE"][K + ["difficulty"]]
    ben = labels[labels["label"] == "BENIGN_LOOKALIKE"][K + ["note"]]
    both = v1.merge(v2, on=K, suffixes=("_v1", "_v2"))
    dropped = v1.merge(v2[K], on=K, how="left", indicator=True).query("_merge=='left_only'")
    added = v2.merge(v1[K], on=K, how="left", indicator=True).query("_merge=='left_only'")
    dropped = dropped.drop(columns="_merge")
    added = added.drop(columns="_merge")
    dropped_pos = dropped.merge(pos, on=K)
    dropped_fp = dropped.merge(pos[K], on=K, how="left", indicator=True).query("_merge=='left_only'")
    dropped_fp = dropped_fp.merge(ben, on=K, how="left")
    return both, dropped_pos, dropped_fp, added


def missed_cases(alerts, labels, version):
    a = alerts[alerts["version"] == version][K]
    pos = labels[labels["label"] == "POSITIVE"]
    m = pos.merge(a, on=K, how="left", indicator=True)
    return m[m["_merge"] == "left_only"].drop(columns="_merge")


def main():
    con = sqlite3.connect(DB_PATH)
    alerts, labels = load(con)
    con.close()
    m = metrics(alerts, labels)
    both, dropped_pos, dropped_fp, added = regression_diff(alerts, labels)
    missed_v2 = missed_cases(alerts, labels, "v2")
    n1 = (alerts["version"] == "v1").sum()
    n2 = (alerts["version"] == "v2").sum()

    REPORT_DIR.mkdir(exist_ok=True)
    m.to_csv(REPORT_DIR / "metrics_by_pattern.csv", index=False)
    md = ["# Alert validation and tuning results", "",
          "## Precision / recall by pattern and threshold version", "",
          m.to_markdown(index=False), "",
          "## v1 -> v2 regression diff", "",
          f"- Total alerts: **{n1} -> {n2}**",
          f"- Alerts in both versions: {len(both)}",
          f"- Removed by tuning: {len(dropped_pos) + len(dropped_fp)} "
          f"({len(dropped_fp)} false positives suppressed, "
          f"{len(dropped_pos)} true positives lost)",
          f"- New in v2: {len(added)}", "",
          "### Missed by v2 (recall trade-off)", ""]
    md.append(missed_v2[["pattern", "account_id", "symbol", "trade_date", "difficulty"]]
              .to_markdown(index=False) if len(missed_v2) else "None")
    md += ["", "### False positives still present in v2", ""]
    v2 = alerts[alerts["version"] == "v2"]
    pos = labels[labels["label"] == "POSITIVE"]
    fp2 = v2.merge(pos[K], on=K, how="left", indicator=True).query("_merge=='left_only'")
    fp2 = fp2.merge(labels[labels["label"] == "BENIGN_LOOKALIKE"][K + ["note"]], on=K, how="left")
    md.append(fp2[["pattern", "account_id", "symbol", "trade_date", "score", "note"]]
              .fillna("unlabeled (background noise)").to_markdown(index=False)
              if len(fp2) else "None")
    (REPORT_DIR / "alert_validation_report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
