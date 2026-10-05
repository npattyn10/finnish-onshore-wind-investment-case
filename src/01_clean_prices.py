"""
01_clean_prices.py
Load ENTSO-E day-ahead prices (bidding zone FI, transparency platform 12.1.D),
build a clean UTC-indexed series and run basic data-quality checks.

Input : data/raw/GUI_ENERGY_PRICES_*.xlsx   (one file per year, as downloaded)
Output: data/processed/fi_dayahead_clean.csv

Columns: ts_utc, ts_fi, price_eur_mwh, res_min, native_15min
Requires: pip install pandas openpyxl
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
LOCAL_TZ = "Europe/Helsinki"

# Day-ahead market moved to 15-min products on 1 Oct 2025 (SDAC go-live). (https://energy.ec.europa.eu/news/eu-electricity-trading-day-ahead-markets-becomes-more-dynamic-2025-10-01_en)
FIRST_NATIVE_15MIN = pd.Timestamp("2025-10-01", tz=LOCAL_TZ)


def strip_tz_tag(label: str) -> str:
    """ENTSO-E adds '(CET)'/'(CEST)' to labels around DST changes; remove it."""
    return re.sub(r"\s*\((CET|CEST)\)", "", label)


def parse_label_start(label: str) -> pd.Timestamp:
    """Start of an interval label such as '01/01/2023 00:00:00 - 01/01/2023 01:00:00'."""
    start = strip_tz_tag(label.split(" - ")[0])
    return pd.to_datetime(start, format="%d/%m/%Y %H:%M:%S")


def detect_resolution_min(label: str) -> int:
    """Resolution in minutes from the first interval label of a file."""
    start, end = (strip_tz_tag(s) for s in label.split(" - "))
    fmt = "%d/%m/%Y %H:%M:%S"
    delta = pd.to_datetime(end, format=fmt) - pd.to_datetime(start, format=fmt)
    return int(delta.total_seconds() // 60)


def file_start_utc(path: Path) -> pd.Timestamp:
    """File names encode the UTC start, e.g. ..._202212312300-202312312300.xlsx"""
    tag = re.search(r"_(\d{12})-\d{12}", path.name).group(1)
    return pd.to_datetime(tag, format="%Y%m%d%H%M").tz_localize("UTC")


def load_file(path: Path) -> pd.DataFrame:
    # Rows 0-6 are report headers; data starts in row 7.
    df = pd.read_excel(path, header=None, skiprows=7, names=["label", "price_eur_mwh"])
    df["price_eur_mwh"] = pd.to_numeric(df["price_eur_mwh"], errors="raise")
    res = detect_resolution_min(df["label"].iloc[0])
    # Build the timestamp from the file's UTC start + fixed step. This avoids all
    # DST ambiguity in the CET/CEST labels (25-hour / 23-hour days).
    df["ts_utc"] = pd.date_range(file_start_utc(path), periods=len(df), freq=f"{res}min")
    df["res_min"] = res
    return df


def main() -> None:
    files = sorted(RAW.glob("GUI_ENERGY_PRICES_*.xlsx"))
    assert files, f"No ENTSO-E files found in {RAW}"
    df = pd.concat([load_file(f) for f in files], ignore_index=True)

    # --- Checks -------------------------------------------------------------
    # 1. No missing values, no duplicate timestamps, strictly increasing
    assert df["price_eur_mwh"].notna().all(), "missing prices"
    assert not df["ts_utc"].duplicated().any(), "duplicate timestamps"
    assert df["ts_utc"].is_monotonic_increasing, "files not contiguous / out of order"

    # 2. Cross-check: UTC index converted to CET/CEST must equal the ENTSO-E labels
    label_start = df["label"].map(parse_label_start)
    utc_as_cet = df["ts_utc"].dt.tz_convert("Europe/Berlin").dt.tz_localize(None)
    n_bad = int((label_start != utc_as_cet).sum())
    assert n_bad == 0, f"{n_bad} rows where UTC index and ENTSO-E label disagree"

    # 3. Gaps: step between rows must equal the resolution of the row's file
    step = df["ts_utc"].diff().dt.total_seconds().div(60)
    jump = (step != df["res_min"]) & step.notna()
    # allowed: the first row of a file with a different resolution than the previous one
    res_change = df["res_min"] != df["res_min"].shift()
    assert not (jump & ~res_change).any(), "gaps between rows"

    # --- Local time + native-15-min flag -------------------------------------
    df["ts_fi"] = df["ts_utc"].dt.tz_convert(LOCAL_TZ)
    df["native_15min"] = df["ts_fi"] >= FIRST_NATIVE_15MIN

    # 4. Expected row count per file/year (DST-aware), printed for the log
    print(f"Rows: {len(df)} | {df['ts_fi'].min()} -> {df['ts_fi'].max()}")
    print(df.groupby(df["ts_fi"].dt.year).size().rename("rows per local year").to_string())

    # 5. Test the 15-min assumption: in 'fake' 15-min data, all four quarter-hours
    #    of an hour carry the same price. Share of such hours per month:
    q = df[df["res_min"] == 15].copy()
    q["hour"] = q["ts_utc"].dt.floor("h")
    per_hour = q.groupby("hour")["price_eur_mwh"].agg(["nunique", "count"])
    per_hour = per_hour[per_hour["count"] == 4]
    month = per_hour.index.tz_convert(LOCAL_TZ).strftime("%Y-%m")
    share_identical = (per_hour["nunique"] == 1).groupby(month).mean().round(3)
    print("\nShare of hours with 4 identical quarter-hour prices (should drop from 1.0 to ~0 at Oct 2025):")
    print(share_identical.to_string())

    # --- Save -----------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["ts_utc", "ts_fi", "price_eur_mwh", "res_min", "native_15min"]
    df[cols].to_csv(OUT / "fi_dayahead_clean.csv", index=False)
    print(f"\nSaved {OUT / 'fi_dayahead_clean.csv'}")


if __name__ == "__main__":
    main()