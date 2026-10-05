"""Build a pinned historical experiment, never a live operational forecast."""

import csv
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forecast_lab.core import (
    HORIZONS,
    LABELS,
    MODELS,
    backtest,
    calibrated_radius,
    interval,
    metrics,
    predict,
    shift,
    validate,
)

SOURCE = "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/04/Monthly-AE-Time-Series-March-2026-F5ldj2.xls"
SPLITS = {
    "selection": ["2021-01", "2022-12"],
    "calibration": ["2023-03", "2024-02"],
    "test": ["2024-05", "2025-12"],
}


def extract(path):
    b = xlrd.open_workbook(path)
    s = b.sheet_by_name("Activity")
    if s.cell_value(13, 2) != "Type 1 Departments - Major A&E":
        raise ValueError("Source schema changed")
    rows = []
    for i in range(14, s.nrows):
        stamp = s.cell(i, 1)
        if stamp.ctype != xlrd.XL_CELL_DATE:
            continue
        d = xlrd.xldate_as_datetime(stamp.value, b.datemode)
        values = [float(s.cell_value(i, c)) for c in (2, 3, 4, 5)]
        if not math.isclose(sum(values[:3]), values[3], abs_tol=0.01):
            raise ValueError(f"Attendance components fail to reconcile at {i}")
        rows.append({"month": d.strftime("%Y-%m"), "attendances": values[0]})
    validate(rows)
    if (len(rows), rows[0]["month"], rows[-1]["month"]) != (188, "2010-08", "2026-03"):
        raise ValueError("Unexpected source window")
    return rows


def write_csv(path, rows):
    stream = io.StringIO(newline="")
    w = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path.write_text(stream.getvalue())


def build():
    path = ROOT / "data/source/monthly-ae-march-2026.xls"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = json.loads((ROOT / "data/source/manifest.json").read_text())["sha256"]
    if digest != expected:
        raise ValueError("Source SHA-256 mismatch")
    rows = extract(path)
    selection = backtest(rows, *SPLITS["selection"])
    scores = {m: metrics([r for r in selection if r["model"] == m]) for m in MODELS}
    winner = min(MODELS, key=lambda m: scores[m]["mae"])
    calibration = backtest(rows, *SPLITS["calibration"], models=(winner,))
    radii = {h: calibrated_radius(calibration, h) for h in HORIZONS}
    # Three-month buffer ensures all calibration targets predate first test origin.
    assert max(r["month"] for r in selection) <= SPLITS["calibration"][0]
    assert max(r["month"] for r in calibration) <= SPLITS["test"][0]
    test = backtest(rows, *SPLITS["test"])
    for r in test:
        if r["model"] == winner:
            r["lower"], r["upper"] = interval(r["predicted"], r["month"], radii[r["horizon"]])
            r["covered"] = r["lower"] <= r["actual"] <= r["upper"]
    report_metrics = []
    for h in HORIZONS:
        for m in MODELS:
            group = [r for r in test if r["horizon"] == h and r["model"] == m]
            report_metrics.append(
                dict(
                    model=m,
                    horizon=h,
                    **metrics(group),
                    coverage=sum(r.get("covered", False) for r in group) / len(group)
                    if m == winner
                    else None,
                )
            )
    projection = []
    for h in HORIZONS:
        target = shift(rows[-1]["month"], h)
        point = predict(rows, h, winner)
        low, high = interval(point, target, radii[h])
        projection.append(
            {"month": target, "horizon": h, "predicted": point, "lower": low, "upper": high}
        )
    payload = {
        "title": "Hospital Demand Lab",
        "source_url": SOURCE,
        "source_sha256": digest,
        "publication_date": "2026-04-16",
        "snapshot_end": "2026-03",
        "target": "England Type 1 A&E attendances",
        "splits": SPLITS,
        "models": LABELS,
        "selected": winner,
        "selection_scores": scores,
        "calibration_n": 12,
        "nominal_coverage": 0.9,
        "radii": radii,
        "history": rows,
        "test": test,
        "metrics": report_metrics,
        "projection": projection,
    }
    (ROOT / "docs/report.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    write_csv(ROOT / "data/attendance.csv", rows)
    write_csv(ROOT / "docs/attendance.csv", rows)
    # Union schema avoids losing interval fields in the other models' rows.
    fields = [
        "origin",
        "month",
        "horizon",
        "model",
        "actual",
        "predicted",
        "error",
        "lower",
        "upper",
        "covered",
    ]
    write_csv(ROOT / "docs/backtest.csv", [{k: r.get(k, "") for k in fields} for r in test])
    (ROOT / "data/results.json").write_text(
        json.dumps({"selected": winner, "metrics": report_metrics, "selection": scores}, indent=2)
        + "\n"
    )
    print(json.dumps({"selected": winner, "metrics": report_metrics}, indent=2))


if __name__ == "__main__":
    build()
