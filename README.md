# World Bank Macroeconomic Data Pipeline

A configuration-driven Python project that automatically collects annual macroeconomic data
from the World Bank API, reshapes it into a structured format, and performs a descriptive
analysis of structural economic change across 17 countries from 2000 to 2025.

---

## Project Purpose

This project answers the question: **How has the role of industry and manufacturing in national
economies changed over the past 25 years?**

It collects GDP, industry value added and manufacturing value added data from the World Bank
API for 17 countries, computes value-added shares and compound annual growth rates (CAGRs),
and summarises findings in a structured table.

---

## Repository Structure

```
worldbank_project/
├── config.toml              # All configuration - countries, years, indicators
├── main.py                  # Single-entry pipeline: fetch -> reshape -> analyse
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── output/
    ├── worldbank_data_wide.csv   # Main dataset in wide format
    └── summary_analysis.csv      # Per-country summary table
```

---

## Configuration (`config.toml`)

All data collection parameters are controlled exclusively through `config.toml`.
No countries, indicators or years are hard-coded in the source code.

```toml
[countries]
list = ["Australia", "Belgium", "United States", ...]  # Country names

[time]
start_year = 2000
end_year = 2025

[series]
industry_value_added_usd_const = "NV.IND.TOTL.KD"
manufacturing_value_added_usd_const = "NV.IND.MANF.KD"
gdp_usd_real = "NY.GDP.MKTP.KD"
```

To change what data is collected, edit only this file. Country names are automatically
mapped to World Bank ISO3 codes inside the pipeline.

---

## How to Run

**Requirements:** Python 3.11 or higher

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/worldbank_project.git
cd worldbank_project

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the pipeline
python main.py
```

All outputs are saved automatically to the `output/` folder.

---

## Output Files

### `output/worldbank_data_wide.csv`

Main dataset in wide format. Each row represents one country-indicator combination.
Each year appears as a separate column (`year_2000`, `year_2001`, ..., `year_2025`).
Missing values are explicit `NaN`.

| country | indicator | year_2000 | year_2001 | ... | year_2024 |
|---------|-----------|-----------|-----------|-----|-----------|
| Germany | gdp_usd_real | 3.04e+12 | 3.07e+12 | ... | 3.41e+12 |

### `output/summary_analysis.csv`

Per-country summary table with one row per country. Columns:

| Column | Description |
|--------|-------------|
| `industry_share_2000` | Industry value added as share of GDP in 2000 |
| `industry_share_2025` | Industry value added as share of GDP in latest available year |
| `manufacturing_share_2000` | Manufacturing value added as share of GDP in 2000 |
| `manufacturing_share_2025` | Manufacturing value added as share of GDP in latest available year |
| `industry_cagr` | Compound annual growth rate of industry value added |
| `manufacturing_cagr` | Compound annual growth rate of manufacturing value added |
| `gdp_cagr` | Compound annual growth rate of GDP |

---

## Analytical Findings

### De-industrialization in Advanced Economies

The data reveals clear signs of de-industrialization across most advanced economies.
The United Kingdom experienced the sharpest decline, with industry's share of GDP falling
from 22.7% in 2000 to 16.4% in 2024 - a structural shift reflecting the long-running
transition toward a service-based economy. France, Belgium and Brazil similarly show
industry shares declining by 3 to 4 percentage points over the same period.

### Manufacturing Declining Faster Than Total Industry

In most countries, manufacturing is declining faster than total industry value added.
Canada is a clear example: its manufacturing CAGR is negative (-0.37% per year) while
total industry still grew modestly. Australia shows manufacturing's share of GDP collapsing
from 9.1% to 5.1% while total industry declined more moderately. This reflects the broader
trend of manufacturing offshoring and the rise of non-manufacturing industrial activity
such as mining, utilities and construction.

### Advanced vs Emerging Economies

The contrast between advanced and emerging economies is stark. Turkey recorded the highest
industry CAGR at 5.1% per year and China at 8.3%, both driven by rapid industrialization
and export-led growth. Meanwhile, Italy recorded near-zero industry growth (-0.04% CAGR)
and Finland and France grew at under 0.5% per year. Japan and Germany, despite remaining
highly industrial relative to peers, also show modest growth rates reflecting mature
industrial bases with limited expansion potential.

### Notable Exceptions

Germany and Japan stand out among advanced economies for maintaining relatively high
manufacturing shares (19.3% and 21.9% respectively in 2024) despite modest growth rates.
Denmark shows an unusual increase in its manufacturing share from 13.3% to 20.7%, likely
reflecting the expansion of its maritime and pharmaceutical manufacturing sectors.
Italy is the only country with negative industry CAGR, highlighting its structural
economic challenges over the 2000-2024 period.

---

## Assumptions and Limitations

- **2025 data unavailability:** The World Bank API does not yet have complete 2025 data
  for most countries. The analysis uses the most recent available year (typically 2023
  or 2024) for end-year computations. The `end_year` column in TOML is used as the
  upper bound for data collection; actual end year used per country may differ.

- **Missing start values:** The United States is missing industry value added data for
  2000 in the World Bank API, which results in NaN CAGR values for that country.
  All other indicators and years for the US are available.

- **China manufacturing data:** China's manufacturing value added for 2000 is not
  available in the API, so the manufacturing start share and CAGR cannot be computed
  for China.

- **Country name mapping:** Country names in `config.toml` are mapped to ISO3 codes
  inside the pipeline. If a new country is added to the config whose name does not
  match the internal mapping, a warning is printed and that country is skipped.

- **CAGR formula:** CAGR is computed as `(end_value / start_value)^(1/n) - 1` where
  `n` is the number of years between the start and end observations. Countries with
  zero or negative values in either year return NaN for CAGR.

- **API reliability:** The World Bank API occasionally times out for certain country-
  indicator combinations. The pipeline retries up to 3 times per request before
  logging an error and continuing.
