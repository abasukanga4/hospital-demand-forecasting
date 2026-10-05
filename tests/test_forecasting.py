import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from forecast_lab.core import (
    MODELS,
    backtest,
    calibrated_radius,
    days,
    interval,
    metrics,
    predict,
    shift,
    validate,
)
from scripts.build_report import SPLITS, extract

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def series():
    return [
        {
            "month": shift("2015-01", i),
            "attendances": (1000 + (i % 12) * 50) * days(shift("2015-01", i)),
        }
        for i in range(120)
    ]


@pytest.mark.parametrize(
    "month,offset,want",
    [("2024-12", 1, "2025-01"), ("2024-01", -1, "2023-12"), ("2024-03", 12, "2025-03")],
)
def test_month_arithmetic(month, offset, want):
    assert shift(month, offset) == want


def test_leap_day():
    assert days("2024-02") == 29 and days("2025-02") == 28


@pytest.mark.parametrize("model", MODELS)
def test_recovers_exact_calendar_seasonality(series, model):
    p = predict(series, 1, model)
    assert p == pytest.approx(31000, abs=1e-7)


def test_seasonal_baseline_adjusts_leap_year():
    rows = [
        {"month": shift("2020-02", i), "attendances": 100 * days(shift("2020-02", i))}
        for i in range(48)
    ]
    assert predict(rows, 1, "seasonal_naive") == 2900


@pytest.mark.parametrize("model", MODELS)
def test_target_mutations_cannot_change_forecast(series, model):
    expected = backtest(series, "2021-01", "2021-01", models=(model,))
    changed = deepcopy(series)
    for row in changed:
        if row["month"] > "2021-01":
            row["attendances"] *= 100
    actual = backtest(changed, "2021-01", "2021-01", models=(model,))
    assert [r["predicted"] for r in expected] == [r["predicted"] for r in actual]
    assert expected[0]["actual"] != actual[0]["actual"]


@pytest.mark.parametrize("defect", ["duplicate", "gap", "nan", "negative"])
def test_bad_series_rejected(series, defect):
    if defect == "duplicate":
        series[20]["month"] = series[19]["month"]
    if defect == "gap":
        series.pop(20)
    if defect == "nan":
        series[20]["attendances"] = np.nan
    if defect == "negative":
        series[20]["attendances"] = -1
    with pytest.raises(ValueError):
        validate(series)


def test_metrics_weight_totals_not_mean_percent():
    m = metrics([{"error": 10, "actual": 10}, {"error": -10, "actual": 90}])
    assert m["wape"] == 0.2 and m["mae"] == 10 and m["bias"] == 0


def test_finite_sample_radius_uses_order_statistic():
    rows = [{"error": i * 31, "month": "2024-01", "horizon": 1} for i in range(1, 13)]
    assert calibrated_radius(rows, 1) == 12
    with pytest.raises(ValueError):
        calibrated_radius(rows[:2], 1)


def test_interval_nonnegative_and_calendar_scaled():
    assert interval(100, "2024-02", 10) == (0, 390)


def test_source_hash_schema_and_reconciliation():
    path = ROOT / "data/source/monthly-ae-march-2026.xls"
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == json.loads((path.parent / "manifest.json").read_text())["sha256"]
    )
    rows = extract(path)
    assert len(rows) == 188
    assert rows[-1]["month"] == "2026-03"


def test_phase_targets_available_before_next_phase_origin():
    assert shift(SPLITS["selection"][1], 3) <= SPLITS["calibration"][0]
    assert shift(SPLITS["calibration"][1], 3) <= SPLITS["test"][0]


def test_report_selection_and_coverage_reconcile():
    r = json.loads((ROOT / "docs/report.json").read_text())
    assert r["selected"] == min(
        r["selection_scores"], key=lambda m: r["selection_scores"][m]["mae"]
    )
    for m in r["metrics"]:
        group = [x for x in r["test"] if x["model"] == m["model"] and x["horizon"] == m["horizon"]]
        assert len(group) == 20
        assert metrics(group)["mae"] == pytest.approx(m["mae"])
        if m["model"] == r["selected"]:
            assert m["coverage"] == sum(x["lower"] <= x["actual"] <= x["upper"] for x in group) / 20


def test_unsupported_horizon_or_model(series):
    with pytest.raises(ValueError):
        predict(series, 12, "seasonal_naive")
    with pytest.raises(ValueError):
        predict(series, 1, "made_up")
