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
def load_one_dataset(local_fname, header_names=['iso3', 'country', 'region', 'area', 'fuel', 'year', 
                                                'percent_lower95', 'percent_median', 'percent_upper95']):
    """Load default WHO headcount data from data folder"""
    try:
        # Try different encodings
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                df = pd.read_csv(local_fname, encoding=encoding)
                required_cols = header_names
                if all(col in df.columns for col in required_cols):
                    df.columns = [c.strip().lower().replace('"','') for c in df.columns]
                    if 'area' in df.columns:
                        df['area'] = df['area'].str.strip().str.lower().map({
                            'urban': 'Urban', 'rural': 'Rural'
                        })
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

def load_default_population_data():
    years = [str(i) for i in range(1950, 2051)]
    headers = ['Index','Region, subregion, country or area','Area','Note','Country-code'] + years
    fname = "data/Population_Annual.csv"
    df = load_one_dataset(fname, headers)
    df.rename(columns={'region, subregion, country or area': 'country'}, inplace=True)
    country_codes_df = load_one_dataset("data/country_codes.csv", header_names=['Country or Area','M49 code','iso3'])
    code_to_iso3 = dict(zip(country_codes_df["m49 code"], country_codes_df["iso3"]))
    df["iso3"] = df['country-code'].map(code_to_iso3)
    df = df.dropna(subset=['iso3'])
    df = df.drop(columns=["country-code"])
    pop_long_df = df.melt(
        id_vars=["iso3", "country", "area"],
        value_vars=years,
        var_name="year",
        value_name="population",
    )
    pop_long_df["year"] = pop_long_df["year"].astype(int)
    # Remove spaces from population values (used as thousands separators in CSV)
    pop_long_df["population"] = pop_long_df["population"].astype(str).str.replace(" ", "", regex=False)
    pop_long_df["population"] = pd.to_numeric(pop_long_df["population"], errors="coerce")
    return pop_long_df

@st.cache_data
def load_default_population_share_fuel_data():
    fname = 'data/percent_HH_fuel_UN_1990_2050.csv'
    header_names = ['iso3', 'country', 'region', 'area', 'fuel', 'year', 
                    'percent_lower95', 'percent_median', 'percent_upper95']
    df = load_one_dataset(fname, header_names)
    df['year'] = df['year'].astype(int)
    for col in ['percent_lower95', 'percent_median', 'percent_upper95']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


@st.cache_data
def load_default_headcount_per_fuel_data():
    """
    fname = 'data/headcount_HH_fuel_UN_1990_2050.csv'
    header_names = ['iso3', 'country', 'region', 'area', 'fuel', 'year', 
                    'population_lower95', 'population_median', 'population_upper95']
    load_one_dataset(fname, header_names)
    """

# Helper function to load default per capita data
@st.cache_data
def load_default_per_capita_data():
    """Load default per capita fuel consumption data from data folder"""
    try:
        df = pd.read_csv('data/per_capita_fuel_placeholder.csv')
        required_cols = ['iso3', 'country', 'area', 'fuel', 'per_capita_tons']
        if all(col in df.columns for col in required_cols):
            return df
        else:
            st.warning("Default per capita data file found but missing required columns")
            return None
    except FileNotFoundError:
        return None
    
def load_default_data():
    pop_df = load_default_population_data()
    if pop_df is not None:
        st.session_state.population_df = pop_df
    else:
        st.sidebar.warning("Failed to load default population data.")
    pop_share_fuel_df = load_default_population_share_fuel_data()
    if pop_share_fuel_df is not None:
        st.session_state.population_share_per_fuel_df = pop_share_fuel_df
    else:
        st.sidebar.warning("Failed to load default population-share per fuels data.")
    

# Sidebar: Step 1 - Country and Year Selection
st.sidebar.header("1. Select Countries and Years")

# Load default data to get available countries
load_default_data()
default_pop_share_data = load_default_data()
available_countries = sorted(st.session_state.population_share_per_fuel_df['country'].unique())
selected_countries = st.sidebar.multiselect(
    "Select Countries",
    options=available_countries if available_countries else ["Upload data to see countries"],
    default=[]
)

# Get available fuel types from data
available_fuels = sorted(st.session_state.population_share_per_fuel_df['fuel'].unique()) if st.session_state.population_share_per_fuel_df is not None else []

# Fuel type selection with compact checkbox format
with st.sidebar.expander("🔥 Fuel Types (click to filter)", expanded=False):
    select_all_fuels = st.checkbox("Select All Fuel Types", value=True, key="select_all_fuels")

    if select_all_fuels:
        selected_fuels = available_fuels
    else:
        selected_fuels = []
        for fuel in available_fuels:
            if st.checkbox(fuel, value=False, key=f"fuel_{fuel}"):
                selected_fuels.append(fuel)

    if not selected_fuels:
        selected_fuels = available_fuels  # Fallback to all if none selected

# Area/Setting selection with compact checkbox format
with st.sidebar.expander("📍 Areas (click to filter)", expanded=False):
    select_all_areas = st.checkbox("Select All Areas", value=True, key="select_all_areas")

    if select_all_areas:
        selected_areas = ['Urban', 'Rural']
    else:
        selected_areas = []
        if st.checkbox("Urban", value=False, key="area_urban"):
            selected_areas.append('Urban')
        if st.checkbox("Rural", value=False, key="area_rural"):
            selected_areas.append('Rural')

    if not selected_areas:
        selected_areas = ['Urban', 'Rural']  # Fallback to all if none selected

year_range = st.sidebar.slider(
    "Select Year Range",
    min_value=1990,
    max_value=2050,
    value=(2020, 2030),
    step=1
)
start_year, end_year = year_range

# Sidebar: Step 2 - Customize Proportional Fuel-Use Data
st.sidebar.header("2. Customize Proportional Fuel-Use Data")

# Option A: Upload full custom dataset
with st.sidebar.expander("📤 Option A: Upload Custom Dataset", expanded=False):
    st.markdown("Upload complete data for all years")
    population_share_per_fuel_data_file = st.file_uploader(
        "Upload CSV/Excel with proportional fuel-use data",
        type=['csv', 'xlsx'],
        key='population_share_per_fuel',
        help="Required columns: country, region, area, fuel, year, percent_median, percent_lower95, percent_upper95"
    )

    if population_share_per_fuel_data_file:
        if population_share_per_fuel_data_file.name.endswith('.csv'):
            st.session_state.population_share_per_fuel_df = load_one_dataset(population_share_per_fuel_data_file)
        else:
            st.session_state.population_share_per_fuel_df = load_one_dataset(population_share_per_fuel_data_file)
        st.success("✅ Custom dataset uploaded!")

# Option B: Customize end year projections (moved from section 4)
if end_year > 2025:
    with st.sidebar.expander("📊 Option B: Customize End Year Projections", expanded=False):
        st.markdown(f"Enter values for **{end_year}** only")
        st.markdown("Data will be interpolated from 2025 baseline")

        # Initialize session state for custom projections
        if 'custom_end_year_data' not in st.session_state:
            st.session_state.custom_end_year_data = None
        if 'use_custom_projections' not in st.session_state:
            st.session_state.use_custom_projections = False

        # Button to open customization modal
        if st.button("📊 Customize End Year Projections", help=f"Enter custom percentage values for {end_year} to enable interpolation from 2025", use_container_width=True):
            st.session_state.show_projection_modal = True

        # Clear custom data button
        if st.session_state.use_custom_projections:
            if st.button("🔄 Clear Custom Projections", help="Revert to default data", use_container_width=True):
                st.session_state.custom_end_year_data = None
                st.session_state.use_custom_projections = False
                st.session_state.show_projection_modal = False
                st.rerun()

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


def interpolate_from_2025_to_end_year(baseline_data, custom_end_year_data, start_year, end_year):
    """
    Linear interpolation from 2025 baseline to custom end year values.

    Parameters:
    - baseline_data: DataFrame with population share data (must include year 2025)
    - custom_end_year_data: DataFrame with user-entered values for end_year
                           columns: iso3, country, region, area, fuel, percent_median
    - start_year: Starting year for output
    - end_year: Ending year for interpolation (user's selected end year)

    Returns:
    - DataFrame with interpolated values for years 2025 to end_year
    """

    # Extract 2025 baseline for selected combinations
    baseline_2025 = baseline_data[baseline_data['year'] == 2025].copy()

    # Prepare custom end year data
    custom_end_year_data = custom_end_year_data.copy()
    custom_end_year_data['year'] = end_year

    # Merge to get both start and end points
    merge_cols = ['iso3', 'country', 'region', 'area', 'fuel']
    baseline_2025 = baseline_2025[merge_cols + ['percent_median', 'percent_lower95', 'percent_upper95']].rename(
        columns={'percent_median': 'percent_2025', 'percent_lower95': 'lower_2025', 'percent_upper95': 'upper_2025'}
    )

    custom_end_year_data = custom_end_year_data[merge_cols + ['percent_median']].rename(
        columns={'percent_median': f'percent_{end_year}'}
    )

    merged = baseline_2025.merge(custom_end_year_data, on=merge_cols, how='inner')

    # Generate interpolated data for each year from 2025 to end_year
    interpolated_rows = []

    for year in range(2025, end_year + 1):
        year_data = merged.copy()
        year_data['year'] = year

        # Linear interpolation formula
        t = (year - 2025) / (end_year - 2025) if end_year > 2025 else 0

        year_data['percent_median'] = year_data['percent_2025'] + t * (year_data[f'percent_{end_year}'] - year_data['percent_2025'])
        # For simplicity, also interpolate confidence intervals proportionally
        year_data['percent_lower95'] = year_data['lower_2025'] + t * (year_data[f'percent_{end_year}'] - year_data['lower_2025'])
        year_data['percent_upper95'] = year_data['upper_2025'] + t * (year_data[f'percent_{end_year}'] - year_data['upper_2025'])

        interpolated_rows.append(year_data[merge_cols + ['year', 'percent_median', 'percent_lower95', 'percent_upper95']])

    interpolated_df = pd.concat(interpolated_rows, ignore_index=True)

    # Combine with historical data (before 2025)
    historical_data = baseline_data[(baseline_data['year'] >= start_year) & (baseline_data['year'] < 2025)].copy()

    # Filter historical data to only include the same combinations as in interpolated data
    historical_data = historical_data.merge(
        interpolated_df[merge_cols].drop_duplicates(),
        on=merge_cols,
        how='inner'
    )

    # Combine historical and interpolated
    combined_df = pd.concat([historical_data, interpolated_df], ignore_index=True)
    combined_df = combined_df.sort_values(['country', 'area', 'fuel', 'year']).reset_index(drop=True)

    return combined_df


def update_headcount_data(selected_pop_share_df, total_pop_df):
    # First try strict merge on iso3+area+year, then fill remaining by country+area+year
    on_keys = ['area','year']
    # Strict
    merged_hc_df = selected_pop_share_df.merge(
        total_pop_df[['iso3','area','year','population']],
        on=['iso3'] + on_keys,
        how='left',
        validate='m:1'
    )
    value_cols = [
        ('percent_median', 'fuel_users_median'),
        ('percent_lower95', 'fuel_users_lower95'),
        ('percent_upper95', 'fuel_users_upper95')
        ]
    merged_hc_df["population"] = pd.to_numeric(merged_hc_df["population"], errors='coerce')
    for col_in, col_out in value_cols:
        merged_hc_df[col_in] = pd.to_numeric(merged_hc_df[col_in], errors='coerce')
        merged_hc_df[col_out] = merged_hc_df[col_in] * merged_hc_df["population"]
        merged_hc_df[col_out] = pd.to_numeric(merged_hc_df[col_out], errors='coerce')
    fuel_user_col_names = [c[1] for c in value_cols]
    out_cols = ['iso3','country','region','area','fuel','year'] + fuel_user_col_names
    return merged_hc_df[out_cols]

# Modal for customizing end year projections
if end_year > 2025 and 'show_projection_modal' in st.session_state and st.session_state.show_projection_modal:
    @st.dialog(f"Customize {end_year} Projections", width="large")
    def show_projection_modal():
        st.markdown(f"### Enter percentage values for {end_year}")
        st.markdown(f"Data will be linearly interpolated from 2025 baseline to {end_year}")

        # Generate template based on selected countries, fuels, and areas
        if selected_countries and selected_fuels and selected_areas:
            # Get baseline 2025 data to extract iso3, region info
            baseline_df = st.session_state.population_share_per_fuel_df
            baseline_2025 = baseline_df[
                (baseline_df['year'] == 2025) &
                (baseline_df['country'].isin(selected_countries)) &
                (baseline_df['fuel'].isin(selected_fuels)) &
                (baseline_df['area'].isin(selected_areas))
            ][['iso3', 'country', 'region', 'area', 'fuel', 'percent_median']].copy()

            if len(baseline_2025) == 0:
                st.error("No 2025 baseline data found for the selected countries, fuels, and areas. Cannot create interpolation.")
                if st.button("Close"):
                    st.session_state.show_projection_modal = False
                    st.rerun()
                return

            # Create template for end year
            template_df = baseline_2025.copy()
            template_df['percent_median'] = template_df['percent_median'].round(2)

            st.info(f"📋 You must provide values for all {len(template_df)} combinations below.")

            # Two input options: Data Editor or CSV Upload
            input_method = st.radio("Input Method", ["Data Editor", "Upload CSV"], horizontal=True)

            if input_method == "Data Editor":
                st.markdown("Edit the percentage values in the table below:")

                # Use data editor for interactive editing
                edited_data = st.data_editor(
                    template_df,
                    disabled=['iso3', 'country', 'region', 'area', 'fuel'],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "percent_median": st.column_config.NumberColumn(
                            f"Percent for {end_year}",
                            help="Enter percentage value (0-100)",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            format="%.2f"
                        )
                    }
                )

                # Validation
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✅ Apply Custom Projections", type="primary", use_container_width=True):
                        # Validate data
                        if edited_data['percent_median'].isna().any():
                            st.error("❌ Missing values detected. Please fill in all percentage values.")
                        elif (edited_data['percent_median'] < 0).any() or (edited_data['percent_median'] > 100).any():
                            st.error("❌ Percentage values must be between 0 and 100.")
                        else:
                            # Store custom data and mark as using custom projections
                            st.session_state.custom_end_year_data = edited_data
                            st.session_state.use_custom_projections = True
                            st.session_state.show_projection_modal = False
                            st.success("✅ Custom projections applied successfully!")
                            st.rerun()

                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.show_projection_modal = False
                        st.rerun()

            else:  # CSV Upload
                st.markdown("Upload a CSV file with the following columns:")
                st.code("iso3, country, region, area, fuel, percent_median")

                # Provide download template
                template_csv = template_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Template CSV",
                    data=template_csv,
                    file_name=f"projection_template_{end_year}.csv",
                    mime="text/csv",
                )

                uploaded_csv = st.file_uploader("Upload Custom Values CSV", type=['csv'])

                if uploaded_csv:
                    try:
                        uploaded_df = pd.read_csv(uploaded_csv)

                        # Validate columns
                        required_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'percent_median']
                        if not all(col in uploaded_df.columns for col in required_cols):
                            st.error(f"❌ CSV must contain columns: {', '.join(required_cols)}")
                        else:
                            # Validate completeness
                            expected_combos = set(template_df.apply(lambda row: (row['iso3'], row['area'], row['fuel']), axis=1))
                            actual_combos = set(uploaded_df.apply(lambda row: (row['iso3'], row['area'], row['fuel']), axis=1))

                            if expected_combos != actual_combos:
                                missing = expected_combos - actual_combos
                                extra = actual_combos - expected_combos
                                if missing:
                                    st.error(f"❌ Missing combinations: {missing}")
                                if extra:
                                    st.warning(f"⚠️ Extra combinations (will be ignored): {extra}")
                            else:
                                st.success("✅ CSV validated successfully!")

                                col1, col2 = st.columns([1, 1])
                                with col1:
                                    if st.button("✅ Apply Custom Projections", type="primary", use_container_width=True):
                                        st.session_state.custom_end_year_data = uploaded_df
                                        st.session_state.use_custom_projections = True
                                        st.session_state.show_projection_modal = False
                                        st.rerun()

                                with col2:
                                    if st.button("❌ Cancel", use_container_width=True):
                                        st.session_state.show_projection_modal = False
                                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error reading CSV: {str(e)}")

        else:
            st.warning("⚠️ Please select countries, fuel types, and areas before customizing projections.")
            if st.button("Close"):
                st.session_state.show_projection_modal = False
                st.rerun()

    show_projection_modal()

# Main Area: Data Preview and Processing
if selected_countries and st.session_state.population_share_per_fuel_df is not None:
    # Show status indicator if using custom projections
    if st.session_state.get('use_custom_projections', False):
        st.success(f"✅ Using Custom Projections: Data interpolated from 2025 to {end_year}")

    st.header("Data Preview")

    # Use interpolated data if custom projections are active
    if st.session_state.get('use_custom_projections', False) and st.session_state.get('custom_end_year_data') is not None:
        # Apply interpolation
        try:
            interpolated_data = interpolate_from_2025_to_end_year(
                st.session_state.population_share_per_fuel_df,
                st.session_state.custom_end_year_data,
                start_year,
                end_year
            )
            pop_share_per_fuel_df = interpolated_data
        except Exception as e:
            st.error(f"❌ Error applying custom projections: {str(e)}")
            pop_share_per_fuel_df = st.session_state.population_share_per_fuel_df
    else:
        pop_share_per_fuel_df = st.session_state.population_share_per_fuel_df

    # Filter data for selected countries, fuels, areas, and years
    filtered_data = pop_share_per_fuel_df[
        (pop_share_per_fuel_df['country'].isin(selected_countries)) &
        (pop_share_per_fuel_df['fuel'].isin(selected_fuels)) &
        (pop_share_per_fuel_df['area'].isin(selected_areas)) &
        (pop_share_per_fuel_df['year'] >= start_year) &
        (pop_share_per_fuel_df['year'] <= end_year) &
        (pop_share_per_fuel_df['area'] != 'Overall')
    ]
    filtered_headcount_data_per_fuel = update_headcount_data(filtered_data,
                                                             st.session_state.population_df)

    # Filter to only include Urban and Rural areas
    filtered_headcount_data_per_fuel = filtered_headcount_data_per_fuel[
        filtered_headcount_data_per_fuel['area'].isin(['Urban', 'Rural'])
    ]

    st.subheader("Headcount Data (Filtered)")
    st.write(f"Total rows: {len(filtered_headcount_data_per_fuel):,}")
    st.write(f"Countries included: {', '.join(selected_countries)}")
    display_cols = ['country', 'region', 'area', 'fuel', 'year','fuel_users_median']
    st.dataframe(filtered_headcount_data_per_fuel[display_cols].head(200), height=400, hide_index=True)
    st.caption(f"Showing first 200 of {len(filtered_headcount_data_per_fuel):,} rows (preview only - download to see all data)")

    # Download headcount data
    csv_headcount = filtered_headcount_data_per_fuel.to_csv(index=False).encode('utf-8')
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
        st.write("**Fuel types:**", ", ".join(sorted(filtered_headcount_data_per_fuel['fuel'].unique())))
        st.write("**Areas:**", ", ".join(sorted(str(x) for x in filtered_headcount_data_per_fuel['area'].dropna().unique())))

    # Calculate fuel consumption if per capita data is available
    if st.session_state.per_capita_data is not None:
        per_capita = st.session_state.per_capita_data
        # Show per capita data
        with st.expander("View Per Capita Fuel Consumption Data"):
            st.dataframe(per_capita, hide_index=True)
        # Auto-generate output (no button needed)
        st.header("Fuel Consumption Output")

        # Merge headcount with per capita consumption
        # Merge on iso3, area, and fuel for country and urban/rural specific values
        final_output = filtered_headcount_data_per_fuel.merge(
            per_capita[['iso3', 'area', 'fuel', 'per_capita_tons']],
            on=['iso3', 'area', 'fuel'],
            how='left'
        )

        # Check for missing matches
        missing_data = final_output[final_output['per_capita_tons'].isna()]
        if len(missing_data) > 0:
            missing_combos = missing_data.groupby(['iso3', 'country', 'area', 'fuel']).size().reset_index(name='count')
            st.warning(f"Warning: {len(missing_data)} rows have no matching per capita values")
            with st.expander("View missing combinations"):
                st.dataframe(missing_combos[['iso3', 'country', 'area', 'fuel']], hide_index=True)
            st.info("These will result in NaN values in the output. Make sure country codes (iso3), areas, and fuel names match exactly between datasets.")

        # Calculate fuel consumption in tons
        if 'per_capita_tons' in final_output.columns:
            #final_output['fuel_tons_lower95'] = final_output['population_lower95'] * final_output['per_capita_tons']
            final_output['fuel_tons_median'] = final_output['fuel_users_median'] * final_output['per_capita_tons']
            #final_output['fuel_tons_upper95'] = final_output['population_upper95'] * final_output['per_capita_tons']

            # Select output columns
            output_df = final_output[['iso3', 'country', 'region', 'area', 'fuel', 'year', 'fuel_tons_median']].copy()

            # AGGREGATE TABLE: Total Annual Fuel Use Per Year Per Country Per Area
            st.subheader("📊 Total Annual Fuel Use Per Year Per Country")

            # Aggregate by country, year, area, and fuel (sum across all fuel types for each area)
            aggregate_table = output_df.groupby(['country', 'year', 'area', 'fuel']).agg({
                'fuel_tons_median': 'sum'
            }).reset_index()

            # Pivot to get fuel types as columns, keeping area as a regular column
            pivot_table = aggregate_table.pivot_table(
                index=['country', 'year', 'area'],
                columns='fuel',
                values='fuel_tons_median',
                aggfunc='sum'
            ).reset_index()

            st.write(f"Total rows: {len(pivot_table):,}")
            st.dataframe(pivot_table, height=400, hide_index=True)
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
                st.dataframe(output_df.head(200), hide_index=True)
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
