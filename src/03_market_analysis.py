"""
03_market_analysis.py
Descriptive statistics of Finnish day-ahead prices on an hourly basis.

Input : data/processed/fi_dayahead_clean.csv   (from 01_clean_prices.py)
Output: results/tables/market_stats_by_window.csv
        results/tables/market_stats_monthly.csv

Why hourly: until Sep 2025 the "15-min" prices are repeated hourly values, so only
an hourly basis is comparable across the whole period.
"""
import pandas as pd

from common import (LOCAL_TZ, PROC, TABLES, WINDOWS, load_prices_hourly,
                    local_month, window_mask)


def price_stats(p: pd.Series) -> dict:
    return {
        "hours": len(p),
        "mean": p.mean(),
        "median": p.median(),
        "std": p.std(),
        "p5": p.quantile(0.05),
        "p95": p.quantile(0.95),
        "min": p.min(),
        "max": p.max(),
        "hours_negative": int((p < 0).sum()),
        "share_negative_pct": 100 * (p < 0).mean(),
        "hours_zero_or_neg": int((p <= 0).sum()),
    }


def avg_daily_spread(p: pd.Series) -> float:
    """Mean of (daily max - daily min) of hourly prices, local days with >= 23 hours.
    Indicator for battery arbitrage potential (upper bound, ignores losses and limits)."""
    local = p.copy()
    local.index = local.index.tz_convert(LOCAL_TZ)
    by_day = local.groupby(local.index.date)
    ok = by_day.size() >= 23
    return (by_day.max() - by_day.min())[ok].mean()


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    h = load_prices_hourly()
    p = h["price"]

    # --- By window ---------------------------------------------------------------
    rows = {}
    for name, (start, end) in WINDOWS.items():
        sub = p[window_mask(p.index.tz_convert(LOCAL_TZ), start, end)]
        r = price_stats(sub)
        r["avg_daily_spread"] = avg_daily_spread(sub)
        rows[name] = r
    by_window = pd.DataFrame(rows).T
    by_window.index.name = "window"
    by_window.round(2).to_csv(TABLES / "market_stats_by_window.csv")
    print("=== Price statistics by window (EUR/MWh, hourly) ===")
    print(by_window.round(1).T.to_string())

    # --- Monthly -------------------------------------------------------------------
    months = local_month(p.index)
    g = p.groupby(months)
    monthly = pd.DataFrame({
        "hours": g.size(),
        "mean": g.mean(),
        "median": g.median(),
        "hours_negative": g.apply(lambda x: int((x < 0).sum())),
    })
    monthly = monthly[(monthly.index >= "2023-01") & (monthly.index <= "2026-09")]
    monthly.index.name = "month"
    monthly.round(2).to_csv(TABLES / "market_stats_monthly.csv")

    # --- Outliers: to be checked against an independent source ------------------------
    print("\n=== Outliers (verify before using in the model) ===")
    loc = p.copy()
    loc.index = loc.index.tz_convert(LOCAL_TZ)
    print("Lowest 3 hours:\n", loc.nsmallest(3).round(1).to_string())
    print("Highest 3 hours:\n", loc.nlargest(3).round(1).to_string())

    # --- Intra-hour volatility in the true 15-min era ----------------------------------
    q = pd.read_csv(PROC / "fi_dayahead_clean.csv", parse_dates=["ts_utc"],
                    usecols=["ts_utc", "price_eur_mwh", "native_15min"])
    q = q[q["native_15min"]]
    q["hour"] = q["ts_utc"].dt.floor("h")
    intra = q.groupby("hour")["price_eur_mwh"].std().mean()
    print(f"\nMean intra-hour std of quarter-hour prices since 1 Oct 2025: {intra:.1f} EUR/MWh")
    print(f"Saved tables to {TABLES}")


if __name__ == "__main__":
    main()