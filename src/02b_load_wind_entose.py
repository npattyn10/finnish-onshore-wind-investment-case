"""
02b_load_wind_entsoe.py
Load Finnish onshore wind generation from the ENTSO-E Transparency Platform
(Actual Generation per Production Type, BZN|FI), aggregate to hourly UTC and
cross-check against the Fingrid series from 02_load_wind.py.

Input : data/raw/AGGREGATED_GENERATION_PER_TYPE_GENERATION_*.csv   (long format)
        data/processed/fi_wind_hourly.csv                          (optional, for the cross-check)
Output: data/processed/fi_wind_hourly_entsoe.csv        columns: ts_utc, wind_mw
        results/tables/wind_crosscheck_monthly.csv

Why this script exists: the Fingrid series (dataset 75) contains long stretches of frozen
(identical) values between June and September 2023; the ENTSO-E series does not.
See the printed cross-check. ENTSO-E states that its near-real-time data are partly measured,
partly planning/extrapolated data and are not updated afterwards. Both sources are probably
not independent (Fingrid is the Finnish TSO) - not verified.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from common import PROC, ROOT, TABLES

RAW = ROOT / "data" / "raw"


def load_entsoe_wind() -> pd.Series:
    files = sorted(RAW.glob("AGGREGATED_GENERATION_PER_TYPE_GENERATION_*.csv"))
    assert files, f"no ENTSO-E generation files in {RAW}"
    parts = []
    for f in files:
        df = pd.read_csv(f, dtype=str)
        df.columns = ["mtu", "area", "ptype", "mw"]
        assert (df["area"] == "BZN|FI").all(), "unexpected bidding zone"
        parts.append(df[df["ptype"].str.contains("Wind", na=False)])
    w = pd.concat(parts, ignore_index=True)

    # Offshore is 'n/e' (does not exist) in Finland -> must contain no numbers
    off = pd.to_numeric(w.loc[w["ptype"] == "Wind Offshore", "mw"], errors="coerce")
    assert off.isna().all(), "Offshore wind has numeric values - check the data"

    w = w[w["ptype"] == "Wind Onshore"].copy()
    w["mw"] = pd.to_numeric(w["mw"], errors="coerce")   # '-' = not yet published
    w = w.dropna(subset=["mw"])

    # Label start is in CET/CEST wall-clock time; '(CET)'/'(CEST)' marks the DST fall-back hour.
    start = w["mtu"].str.split(" - ").str[0]
    is_cest = start.str.contains(r"\(CEST\)").values
    naive = pd.to_datetime(start.str.replace(r"\s*\((CET|CEST)\)", "", regex=True),
                           format="%d/%m/%Y %H:%M:%S")
    w["ts_utc"] = naive.dt.tz_localize("Europe/Berlin", ambiguous=is_cest).dt.tz_convert("UTC")
    w = w.sort_values("ts_utc")
    assert not w["ts_utc"].duplicated().any(), "duplicate timestamps"

    # Hourly mean: 2023 is hourly (1 value), from 2024 quarter-hourly (4 values per hour)
    g = w.groupby(w["ts_utc"].dt.floor("h"))["mw"].agg(["mean", "count"])
    assert g["count"].isin([1, 4]).all(), "incomplete hours in ENTSO-E data"
    hourly = g["mean"].rename("wind_mw")
    full = pd.date_range(hourly.index.min(), hourly.index.max(), freq="h")
    print(f"ENTSO-E onshore wind: {len(hourly)} hours | {hourly.index.min()} -> {hourly.index.max()} | "
          f"missing hours: {len(full.difference(hourly.index))}")
    return hourly


def frozen_share(s: pd.Series, min_run: int = 3) -> pd.Series:
    """Share of hours (per month) inside runs of >= min_run identical consecutive values."""
    grp = (s != s.shift()).cumsum()
    flag = (s.groupby(grp).transform("size") >= min_run) & s.notna()
    return 100 * flag.groupby(flag.index.strftime("%Y-%m")).mean()


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    e = load_entsoe_wind()
    e.index.name = "ts_utc"
    e.reset_index().to_csv(PROC / "fi_wind_hourly_entsoe.csv", index=False)
    print(f"Saved {PROC / 'fi_wind_hourly_entsoe.csv'}")

    fp = PROC / "fi_wind_hourly.csv"
    if not fp.exists():
        print("fi_wind_hourly.csv not found - run 02_load_wind.py for the cross-check.")
        return
    f = pd.read_csv(fp, parse_dates=["ts_utc"]).set_index("ts_utc")["wind_mw"]

    d = pd.concat([f.rename("fingrid"), e.rename("entsoe")], axis=1, join="inner").dropna()
    diff = d["fingrid"] - d["entsoe"]
    month = d.index.strftime("%Y-%m")
    out = pd.DataFrame({
        "hours": diff.groupby(month).size(),
        "mean_fingrid": d["fingrid"].groupby(month).mean(),
        "mean_entsoe": d["entsoe"].groupby(month).mean(),
        "bias_f_minus_e": diff.groupby(month).mean(),
        "mae": diff.abs().groupby(month).mean(),
        "frozen_fingrid_pct": frozen_share(d["fingrid"]),
        "frozen_entsoe_pct": frozen_share(d["entsoe"]),
    })
    out["mae_pct_of_mean"] = 100 * out["mae"] / out["mean_entsoe"]
    out.index.name = "month"
    out.round(2).to_csv(TABLES / "wind_crosscheck_monthly.csv")

    print("\n=== Cross-check Fingrid vs ENTSO-E, hourly (months with MAE > 5 % or frozen share > 5 %) ===")
    bad = out[(out["mae_pct_of_mean"] > 5) | (out["frozen_fingrid_pct"] > 5)]
    print(bad.round(1).to_string())
    print(f"\nAll other months: median MAE {out.drop(bad.index)['mae_pct_of_mean'].median():.2f} % of mean wind")
    print(f"Saved {TABLES / 'wind_crosscheck_monthly.csv'}")


if __name__ == "__main__":
    main()