# Cooking Fuel Data Tool

A Streamlit application for calculating total cooking fuel consumption in tons based on WHO headcount projections and per-capita fuel consumption data.

## Features

- Select multiple countries and year ranges (1990-2050)
- Uses WHO headcount data (number of people using each fuel type)
- Calculates total fuel consumption by multiplying headcount × per-capita consumption
- Confidence intervals (lower95, median, upper95) propagated through calculations
- Download results as CSV or Excel

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

The app will open in your default browser at `http://localhost:8501`

## Data Files

### 1. WHO Headcount Data (Included)

**File location:** `data/headcount_HH_fuel_UN_1990_2050.csv`

This file contains the number of people (headcount) using each fuel type.

**Columns:**
- `iso3`: ISO3 country code (e.g., "USA", "IND")
- `country`: Country name
- `region`: Geographic region
- `area`: "Urban" or "Rural"
- `fuel`: Fuel type (e.g., "Kerosene", "Wood", "Coal", "LPG", etc.)
- `year`: Year (1990-2050)
- `population_lower95`: Lower 95% confidence interval for headcount
- `population_median`: Median headcount of people using this fuel
- `population_upper95`: Upper 95% confidence interval for headcount

**Example:**
```csv
iso3,country,region,area,fuel,year,population_lower95,population_median,population_upper95
AFG,Afghanistan,Central Asia,Urban,Kerosene,1990,0,0,137.479191
USA,United States,Americas,Rural,Wood,2020,1000000,1500000,2000000
```

### 2. Per Capita Fuel Consumption Data (Required Upload)

**File location:** Upload via the app interface

**Required columns:**
- `fuel`: Fuel type (must match fuel types in WHO data exactly - case sensitive!)
- `per_capita_tons`: Per capita fuel consumption in tons per year

**Example:**
```csv
fuel,per_capita_tons
clean,0.5
charcoal,0.3
wood,0.8
coal,0.4
Kerosene,0.35
LPG,0.45
```

**IMPORTANT:** Fuel names must match exactly between the headcount data and per capita data (case-sensitive).

## Usage Workflow

### Step 1: Select Countries and Years
- Use the sidebar to select one or more countries from the dropdown
- Choose the year range using the slider (1990-2050)

### Step 2: Upload Custom Data (Optional)
- Optionally upload custom headcount data if you don't want to use the default WHO data

### Step 3: Upload Per Capita Fuel Consumption
- Upload a CSV or Excel file with per capita fuel consumption data
- Format: Two columns (`fuel`, `per_capita_tons`)
- A placeholder file is provided: `data/per_capita_fuel_placeholder.csv`

### Step 4: Generate Output
- Click "Generate Fuel Consumption Output" to calculate total fuel consumption
- View the results in the app
- Download as CSV or Excel

## Output Format

**Columns:**
- `iso3`: ISO3 country code
- `country`: Country name
- `region`: Geographic region
- `area`: "Urban" or "Rural"
- `fuel`: Fuel type
- `year`: Year
- `fuel_tons_lower95`: Fuel consumption in tons (lower 95% CI)
- `fuel_tons_median`: Fuel consumption in tons (median)
- `fuel_tons_upper95`: Fuel consumption in tons (upper 95% CI)

## Calculation Methodology

**Fuel Consumption Calculation:**
```
fuel_tons = headcount × per_capita_tons
```

Where:
- `headcount` = number of people using that fuel (from WHO data)
- `per_capita_tons` = tons of fuel per person per year (from uploaded data)

Confidence intervals are calculated separately:
- `fuel_tons_lower95 = population_lower95 × per_capita_tons`
- `fuel_tons_median = population_median × per_capita_tons`
- `fuel_tons_upper95 = population_upper95 × per_capita_tons`

## Project Structure

```
cooking-fuel-tool/
├── app.py                                    # Main Streamlit application
├── requirements.txt                          # Python dependencies
├── README.md                                # This file
└── data/                                    # Data folder
    ├── headcount_HH_fuel_UN_1990_2050.csv   # WHO headcount data
    ├── Population_Annual.csv                # UN population data (not currently used)
    └── per_capita_fuel_placeholder.csv      # Example per capita data
```

## Common Fuel Types in WHO Data

Based on the headcount data, common fuel types include:
- Kerosene
- Wood
- Charcoal
- Coal
- LPG (Liquefied Petroleum Gas)
- Natural Gas
- Electricity
- Biogas

**Note:** Check the actual fuel names in your headcount data and ensure your per capita data uses the exact same names (including capitalization).

## Troubleshooting

**"Warning: The following fuels in headcount data have no matching per capita values"**
- Make sure fuel names in your per capita CSV exactly match the fuel names in the headcount data
- Fuel names are case-sensitive (e.g., "Kerosene" ≠ "kerosene")
- Check for extra spaces or special characters

**"No default WHO data found"**
- Make sure `headcount_HH_fuel_UN_1990_2050.csv` is in the `data/` folder
- The file path should be: `data/headcount_HH_fuel_UN_1990_2050.csv`

**App doesn't show any countries**
- The default data file may not be loaded properly
- Try uploading the headcount CSV manually via the sidebar

## Notes

- The WHO headcount data already contains population counts (not percentages), so no additional population data is needed
- The `Population_Annual.csv` file is included but not currently used by the app
- All calculations propagate confidence intervals through to the final output
- Missing per capita values will result in NaN (Not a Number) in the output

## License

This tool is created for data analysis and projection purposes.
