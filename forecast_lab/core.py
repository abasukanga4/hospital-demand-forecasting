"""Calendar-aware baselines, regression and chronological evaluation."""

from calendar import monthrange
from datetime import date
from math import ceil, isfinite, sqrt

import numpy as np

MODELS = ("seasonal_naive", "recent_growth", "seasonal_trend")
HORIZONS = (1, 3)
LABELS = {
    "seasonal_naive": "Seasonal baseline",
    "recent_growth": "Recent growth + seasonality",
    "seasonal_trend": "Seasonal trend regression",
}


def shift(month, offset):
    d = date.fromisoformat(month + "-01")
    y, m = divmod(d.year * 12 + d.month - 1 + offset, 12)
    return f"{y:04d}-{m + 1:02d}"


def days(month):
    y, m = map(int, month.split("-"))
    return monthrange(y, m)[1]


def validate(rows):
    if len(rows) < 60:
        raise ValueError("At least 60 monthly observations required")
    for i, row in enumerate(rows):
        if not isfinite(row["attendances"]) or row["attendances"] <= 0:
            raise ValueError("Attendance must be finite and positive")
        if i and row["month"] != shift(rows[i - 1]["month"], 1):
            raise ValueError("Months must be unique, ordered and contiguous")


def features(t, month):
    return [1.0, t / 12.0] + [float(int(month[-2:]) == m) for m in range(2, 13)]


def predict(history, horizon, model):
    """Accept ONLY information available through an origin month; output total."""
    if horizon not in HORIZONS:
        raise ValueError("Supported horizons are 1 and 3 months")
    if model not in MODELS:
        raise ValueError("Unknown model")
    if len(history) < 36:
        raise ValueError("At least 36 months required")
    rates = np.array([r["attendances"] / days(r["month"]) for r in history])
    target = shift(history[-1]["month"], horizon)
    seasonal = rates[horizon - 13]
    if model == "seasonal_naive":
        rate = seasonal
    elif model == "recent_growth":
        # Fixed rule: median of latest three year-on-year daily-rate ratios.
        rate = seasonal * float(np.median(rates[-3:] / rates[-15:-12]))
    else:
        # Fixed 36-month window; trend plus eleven month indicators and intercept.
        x = np.array([features(i, r["month"]) for i, r in enumerate(history[-36:])])
        beta = np.linalg.lstsq(x, rates[-36:], rcond=None)[0]
        rate = float(np.array(features(35 + horizon, target)) @ beta)
    return max(0.0, float(rate) * days(target))


def backtest(rows, start, end, models=MODELS):
    results = []
    for i, origin in enumerate(rows):
        if not start <= origin["month"] <= end:
            continue
        for h in HORIZONS:
            if i + h >= len(rows):
                raise ValueError("Evaluation target not observed")
            actual = rows[i + h]
            for model in models:
                forecast = predict(rows[: i + 1], h, model)
                results.append(
                    {
                        "origin": origin["month"],
                        "month": actual["month"],
                        "horizon": h,
                        "model": model,
                        "actual": actual["attendances"],
                        "predicted": forecast,
                        "error": forecast - actual["attendances"],
                    }
                )
    return results


def metrics(results):
    if not results:
        raise ValueError("No observations")
    errors = np.array([r["error"] for r in results])
    actual = sum(r["actual"] for r in results)
    return {
        "n": len(results),
        "mae": float(np.abs(errors).mean()),
        "rmse": sqrt(float((errors**2).mean())),
        "wape": float(np.abs(errors).sum()) / actual,
        "bias": float(errors.mean()),
    }


def calibrated_radius(results, horizon, coverage=0.9):
    scores = sorted(abs(r["error"]) / days(r["month"]) for r in results if r["horizon"] == horizon)
    k = ceil((len(scores) + 1) * coverage)
    if not scores or not 1 <= k <= len(scores):
        raise ValueError("Insufficient calibration observations for requested coverage")
    return scores[k - 1]


def interval(point, target, radius):
    width = radius * days(target)
    return max(0.0, point - width), point + width
