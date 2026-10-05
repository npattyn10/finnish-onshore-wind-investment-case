"""
02_load_wind.py
Load Fingrid open data set 75 (wind power generation), harmonise the mixed
time resolution and aggregate to hourly UTC.
Now used only as a cross-check; contains frozen values Jun-Sep 2023
Input : data/raw/75_*.csv             (semicolon-separated, quoted, UTC timestamps)
Output: data/processed/fi_wind_hourly.csv   columns: ts_utc, wind_mw, n_slots

Known quirks of the raw file (found in the data, not from documentation):
  - 60-min rows until 2023-06-13, 15-min rows afterwards, one 30-min row (2024-11-15)
  - the first 15-min row overlaps with the last hourly row
  - 32 rows carry a 1-2 s offset in the timestamp (e.g. 14:45:01)
  - ~0.3 % of 15-min slots are missing (mostly Jun-Nov 2024)
Unit is MW (average power per interval)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

MIN_SLOTS = 3  # an hour needs >= 3 of 4 quarter-hours, else it is set to NaN (own assumption), Sensitivity tested: capture rate (last 12m) is 61.82 % for thresholds 1–3. One hour with 0 15min intervals, 1 with 1, 9 with 2


def load_raw() -> pd.DataFrame:
    files = sorted(RAW.glob("75_*.csv"))
    assert len(files) == 1, f"expected exactly one 75_*.csv in {RAW}, found {len(files)}"
    df = pd.read_csv(files[0], sep=";", dtype=str)
    df.columns = ["start", "end", "mw"]
    df["mw"] = pd.to_numeric(df["mw"], errors="raise")
    df["start"] = pd.to_datetime(df["start"], utc=True).dt.round("min")  # removes the :01 / :02 offsets
    df["end"] = pd.to_datetime(df["end"], utc=True).dt.round("min")
    df["res"] = ((df["end"] - df["start"]).dt.total_seconds() // 60).astype(int)
    assert df["res"].isin([15, 30, 60]).all(), "unexpected interval length"
    return df


def to_15min_grid(df: pd.DataFrame) -> pd.Series:
    """Expand 30/60-min rows to 15-min slots. Where several rows cover the same
    slot, the finest resolution wins; identical-resolution duplicates are averaged."""
    parts = []
    for res, g in df.groupby("res"):
        k = res // 15
        slot = np.repeat(g["start"].values, k) + np.tile(np.arange(k) * np.timedelta64(15, "m"), len(g))
        parts.append(pd.DataFrame({"slot": pd.to_datetime(slot, utc=True),
                                   "mw": np.repeat(g["mw"].values, k), "res": res}))
    s = pd.concat(parts)
    s = s[s["res"] == s.groupby("slot")["res"].transform("min")]
    s = s.groupby("slot")["mw"].mean()
    full = pd.date_range(s.index.min(), s.index.max(), freq="15min")
    return s.reindex(full)  # missing slots become NaN


def main() -> None:
    raw = load_raw()
    slots = to_15min_grid(raw)

    # --- Checks / log ---------------------------------------------------------
    print(f"Raw rows: {len(raw)} | resolutions: {raw['res'].value_counts().to_dict()}")
    print(f"15-min slots: {len(slots)} | missing: {int(slots.isna().sum())} "
          f"({100 * slots.isna().mean():.2f} %)")
    print(f"Negative values: {int((slots < 0).sum())} (small, kept as-is; cause not verified - probably consumption of idle turbines or data correction artifacts)")

    # --- Hourly aggregation ---------------------------------------------------
    hour = slots.index.floor("h")
    hourly = slots.groupby(hour).agg(wind_mw="mean", n_slots="count")
    hourly.loc[hourly["n_slots"] < MIN_SLOTS, "wind_mw"] = np.nan
    print(f"Hours: {len(hourly)} | set to NaN (< {MIN_SLOTS} slots): {int(hourly['wind_mw'].isna().sum())}")

    OUT.mkdir(parents=True, exist_ok=True)
    hourly.index.name = "ts_utc"
    hourly.reset_index().to_csv(OUT / "fi_wind_hourly.csv", index=False)
    print(f"Saved {OUT / 'fi_wind_hourly.csv'}")


if __name__ == "__main__":
    main()