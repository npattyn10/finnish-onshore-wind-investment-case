[README.md](https://github.com/user-attachments/files/33063244/README.md)
## Finnish Onshore Wind – Independent Investment Case

**What would have to be true for a 100 MW onshore wind farm in Finland to reach FID?**

An independent, screening-level investment case combining a market data pipeline (Python), a project finance model (Excel), an investment memo and a decision deck. Built in September–October 2026.

## Key findings

- **Cannibalisation is the core market risk.** The Finnish wind capture rate fell from 72 % (2023) to 55 % (2025) as wind capacity grew by about 60 %; 62 % over Oct 2025–Sep 2026. KYOS implies 60 % for 2027–36, the lowest of all zones in its outlook.
- **The PPA price decides.** At 50 EUR/MWh the project has an NPV of −46.5 EUR m (6 % WACC). Break-even PPA price: 70.35 EUR/MWh (NPV = 0) to 73.94 EUR/MWh (10 % equity IRR), vs 29–50 EUR/MWh in public references.
- **Fully merchant does not finance under base assumptions.** DSCR-sized debt covers only 17 % of CAPEX (47 % with a PPA).
- **No single cost or financing lever closes the gap.** Lower CAPEX and a better site cut the required price to about 54–62 EUR/MWh, still above public offers.
- **A co-located battery is a separate bet.** A standalone 25 MW / 50 MWh BESS breaks even at 78 kEUR/MW/yr vs 89 today; it does not change the wind economics.

Recommendation: take FID only with a ≥ 15-year corporate PPA at about 70–74 EUR/MWh.

## Deliverables

| Item | Location |
| --- | --- |
| Decision deck (12 slides) | `docs/deck.pdf` |
| Investment memo | `docs/memo.pdf` |
| Project finance model | `model/Finnish_Onshore_Wind_Project_Finance_Model_v1_8.xlsx` |
| Market analysis scripts | `src/` |
| Result tables | `results/tables/` |

## Model structure

`Inputs → Prices → Production → Revenue → Taxes → Financing → Cashflow → Outputs`, plus a separate `BESS` sheet, `Checks` (27 integrity checks), `Sources & Checks` (validation log and AI-use log) and `Changelog`.

- Inputs in real 2026 EUR, indexed at 2 %; model runs in nominal terms, 2026–2058.
- Debt sculpted to a target DSCR on CFADS after unlevered tax (no circularity), capped at 75 % gearing.
- Every input carries a source and a status flag: verified, source-based, own assumption, to verify.

## Market analysis pipeline

Run in this order:

```
01_clean_prices.py      ENTSO-E day-ahead prices (FI), UTC index
02_load_wind.py         Fingrid wind (dataset 75), cross-check only
02b_load_wind_entsoe.py ENTSO-E wind generation, main source
03_market_analysis.py   price statistics by window and month
04_capture_rate.py      capture rate, price by wind quintile
05_wind_cf.py           fleet capacity factor, seasonal profile
```

Raw data is not included. Download day-ahead prices and actual generation per production type (bidding zone FI) from the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) and Fingrid datasets 75 and 268 from [Fingrid Open Data](https://data.fingrid.fi/) (CC BY 4.0), then place them in `data/raw/`.

## Validation and AI use

Results were checked against independent sources and hand calculations: capture rate vs KYOS (60.2 % vs 60 %), LCOE hand calculation (47.8 vs 47.9 EUR/MWh), LCOE bridge to IRENA Finland 2025, break-even plausibility (project IRR = WACC at NPV = 0), Fingrid vs ENTSO-E wind data, and full recalculation of all scenario runs.

AI (Claude, Anthropic) was used for formula auditing, source discovery, drafting the Python pipeline and automating scenario runs. All inputs were entered by the author after reading the source, and all outputs were reviewed and independently checked. Each use is logged in the model's `Sources & Checks` sheet.

## Roadmap

**v1 (October 2026) – complete.** The conclusion is robust to the simplifications below.

**v2 – planned**
- [ ] Lender case vs sponsor case: P90 generation, DSCR on P90, LLCR
- [ ] Construction financing: drawdown schedule, interest during construction, fees, DSRA
- [ ] Tax update: 18 % rate and 25-year loss carry-forward (Government proposal HE 151/2026), EUR 3m external-interest safe harbour, carry-forward of disallowed interest
- [ ] Hybrid offer: wind + BESS with a shaped corporate PPA – does storage close the price gap?
- [ ] Linked price and capture-rate scenarios instead of independent switches

**Known limitations of v1:** P50 only, single DSCR, fleet profile as park proxy, long-term prices from one academic forecast (Lampela 2023). Details in the memo.

## Main sources

ENTSO-E Transparency Platform · Fingrid Open Data · EEX Finnish Power Futures · KYOS PPA Insights No. 19 (Jun 2026) · LevelTen European PPA Price Index (Q1/Q2 2026) · Pexapark · IRENA, Renewable Power Generation Costs in 2025 · Clean Horizon Storage Index · OX2 press releases (2025) · Lampela, S. (2023), MSc thesis, Tampere University. Paid or copyrighted reports are cited, not included.

## Author

[Nils Pattyn] · [[LinkedIn](https://www.linkedin.com/in/nils-pattyn/)] · 
