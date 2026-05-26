# Cooking Fuel Data Tool

A Streamlit application that projects country-level cooking fuel consumption and the associated greenhouse-gas emissions between 1990 and 2050. It combines WHO fuel-use shares, UN population projections, per-capita consumption rates, and per-fuel emissions intensities into a single interactive workflow.

For a higher-level overview of the tool's purpose, data sources, and assumptions, see [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md).

## Features

- Select countries, fuel types, urban/rural areas, and a year range (1990–2050)
- Compute the number of users of each fuel: `population_share × total_population`
- Compute total fuel consumption: `num_fuel_users_thousands × per_capita_consumption`
- Compute total emissions (CO₂, CH₄, N₂O) and CO₂-equivalent using IPCC AR5 GWP-100 factors (CH₄ = 28, N₂O = 265 — UNFCCC Enhanced Transparency Framework default, post-2024)
- Apply a configurable wood-to-charcoal kiln-yield factor so charcoal totals can be reported in fuelwood-equivalent biomass (default 6:1)
- Edit fuel-share and per-capita values inline (paste from Excel supported), or upload custom datasets
- Customize a single future year and linearly interpolate every other year between the WHO baseline endpoints and the custom value
- Download outputs as Excel workbooks with a Metadata & Sources sheet that records the active data sources, citations, and any in-app edits

## Installation

1. Navigate to the project directory:
```bash
cd cooking-fuel-tool
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`.

## Data Files

All default data ships in the `data/` folder and is loaded automatically on startup.

### 1. Fuel-use shares — `data/percent_HH_fuel_UN_1990_2050.csv`

Percentage of each country's urban/rural population using each cooking fuel, for every year from 1990 to 2050. Source: updated UN WHO data from O. Stoner, applying the methods in Stoner et al. (2021), Nat Commun 12:5795.

**Columns:**
- `iso3` — ISO3 country code
- `country` — country name
- `region` — geographic region (overwritten on load with the canonical region from `country_codes.csv`)
- `area` — `Urban` or `Rural`
- `fuel` — fuel type (normalized to lowercase on load; `biomass` is renamed to `fuelwood` and `electricity` to `electric`)
- `year` — 1990–2050
- `percent_median` — share of population using this fuel (the lower95/upper95 columns are dropped on load; only the median is used)

### 2. Population — `data/Population_Annual.csv`

UN World Population Prospects total population by country, urban/rural, and year (1950–2050). Joined to the fuel-share data by `iso3 + area + year` to convert percentages into headcounts.

### 3. Country codes — `data/country_codes.csv`

Maps `iso3` ↔ M49 code and assigns each country to a canonical region (`ssa`, `south_asia`, `east_asia`, `latam`, `other`, ...). The region values are the join key for per-capita rates.

**Columns:** `Country or Area, M49 code, iso3, region`

### 4. Per-capita consumption — `data/per_cap_cons_per_fuel_per_region.csv`

How much fuel an average user of each fuel type consumes per year, keyed by region. Default source: DFloess, Grieshop, Puzzolo, et al. (2023).

**Columns:**
- `fuel` — fuel type (lowercased on load; must match the fuel-share data after normalization)
- `region` — canonical region from `country_codes.csv`. **Leave blank for a global value** — empty-region rows are expanded to every region at load time.
- `pc_fuel` — per-capita consumption rate
- `pc_fuel_units` — units string. Mixed units by fuel:
  - `MWh/person-year` for `electric`
  - `oven-dry tons/person-year` for `fuelwood` and `imp_fuelwood`
  - `tons/person-year` for all other fuels

### 5. Non-electric emissions intensities — `data/em_intens_per_fuel_no_elec_all_countries.csv`

Per-fuel emissions factors for CO₂, CH₄, and N₂O (mass ratios — kg GHG per kg fuel = tons per ton). The Electricity row in this file is intentionally ignored; electricity emissions come from file 6.

**Columns:** `fueltype, CO2, CH4, N2O` (`fueltype` is renamed to `fuel` on load; `imp_biomass` is renamed to `imp_fuelwood`)

### 6. Electricity grid emissions — `data/elec_ems_intens_per_country.csv`

Per-country Combined Margin grid emission factor for electricity consumption. The source header reads `kgCO2/kWh` but the numeric values are physically consistent with **grams**, not kilograms; the loader divides by 1000 so the in-memory value is tons CO₂ / MWh — which makes `total_fuel_cons_tons (MWh) × em_intens_CO2 (tCO2/MWh) = tons CO2` line up directly with the non-electric rows. CH₄ and N₂O are set to 0 for electricity (country-level data unavailable; for most grids those gases contribute <5% of CO₂-equivalent). Source: UNFCCC — IFI TWG List of Methodologies.

## Usage Workflow

1. **Filter** in the sidebar — pick countries, fuels, areas, and a year range.
2. **Outputs tab** (default view) — see the computed `Total fuel consumption` and `Total emissions` tables and download them as Excel workbooks.
3. **Inputs tab** (`✏️ See / edit input data`) — view and edit the underlying fuel shares and per-capita rates:
   - **Fuel shares** — edit cells inline (or paste from Excel) and click *Save edits*; upload a custom shares dataset via the modal; or customize a specific future year and let the tool linearly interpolate every other year between the WHO endpoints and your custom value.
   - **Per-capita rates** — edit cells inline; upload a custom region-keyed rates file; set the wood-to-charcoal kiln-yield factor (default 6, applied only to charcoal rows in the consumption output).
4. **Citations** — all custom uploads require a source description and full citation. The active source is shown in a ribbon under each table and recorded in the Metadata sheet of every Excel download.

## Output Format

### Total fuel consumption

| Column | Meaning |
|---|---|
| `iso3, country, region, area, fuel, year` | Identifiers |
| `num_fuel_users_thousands` | Number of people using this fuel, **in thousands** (`population_share × total_population`). UN population figures are in thousands and are not rescaled — multiply by 1,000 for absolute people. |
| `per_capita_fuel_cons` | Per-capita rate from the per-capita data (units vary by fuel — see file 4 above) |
| `total_fuel_cons_tons` | `num_fuel_users_thousands × per_capita_fuel_cons`, so values are **in thousands of tons** (multiply by 1,000 for absolute tons); for **charcoal** rows, additionally multiplied by the kiln-yield factor so the value represents upstream fuelwood biomass, not charcoal at the stove |

> **Units note:** because UN population is expressed in thousands and is not rescaled, `num_fuel_users_thousands` and every `total_*` column (consumption and emissions) are in **thousands**. Multiply by 1,000 for absolute people / tons.

### Total emissions

Two views in the app:

- **Per-fuel detail** — `total_fuel_cons_tons`, `em_intens_{CO2,CH4,N2O}`, and `total_{CO2,CH4,N2O}` per `iso3 × area × fuel × year`. `total_GHG = total_fuel_cons_tons × em_intens_GHG`. All `total_*` columns are in **thousands of tons** of GHG (multiply by 1,000 for absolute tons).
- **Country / area summary (CO₂-eq)** — emissions summed across all fuels per `iso3 × area × year`, plus `total_CO2eq = total_CO2 + 28 × total_CH4 + 265 × total_N2O`.

Excel downloads include a `Metadata & Sources` sheet capturing the active sources, citations, year range, filters, charcoal factor, and whether in-app edits were made during the session.

## Calculation Methodology

**Stage 1 — number of fuel users:**
```
num_fuel_users_thousands = population_share × total_population
```
joined on `iso3 + area + year`. `total_population` is in thousands (UN convention, not rescaled), so the result is in thousands of people.

**Stage 2 — total fuel consumption:**
```
total_fuel_cons_tons = num_fuel_users_thousands × per_capita_fuel_cons
```
(in thousands of tons, since the headcount is in thousands)
joined on `region + fuel`. For charcoal, additionally multiplied by the kiln-yield factor (default 6) so the output represents upstream wood biomass.

**Stage 3 — emissions:**
```
total_GHG  = total_fuel_cons_tons × em_intens_GHG     (for each of CO2, CH4, N2O)
total_CO2eq = total_CO2 + 28 × total_CH4 + 265 × total_N2O
```
For non-electric fuels, intensities are mass ratios from file 5. For electricity, the per-country grid factor from file 6 (converted to tons CO₂ / MWh at load) is used; CH₄ and N₂O are 0.

## Project Structure

```
cooking-fuel-tool/
├── app.py                                       # Main Streamlit application
├── requirements.txt                             # Python dependencies
├── README.md                                    # This file
├── PRODUCT_OVERVIEW.md                          # High-level product overview
└── data/
    ├── percent_HH_fuel_UN_1990_2050.csv         # WHO fuel-share data (percentages)
    ├── Population_Annual.csv                    # UN total population by area/year
    ├── country_codes.csv                        # ISO3 ↔ M49 ↔ canonical region
    ├── per_cap_cons_per_fuel_per_region.csv     # Default per-capita rates by region
    ├── em_intens_per_fuel_no_elec_all_countries.csv  # Per-fuel emissions intensities
    └── elec_ems_intens_per_country.csv          # Per-country grid emission factor
```

## Fuel Types

After normalization on load, the canonical fuel names are: `fuelwood`, `imp_fuelwood`, `charcoal`, `imp_charcoal`, `gas`, `kerosene`, `electric`, `pellets`, `ethanol`, `biogas`, `coal`, `other`. Source fuel names are lowercased; `biomass` is renamed to `fuelwood`, `electricity` to `electric`, and `imp_biomass` to `imp_fuelwood`. The aggregate rows `total clean` and `total polluting` are excluded from the fuel filter.

Custom uploads must use these canonical names (after lowercasing) for the merge keys to line up.

## Troubleshooting

**"⚠️ N rows have no matching per-capita rate"**
- The merge key is `region + fuel`. Check that your per-capita data uses the canonical regions from `country_codes.csv` (`ssa`, `south_asia`, etc.) and that fuel names match after lowercasing.
- For a value that should apply everywhere, leave `region` blank — empty-region rows are expanded to all regions at load.

**"⚠️ N rows have no matching emissions intensity"**
- The fuel name isn't present in `em_intens_per_fuel_no_elec_all_countries.csv` (or, for electricity, the ISO3 isn't in `elec_ems_intens_per_country.csv`).

**No countries appear in the sidebar**
- The default fuel-share file failed to load. Confirm `data/percent_HH_fuel_UN_1990_2050.csv` exists and has the expected columns.

**Custom-projection interpolation produces 0 or 100**
- Values are clipped to `[0, 100]` and are expected to be in the 0–1 range when entered via the population-share editor (the editor enforces this). Check that your input scale matches.

## Notes

- Only the median fuel-share values are used in calculations. The `lower95`/`upper95` columns in the source file are dropped at load.
- The `region` column on the fuel-share data is overwritten at load with the canonical region from `country_codes.csv` so it serves as a reliable join key for per-capita rates.
- All custom data uploads require a source description and full citation; both are recorded in the Excel `Metadata & Sources` sheet.

## License

This tool is created for data analysis and projection purposes.
