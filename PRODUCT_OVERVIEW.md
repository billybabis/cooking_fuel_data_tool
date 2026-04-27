# Cooking Fuel Data Tool — Product Overview

## What is this tool?

The Cooking Fuel Data Tool is a web-based application that answers one core question:

**"How much cooking fuel is consumed in a given country, and how might that change over time?"**

It combines global datasets on population, fuel choice, and consumption rates to produce country-level estimates of total cooking fuel use — broken down by fuel type (fuelwood, charcoal, improved fuelwood, improved charcoal, gas, kerosene, electric, pellets, ethanol, biogas, coal, and other), setting (urban vs. rural), and year (1990–2050).

---

## Why does it exist?

Understanding cooking fuel demand is essential for planning biofuel transitions, assessing emissions, and evaluating clean cooking programs. But the underlying data lives in separate sources — population projections from the UN, fuel-use patterns from the WHO, and per-capita consumption rates from the research literature. This tool brings those sources together into a single, interactive workflow so that analysts can quickly generate estimates without manually wrangling spreadsheets.

---

## What does it do, step by step?

The tool performs a straightforward calculation in two stages:

### Stage 1: How many people use each fuel?

The tool starts with WHO estimates of the share of the population that uses each cooking fuel (e.g., "35% of rural households in Country X use fuelwood in 2025"). It multiplies those shares by UN population figures to get the actual number of people — the "headcount" — using each fuel.

> *Share of population using a fuel* **x** *Total population* **=** *Number of fuel users*

### Stage 2: How much fuel do those people consume?

The tool then multiplies the number of fuel users by a per-capita consumption rate (e.g., "each fuelwood user consumes 0.8 tons per year") to arrive at total fuel consumption in tons.

> *Number of fuel users* **x** *Per-capita consumption rate* **=** *Total fuel consumed (tons)*

---

## What data does it use?

The tool comes pre-loaded with four datasets:

| Dataset | Source | What it provides |
|---------|--------|-----------------|
| Fuel use shares | WHO (Stoner et al. 2021) | The percentage of each country's urban and rural population using each fuel type, for every year from 1990 to 2050 |
| Population figures | UN World Population Prospects | Total urban and rural population by country, 1950–2050 |
| Country code mapping | UN Statistics Division | Links the different country code systems used by the population and fuel datasets |
| Per-capita consumption rates | Placeholder (pending final source) | How much fuel (in tons) an average user of each fuel type consumes per year, by country and setting |

---

## What can users control?

Using the sidebar, users must select:

- **Choose countries** — select one or more countries to analyze
- **Choose fuel types** — include or exclude specific fuels from the following list:
  - fuelwood (formerly Biomass)
  - charcoal
  - imp_fuelwood
  - imp_charcoal
  - gas
  - kerosene
  - electric (formerly electricity)
  - pellets
  - ethanol
  - biogas
  - coal
  - other
- **Choose urban/rural** — look at urban areas, rural areas, or both
- **Set a year range** — focus on any period between 1990 and 2050

Users also have the option to edit the following underlying data:

- **Custom fuel-use data**
  - Replace the default WHO shares with an alternative dataset (e.g., from a newer study or a national survey)
  - Enter custom fuel-use shares for a specific future year, and the tool will smoothly interpolate between the baseline and the custom values
- **Upload custom per-capita rates** — replace the default consumption rates with values from a specific study or region

All custom data uploads require a source description and citation, so the provenance of results is always traceable.

---

## What outputs does it produce?

### Tables

1. **Fuel user headcount** — the estimated number of people using each fuel, by country, area, fuel type, and year
2. **Total fuel consumption** — the estimated tons of each fuel consumed, presented both as a summary pivot table (fuel types as columns) and as a detailed row-by-row breakdown
3. **Summary statistics** — totals by fuel type and by country

### Downloads

- **CSV files** — headcount data and fuel consumption data, ready for use in other tools
- **Excel workbook** — a multi-sheet file that includes:
  - A metadata sheet with data sources, citations, and methodology notes
  - A summary sheet with the pivot table view
  - A detailed data sheet with the full breakdown

### Source tracking

Every output view includes a ribbon showing which data source is active and an expandable citations section. If custom data or projections have been applied, this is clearly flagged so results are never mistaken for the default WHO baseline.

---

## Key assumptions and limitations

- **Per-capita rates are static** — the default consumption rates do not vary by year. A person using fuelwood in 2025 is assumed to consume the same amount as one in 2040. Custom uploads can address this if time-varying rates are available.
- **Placeholder per-capita data** — the default per-capita rates are placeholders pending a finalized data source. Users should upload study-specific rates for final analyses.
- **Linear interpolation for projections** — when users customize a future year, all other years are adjusted using straight-line interpolation between the baseline endpoints and the custom value. This is a simple approach and may not capture non-linear trends.
- **No interaction between fuels** — each fuel type is estimated independently. The tool does not enforce that fuel shares across all types sum to 100% when custom values are entered.

---

## Who is it for?

The tool is designed for researchers, analysts, and program planners working on cooking fuel transitions, biofuel feasibility, emissions accounting, or clean cooking initiatives — anyone who needs country-level fuel consumption estimates without building their own data pipeline from scratch.
