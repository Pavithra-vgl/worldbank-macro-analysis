# World Bank Macro Data Pipeline
# Fetches GDP, industry and manufacturing data -> reshapes -> analyses
# Usage: python main.py

import tomllib
import requests
import pandas as pd
import numpy as np
from pathlib import Path



# Country name - World Bank ISO3 code mapping

COUNTRY_CODES = {
    "Australia": "AUS",
    "Belgium": "BEL",
    "United States": "USA",
    "Canada": "CAN",
    "Mexico": "MEX",
    "Brazil": "BRA",
    "Germany": "DEU",
    "France": "FRA",
    "Italy": "ITA",
    "Denmark": "DNK",
    "Finland": "FIN",
    "Netherlands": "NLD",
    "United Kingdom": "GBR",
    "South Africa": "ZAF",
    "China": "CHN",
    "Japan": "JPN",
    "Turkey": "TUR",
}


def load_config(path: str = "config.toml") -> dict:
    # Load config from TOML
    with open(path, "rb") as f:
        return tomllib.load(f)


def fetch_indicator(iso_code: str, indicator: str, start_year: int, end_year: int, retries: int = 3) -> list:
    # Fetch one indicator for one country, handles pagination and retries
    base_url = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
    url = base_url.format(country=iso_code, indicator=indicator)

    params = {
        "format": "json",
        "date": f"{start_year}:{end_year}",
        "per_page": 100,
        "page": 1,
    }

    results = []

    while True:
        for attempt in range(retries):
            try:
                response = requests.get(url, params=params, timeout=60)
                response.raise_for_status()
                break
            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    print(f"    [RETRY {attempt + 1}/{retries}] Timeout - retrying...")
                else:
                    raise

        data = response.json()

        # World Bank returns [metadata, data_list]
        if len(data) < 2 or not data[1]:
            break

        metadata = data[0]
        records = data[1]

        for record in records:
            year = int(record["date"])
            value = record["value"]  # None if missing
            results.append((year, value))

        # Checking if more pages exist
        total_pages = metadata.get("pages", 1)
        current_page = metadata.get("page", 1)
        if current_page >= total_pages:
            break

        params["page"] += 1

    return results


def collect_all_data(config: dict) -> pd.DataFrame:
    # Loop through all countries and indicators from config and collect raw data
    countries = config["countries"]["list"]
    start_year = config["time"]["start_year"]
    end_year = config["time"]["end_year"]
    series = config["series"]

    rows = []

    for country_name in countries:
        iso_code = COUNTRY_CODES.get(country_name)
        if iso_code is None:
            print(f"  [WARNING] No ISO code found for '{country_name}' - skipping.")
            continue

        print(f"  Fetching data for {country_name} ({iso_code})...")

        for indicator_key, indicator_code in series.items():
            try:
                records = fetch_indicator(iso_code, indicator_code, start_year, end_year)
                for year, value in records:
                    rows.append({
                        "country": country_name,
                        "indicator": indicator_key,
                        "year": year,
                        "value": value,
                    })
            except Exception as e:
                print(f"    [ERROR] Failed to fetch {indicator_key} for {country_name}: {e}")

    return pd.DataFrame(rows)


def reshape_wide(df_long: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    # Pivot from long to wide format - one column per year
    df_wide = df_long.pivot_table(
        index=["country", "indicator"],
        columns="year",
        values="value",
        aggfunc="first",
    ).reset_index()

    # Ensuring all years are present as columns, even if there are no data
    all_years = list(range(start_year, end_year + 1))
    for year in all_years:
        if year not in df_wide.columns:
            df_wide[year] = np.nan

    # Renaming year columns to year_YYYY format
    year_cols = {y: f"year_{y}" for y in all_years}
    df_wide = df_wide.rename(columns=year_cols)

    # Sorting columns cleanly
    meta_cols = ["country", "indicator"]
    year_col_names = [f"year_{y}" for y in all_years]
    df_wide = df_wide[meta_cols + year_col_names]

    df_wide = df_wide.sort_values(["country", "indicator"]).reset_index(drop=True)

    return df_wide


def compute_cagr(start_val, end_val, n_years: int) -> float:
    # CAGR formula: (end/start)^(1/n) - 1, returns NaN if data is missing or invalid
    if pd.isna(start_val) or pd.isna(end_val):
        return np.nan
    if start_val <= 0 or end_val <= 0:
        return np.nan
    return (end_val / start_val) ** (1 / n_years) - 1


def get_last_available_year(df_long: pd.DataFrame, country: str, indicator: str, end_year: int) -> tuple:
    # World Bank often missing recent years - use latest available instead of hardcoded end year
    rows = df_long[
        (df_long["country"] == country) &
        (df_long["indicator"] == indicator) &
        (df_long["year"] <= end_year) &
        (df_long["value"].notna())
    ].sort_values("year", ascending=False)

    if rows.empty:
        return None, np.nan
    row = rows.iloc[0]
    return int(row["year"]), row["value"]


def analyse(df_long: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    # Per-country summary: shares of GDP and CAGRs
    n_years = end_year - start_year
    countries = df_long["country"].unique()
    summary_rows = []

    for country in countries:
        country_df = df_long[df_long["country"] == country]

        def get_val(indicator_key: str, year: int):
            """Helper to extract a single value safely."""
            row = country_df[
                (country_df["indicator"] == indicator_key) &
                (country_df["year"] == year)
            ]
            if row.empty:
                return np.nan
            return row["value"].values[0]

        # Using start year values
        ind_start = get_val("industry_value_added_usd_const", start_year)
        man_start = get_val("manufacturing_value_added_usd_const", start_year)
        gdp_start = get_val("gdp_usd_real", start_year)

        # Using last available year for end values
        ind_end_year, ind_end   = get_last_available_year(df_long, country, "industry_value_added_usd_const", end_year)
        man_end_year, man_end   = get_last_available_year(df_long, country, "manufacturing_value_added_usd_const", end_year)
        gdp_end_year, gdp_end   = get_last_available_year(df_long, country, "gdp_usd_real", end_year)

        # Using GDP end year for shares (most conservative)
        gdp_end_yr = gdp_end_year or end_year
        n_years = gdp_end_yr - start_year if gdp_end_yr else end_year - start_year

        # Shares
        ind_share_start = (ind_start / gdp_start) if (gdp_start and not pd.isna(gdp_start)) else np.nan
        ind_share_end   = (ind_end   / gdp_end)   if (gdp_end   and not pd.isna(gdp_end))   else np.nan
        man_share_start = (man_start / gdp_start) if (gdp_start and not pd.isna(gdp_start)) else np.nan
        man_share_end   = (man_end   / gdp_end)   if (gdp_end   and not pd.isna(gdp_end))   else np.nan

        # CAGRs
        ind_cagr = compute_cagr(ind_start, ind_end, n_years)
        man_cagr = compute_cagr(man_start, man_end, n_years)
        gdp_cagr = compute_cagr(gdp_start, gdp_end, n_years)

        summary_rows.append({
            "country":                  country,
            "industry_share_2000":      round(ind_share_start, 4) if not pd.isna(ind_share_start) else np.nan,
            "industry_share_2025":      round(ind_share_end,   4) if not pd.isna(ind_share_end)   else np.nan,
            "manufacturing_share_2000": round(man_share_start, 4) if not pd.isna(man_share_start) else np.nan,
            "manufacturing_share_2025": round(man_share_end,   4) if not pd.isna(man_share_end)   else np.nan,
            "industry_cagr":            round(ind_cagr, 4) if not pd.isna(ind_cagr) else np.nan,
            "manufacturing_cagr":       round(man_cagr, 4) if not pd.isna(man_cagr) else np.nan,
            "gdp_cagr":                 round(gdp_cagr, 4) if not pd.isna(gdp_cagr) else np.nan,
        })

    return pd.DataFrame(summary_rows).sort_values("country").reset_index(drop=True)


def main():
    print("=" * 60)
    print("World Bank Macroeconomic Data Pipeline")
    print("=" * 60)

    # Creating output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Step 1: Loading config
    print("\n[1/4] Loading configuration from config.toml...")
    config = load_config("config.toml")
    start_year = config["time"]["start_year"]
    end_year   = config["time"]["end_year"]
    print(f"      Countries : {len(config['countries']['list'])}")
    print(f"      Indicators: {len(config['series'])}")
    print(f"      Years     : {start_year} - {end_year}")

    # Step 2: Fetching data
    print("\n[2/4] Fetching data from World Bank API...")
    df_long = collect_all_data(config)
    print(f"      Collected {len(df_long)} records.")

    # Step 3: Reshaping to wide format
    print("\n[3/4] Reshaping data to wide format...")
    df_wide = reshape_wide(df_long, start_year, end_year)
    wide_path = output_dir / "worldbank_data_wide.csv"
    df_wide.to_csv(wide_path, index=False)
    print(f"      Saved: {wide_path} ({len(df_wide)} rows)")

    # Step 4: Analysing
    print("\n[4/4] Computing analysis (shares, CAGRs, summary table)...")
    df_summary = analyse(df_long, start_year, end_year)
    summary_path = output_dir / "summary_analysis.csv"
    df_summary.to_csv(summary_path, index=False)
    print(f"      Saved: {summary_path} ({len(df_summary)} rows)")

    print("\n" + "=" * 60)
    print("Pipeline complete. Output files in /output/")
    print("=" * 60)

    # Printing the summary table to console
    print("\nSummary Table Preview:")
    print(df_summary.to_string(index=False))


if __name__ == "__main__":
    main()