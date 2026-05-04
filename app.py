import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# IPCC AR5 GWP-100 factors (UNFCCC Enhanced Transparency Framework default, post-2024)
GWP_CH4 = 28
GWP_N2O = 265

# Page configuration
st.set_page_config(page_title="Cooking Fuel Data Tool", layout="wide")

st.title("Cooking Fuel Data Tool")
st.markdown("Generate tables projecting country-specific cooking fuel demand between 1990 and 2050")

# Initialize session state
if 'headcount_data' not in st.session_state:
    st.session_state.headcount_data = None
if 'per_capita_data' not in st.session_state:
    st.session_state.per_capita_data = None
if 'data_source_population_share' not in st.session_state:
    st.session_state.data_source_population_share = "Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021)"
if 'data_source_base_citation' not in st.session_state:
    st.session_state.data_source_base_citation = (
        "Projections through 2050 are updated estimates shared by O. Stoner, applying the methods "
        "described in: Stoner, O., Shaddick, G., Economou, T. et al. *Global household energy model: "
        "a multivariate hierarchical approach to estimating trends in the use of polluting and clean "
        "fuels for cooking.* Nat Commun 12, 5795 (2021). "
        "[https://doi.org/10.1038/s41467-021-26036-x](https://doi.org/10.1038/s41467-021-26036-x). "
        "The published paper itself reports projections through 2030; values for 2031–2050 come from "
        "subsequent runs by the same author using the same methodology."
    )
if 'data_source_custom_citation' not in st.session_state:
    st.session_state.data_source_custom_citation = None
if 'custom_source_description' not in st.session_state:
    st.session_state.custom_source_description = None
if 'data_source_per_capita' not in st.session_state:
    st.session_state.data_source_per_capita = "DFloess, Grieshop, Puzzolo, et al. (2023)"
if 'per_capita_base_citation' not in st.session_state:
    st.session_state.per_capita_base_citation = "DFloess, Emily, Andrew Grieshop, Elisa Puzzolo, et al. “Scaling up Gas and Electric Cooking in Low- and Middle-Income Countries: Climate Threat or Mitigation Strategy with Co-Benefits?” Environmental Research Letters 18, no. 3 (2023): 034010. https://doi.org/10.1088/1748-9326/acb501."
if 'per_capita_source_description' not in st.session_state:
    st.session_state.per_capita_source_description = None
if 'custom_projection_source' not in st.session_state:
    st.session_state.custom_projection_source = None

@st.cache_data
def load_one_dataset(local_fname, header_names=['iso3', 'country', 'region', 'area', 'fuel', 'year',
                                                'percent_lower95', 'percent_median', 'percent_upper95']):
    """Load a CSV from data folder, trying multiple encodings."""
    try:
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                df = pd.read_csv(local_fname, encoding=encoding)
                if all(col in df.columns for col in header_names):
                    df.columns = [c.strip().lower().replace('"','') for c in df.columns]
                    if 'area' in df.columns:
                        df['area'] = df['area'].str.strip().str.lower().map({
                            'urban': 'Urban', 'rural': 'Rural'
                        })
                    return df
                else:
                    st.warning(f"{local_fname} found but missing required columns")
                    return None
            except UnicodeDecodeError:
                continue
        st.error("Could not read the CSV file with any standard encoding")
        return None
    except FileNotFoundError:
        return None

@st.cache_data
def load_country_codes():
    """Load country_codes.csv with iso3, M49, region columns."""
    df = load_one_dataset(
        "data/country_codes.csv",
        header_names=['Country or Area', 'M49 code', 'iso3', 'region']
    )
    return df

@st.cache_data
def get_iso3_to_region():
    """Map iso3 → region (e.g. 'ssa', 'south_asia', ...) from country_codes."""
    cc = load_country_codes()
    return dict(zip(cc['iso3'], cc['region']))

def load_default_population_data():
    years = [str(i) for i in range(1950, 2051)]
    headers = ['Index','Region, subregion, country or area','Area','Note','Country-code'] + years
    fname = "data/Population_Annual.csv"
    df = load_one_dataset(fname, headers)
    df.rename(columns={'region, subregion, country or area': 'country'}, inplace=True)

    cc = load_country_codes()
    code_to_iso3 = dict(zip(cc["m49 code"], cc["iso3"]))
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
    df['percent_median'] = pd.to_numeric(df['percent_median'], errors='coerce')
    if 'percent_lower95' in df.columns:
        df = df.drop(columns=['percent_lower95'])
    if 'percent_upper95' in df.columns:
        df = df.drop(columns=['percent_upper95'])

    # Normalize fuel: lowercase + canonical renames
    df['fuel'] = df['fuel'].astype(str).str.strip().str.lower()
    df['fuel'] = df['fuel'].replace({'biomass': 'fuelwood', 'electricity': 'electric'})

    # Overwrite region with country_codes region (canonical taxonomy used for per-capita lookup)
    iso3_to_region = get_iso3_to_region()
    df['region'] = df['iso3'].map(iso3_to_region)

    return df

@st.cache_data
def load_default_per_capita_data():
    """Load region-keyed per capita fuel consumption data.

    Source schema: [fuel, region, pc_fuel, pc_fuel_units]. Rows with empty
    region apply globally and are expanded to every region from country_codes.
    """
    try:
        df = pd.read_csv('data/per_cap_cons_per_fuel_per_region.csv')
        df.columns = [c.strip().lower() for c in df.columns]
        required_cols = ['fuel', 'region', 'pc_fuel', 'pc_fuel_units']
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            st.warning(f"Default per capita data file missing columns: {missing}")
            return None

        df['fuel'] = df['fuel'].astype(str).str.strip().str.lower()
        df['region'] = df['region'].fillna('').astype(str).str.strip().str.lower()
        df['pc_fuel'] = pd.to_numeric(df['pc_fuel'], errors='coerce')
        df['pc_fuel_units'] = df['pc_fuel_units'].astype(str).str.strip()

        cc = load_country_codes()
        all_regions = sorted([r for r in cc['region'].dropna().unique().tolist() if str(r).strip() != ''])

        global_rows = df[df['region'] == ''].copy()
        specific_rows = df[df['region'] != ''].copy()

        if len(global_rows) > 0 and all_regions:
            expanded = []
            for r in all_regions:
                g = global_rows.copy()
                g['region'] = r
                expanded.append(g)
            global_expanded = pd.concat(expanded, ignore_index=True)
            df = pd.concat([specific_rows, global_expanded], ignore_index=True)
        else:
            df = specific_rows

        return df.reset_index(drop=True)
    except FileNotFoundError:
        return None

def load_default_data():
    pop_df = load_default_population_data()
    if pop_df is not None:
        st.session_state.population_df = pop_df
    else:
        st.warning("Failed to load default population data.")
    pop_share_fuel_df = load_default_population_share_fuel_data()
    if pop_share_fuel_df is not None:
        st.session_state.population_share_per_fuel_df = pop_share_fuel_df
    else:
        st.warning("Failed to load default population-share per fuels data.")


@st.cache_data
def load_em_intens_no_elec():
    """Per-fuel emissions intensities (excludes electricity by design).

    Source: data/em_intens_per_fuel_no_elec_all_countries.csv. The Electricity row
    in the source file is ignored — electricity emissions come from the per-country
    placeholder file.
    """
    try:
        df = pd.read_csv('data/em_intens_per_fuel_no_elec_all_countries.csv')
        df.columns = [c.strip() for c in df.columns]
        if 'fueltype' in df.columns:
            df = df.rename(columns={'fueltype': 'fuel'})
        df['fuel'] = df['fuel'].astype(str).str.strip().str.lower()
        df['fuel'] = df['fuel'].replace({
            'biomass': 'fuelwood',
            'imp_biomass': 'imp_fuelwood',
            'electricity': 'electric',
        })
        df = df[df['fuel'] != 'electric'].reset_index(drop=True)
        for col in ['CO2', 'CH4', 'N2O']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except FileNotFoundError:
        return None


@st.cache_data
def load_em_intens_electricity():
    """Per-country electricity grid emission intensity.

    Source: `data/elec_ems_intens_per_country.csv` (Combined Margin grid emission
    factor, gCO2/kWh — header text says kgCO2/kWh but the values are physically
    consistent with grams, not kilograms). Divided by 1000 at load time so the
    stored value is in tons CO2 / MWh, which makes the per-row math
    `total_fuel_cons_tons (MWh) × em_intens_CO2 (tCO2/MWh) = tons CO2`
    align directly with non-electric rows.

    CH4 and N2O are set to 0 — data not available, and for electricity these
    contribute <5% of the CO2-equivalent total in most grids.
    """
    try:
        df = pd.read_csv('data/elec_ems_intens_per_country.csv')
        df.columns = [c.strip() for c in df.columns]
        # Map to canonical schema (column names in source are long/varied)
        iso_col, name_col, val_col = df.columns[0], df.columns[1], df.columns[2]
        df = df.rename(columns={iso_col: 'iso3', name_col: 'country', val_col: 'CO2'})
        df['iso3'] = df['iso3'].astype(str).str.strip()
        # Drop rows with no ISO3 (sub-regions like Azores/Madeira/Canary Islands,
        # or non-UN-recognized: Kosovo, Taiwan, Channel Islands aggregate)
        df = df[df['iso3'].notna() & (df['iso3'] != '') & (df['iso3'].str.lower() != 'nan')]
        df['CO2'] = pd.to_numeric(df['CO2'], errors='coerce') / 1000.0  # gCO2/kWh -> tCO2/MWh
        df['CH4'] = 0.0
        df['N2O'] = 0.0
        return df.reset_index(drop=True)
    except FileNotFoundError:
        return None


def apply_custom_year_adjustments(baseline_data, custom_year_data, custom_year, start_year, end_year):
    """
    Apply linear interpolation to all years based on custom values for a specific year.

    Parameters:
    - baseline_data: DataFrame with population share data
    - custom_year_data: DataFrame with user-entered values for custom_year
                       columns: iso3, country, region, area, fuel, percent_median (internal name)
    - custom_year: The year for which custom values are provided
    - start_year: Starting year for output
    - end_year: Ending year for output

    Returns:
    - DataFrame with linearly interpolated values for all years in the range
    """

    merge_cols = ['iso3', 'country', 'region', 'area', 'fuel']

    custom_year_data = custom_year_data.copy()
    custom_year_data = custom_year_data[merge_cols + ['percent_median']].rename(
        columns={'percent_median': 'custom_value'}
    )

    filtered_data = baseline_data[
        (baseline_data['year'] >= start_year) &
        (baseline_data['year'] <= end_year)
    ].copy()

    filtered_data = filtered_data.merge(
        custom_year_data[merge_cols].drop_duplicates(),
        on=merge_cols,
        how='inner'
    )

    filtered_data = filtered_data.merge(
        custom_year_data,
        on=merge_cols,
        how='left'
    )

    result_list = []

    for combo_vals, group in filtered_data.groupby(merge_cols):
        group = group.sort_values('year').copy()

        custom_val = group['custom_value'].iloc[0]
        years = group['year'].values
        baseline_values = group['percent_median'].values

        custom_year_idx = np.where(years == custom_year)[0]
        if len(custom_year_idx) == 0:
            continue
        custom_year_idx = custom_year_idx[0]

        new_values = baseline_values.copy()

        if custom_year_idx > 0:
            first_year = years[0]
            first_value = baseline_values[0]
            for i in range(custom_year_idx + 1):
                if years[i] == custom_year:
                    new_values[i] = custom_val
                else:
                    new_values[i] = first_value + (custom_val - first_value) * (years[i] - first_year) / (custom_year - first_year)
        else:
            new_values[0] = custom_val

        if custom_year_idx < len(years) - 1:
            last_year = years[-1]
            last_value = baseline_values[-1]
            for i in range(custom_year_idx, len(years)):
                if years[i] == custom_year:
                    new_values[i] = custom_val
                else:
                    new_values[i] = custom_val + (last_value - custom_val) * (years[i] - custom_year) / (last_year - custom_year)

        group['percent_median'] = new_values
        group['percent_median'] = group['percent_median'].clip(lower=0, upper=100)
        result_list.append(group)

    if result_list:
        result_data = pd.concat(result_list, ignore_index=True)
        result_data = result_data.drop(columns=['custom_value'])
        result_data = result_data.sort_values(['country', 'area', 'fuel', 'year']).reset_index(drop=True)
        return result_data
    else:
        return pd.DataFrame(columns=filtered_data.columns)


def update_headcount_data(selected_pop_share_df, total_pop_df):
    on_keys = ['area', 'year']
    merged_hc_df = selected_pop_share_df.merge(
        total_pop_df[['iso3', 'area', 'year', 'population']],
        on=['iso3'] + on_keys,
        how='left',
        validate='m:1'
    )
    merged_hc_df["population"] = pd.to_numeric(merged_hc_df["population"], errors='coerce')
    merged_hc_df['percent_median'] = pd.to_numeric(merged_hc_df['percent_median'], errors='coerce')
    merged_hc_df['fuel_users_median'] = merged_hc_df['percent_median'] * merged_hc_df["population"]
    merged_hc_df['fuel_users_median'] = pd.to_numeric(merged_hc_df['fuel_users_median'], errors='coerce')

    out_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'year', 'fuel_users_median']
    return merged_hc_df[out_cols]


# ----------------------------------------------------------------------------
# Load default data so filter widgets have options
# ----------------------------------------------------------------------------
load_default_data()
if st.session_state.per_capita_data is None:
    default_per_capita = load_default_per_capita_data()
    if default_per_capita is not None:
        st.session_state.per_capita_data = default_per_capita

# ----------------------------------------------------------------------------
# Sidebar filters
# ----------------------------------------------------------------------------
available_countries = sorted(st.session_state.population_share_per_fuel_df['country'].unique()) \
    if st.session_state.get('population_share_per_fuel_df') is not None else []
all_fuels_in_data = st.session_state.population_share_per_fuel_df['fuel'].unique() \
    if st.session_state.get('population_share_per_fuel_df') is not None else []
available_fuels = sorted([f for f in all_fuels_in_data if f not in ['total clean', 'total polluting']])

with st.sidebar:
    st.header("Select data parameters")
    st.caption("Pick countries, fuels, areas, and a year range — then view the relevant data on the right.")
    st.markdown("---")
    st.header("Filters")
    selected_countries = st.multiselect(
        "Countries",
        options=available_countries,
        default=[],
        key="filt_countries",
    )
    selected_fuels = st.multiselect(
        "Fuel types",
        options=available_fuels,
        default=available_fuels,
        key="filt_fuels",
    )
    if not selected_fuels:
        selected_fuels = available_fuels
    selected_areas = st.multiselect(
        "Areas",
        options=['Urban', 'Rural'],
        default=['Urban', 'Rural'],
        key="filt_areas",
    )
    if not selected_areas:
        selected_areas = ['Urban', 'Rural']
    year_range = st.slider(
        "Year range",
        min_value=1990, max_value=2050,
        value=(2020, 2030), step=1,
        key="filt_years",
    )

start_year, end_year = year_range


# ----------------------------------------------------------------------------
# Modals (definitions + conditional invocation)
# ----------------------------------------------------------------------------

# Modal: upload custom proportional fuel-use dataset
@st.dialog("Upload Custom Proportional Fuel-Use Dataset", width="large")
def show_custom_dataset_modal():
    st.markdown("### Upload Complete Fuel Proportion Dataset (Percentages)")
    st.markdown("Upload your own **proportional fuel use data** (in percentages) for **all years** to replace the default UN WHO dataset")
    st.caption("These percentages will be used to calculate headcount and fuel consumption outputs.")

    st.warning("⚠️ **Important Data Quality Notice**: Custom data should be based on robust sources supported by peer-reviewed academic literature, official government statistics, or reputable international organizations.")

    st.markdown("---")
    st.markdown("### 📚 Step 1: Describe Your Data Source")

    source_description = st.text_input(
        "Brief source description (required):",
        placeholder="e.g., IEA Energy Database 2024, Custom Regional Study, National Statistics Office",
        key="custom_source_description_input"
    )

    dataset_citation = st.text_area(
        "Full citation (required):",
        placeholder="e.g., Smith, J., Doe, A. et al. (2024). 'Global Cooking Fuel Transitions Database.' Journal of Energy Studies, 45(3), 123-145. DOI: 10.xxxx/xxxxx",
        height=100,
        key="full_dataset_citation"
    )

    source_info_complete = (source_description and len(source_description.strip()) > 0 and
                            dataset_citation and len(dataset_citation.strip()) > 0)

    st.markdown("---")
    st.markdown("### 📁 Step 2: Upload Your Data File")

    if not source_info_complete:
        st.info("ℹ️ Please complete Step 1 above before uploading your file.")

    st.markdown("#### Required Columns:")
    st.code("iso3, country, region, area, fuel, year, population_share")
    st.caption("**Note:** `population_share` values should be between 0 and 1 (e.g., 0.75 = 75%). The `region` column will be re-derived from country_codes after upload.")

    uploaded_file = st.file_uploader(
        "Choose CSV or Excel file",
        type=['csv', 'xlsx'],
        disabled=not source_info_complete
    )

    if uploaded_file and source_info_complete:
        st.success(f"✅ File '{uploaded_file.name}' uploaded")
        try:
            if uploaded_file.name.endswith('.csv'):
                preview_df = pd.read_csv(uploaded_file)
            else:
                preview_df = pd.read_excel(uploaded_file)

            st.markdown("---")
            st.markdown("### 📊 Step 3: Preview & Validate")
            st.dataframe(preview_df.head(10), use_container_width=True)

            required_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'year', 'population_share']
            missing_cols = [col for col in required_cols if col not in preview_df.columns]

            if missing_cols:
                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
            else:
                st.success("✅ All required columns found")
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✅ Load Custom Dataset", type="primary", use_container_width=True):
                        uploaded_file.seek(0)
                        if uploaded_file.name.endswith('.csv'):
                            new_df = pd.read_csv(uploaded_file)
                        else:
                            new_df = pd.read_excel(uploaded_file)
                        new_df.columns = [c.strip().lower().replace('"', '') for c in new_df.columns]
                        if 'population_share' in new_df.columns:
                            new_df = new_df.rename(columns={'population_share': 'percent_median'})
                        new_df['fuel'] = new_df['fuel'].astype(str).str.strip().str.lower()
                        new_df['fuel'] = new_df['fuel'].replace({'biomass': 'fuelwood', 'electricity': 'electric'})
                        # Re-derive region from country_codes for canonical taxonomy
                        iso3_to_region = get_iso3_to_region()
                        new_df['region'] = new_df['iso3'].map(iso3_to_region)
                        st.session_state.population_share_per_fuel_df = new_df

                        st.session_state.data_source_population_share = source_description.strip()
                        st.session_state.custom_source_description = source_description.strip()
                        st.session_state.data_source_custom_citation = dataset_citation.strip()

                        st.success("✅ Custom dataset loaded successfully!")
                        st.rerun()
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.rerun()
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")

    if not uploaded_file:
        st.markdown("---")
        if st.button("❌ Close", use_container_width=True):
            st.rerun()


# Modal: upload custom per-capita data (region-keyed)
@st.dialog("Upload Custom Per Capita Data", width="large")
def show_per_capita_modal():
    st.markdown("### Upload Per Capita Fuel Consumption Data")
    st.markdown("Upload custom per-capita consumption rates keyed by **region** and **fuel**.")
    st.caption("**Region values:** must match country_codes regions (e.g., `ssa`, `east_asia`, `south_asia`, `latam`, `other`). Leave region blank to apply a value globally — it will be expanded to all regions on load.")

    st.warning("⚠️ **Important Data Quality Notice**: Custom data should be based on robust sources supported by peer-reviewed academic literature, official government statistics, or reputable international organizations.")

    st.markdown("---")
    st.markdown("### 📚 Step 1: Describe Your Data Source")

    per_capita_source_desc = st.text_input(
        "Brief source description (required):",
        placeholder="e.g., World Bank Energy Data 2024, Regional Consumption Survey, National Energy Statistics",
        key="per_capita_source_desc_input"
    )

    per_capita_citation_input = st.text_area(
        "Full citation (required):",
        placeholder="e.g., Jones, A., Smith, B. (2024). 'Per Capita Fuel Consumption Patterns.' Energy Economics, 78(2), 45-67. DOI: 10.xxxx/xxxxx",
        height=100,
        key="per_capita_full_citation"
    )

    per_capita_source_complete = (per_capita_source_desc and len(per_capita_source_desc.strip()) > 0 and
                                  per_capita_citation_input and len(per_capita_citation_input.strip()) > 0)

    st.markdown("---")
    st.markdown("### 📁 Step 2: Upload Your Data File")

    if not per_capita_source_complete:
        st.info("ℹ️ Please complete Step 1 above before uploading your file.")

    st.markdown("#### Required Columns:")
    st.code("fuel, region, pc_fuel, pc_fuel_units")
    st.caption("**Units example:** `MWh/person-year` for electric, `oven-dry tons/person-year` for fuelwood, `tons/person-year` for others.")

    uploaded_per_capita_file = st.file_uploader(
        "Choose CSV or Excel file",
        type=['csv', 'xlsx'],
        disabled=not per_capita_source_complete,
        key="per_capita_file_uploader"
    )

    if uploaded_per_capita_file and per_capita_source_complete:
        st.success(f"✅ File '{uploaded_per_capita_file.name}' uploaded")
        try:
            if uploaded_per_capita_file.name.endswith('.csv'):
                preview_per_capita_df = pd.read_csv(uploaded_per_capita_file)
            else:
                preview_per_capita_df = pd.read_excel(uploaded_per_capita_file)

            st.markdown("---")
            st.markdown("### 📊 Step 3: Preview & Validate")
            st.dataframe(preview_per_capita_df.head(10), use_container_width=True)

            required_cols = ['fuel', 'region', 'pc_fuel', 'pc_fuel_units']
            preview_cols_lower = [c.lower() for c in preview_per_capita_df.columns]
            missing_cols = [col for col in required_cols if col not in preview_cols_lower]

            if missing_cols:
                st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
            else:
                st.success("✅ All required columns found")
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("✅ Load Custom Per Capita Data", type="primary", use_container_width=True):
                        uploaded_per_capita_file.seek(0)
                        if uploaded_per_capita_file.name.endswith('.csv'):
                            new_pc = pd.read_csv(uploaded_per_capita_file)
                        else:
                            new_pc = pd.read_excel(uploaded_per_capita_file)

                        new_pc.columns = [c.strip().lower() for c in new_pc.columns]
                        new_pc['fuel'] = new_pc['fuel'].astype(str).str.strip().str.lower()
                        new_pc['region'] = new_pc['region'].fillna('').astype(str).str.strip().str.lower()
                        new_pc['pc_fuel'] = pd.to_numeric(new_pc['pc_fuel'], errors='coerce')
                        new_pc['pc_fuel_units'] = new_pc['pc_fuel_units'].astype(str).str.strip()

                        # Expand global rows (empty region) to all regions
                        cc = load_country_codes()
                        all_regions = sorted([r for r in cc['region'].dropna().unique().tolist() if str(r).strip() != ''])
                        global_rows = new_pc[new_pc['region'] == ''].copy()
                        specific_rows = new_pc[new_pc['region'] != ''].copy()
                        if len(global_rows) > 0 and all_regions:
                            expanded = []
                            for r in all_regions:
                                g = global_rows.copy()
                                g['region'] = r
                                expanded.append(g)
                            new_pc = pd.concat([specific_rows, pd.concat(expanded, ignore_index=True)], ignore_index=True)
                        else:
                            new_pc = specific_rows

                        st.session_state.per_capita_data = new_pc.reset_index(drop=True)
                        st.session_state.data_source_per_capita = per_capita_source_desc.strip()
                        st.session_state.per_capita_source_description = per_capita_source_desc.strip()
                        st.session_state.per_capita_citation = per_capita_citation_input.strip()

                        st.success("✅ Custom per capita data loaded successfully!")
                        st.rerun()
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.rerun()
        except Exception as e:
            st.error(f"❌ Error reading file: {str(e)}")

    if not uploaded_per_capita_file:
        st.markdown("---")
        if st.button("❌ Close", use_container_width=True):
            st.rerun()


# Modal: customize year projections
@st.dialog("Customize Proportional Fuel-Use Projections", width="large")
def show_projection_modal():
    st.markdown("### Enter Proportional Fuel Use Percentages for Any Year")

    selected_custom_year = st.selectbox(
        "Select year to customize:",
        options=list(range(start_year, end_year + 1)),
        index=end_year - start_year,
    )

    st.caption(f"Your custom values for {selected_custom_year} will be linearly interpolated to the 1990 and 2050 WHO baseline data.")

    if selected_countries and selected_fuels and selected_areas:
        st.warning("⚠️ **Data Quality Notice**: Custom projections should be based on robust data supported by peer-reviewed literature, official statistics, or reputable organizations.")
        baseline_df = st.session_state.population_share_per_fuel_df
        baseline_custom_year = baseline_df[
            (baseline_df['year'] == selected_custom_year) &
            (baseline_df['country'].isin(selected_countries)) &
            (baseline_df['fuel'].isin(selected_fuels)) &
            (baseline_df['area'].isin(selected_areas))
        ][['iso3', 'country', 'region', 'area', 'fuel', 'percent_median']].copy()

        if len(baseline_custom_year) == 0:
            st.error(f"No baseline data found for {selected_custom_year} for the selected filters.")
            if st.button("Close"):
                st.rerun()
            return

        template_df = baseline_custom_year.copy()
        template_df['percent_median'] = template_df['percent_median'].round(2)
        template_df = template_df.rename(columns={'percent_median': 'population_share'})

        st.markdown("---")
        st.markdown(f"**{len(template_df)} combinations** found for your selected filters.")

        input_method = st.radio("Choose input method:", ["Data Editor", "Upload CSV"], horizontal=True)

        if input_method == "Data Editor":
            st.markdown("Edit the percentage values in the table below:")
            st.caption("**Note:** `population_share` values should be between 0 and 1.")

            edited_data = st.data_editor(
                template_df,
                disabled=['iso3', 'country', 'region', 'area', 'fuel'],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "population_share": st.column_config.NumberColumn(
                        f"Population Share for {selected_custom_year}",
                        min_value=0.0, max_value=1.0, step=0.01, format="%.2f"
                    )
                }
            )

            st.markdown("---")
            st.markdown("**📚 Data Source Citation (Required)**")
            data_source_citation = st.text_area(
                "Provide citation for your custom data:",
                placeholder="e.g., Smith et al. (2024). 'Cooking Fuel Projections for Sub-Saharan Africa.' Energy Policy Journal. DOI: 10.xxxx/xxxxx",
                height=100,
                key="custom_projection_citation"
            )

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✅ Apply Custom Projections", type="primary", use_container_width=True):
                    if edited_data['population_share'].isna().any():
                        st.error("❌ Missing values detected.")
                    elif (edited_data['population_share'] < 0).any() or (edited_data['population_share'] > 1).any():
                        st.error("❌ Population share values must be between 0 and 1.")
                    elif not data_source_citation or len(data_source_citation.strip()) == 0:
                        st.error("❌ Please provide a citation.")
                    else:
                        edited_data_internal = edited_data.rename(columns={'population_share': 'percent_median'})
                        st.session_state.custom_year_data = edited_data_internal
                        st.session_state.custom_year = selected_custom_year
                        st.session_state.custom_projection_source = data_source_citation.strip()
                        st.session_state.use_custom_projections = True
                        st.session_state.data_source_population_share = f"Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021), with Custom Projections (Year {selected_custom_year})"
                        st.success("✅ Custom projections applied!")
                        st.rerun()
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.rerun()

        else:
            st.markdown("Upload a CSV with the following columns:")
            st.code("iso3, country, region, area, fuel, population_share")

            template_csv = template_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Template CSV",
                data=template_csv,
                file_name=f"projection_template_{selected_custom_year}.csv",
                mime="text/csv",
            )

            uploaded_csv = st.file_uploader("Upload Custom Values CSV", type=['csv'])

            if uploaded_csv:
                try:
                    uploaded_df = pd.read_csv(uploaded_csv)
                    required_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'population_share']
                    if not all(col in uploaded_df.columns for col in required_cols):
                        st.error(f"❌ CSV must contain columns: {', '.join(required_cols)}")
                    else:
                        uploaded_df = uploaded_df.rename(columns={'population_share': 'percent_median'})
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
                            st.success("✅ CSV validated.")
                            st.markdown("---")
                            st.markdown("**📚 Data Source Citation (Required)**")
                            csv_data_source_citation = st.text_area(
                                "Provide citation for your custom data:",
                                height=100,
                                key="custom_projection_citation_csv"
                            )

                            col1, col2 = st.columns([1, 1])
                            with col1:
                                if st.button("✅ Apply Custom Projections", type="primary", use_container_width=True):
                                    if not csv_data_source_citation or len(csv_data_source_citation.strip()) == 0:
                                        st.error("❌ Please provide a citation.")
                                    else:
                                        st.session_state.custom_year_data = uploaded_df
                                        st.session_state.custom_year = selected_custom_year
                                        st.session_state.custom_projection_source = csv_data_source_citation.strip()
                                        st.session_state.use_custom_projections = True
                                        st.session_state.data_source_population_share = f"Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021), with Custom Projections (Year {selected_custom_year})"
                                        st.rerun()
                            with col2:
                                if st.button("❌ Cancel", use_container_width=True):
                                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error reading CSV: {str(e)}")
    else:
        st.warning("⚠️ Please select countries, fuel types, and areas before customizing projections.")
        if st.button("Close"):
            st.rerun()


# ----------------------------------------------------------------------------
# Compute shared filtered data once (used by all tabs)
# ----------------------------------------------------------------------------
if selected_countries and st.session_state.get('population_share_per_fuel_df') is not None:
    if st.session_state.get('use_custom_projections', False) and st.session_state.get('custom_year_data') is not None:
        try:
            pop_share_per_fuel_df = apply_custom_year_adjustments(
                st.session_state.population_share_per_fuel_df,
                st.session_state.custom_year_data,
                st.session_state.custom_year,
                start_year, end_year
            )
        except Exception as e:
            st.error(f"❌ Error applying custom projections: {str(e)}")
            pop_share_per_fuel_df = st.session_state.population_share_per_fuel_df
    else:
        pop_share_per_fuel_df = st.session_state.population_share_per_fuel_df

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
    filtered_headcount_data_per_fuel = filtered_headcount_data_per_fuel[
        filtered_headcount_data_per_fuel['area'].isin(['Urban', 'Rural'])
    ]
else:
    filtered_data = pd.DataFrame()
    filtered_headcount_data_per_fuel = pd.DataFrame()


# ----------------------------------------------------------------------------
# View "folder tabs": two big buttons (Inputs left, Outputs right) framing a
# bordered container below — visually like file-folder dividers.
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* --- Folder-tab buttons --- */
    .folder-tabs-wrap div[data-testid="stButton"] > button,
    .folder-tabs-wrap div[data-testid="stButton"] > button:hover,
    .folder-tabs-wrap div[data-testid="stButton"] > button:focus,
    .folder-tabs-wrap div[data-testid="stButton"] > button:active {
        height: 4.5rem !important;
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        border-radius: 14px 14px 0 0 !important;
        border: 1.5px solid #cdd0d8 !important;
        border-bottom: none !important;
        margin-bottom: 0 !important;
        padding: 1rem !important;
        position: relative;
        z-index: 1;
        box-shadow: none !important;
    }
    /* Active (primary) tab: gentle off-white, "in front" of body */
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="primary"],
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="primary"]:hover,
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="primary"]:focus,
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="primary"]:active {
        background-color: #f8f9fa !important;
        color: #1a1d23 !important;
        border-color: #cdd0d8 !important;
        z-index: 3;
    }
    /* Inactive (secondary) tab: slightly darker neutral, faded text, "behind" */
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="secondary"],
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="secondary"]:hover,
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="secondary"]:focus,
    .folder-tabs-wrap div[data-testid="stButton"] > button[kind="secondary"]:active {
        background-color: #e9ecef !important;
        color: #6c757d !important;
        border-color: #cdd0d8 !important;
    }
    /* --- Body container: matches active tab, no top border, hugs the buttons --- */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div.folder-body-marker) {
        border: 1.5px solid #cdd0d8 !important;
        border-top: none !important;
        border-radius: 0 0 14px 14px !important;
        margin-top: -2.5rem !important;
        padding: 1.5rem !important;
        background-color: #f8f9fa !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not selected_countries:
    st.info("👆 Select at least one country in the sidebar to view data.")
    st.stop()

if 'view_top_key' not in st.session_state:
    st.session_state.view_top_key = "outputs"  # auto-select Outputs

col_in, col_out = st.columns([1, 1], gap="small")
with col_in:
    if st.button(
        "✏️ See / edit input data",
        key="folder_tab_inputs",
        use_container_width=True,
        type="primary" if st.session_state.view_top_key == "inputs" else "secondary",
    ):
        st.session_state.view_top_key = "inputs"
        st.rerun()
with col_out:
    if st.button(
        "📊 Outputs",
        key="folder_tab_outputs",
        use_container_width=True,
        type="primary" if st.session_state.view_top_key == "outputs" else "secondary",
    ):
        st.session_state.view_top_key = "outputs"
        st.rerun()

view_top = "📊 Outputs" if st.session_state.view_top_key == "outputs" else "✏️ See / edit input data"

with st.container(border=True):
    st.markdown('<div class="folder-body-marker"></div>', unsafe_allow_html=True)

    if view_top.startswith("📊"):
        if not selected_countries:
            pass  # alert shown above the pills
        elif st.session_state.per_capita_data is None:
            st.warning("Per-capita data not loaded. Upload rates in the **Per-capita rates** tab.")
        elif filtered_headcount_data_per_fuel.empty:
            st.info("No data matches your filters.")
        else:
            # Compute output_df ONCE — shared by both output sub-tabs
            per_capita = st.session_state.per_capita_data
            hc = filtered_headcount_data_per_fuel.copy()
            hc['_fuel_join'] = hc['fuel'].astype(str).str.lower()
            pc_for_merge = per_capita[['region', 'fuel', 'pc_fuel', 'pc_fuel_units']].rename(
                columns={'fuel': '_fuel_join'}
            )
            final_output = hc.merge(
                pc_for_merge,
                on=['region', '_fuel_join'],
                how='left'
            ).drop(columns=['_fuel_join'])

            final_output['pc_fuel'] = pd.to_numeric(final_output['pc_fuel'], errors='coerce')
            final_output['total_fuel_cons_tons'] = final_output['fuel_users_median'] * final_output['pc_fuel']
            # Charcoal → fuelwood-equivalence multiplier is applied below, inside sub_consumption
            final_output = final_output.rename(columns={
                'fuel_users_median': 'num_fuel_users',
                'pc_fuel': 'per_capita_fuel_cons',
            })

            out_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'year',
                        'num_fuel_users', 'per_capita_fuel_cons', 'total_fuel_cons_tons']
            output_df = final_output[out_cols].copy()

            # Shared filename-sanitization charset
            illegal = '\\/:*?"<>|'

            sub_consumption, sub_emissions = st.tabs(["Total fuel consumption", "Total emissions"])

            with sub_consumption:
                st.subheader("Total fuel consumption")

                # Read the wood-to-charcoal kiln yield from session state (the input widget
                # lives in the Per-capita rates input tab — see sub_per_capita).
                try:
                    charcoal_multiplier = float(st.session_state.get("charcoal_multiplier", "6"))
                    if charcoal_multiplier < 0:
                        raise ValueError
                except (ValueError, TypeError):
                    charcoal_multiplier = 6.0

                charcoal_mask = output_df['fuel'].astype(str).str.lower() == 'charcoal'
                output_df.loc[charcoal_mask, 'total_fuel_cons_tons'] = (
                    output_df.loc[charcoal_mask, 'num_fuel_users']
                    * output_df.loc[charcoal_mask, 'per_capita_fuel_cons']
                    * charcoal_multiplier
                )

                st.write(f"Total rows: {len(output_df):,}")
                st.dataframe(output_df.head(500), hide_index=True, height=500, use_container_width=True)
                st.caption(
                    f"Showing first 500 of {len(output_df):,} rows. "
                    "**Units note:** `per_capita_fuel_cons` units vary by fuel — MWh/person-year for electric, "
                    "oven-dry tons/person-year for fuelwood and imp_fuelwood, and tons/person-year for the remaining fuels. "
                    "`total_fuel_cons_tons` inherits these per-fuel units. "
                    f"**Charcoal rows:** `total_fuel_cons_tons` is reported in **tons of fuelwood-equivalent biomass** "
                    f"(charcoal mass × {charcoal_multiplier:g} kiln-yield factor — set in the *Per-capita rates* input tab), not charcoal at the stove."
                )

                missing = output_df[output_df['per_capita_fuel_cons'].isna()]
                if len(missing) > 0:
                    with st.expander(f"⚠️ {len(missing):,} rows have no matching per-capita rate"):
                        missing_combos = missing.groupby(['region', 'fuel']).size().reset_index(name='count')
                        st.dataframe(missing_combos, hide_index=True)
                        st.caption("Check that fuel names and regions match between datasets.")

                st.markdown("---")

                st.info(
                    f"📊 **Fuel-share data**: {st.session_state.get('data_source_population_share', 'Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021)')}  \n"
                    f"📊 **Per-capita data**: {st.session_state.get('data_source_per_capita', 'Default Per Capita Data (Placeholder)')}"
                )

                # Excel download (2 sheets: Metadata + Data)
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    data_src = st.session_state.get('data_source_population_share', 'Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021)')
                    citations_list = []
                    if 'Stoner' in data_src:
                        citations_list.append(st.session_state.get('data_source_base_citation', 'N/A'))
                    custom_cite = st.session_state.get('data_source_custom_citation') or st.session_state.get('custom_projection_source')
                    if custom_cite:
                        citations_list.append(custom_cite)
                    combined_citations = ' | '.join(citations_list) if citations_list else 'N/A'

                    metadata_dict = {
                        'Field': [
                            'Tool Name',
                            'Generation Date',
                            'Year Range',
                            'Countries Analyzed',
                            'Fuel Types',
                            'Areas (Settings)',
                            'Population Share Data Source',
                            'Population Share Citations',
                            'Population Share — In-App Edits',
                            'Per Capita Data Source',
                            'Per Capita Citation',
                            'Per Capita — In-App Edits',
                            'Charcoal → Fuelwood Equivalence Factor',
                            'Units (per_capita_fuel_cons / total_fuel_cons_tons)',
                            'Notes',
                        ],
                        'Value': [
                            'Cooking Fuel Data Tool',
                            pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                            f"{start_year} - {end_year}",
                            ', '.join(selected_countries),
                            ', '.join(selected_fuels),
                            ', '.join(selected_areas),
                            data_src,
                            combined_citations,
                            'Yes (rows edited inline during this session)' if st.session_state.get('user_edited_shares') else 'No',
                            st.session_state.get('data_source_per_capita', 'Default Per Capita Data (Placeholder)'),
                            st.session_state.get('per_capita_citation') or st.session_state.get('per_capita_base_citation', 'N/A'),
                            'Yes (rows edited inline during this session)' if st.session_state.get('user_edited_per_capita') else 'No',
                            f"{charcoal_multiplier:g} (applied to charcoal total_fuel_cons_tons only)",
                            'MWh/person-year for electric; oven-dry tons/person-year for fuelwood and imp_fuelwood; tons/person-year for all other fuels.',
                            'All custom data should be supported by peer-reviewed literature or official statistics.',
                        ],
                    }
                    pd.DataFrame(metadata_dict).to_excel(writer, index=False, sheet_name='Metadata & Sources')
                    output_df.to_excel(writer, index=False, sheet_name='Fuel Consumption Data')
                buffer.seek(0)

                default_filename = f"cooking_fuel_output_{start_year}_{end_year}"
                filename_input = st.text_input(
                    "Filename (without extension)",
                    value=default_filename,
                    key="excel_filename",
                    help="Edit the name before downloading. Illegal filename characters are removed automatically.",
                )
                sanitized = ''.join(c for c in (filename_input or default_filename).strip() if c not in illegal) or default_filename
                final_name = sanitized if sanitized.lower().endswith('.xlsx') else f"{sanitized}.xlsx"

                st.download_button(
                    label="📥 Download Excel Workbook",
                    data=buffer,
                    file_name=final_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with sub_emissions:
                em_no_elec = load_em_intens_no_elec()
                em_elec = load_em_intens_electricity()

                if em_no_elec is None or em_elec is None:
                    st.error("Emissions intensity data not available.")
                else:
                    em_df = output_df.copy()
                    em_no_elec_join = em_no_elec.set_index('fuel')[['CO2', 'CH4', 'N2O']].rename(
                        columns={'CO2': 'em_intens_CO2', 'CH4': 'em_intens_CH4', 'N2O': 'em_intens_N2O'}
                    )
                    em_df = em_df.join(em_no_elec_join, on='fuel', how='left')

                    # Override electricity rows with per-country values
                    elec_mask = em_df['fuel'].astype(str).str.lower() == 'electric'
                    if elec_mask.any():
                        elec_intens = em_elec.set_index('iso3')[['CO2', 'CH4', 'N2O']]
                        for ghg in ['CO2', 'CH4', 'N2O']:
                            em_df.loc[elec_mask, f'em_intens_{ghg}'] = em_df.loc[elec_mask, 'iso3'].map(elec_intens[ghg])

                    # Compute totals
                    for ghg in ['CO2', 'CH4', 'N2O']:
                        em_df[f'total_{ghg}'] = em_df['total_fuel_cons_tons'] * em_df[f'em_intens_{ghg}']

                    em_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'year',
                               'num_fuel_users', 'total_fuel_cons_tons',
                               'em_intens_CO2', 'em_intens_CH4', 'em_intens_N2O',
                               'total_CO2', 'total_CH4', 'total_N2O']
                    em_output_df = em_df[em_cols].copy()

                    # Aggregate by country / area / year (sum across fuels) and compute CO2-eq
                    summary_group_cols = ['iso3', 'country', 'region', 'area', 'year']
                    em_summary_df = (
                        em_df.groupby(summary_group_cols, dropna=False, as_index=False)[
                            ['total_CO2', 'total_CH4', 'total_N2O']
                        ].sum(min_count=1)
                    )
                    em_summary_df['total_CO2eq'] = (
                        em_summary_df['total_CO2'].fillna(0)
                        + GWP_CH4 * em_summary_df['total_CH4'].fillna(0)
                        + GWP_N2O * em_summary_df['total_N2O'].fillna(0)
                    )

                    st.subheader("Total emissions")
                    em_view = st.radio(
                        "Table view",
                        options=["Per-fuel detail", "Country / area summary (CO₂-eq)"],
                        horizontal=True,
                        key="emissions_view",
                    )

                    if em_view == "Per-fuel detail":
                        st.write(f"Total rows: {len(em_output_df):,}")
                        st.dataframe(em_output_df.head(500), hide_index=True, height=500, use_container_width=True)
                        st.caption(
                            f"Showing first 500 of {len(em_output_df):,} rows. "
                            "**Calculation:** `total_GHG = total_fuel_cons_tons × em_intens_GHG` per row. "
                            "**Units:** all `total_*` columns are in **tons of GHG**. "
                            "Non-electric: intensities are mass ratios (kg GHG / kg fuel = tons/ton). "
                            "Electric: source values are gCO2/kWh and divided by 1000 at load (= tons CO2 / MWh), so the multiplication directly yields tons. "
                            "**CH4 and N2O for electricity are 0** — country-level data not available; those gases contribute <5% of CO2-eq for most grids."
                        )
                    else:
                        st.write(f"Total rows: {len(em_summary_df):,}")
                        st.dataframe(em_summary_df.head(500), hide_index=True, height=500, use_container_width=True)
                        st.caption(
                            f"Showing first 500 of {len(em_summary_df):,} rows. "
                            "Aggregated by country / area / year, summing emissions across all fuels. "
                            f"**`total_CO2eq` = total_CO2 + {GWP_CH4} × total_CH4 + {GWP_N2O} × total_N2O** "
                            "(IPCC AR5 GWP-100, the UNFCCC Enhanced Transparency Framework default). "
                            "**Units:** all columns in **tons**."
                        )

                    missing_em = em_output_df[em_output_df['em_intens_CO2'].isna()]
                    if len(missing_em) > 0:
                        with st.expander(f"⚠️ {len(missing_em):,} rows have no matching emissions intensity"):
                            missing_em_summary = missing_em.groupby(['fuel']).size().reset_index(name='count')
                            st.dataframe(missing_em_summary, hide_index=True)
                            st.caption("Likely cause: the fuel name is not present in either emissions-intensity file.")

                    st.markdown("---")

                    st.info(
                        "📊 **Non-electric emissions intensity**: per-fuel intensities for all countries (Electricity row ignored — handled separately)  \n"
                        "📊 **Electricity emissions intensity**: per-country Combined Margin grid emission factor (CO2 only; CH4 and N2O set to 0). "
                        "Source: [UNFCCC — IFI TWG List of Methodologies](https://unfccc.int/climate-action/sectoral-engagement/ifis-harmonization-of-standards-for-ghg-accounting/ifi-twg-list-of-methodologies)."
                    )

                    # Excel download (2 sheets: Metadata + Data)
                    em_buffer = BytesIO()
                    with pd.ExcelWriter(em_buffer, engine='openpyxl') as writer:
                        em_metadata = {
                            'Field': [
                                'Tool Name',
                                'Generation Date',
                                'Year Range',
                                'Countries Analyzed',
                                'Fuel Types',
                                'Areas (Settings)',
                                'Non-Electric Emissions Source',
                                'Electricity Emissions Source',
                                'Charcoal → Fuelwood Equivalence Factor',
                                'Calculation',
                                'CO2-eq Calculation',
                                'GWP Source',
                                'Notes',
                            ],
                            'Value': [
                                'Cooking Fuel Data Tool',
                                pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                                f"{start_year} - {end_year}",
                                ', '.join(selected_countries),
                                ', '.join(selected_fuels),
                                ', '.join(selected_areas),
                                'Per-fuel emissions intensities for all countries (Electricity row ignored)',
                                'Per-country Combined Margin grid emission factor, gCO2/kWh; CO2 only — CH4/N2O set to 0. Source: UNFCCC — IFI TWG List of Methodologies (https://unfccc.int/climate-action/sectoral-engagement/ifis-harmonization-of-standards-for-ghg-accounting/ifi-twg-list-of-methodologies)',
                                f"{charcoal_multiplier:g} (applied to charcoal total_fuel_cons_tons only)",
                                'total_GHG = total_fuel_cons_tons × em_intens_GHG',
                                f'total_CO2eq = total_CO2 + {GWP_CH4} × total_CH4 + {GWP_N2O} × total_N2O',
                                'IPCC AR5 GWP-100 (UNFCCC Enhanced Transparency Framework default, post-2024)',
                                'All total_* columns are in tons of GHG. Non-electric: intensities are mass ratios (kg/kg). Electric: source gCO2/kWh / 1000 = tons CO2 / MWh, applied to total_fuel_cons_tons (MWh for electric rows). CH4 and N2O for electricity are 0 (data unavailable; <5% of CO2-eq). The "Summary by Country-Area" sheet aggregates emissions across all fuels per country/area/year.',
                            ],
                        }
                        pd.DataFrame(em_metadata).to_excel(writer, index=False, sheet_name='Metadata & Sources')
                        em_output_df.to_excel(writer, index=False, sheet_name='Total Emissions')
                        em_summary_df.to_excel(writer, index=False, sheet_name='Summary by Country-Area')
                    em_buffer.seek(0)

                    em_default_filename = f"cooking_fuel_emissions_{start_year}_{end_year}"
                    em_filename_input = st.text_input(
                        "Filename (without extension)",
                        value=em_default_filename,
                        key="emissions_filename",
                        help="Edit the name before downloading. Illegal filename characters are removed automatically.",
                    )
                    em_sanitized = ''.join(c for c in (em_filename_input or em_default_filename).strip() if c not in illegal) or em_default_filename
                    em_final_name = em_sanitized if em_sanitized.lower().endswith('.xlsx') else f"{em_sanitized}.xlsx"

                    st.download_button(
                        label="📥 Download Emissions Excel Workbook",
                        data=em_buffer,
                        file_name=em_final_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )



    else:
        sub_shares, sub_per_capita = st.tabs(["Fuel shares", "Per-capita rates"])

        with sub_shares:
            if not selected_countries:
                pass  # alert shown above the pills
            else:
                data_source = st.session_state.get('data_source_population_share', 'Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021)')
                base_citation = st.session_state.get('data_source_base_citation')
                custom_citation = st.session_state.get('data_source_custom_citation') or st.session_state.get('custom_projection_source')
                has_custom_dataset = st.session_state.get('custom_source_description') is not None
                is_custom = has_custom_dataset or "Custom" in data_source

                st.subheader("Filtered fuel-share data")
                st.caption("% of population using each fuel, by country, region, area, fuel, and year. **Edit cells directly or paste from Excel, then click Save.**")
                if filtered_data.empty:
                    st.info("No data matches your filters.")
                else:
                    display_share = filtered_data[['iso3', 'country', 'region', 'area', 'fuel', 'year', 'percent_median']].copy()
                    display_share = display_share.rename(columns={'percent_median': 'population_share'}).reset_index(drop=True)
                    st.write(f"Total rows: {len(display_share):,}")

                    if len(display_share) > 8000:
                        st.warning("Too many rows for inline editing — narrow your filters (fewer countries, shorter year range) to enable editing. Showing read-only view.")
                        st.dataframe(display_share.head(500), height=400, hide_index=True)
                        st.caption(f"Showing first 500 of {len(display_share):,} rows.")
                    else:
                        edited_shares = st.data_editor(
                            display_share,
                            height=400,
                            hide_index=True,
                            disabled=['iso3', 'country', 'region', 'area', 'fuel', 'year'],
                            num_rows="fixed",
                            key=f"shares_editor_{len(display_share)}",
                            column_config={
                                "population_share": st.column_config.NumberColumn(
                                    "population_share",
                                    min_value=0.0, max_value=1.0, step=0.01, format="%.4f",
                                    help="Share of population using this fuel (0–1)",
                                )
                            },
                            use_container_width=True,
                        )
                        if st.button("💾 Save edits", key="save_shares", type="primary"):
                            edits = edited_shares.rename(columns={'population_share': 'percent_median'})
                            edits = edits.dropna(subset=['percent_median'])
                            master = st.session_state.population_share_per_fuel_df.copy()
                            keys = ['iso3', 'area', 'fuel', 'year']
                            edits_idx = edits.set_index(keys)['percent_median']
                            master = master.set_index(keys)
                            master.loc[edits_idx.index.intersection(master.index), 'percent_median'] = edits_idx
                            st.session_state.population_share_per_fuel_df = master.reset_index()
                            st.session_state.user_edited_shares = True
                            st.success(f"Applied {len(edits):,} edits to fuel-share data.")
                            st.rerun()

                st.markdown("---")

                # Source ribbon (below table)
                edit_suffix = " — **with in-app edits**" if st.session_state.get('user_edited_shares') else ""
                if is_custom or st.session_state.get('user_edited_shares'):
                    st.warning(f"📊 **Data Source**: {data_source}{edit_suffix}")
                else:
                    st.info(f"📊 **Data Source**: {data_source}")

                with st.expander("📚 View Full Citations", expanded=False):
                    if has_custom_dataset:
                        st.markdown("**Data Citation:**")
                        st.markdown(custom_citation)
                    elif "Stoner" in data_source:
                        st.markdown("**Base Data Citation:**")
                        st.markdown(base_citation)
                        if custom_citation:
                            st.markdown("---")
                            st.markdown("**Custom Projection Citation:**")
                            st.markdown(custom_citation)

                if st.session_state.get('use_custom_projections', False):
                    cy = st.session_state.get('custom_year', 'N/A')
                    st.success(f"✅ Using Custom Projections: All years linearly interpolated based on custom values for {cy}")

                # Edit-data buttons (below ribbon)
                st.markdown("##### Customize the proportional fuel-use data")
                bcols = st.columns([1, 1, 1, 1])
                with bcols[0]:
                    if st.button("📤 Upload custom dataset", use_container_width=True):
                        show_custom_dataset_modal()
                with bcols[1]:
                    if st.button("📈 Customize year projections", use_container_width=True):
                        show_projection_modal()
                with bcols[2]:
                    if st.session_state.get('custom_source_description'):
                        if st.button("🔄 Revert to default WHO data", use_container_width=True):
                            load_default_data()
                            st.session_state.data_source_population_share = "Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021)"
                            st.session_state.data_source_custom_citation = None
                            st.session_state.custom_source_description = None
                            st.rerun()
                with bcols[3]:
                    if st.session_state.get('use_custom_projections', False):
                        if st.button("🔄 Clear custom projections", use_container_width=True):
                            st.session_state.use_custom_projections = False
                            st.session_state.custom_year_data = None
                            st.session_state.custom_year = None
                            st.session_state.custom_projection_source = None
                            st.session_state.data_source_population_share = "Updated UN WHO data from O. Stoner (methods: Stoner et al. 2021)"
                            st.rerun()


        # --- Tab 2: Per-capita rates ---

        with sub_per_capita:
            if st.session_state.per_capita_data is None:
                st.warning("Per-capita data not loaded.")
                if st.button("📤 Upload custom rates", key="pc_upload_empty"):
                    show_per_capita_modal()
            else:
                per_capita_source = st.session_state.get('data_source_per_capita', 'Default Per Capita Data (Placeholder)')
                per_capita_base_cite = st.session_state.get('per_capita_base_citation')
                per_capita_custom_cite = st.session_state.get('per_capita_citation')
                has_custom_per_capita = st.session_state.get('per_capita_source_description') is not None

                st.subheader("Per-capita rates by region and fuel")
                st.caption("Each value is per fuel user per year. Rows from the source data with no region apply globally — they have been expanded to all regions. **Edit cells directly or paste from Excel, then click Save.**")

                per_cap_display = st.session_state.per_capita_data.copy()
                if selected_fuels:
                    per_cap_display = per_cap_display[per_cap_display['fuel'].isin(selected_fuels)]
                per_cap_display = per_cap_display.sort_values(['fuel', 'region']).reset_index(drop=True)
                st.write(f"Total rows: {len(per_cap_display):,}")

                edited_pc = st.data_editor(
                    per_cap_display,
                    hide_index=True,
                    height=400,
                    disabled=['fuel', 'region', 'pc_fuel_units'],
                    num_rows="fixed",
                    key=f"pc_editor_{len(per_cap_display)}",
                    column_config={
                        "pc_fuel": st.column_config.NumberColumn(
                            "pc_fuel",
                            min_value=0.0, step=0.01, format="%.4f",
                            help="Per-capita consumption (units shown in pc_fuel_units column)",
                        )
                    },
                    use_container_width=True,
                )
                if st.button("💾 Save edits", key="save_pc", type="primary"):
                    edits = edited_pc[['fuel', 'region', 'pc_fuel']].dropna(subset=['pc_fuel'])
                    master = st.session_state.per_capita_data.copy()
                    keys = ['fuel', 'region']
                    edits_idx = edits.set_index(keys)['pc_fuel']
                    master = master.set_index(keys)
                    master.loc[edits_idx.index.intersection(master.index), 'pc_fuel'] = edits_idx
                    st.session_state.per_capita_data = master.reset_index()
                    st.session_state.user_edited_per_capita = True
                    st.success(f"Applied {len(edits):,} edits to per-capita data.")
                    st.rerun()

                st.markdown("---")

                # Wood-to-charcoal kiln yield (applied to charcoal totals in the Outputs tab)
                hcol, icol, _ = st.columns([3, 1, 6], gap="small", vertical_alignment="bottom")
                with hcol:
                    st.markdown("##### Wood-to-charcoal kiln yield")
                with icol:
                    st.text_input(
                        "Wood-to-charcoal kiln yield",
                        value="6",
                        key="charcoal_multiplier",
                        label_visibility="collapsed",
                        help=(
                            "Kilograms of dry wood needed to produce 1 kg of charcoal in a kiln. "
                            "In the Outputs tab, charcoal rows of `total_fuel_cons_tons` are multiplied by this factor "
                            "so they represent the upstream wood biomass that was felled and burned to make the charcoal — "
                            "the right number for forest-impact / biomass-supply analyses. "
                            "Default 6 reflects a typical traditional earthen-kiln yield in sub-Saharan Africa (FAO regional reference). "
                            "More efficient kilns: 3–5. Use 1 to keep charcoal as stove-side mass."
                        ),
                    )
                st.caption(
                    "**Why this matters:** charcoal kilns waste most of their input wood as heat. "
                    "A factor of 6 means producing 1 ton of charcoal consumes ~6 tons of dry wood. "
                    "In the Outputs tab, charcoal rows of `total_fuel_cons_tons` count this upstream "
                    "wood biomass, not charcoal mass at the stove."
                    "Wood-to-charcoal conversion efficiencies vary widely. The recent [UNFCCC fNRB "
                    "assessment](https://cdm.unfccc.int/DNA/fNRB/index.html), which was used to derive "
                    "the data in UNFCCC's [Tool33](https://cdm.unfccc.int/methodologies/PAmethodologies/tools/am-tool-33-v3.pdf) "
                    "used 6:1, which we use here as a default. Any alternate entry should be " \
                    "supported by a well-documented field-based assessment." 
                )

                st.markdown("---")

                # Source ribbon (below table)
                pc_edit_suffix = " — **with in-app edits**" if st.session_state.get('user_edited_per_capita') else ""
                if has_custom_per_capita or st.session_state.get('user_edited_per_capita'):
                    st.warning(f"📊 **Per Capita Data Source**: {per_capita_source}{pc_edit_suffix}")
                else:
                    st.info(f"📊 **Per Capita Data Source**: {per_capita_source}")

                with st.expander("📚 View Per Capita Citation", expanded=False):
                    if has_custom_per_capita:
                        st.markdown("**Per Capita Data Citation:**")
                        st.markdown(per_capita_custom_cite)
                    else:
                        st.markdown("**Default Per Capita Data:**")
                        st.markdown(per_capita_base_cite)

                # Edit-data buttons (below ribbon)
                st.markdown("##### Customize the per-capita rates")
                bcols = st.columns([1, 1, 2])
                with bcols[0]:
                    if st.button("📤 Upload custom rates", use_container_width=True, key="pc_upload"):
                        show_per_capita_modal()
                with bcols[1]:
                    if st.session_state.get('per_capita_source_description'):
                        if st.button("🔄 Revert to defaults", use_container_width=True, key="pc_revert"):
                            default_pc = load_default_per_capita_data()
                            if default_pc is not None:
                                st.session_state.per_capita_data = default_pc
                            st.session_state.data_source_per_capita = "Default Per Capita Data (Placeholder)"
                            st.session_state.per_capita_citation = None
                            st.session_state.per_capita_source_description = None
                            st.rerun()


        # --- Tab 3: Total fuel consumption ---
# Footer
st.markdown("---")
st.caption("Cooking Fuel Data Tool - Projecting cooking fuel demand from 1990 to 2050")
