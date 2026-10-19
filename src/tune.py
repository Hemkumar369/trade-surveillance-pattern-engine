"""Threshold sweeps: how precision and recall move as one threshold changes.

Holds every other v2 threshold fixed and sweeps one, which is how a threshold is
chosen (and defended) rather than guessed.
"""
import copy
import sqlite3

import pandas as pd

from config import DB_PATH, PARAMS, REPORT_DIR
from evaluate import K
from patterns import run_pattern, to_alerts

SWEEPS = [
    ("wash_trade", "qty_tol", [0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.25]),
    ("wash_trade", "window_s", [30, 60, 120, 180, 240, 300]),
    ("layering_spoofing", "min_orders", [3, 4, 5, 6, 7]),
    ("marking_the_close", "min_share", [0.10, 0.15, 0.18, 0.20, 0.25, 0.30, 0.35]),
]


def main():
    con = sqlite3.connect(DB_PATH)
    labels = pd.read_sql_query("SELECT * FROM gt_case_labels", con)
    rows = []
    for pattern, param, values in SWEEPS:
        pos = labels[(labels["pattern"] == pattern) & (labels["label"] == "POSITIVE")]
        for v in values:
            p = copy.deepcopy(PARAMS["v2"][pattern])
            p[param] = v
            a = to_alerts(run_pattern(con, pattern, p), pattern, "sweep")
            n = len(a)
            tp = a.merge(pos[K], on=K).shape[0] if n else 0
            rows.append(dict(pattern=pattern, parameter=param, value=v, alerts=n,
                             true_pos=tp, precision=round(tp / n, 3) if n else None,
                             recall=round(tp / len(pos), 3)))
    con.close()
    out = pd.DataFrame(rows)
    out.to_csv(REPORT_DIR / "threshold_sweep.csv", index=False)
    md = "# Threshold sensitivity (all other v2 thresholds held fixed)\n\n" + out.to_markdown(index=False) + "\n"
    (REPORT_DIR / "threshold_sweep.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
