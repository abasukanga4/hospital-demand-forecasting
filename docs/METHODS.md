# Methods and limitations

## Question and unit

Can simple calendar-aware models anticipate England's monthly Type 1 (major A&E) attendances one and three months ahead? This is an aggregate analytics experiment, not a patient-risk model or a hospital staffing tool.

The pinned NHS England workbook was published on 16 April 2026 and ends in March 2026. Its **Activity** sheet provides 188 observations from August 2010. Each forecast predicts a monthly attendance total. Models work on daily rates (monthly total divided by calendar days), then convert predictions back to totals. February and leap years therefore receive the correct exposure.

The workbook is preserved with a SHA-256 manifest. Extraction checks the expected header, all 188 ordered months, positive finite values and reconciliation of Type 1 + Type 2 + Type 3 to total activity. Early apportioned estimates can be fractional; the extractor intentionally does not coerce them to integers.

## Fixed candidates

- **Seasonal baseline:** use the daily rate from the same calendar month in the preceding year.
- **Recent growth + seasonality:** multiply that baseline by the median of the latest three available year-on-year daily-rate ratios. The window and aggregation rule are fixed.
- **Seasonal trend regression:** least-squares regression on the most recent 36 monthly daily rates, with an intercept, a linear time trend and eleven month indicators. No hyperparameter search on the test period. Negative forecasts are clipped to zero.

These methods are intentionally interpretable. The regression uses NumPy's least-squares solver rather than a complex framework.

## Chronology

An origin is the last observed month passed to a model. Every prediction receives only rows at or before that origin. Models refit when the origin advances; model-selection and interval-calibration decisions remain frozen.

| Phase | Origins | Last target | Purpose |
|---|---|---|---|
| Selection | Jan 2021–Dec 2022; 24 origins | Mar 2023 | Select lowest pooled MAE over horizons 1 and 3 |
| Calibration | Mar 2023–Feb 2024; 12 origins | May 2024 | Estimate selected model's error bands |
| Final test | May 2024–Dec 2025; 20 origins | Mar 2026 | Report each horizon separately |

The gaps ensure all earlier phase targets are observed before the next phase begins. Months can occur as targets at different horizons, so 40 selected-model predictions do **not** mean 40 independent months. The selection period contains pandemic recovery; it is not assumed representative of later demand.

## Scoring and result

MAE is the average absolute error in attendance counts. RMSE penalises larger errors. WAPE is sum(abs(error)) / sum(actual), not an average of monthly percentage errors. Bias is forecast minus actual. Metrics are exported per model and horizon.

The seasonal baseline wins the earlier selection phase. At one month, its final-test MAE is **31,752** attendances, WAPE **2.25%**, and bias **−20,786**. At three months, MAE is **31,339** and WAPE **2.22%**. The trend regression's corresponding MAEs are **21,519** and **20,425**. This later advantage is shown transparently; it does not retroactively make regression the selected model. A subsequent experiment could evaluate a predeclared periodic reselection policy on a *new* test period. This result alone does not establish which model will perform best in future.

## Empirical uncertainty

For each horizon, compute absolute daily-rate errors on the 12 calibration origins. The radius is the ordered value at rank `ceil((n+1) × 0.90)`, with one-based indexing. This is the maximum for n=12. Multiply the radius by target-month days and form a symmetric band about the prediction; clip the lower bound at zero.

The selected model covers **20/20** final targets at each horizon. Coverage is reported alongside band width, because a wide band can achieve high coverage while adding little operational value. The errors are temporally dependent and the data distribution changes. The nominal 90% label is **not** a distribution-free coverage guarantee for this series. The small calibration set makes coverage assessment unstable. We do not fit intervals to the test errors or recalibrate after inspecting test results.

## Vintage and collection caveats

- This is a retrospective rolling-origin evaluation using a single revised vintage, not a true historical as-of simulation. Publication delays, missing provisional releases and revisions are not modelled. Source months become available later than their month-end in real life.
- November 2010–May 2015 values were estimated by apportioning published weekly data. The source begins earlier, in August 2010.
- From August 2020, activity includes booked appointments. This definition change and the pandemic complicate comparison with earlier periods.
- The Activity sheet includes all providers. The Performance sheet's trial-trust exclusions for May 2019–May 2023 are a different series and are not substituted here.
- The source notes Type 3 cyber-attack-related shortfalls between August 2022 and February 2023. The target here is Type 1, not all-type attendance.
- National variation cannot infer individual hospital capacity, staffing or clinical outcomes. Population, holidays, weather, service changes and provider-level differences are not modelled.
- The April and June 2026 projections are archived snapshot-boundary illustrations. They are neither current predictions nor additional held-out tests.

## References

- [NHS England source workbook, April 2026 publication](https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/04/Monthly-AE-Time-Series-March-2026-F5ldj2.xls), including its Notes sheet.
- Hyndman & Athanasopoulos, [time-series cross-validation](https://otexts.com/fpp3/tscv.html) and [simple forecasting methods](https://otexts.com/fpp3/simple-methods.html), *Forecasting: Principles and Practice*, 3rd ed.

The project implements its own compact evaluation code; the book provides methodological context, not a claim that this experiment meets an operational NHS standard.
