"""
04_capture_rate.py
Wind capture rate for Finland: price earned by wind relative to the average price.

    capture rate = wind-weighted average price / time-average price

Input : data/processed/fi_dayahead_clean.csv, data/processed/fi_wind_hourly_entsoe.csv
Output: results/tables/capture_rate_by_window.csv
        results/tables/capture_rate_monthly.csv
        results/tables/price_by_wind_quintile.csv

Method notes (own assumptions, document in the model):
  - Join on hourly UTC timestamps; hours with a wind gap are dropped from BOTH series.
  - Fleet-wide wind output is used as a proxy for a single park's profile (simplification).
  - "curtailed" variant: the park switches off at negative prices (own definition).
"""
import pandas as pd

from common import (LOCAL_TZ, TABLES, WINDOWS, load_prices_hourly, load_wind_hourly,
                    local_month, window_mask)


def capture_stats(d: pd.DataFrame) -> dict:
    w = d["wind_mw"].clip(lower=0)
    avg_price = d["price"].mean()
    wind_price = (d["price"] * w).sum() / w.sum()

    run = d["price"] >= 0                       # hours in which a curtailing park produces
    curtailed_price = (d["price"][run] * w[run]).sum() / w[run].sum()
    return {
        "hours": len(d),
        "avg_price": avg_price,
        "wind_weighted_price": wind_price,
        "capture_rate_pct": 100 * wind_price / avg_price,
        "capture_rate_curtailed_pct": 100 * curtailed_price / avg_price,
        "energy_in_negative_hours_pct": 100 * w[~run].sum() / w.sum(),
        "avg_wind_mw": d["wind_mw"].mean(),
        "corr_wind_price": d["wind_mw"].corr(d["price"]),
    }


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    d = load_prices_hourly().join(load_wind_hourly(), how="inner").dropna()
    loc_idx = d.index.tz_convert(LOCAL_TZ)
    print(f"Joined hours: {len(d)} | {d.index.min()} -> {d.index.max()}")

    # --- By window -------------------------------------------------------------------
    rows = {name: capture_stats(d[window_mask(loc_idx, s, e)]) for name, (s, e) in WINDOWS.items()}
    by_window = pd.DataFrame(rows).T
    by_window.index.name = "window"
    by_window.round(2).to_csv(TABLES / "capture_rate_by_window.csv")
    print("\n=== Capture rate by window ===")
    print(by_window.round(1).T.to_string())

    # Window sensitivity: same months in different years (avoids the seasonal bias of YTD)
    print("\n=== Jan-Sep only, per year (like-for-like) ===")
    for y in (2023, 2024, 2025, 2026):
        sub = d[window_mask(loc_idx, f"{y}-01-01", f"{y}-10-01")]
        print(f"  {y}: capture rate {capture_stats(sub)['capture_rate_pct']:.1f} %")

    # --- Monthly -----------------------------------------------------------------------
    months = local_month(d.index)
    monthly = pd.DataFrame({m: capture_stats(g) for m, g in d.groupby(months)}).T
    monthly = monthly[(monthly.index >= "2023-01") & (monthly.index <= "2026-09")]
    monthly.index.name = "month"
    monthly.round(2).to_csv(TABLES / "capture_rate_monthly.csv")

    # --- Cannibalisation evidence: price by wind-output quintile (last 12 months) ----------
    last12 = d[window_mask(loc_idx, *WINDOWS["Last 12m (Oct25-Sep26)"])].copy()
    last12["wind_quintile"] = pd.qcut(last12["wind_mw"], 5, labels=["Q1 (low)", "Q2", "Q3", "Q4", "Q5 (high)"])
    q = last12.groupby("wind_quintile", observed=True).agg(
        avg_wind_mw=("wind_mw", "mean"),
        avg_price=("price", "mean"),
        share_negative_hours_pct=("price", lambda x: 100 * (x < 0).mean()),
    )
    q.round(2).to_csv(TABLES / "price_by_wind_quintile.csv")
    print("\n=== Price by wind quintile, last 12 months ===")
    print(q.round(1).to_string())
    print(f"\nSaved tables to {TABLES}")


if __name__ == "__main__":
    main()