import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# Page configuration
st.set_page_config(page_title="Cooking Fuel Data Tool", layout="wide")

st.title("Cooking Fuel Data Tool")
st.markdown("Generate tables projecting country-specific cooking fuel demand between 2000 and 2050")

# Initialize session state
if 'headcount_data' not in st.session_state:
    st.session_state.headcount_data = None
if 'per_capita_data' not in st.session_state:
    st.session_state.per_capita_data = None

# Helper function to load default WHO headcount data
@st.cache_data
def load_default_headcount_data():
    """Load default WHO headcount data from data folder"""
    try:
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                df = pd.read_csv('data/headcount_HH_fuel_UN_1990_2050.csv', encoding=encoding)
                required_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'year',
                                'population_lower95', 'population_median', 'population_upper95']
                if all(col in df.columns for col in required_cols):
                    return df
                else:
                    st.warning("Default WHO data file found but missing required columns")
                    return None
            except UnicodeDecodeError:
                continue
        st.error("Could not read the CSV file with any standard encoding")
        return None
    except FileNotFoundError:
        return None

# Helper function to load default per capita data
@st.cache_data
def load_default_per_capita_data():
    """Load default per capita fuel consumption data from data folder"""
    try:
        df = pd.read_csv('data/per_capita_fuel_placeholder.csv')
        if 'fuel' in df.columns and 'per_capita_tons' in df.columns:
            return df
        else:
            st.warning("Default per capita data file found but missing required columns")
            return None
    except FileNotFoundError:
        return None

# Sidebar: Step 1 - Country and Year Selection
st.sidebar.header("1. Select Countries and Years")

# Load default data to get available countries
default_headcount = load_default_headcount_data()
if default_headcount is not None:
    available_countries = sorted(default_headcount['country'].unique())
    st.session_state.headcount_data = default_headcount
else:
    available_countries = []
    st.sidebar.warning("No default WHO data found in data/headcount_HH_fuel_UN_1990_2050.csv")

selected_countries = st.sidebar.multiselect(
    "Select Countries",
    options=available_countries if available_countries else ["Upload data to see countries"],
    default=[]
)

year_range = st.sidebar.slider(
    "Select Year Range",
    min_value=1990,
    max_value=2050,
    value=(2020, 2030),
    step=1
)

start_year, end_year = year_range

# Sidebar: Step 2 - Data Upload (Optional)
st.sidebar.header("2. Upload Custom Data (Optional)")

headcount_file = st.sidebar.file_uploader(
    "Upload Custom Headcount Data (CSV/Excel)",
    type=['csv', 'xlsx'],
    key='headcount',
    help="Optional: Upload custom data instead of using default"
)

if headcount_file:
    if headcount_file.name.endswith('.csv'):
        st.session_state.headcount_data = pd.read_csv(headcount_file)
    else:
        st.session_state.headcount_data = pd.read_excel(headcount_file)
    st.sidebar.success("Custom headcount data uploaded!")

# Sidebar: Step 3 - Per Capita Fuel Consumption
st.sidebar.header("3. Per Capita Fuel Consumption")

# Load default per capita data if not already loaded
if st.session_state.per_capita_data is None:
    default_per_capita = load_default_per_capita_data()
    if default_per_capita is not None:
        st.session_state.per_capita_data = default_per_capita
        st.sidebar.info("Using default per capita values (placeholder)")

per_capita_file = st.sidebar.file_uploader(
    "Upload Per Capita Fuel Consumption Data (CSV/Excel)",
    type=['csv', 'xlsx'],
    key='per_capita',
    help="Optional: Upload custom per capita data to override defaults"
)

if per_capita_file:
    if per_capita_file.name.endswith('.csv'):
        st.session_state.per_capita_data = pd.read_csv(per_capita_file)
    else:
        st.session_state.per_capita_data = pd.read_excel(per_capita_file)
    st.sidebar.success("Custom per capita data uploaded!")

# Main Area: Data Preview and Processing
if selected_countries and st.session_state.headcount_data is not None:

    st.header("Data Preview")

    # Filter data for selected countries and years
    headcount_data = st.session_state.headcount_data

    # Filter by countries and years, and exclude "Overall" area
    filtered_data = headcount_data[
        (headcount_data['country'].isin(selected_countries)) &
        (headcount_data['year'] >= start_year) &
        (headcount_data['year'] <= end_year) &
        (headcount_data['area'] != 'Overall')
    ]

    st.subheader("Headcount Data (Filtered)")
    st.write(f"Total rows: {len(filtered_data):,}")
    st.write(f"Countries included: {', '.join(selected_countries)}")
    st.dataframe(filtered_data.head(200), height=400)
    st.caption(f"Showing first 200 of {len(filtered_data):,} rows (preview only - download to see all data)")

    # Download headcount data
    csv_headcount = filtered_data.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Complete Headcount Data as CSV",
        data=csv_headcount,
        file_name=f"headcount_data_{start_year}_{end_year}.csv",
        mime="text/csv",
    )

    # Summary statistics
    with st.expander("View Summary Statistics"):
        st.write("**Countries:**", ", ".join(selected_countries))
        st.write("**Years:**", f"{start_year} - {end_year}")
        st.write("**Fuel types:**", ", ".join(sorted(filtered_data['fuel'].unique())))
        st.write("**Areas:**", ", ".join(sorted(filtered_data['area'].unique())))

    # Calculate fuel consumption if per capita data is available
    if st.session_state.per_capita_data is not None:

        per_capita = st.session_state.per_capita_data

        # Show per capita data
        with st.expander("View Per Capita Fuel Consumption Data"):
            st.dataframe(per_capita)

        # Auto-generate output (no button needed)
        st.header("Fuel Consumption Output")

        # Merge headcount with per capita consumption
        # Note: fuel names must match between datasets
        final_output = filtered_data.merge(
            per_capita,
            on='fuel',
            how='left'
        )

        # Check for missing matches
        missing_fuels = final_output[final_output['per_capita_tons'].isna()]['fuel'].unique()
        if len(missing_fuels) > 0:
            st.warning(f"Warning: The following fuels in headcount data have no matching per capita values: {', '.join(missing_fuels)}")
            st.info("These will result in NaN values in the output. Make sure fuel names match exactly (case-sensitive).")

        # Calculate fuel consumption in tons
        if 'per_capita_tons' in final_output.columns:
            final_output['fuel_tons_lower95'] = final_output['population_lower95'] * final_output['per_capita_tons']
            final_output['fuel_tons_median'] = final_output['population_median'] * final_output['per_capita_tons']
            final_output['fuel_tons_upper95'] = final_output['population_upper95'] * final_output['per_capita_tons']

            # Select output columns
            output_df = final_output[['iso3', 'country', 'region', 'area', 'fuel', 'year',
                                     'fuel_tons_lower95', 'fuel_tons_median', 'fuel_tons_upper95']].copy()

            # AGGREGATE TABLE: Total Annual Fuel Use Per Year Per Country Per Area
            st.subheader("📊 Total Annual Fuel Use Per Year Per Country")

            # Aggregate by country, year, area, and fuel (sum across all fuel types for each area)
            aggregate_table = output_df.groupby(['country', 'year', 'area', 'fuel']).agg({
                'fuel_tons_lower95': 'sum',
                'fuel_tons_median': 'sum',
                'fuel_tons_upper95': 'sum'
            }).reset_index()

            # Pivot to get fuel types as columns, keeping area as a regular column
            pivot_table = aggregate_table.pivot_table(
                index=['country', 'year', 'area'],
                columns='fuel',
                values='fuel_tons_median',
                aggfunc='sum'
            ).reset_index()

            st.write(f"Total rows: {len(pivot_table):,}")
            st.dataframe(pivot_table, height=400)
            st.caption("Showing median fuel consumption in tons by country, year, and area (Urban/Rural)")

            # Download aggregate table
            csv_aggregate = pivot_table.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Fuel Consumption Table as CSV",
                data=csv_aggregate,
                file_name=f"fuel_consumption_by_area_{start_year}_{end_year}.csv",
                mime="text/csv",
            )

            # Detailed output table (in expander)
            with st.expander("🔍 View Detailed Output (All Rows by Area)"):
                st.write(f"Total rows: {len(output_df):,}")
                st.dataframe(output_df.head(200))
                st.caption(f"Showing first 200 of {len(output_df):,} rows (includes Urban/Rural breakdown)")

            # Summary statistics
            st.subheader("📈 Summary Statistics")

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Total Fuel Consumption by Fuel Type (Median, Tons)**")
                summary_fuel = output_df.groupby('fuel')['fuel_tons_median'].sum().sort_values(ascending=False)
                st.dataframe(summary_fuel.reset_index().rename(columns={'fuel_tons_median': 'Total Tons'}))

            with col2:
                st.write("**Total Fuel Consumption by Country (Median, Tons)**")
                summary_country = output_df.groupby('country')['fuel_tons_median'].sum().sort_values(ascending=False)
                st.dataframe(summary_country.reset_index().rename(columns={'fuel_tons_median': 'Total Tons'}))

            # Download buttons for detailed data
            st.subheader("📥 Download Detailed Data")
            col1, col2 = st.columns(2)

            with col1:
                csv = output_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Detailed Data as CSV",
                    data=csv,
                    file_name=f"cooking_fuel_detailed_{start_year}_{end_year}.csv",
                    mime="text/csv",
                )

            with col2:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    pivot_table.to_excel(writer, index=False, sheet_name='Fuel Consumption Summary')
                    aggregate_table.to_excel(writer, index=False, sheet_name='By Country Year Area Fuel')
                    output_df.to_excel(writer, index=False, sheet_name='Detailed Data')
                buffer.seek(0)

                st.download_button(
                    label="Download All Tables as Excel",
                    data=buffer,
                    file_name=f"cooking_fuel_output_{start_year}_{end_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.error("Per capita data must contain 'per_capita_tons' column")
    else:
        st.info("👈 Upload per capita fuel consumption data in the sidebar to calculate total fuel consumption in tons")

        # Still show option to download headcount data
        st.subheader("Download Headcount Data")

        headcount_output = filtered_data[['iso3', 'country', 'region', 'area', 'fuel', 'year',
                                          'population_lower95', 'population_median', 'population_upper95']]

        csv = headcount_output.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Headcount Data as CSV",
            data=csv,
            file_name=f"cooking_fuel_headcount_{start_year}_{end_year}.csv",
            mime="text/csv",
        )

else:
    st.info("👈 Please select countries in the sidebar to begin")

# Footer
st.markdown("---")
st.caption("Cooking Fuel Data Tool - Projecting cooking fuel demand from 1990 to 2050")
