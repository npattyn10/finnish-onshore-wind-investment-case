"""
05_wind_cf.py
Capacity factor (CF) of the Finnish wind fleet = wind generation / capacity.

Input : data/processed/fi_wind_hourly_entsoe.csv       (from 02_load_wind.py)
        data/raw/268_*.csv                      (Fingrid dataset 268, hourly, MW, UTC)
Output: results/tables/wind_cf_by_window.csv
        results/tables/wind_cf_monthly.csv
        results/tables/wind_cf_seasonal_profile.csv

Dataset 268 = "Total production capacity used in the wind power forecast".
Fingrid states it is NOT the official installed capacity (adjusted retroactively to
actual production, updated manually ~weekly). Therefore the result is a
"CF relative to the capacity used in Fingrid's wind forecast", a fleet benchmark.
It is not the yield of a new 50 MW park (new turbines are likely better - TO VERIFY).
Licence of the data: CC BY 4.0 (cite Fingrid).
"""
import pandas as pd

from common import (LOCAL_TZ, ROOT, TABLES, WINDOWS, load_wind_hourly,
                    local_month, window_mask)

DAYS_IN_MONTH = pd.Series([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
                          index=range(1, 13))


def load_capacity() -> pd.Series:
    files = sorted((ROOT / "data" / "raw").glob("268_*.csv"))
    assert len(files) == 1, f"expected exactly one 268_*.csv in data/raw, found {len(files)}"
    df = pd.read_csv(files[0], sep=";", dtype=str)
    df.columns = ["start", "end", "cap_mw"]
    assert df["start"].str.endswith("Z").all(), "timestamps are not all UTC (no 'Z' suffix)"
    df["cap_mw"] = pd.to_numeric(df["cap_mw"], errors="raise")
    df["start"] = pd.to_datetime(df["start"], utc=True)
    assert ((pd.to_datetime(df["end"], utc=True) - df["start"]) == pd.Timedelta("1h")).all(), "not hourly"
    assert not df["start"].duplicated().any(), "duplicate timestamps"
    return df.set_index("start")["cap_mw"]


def cf_stats(g: pd.DataFrame) -> dict:
    return {
        "hours": len(g),
        "avg_wind_mw": g["wind_mw"].mean(),
        "avg_capacity_mw": g["cap_mw"].mean(),
        # energy-weighted CF = total generation / total capacity-hours
        "cf_pct": 100 * g["wind_mw"].sum() / g["cap_mw"].sum(),
        "hourly_cf_median_pct": 100 * g["cf"].median(),
        "hourly_cf_p95_pct": 100 * g["cf"].quantile(0.95),
        "hourly_cf_max_pct": 100 * g["cf"].max(),
    }


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    cap = load_capacity()
    wind = load_wind_hourly()["wind_mw"]
    d = pd.concat([wind, cap], axis=1, join="inner").dropna()
    d["cf"] = d["wind_mw"] / d["cap_mw"]
    loc_idx = d.index.tz_convert(LOCAL_TZ)

    # --- Checks ------------------------------------------------------------------------
    full = pd.date_range(cap.index.min(), cap.index.max(), freq="h")
    print(f"Capacity rows: {len(cap)} | missing hours: {len(full.difference(cap.index))}")
    print(f"Joined hours: {len(d)} | wind > capacity in {(d['cf'] > 1).sum()} hours | "
          f"max hourly CF {100 * d['cf'].max():.1f} %")
    print(f"Capacity used in forecast: {cap.iloc[0]:.0f} MW (start) -> {cap.iloc[-1]:.0f} MW (end), "
          f"{100 * (cap.iloc[-1] / cap.iloc[0] - 1):.0f} % growth")

    # --- By window ---------------------------------------------------------------------
    by_window = pd.DataFrame({n: cf_stats(d[window_mask(loc_idx, s, e)])
                              for n, (s, e) in WINDOWS.items()}).T
    by_window.index.name = "window"
    by_window.round(2).to_csv(TABLES / "wind_cf_by_window.csv")
    print("\n=== Capacity factor by window ===")
    print(by_window.round(1).T.to_string())

    print("\n=== Jan-Sep only, per year (like-for-like, avoids seasonal bias) ===")
    for y in (2023, 2024, 2025, 2026):
        g = d[window_mask(loc_idx, f"{y}-01-01", f"{y}-10-01")]
        print(f"  {y}: CF {100 * g['wind_mw'].sum() / g['cap_mw'].sum():.1f} %")

    # --- Monthly series + seasonal profile ----------------------------------------------
    months = local_month(d.index)
    monthly = pd.DataFrame({m: cf_stats(g) for m, g in d.groupby(months)}).T
    monthly = monthly[(monthly.index >= "2023-01") & (monthly.index <= "2026-09")]
    monthly.index.name = "month"
    monthly.round(2).to_csv(TABLES / "wind_cf_monthly.csv")

    moy = pd.Series(monthly.index.str[5:7].astype(int), index=monthly.index)
    cf_m = (monthly["cf_pct"].astype(float).groupby(moy).mean())  # mean over available years
    n_years = moy.groupby(moy).size()
    annual_cf = (cf_m * DAYS_IN_MONTH).sum() / DAYS_IN_MONTH.sum()  # day-weighted
    profile = pd.DataFrame({
        "cf_pct": cf_m,
        "n_years": n_years,
        "index_vs_annual": cf_m / annual_cf,
        "share_of_annual_energy_pct": 100 * cf_m * DAYS_IN_MONTH / (cf_m * DAYS_IN_MONTH).sum(),
    })
    profile.index.name = "month_of_year"
    profile.round(3).to_csv(TABLES / "wind_cf_seasonal_profile.csv")
    print("\n=== Seasonal profile (mean over available years; Oct-Dec have only 3) ===")
    print(profile.round(2).to_string())
    print(f"\nAnnual fleet CF from profile (day-weighted): {annual_cf:.1f} %")
    print(f"Illustration: 50 MW x 8760 h x {annual_cf:.1f} % = {50 * 8760 * annual_cf / 100 / 1000:.0f} GWh/a "
          "(fleet benchmark, NOT a yield assessment)")
    print(f"Saved tables to {TABLES}")


if __name__ == "__main__":
    main()