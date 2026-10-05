"""
common.py
Shared paths, loaders and analysis windows for the analysis scripts (03, 04, ...).
Not run on its own.

Convention: join and compute in UTC, slice and report in Helsinki time.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TABLES = ROOT / "results" / "tables"
LOCAL_TZ = "Europe/Helsinki"

# Analysis windows in Helsinki local time, [start, end). Own definition.
# 2026 is year-to-date (day-ahead prices for 1 Oct 2026 exist but wind data does not).
WINDOWS = {
    "2023": ("2023-01-01", "2024-01-01"),
    "2024": ("2024-01-01", "2025-01-01"),
    "2025": ("2025-01-01", "2026-01-01"),
    "2026 Jan-Sep": ("2026-01-01", "2026-10-01"),
    "Last 12m (Oct25-Sep26)": ("2025-10-01", "2026-10-01"),
}


def window_mask(index: pd.DatetimeIndex, start: str, end: str) -> pd.Series:
    """Boolean mask for [start, end) in Helsinki local time; index must be tz-aware."""
    s = pd.Timestamp(start, tz=LOCAL_TZ)
    e = pd.Timestamp(end, tz=LOCAL_TZ)
    return (index >= s) & (index < e)


def local_month(index: pd.DatetimeIndex) -> pd.Index:
    return index.tz_convert(LOCAL_TZ).strftime("%Y-%m")


def load_prices_hourly() -> pd.DataFrame:
    """Hourly day-ahead price (EUR/MWh), index = hour start in UTC.
    Quarter-hour prices (from Oct 2025) are averaged to the hour."""
    df = pd.read_csv(PROC / "fi_dayahead_clean.csv",
                     usecols=["ts_utc", "price_eur_mwh"], parse_dates=["ts_utc"])
    df["hour"] = df["ts_utc"].dt.floor("h")
    h = df.groupby("hour")["price_eur_mwh"].agg(price="mean", n="size")
    assert h["n"].isin([1, 4]).all(), "incomplete hours in price data"
    return h[["price"]]


def load_wind_hourly() -> pd.DataFrame:
    """Hourly onshore wind generation (MW, mean per hour) from ENTSO-E Actual Generation per Production Type, FI. Created by 02b_load_wind_entsoe.py., index = hour start in UTC. NaN = gap."""
    w = pd.read_csv(PROC / "fi_wind_hourly_entsoe.csv", parse_dates=["ts_utc"]).set_index("ts_utc")
    return w[["wind_mw"]]