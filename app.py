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
if 'data_source_population_share' not in st.session_state:
    st.session_state.data_source_population_share = "UN WHO Data from Stoner et al. 2021"
if 'data_source_base_citation' not in st.session_state:
    st.session_state.data_source_base_citation = "Stoner, O., Shaddick, G., Economou, T. et al. Global household energy model: a multivariate hierarchical approach to estimating trends in the use of polluting and clean fuels for cooking. Nat Commun 12, 5795 (2021). https://doi.org/10.1038/s41467-021-26036-x"
if 'data_source_custom_citation' not in st.session_state:
    st.session_state.data_source_custom_citation = None
if 'custom_source_description' not in st.session_state:
    st.session_state.custom_source_description = None
if 'data_source_per_capita' not in st.session_state:
    st.session_state.data_source_per_capita = "Default Per Capita Data (Placeholder)"
if 'per_capita_base_citation' not in st.session_state:
    st.session_state.per_capita_base_citation = "[Citation pending - placeholder data]"
if 'per_capita_source_description' not in st.session_state:
    st.session_state.per_capita_source_description = None
if 'custom_projection_source' not in st.session_state:
    st.session_state.custom_projection_source = None

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
st.sidebar.header("Select Countries and Years")

# Load default data to get available countries
load_default_data()
default_pop_share_data = load_default_data()
available_countries = sorted(st.session_state.population_share_per_fuel_df['country'].unique())
selected_countries = st.sidebar.multiselect(
    "Select Countries",
    options=available_countries if available_countries else ["Upload data to see countries"],
    default=[]
)

# Get available fuel types from data, excluding category totals
if st.session_state.population_share_per_fuel_df is not None:
    all_fuels = st.session_state.population_share_per_fuel_df['fuel'].unique()
    # Filter out Total Clean and Total Polluting categories
    available_fuels = sorted([f for f in all_fuels if f not in ['Total Clean', 'Total Polluting']])
else:
    available_fuels = []

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
st.sidebar.header("Customize Proportional Fuel-Use Data")
st.sidebar.caption("OPTIONAL")

# Option A: Upload full custom dataset
with st.sidebar.expander("📤 Option A: Upload Custom Dataset", expanded=False):
    st.markdown("Replace all default data with your own complete dataset")

    # Initialize session state for custom dataset modal
    if 'show_custom_dataset_modal' not in st.session_state:
        st.session_state.show_custom_dataset_modal = False

    if st.button("📤 Upload Custom Dataset", help="Upload complete fuel proportion data for all years", use_container_width=True):
        st.session_state.show_custom_dataset_modal = True

    # Show indicator if custom dataset is loaded
    current_source = st.session_state.get('data_source_population_share', '')
    if st.session_state.get('custom_source_description'):
        st.success(f"✅ Using: {current_source}")
        if st.button("🔄 Revert to Default UN WHO Data", use_container_width=True):
            # Reload default data
            load_default_data()
            st.session_state.data_source_population_share = "UN WHO Data from Stoner et al. 2021"
            st.session_state.data_source_custom_citation = None
            st.session_state.custom_source_description = None
            st.rerun()

# Option B: Customize end year projections (moved from section 4)
if end_year > 2025:
    with st.sidebar.expander("📊 Option B: Customize Year Projections", expanded=False):
        st.markdown(f"Enter custom values for any year within range")
        st.markdown("All years will be scaled proportionally based on your adjustments")

        # Initialize session state for custom projections
        if 'custom_year_data' not in st.session_state:
            st.session_state.custom_year_data = None
        if 'custom_year' not in st.session_state:
            st.session_state.custom_year = None
        if 'use_custom_projections' not in st.session_state:
            st.session_state.use_custom_projections = False

        # Button to open customization modal
        if st.button("📊 Customize Year Projections", help=f"Enter custom percentage values for any year to shift all projections", use_container_width=True):
            st.session_state.show_projection_modal = True

        # Clear custom data button
        if st.session_state.use_custom_projections:
            if st.button("🔄 Clear Custom Projections", help="Revert to default data", use_container_width=True):
                st.session_state.custom_year_data = None
                st.session_state.custom_year = None
                st.session_state.custom_projection_source = None
                st.session_state.use_custom_projections = False
                st.session_state.data_source_population_share = "UN WHO Data from Stoner et al. 2021"
                st.session_state.show_projection_modal = False
                st.rerun()

st.sidebar.header("Per Capita Fuel Consumption")
st.sidebar.caption("OPTIONAL")

# Load default per capita data if not already loaded
if st.session_state.per_capita_data is None:
    default_per_capita = load_default_per_capita_data()
    if default_per_capita is not None:
        st.session_state.per_capita_data = default_per_capita
        st.sidebar.info("Using default per capita values (placeholder)")

# Initialize session state for per capita modal
if 'show_per_capita_modal' not in st.session_state:
    st.session_state.show_per_capita_modal = False

if st.sidebar.button("📊 Upload Custom Per Capita Data", help="Upload custom per capita fuel consumption data", use_container_width=True):
    st.session_state.show_per_capita_modal = True

# Show indicator if custom per capita data is loaded
per_capita_source = st.session_state.get('data_source_per_capita', '')
if st.session_state.get('per_capita_source_description'):
    st.sidebar.success(f"✅ Using: {per_capita_source}")
    if st.sidebar.button("🔄 Revert to Default Per Capita Data", use_container_width=True):
        # Reload default data
        default_per_capita = load_default_per_capita_data()
        if default_per_capita is not None:
            st.session_state.per_capita_data = default_per_capita
        st.session_state.data_source_per_capita = "Default Per Capita Data (Placeholder)"
        st.session_state.per_capita_citation = None
        st.session_state.per_capita_source_description = None
        st.rerun()


def apply_custom_year_adjustments(baseline_data, custom_year_data, custom_year, start_year, end_year):
    """
    Apply proportional scaling to all years based on the ratio between custom and default values for a specific year.

    Parameters:
    - baseline_data: DataFrame with population share data
    - custom_year_data: DataFrame with user-entered values for custom_year
                       columns: iso3, country, region, area, fuel, percent_median
    - custom_year: The year for which custom values are provided
    - start_year: Starting year for output
    - end_year: Ending year for output

    Returns:
    - DataFrame with proportionally scaled values for all years in the range

    Note: Uses proportional scaling (new_value = old_value × scaling_factor) where
    scaling_factor = custom_value / baseline_value. This maintains relative trends
    and naturally keeps values within valid bounds.
    """

    # Prepare merge columns
    merge_cols = ['iso3', 'country', 'region', 'area', 'fuel']

    # Get the baseline data for the custom year
    baseline_custom_year = baseline_data[baseline_data['year'] == custom_year].copy()
    baseline_custom_year = baseline_custom_year[merge_cols + ['percent_median', 'percent_lower95', 'percent_upper95']].rename(
        columns={
            'percent_median': 'baseline_median',
            'percent_lower95': 'baseline_lower95',
            'percent_upper95': 'baseline_upper95'
        }
    )

    # Prepare custom year data
    custom_year_data = custom_year_data.copy()
    custom_year_data = custom_year_data[merge_cols + ['percent_median']].rename(
        columns={'percent_median': 'custom_median'}
    )

    # Merge to compute the scaling factor
    merged = baseline_custom_year.merge(custom_year_data, on=merge_cols, how='inner')

    # Compute the scaling factor (with protection against division by zero)
    # If baseline is 0, we'll use additive shift instead for that specific case
    merged['scaling_factor'] = np.where(
        merged['baseline_median'] > 0.001,  # Use small threshold to avoid division issues
        merged['custom_median'] / merged['baseline_median'],
        np.nan  # Will handle separately
    )

    # For cases where baseline is ~0, compute an additive shift instead
    merged['additive_shift'] = np.where(
        merged['baseline_median'] <= 0.001,
        merged['custom_median'] - merged['baseline_median'],
        0
    )

    # Get all data for the selected year range
    filtered_data = baseline_data[
        (baseline_data['year'] >= start_year) &
        (baseline_data['year'] <= end_year)
    ].copy()

    # Filter to only include combinations that have custom values
    filtered_data = filtered_data.merge(
        merged[merge_cols].drop_duplicates(),
        on=merge_cols,
        how='inner'
    )

    # Merge the scaling factor and additive shift with all years
    scaled_data = filtered_data.merge(
        merged[merge_cols + ['scaling_factor', 'additive_shift']],
        on=merge_cols,
        how='left'
    )

    # Apply proportional scaling or additive shift depending on baseline value
    for col in ['percent_median', 'percent_lower95', 'percent_upper95']:
        # Where we have a valid scaling factor, multiply
        scaled_data[col] = np.where(
            scaled_data['scaling_factor'].notna(),
            scaled_data[col] * scaled_data['scaling_factor'],
            scaled_data[col] + scaled_data['additive_shift']  # Otherwise add
        )

    # Ensure percentages stay within valid range [0, 100]
    for col in ['percent_median', 'percent_lower95', 'percent_upper95']:
        scaled_data[col] = scaled_data[col].clip(lower=0, upper=100)

    # Drop the temporary columns and return
    scaled_data = scaled_data.drop(columns=['scaling_factor', 'additive_shift'])
    scaled_data = scaled_data.sort_values(['country', 'area', 'fuel', 'year']).reset_index(drop=True)

    return scaled_data


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

# Modal for uploading custom dataset
if 'show_custom_dataset_modal' in st.session_state and st.session_state.show_custom_dataset_modal:
    @st.dialog("Upload Custom Dataset", width="large")
    def show_custom_dataset_modal():
        st.markdown("### Upload Complete Fuel Proportion Dataset")
        st.markdown("Upload your own data for **all years** to replace the default UN WHO dataset")

        st.warning("⚠️ **Important Data Quality Notice**: Custom data should be based on robust sources supported by peer-reviewed academic literature, official government statistics, or reputable international organizations.")

        # STEP 1: Source description and citation (BEFORE file upload)
        st.markdown("---")
        st.markdown("### 📚 Step 1: Describe Your Data Source")
        st.markdown("Please provide source information before uploading your file.")

        source_description = st.text_input(
            "Brief source description (required):",
            placeholder="e.g., IEA Energy Database 2024, Custom Regional Study, National Statistics Office",
            help="This will appear in the data source ribbon (keep it concise)",
            key="custom_source_description_input"
        )

        dataset_citation = st.text_area(
            "Full citation (required):",
            placeholder="e.g., Smith, J., Doe, A. et al. (2024). 'Global Cooking Fuel Transitions Database.' Journal of Energy Studies, 45(3), 123-145. DOI: 10.xxxx/xxxxx",
            help="Include authors, year, title, journal/source, volume/issue, pages, and DOI/URL if available",
            height=100,
            key="full_dataset_citation"
        )

        # Check if source info is provided
        source_info_complete = (source_description and len(source_description.strip()) > 0 and
                                dataset_citation and len(dataset_citation.strip()) > 0)

        # STEP 2: File upload (enabled only if source info provided)
        st.markdown("---")
        st.markdown("### 📁 Step 2: Upload Your Data File")

        if not source_info_complete:
            st.info("ℹ️ Please complete Step 1 above before uploading your file.")

        st.markdown("#### Required Columns:")
        st.code("iso3, country, region, area, fuel, year, percent_median, percent_lower95, percent_upper95")

        # File uploader (always shown, but with guidance)
        uploaded_file = st.file_uploader(
            "Choose CSV or Excel file",
            type=['csv', 'xlsx'],
            help="Must contain all required columns listed above",
            disabled=not source_info_complete
        )

        # STEP 3: Preview and validation
        if uploaded_file and source_info_complete:
            st.success(f"✅ File '{uploaded_file.name}' uploaded")

            # Show preview
            try:
                if uploaded_file.name.endswith('.csv'):
                    preview_df = pd.read_csv(uploaded_file)
                else:
                    preview_df = pd.read_excel(uploaded_file)

                st.markdown("---")
                st.markdown("### 📊 Step 3: Preview & Validate")
                st.markdown("#### Data Preview (first 10 rows):")
                st.dataframe(preview_df.head(10), use_container_width=True)

                # Validate columns
                required_cols = ['iso3', 'country', 'region', 'area', 'fuel', 'year', 'percent_median', 'percent_lower95', 'percent_upper95']
                missing_cols = [col for col in required_cols if col not in preview_df.columns]

                if missing_cols:
                    st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                else:
                    st.success("✅ All required columns found")

                    # Action buttons
                    st.markdown("---")
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        if st.button("✅ Load Custom Dataset", type="primary", use_container_width=True):
                            # Load the data
                            uploaded_file.seek(0)  # Reset file pointer
                            if uploaded_file.name.endswith('.csv'):
                                st.session_state.population_share_per_fuel_df = pd.read_csv(uploaded_file)
                            else:
                                st.session_state.population_share_per_fuel_df = pd.read_excel(uploaded_file)

                            # Clean up column names
                            st.session_state.population_share_per_fuel_df.columns = [
                                c.strip().lower().replace('"','')
                                for c in st.session_state.population_share_per_fuel_df.columns
                            ]

                            # Store metadata
                            st.session_state.data_source_population_share = source_description.strip()
                            st.session_state.custom_source_description = source_description.strip()
                            st.session_state.data_source_custom_citation = dataset_citation.strip()
                            st.session_state.show_custom_dataset_modal = False

                            st.success("✅ Custom dataset loaded successfully!")
                            st.rerun()

                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state.show_custom_dataset_modal = False
                            st.rerun()

            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")

        # Show close button if no file uploaded yet
        if not uploaded_file:
            st.markdown("---")
            if st.button("❌ Close", use_container_width=True):
                st.session_state.show_custom_dataset_modal = False
                st.rerun()

    show_custom_dataset_modal()

# Modal for uploading custom per capita data
if 'show_per_capita_modal' in st.session_state and st.session_state.show_per_capita_modal:
    @st.dialog("Upload Custom Per Capita Data", width="large")
    def show_per_capita_modal():
        st.markdown("### Upload Per Capita Fuel Consumption Data")
        st.markdown("Upload custom per capita consumption values (tons per person)")

        st.warning("⚠️ **Important Data Quality Notice**: Custom data should be based on robust sources supported by peer-reviewed academic literature, official government statistics, or reputable international organizations.")

        # STEP 1: Source description and citation (BEFORE file upload)
        st.markdown("---")
        st.markdown("### 📚 Step 1: Describe Your Data Source")
        st.markdown("Please provide source information before uploading your file.")

        per_capita_source_desc = st.text_input(
            "Brief source description (required):",
            placeholder="e.g., World Bank Energy Data 2024, Regional Consumption Survey, National Energy Statistics",
            help="This will be included in the data source tracking (keep it concise)",
            key="per_capita_source_desc_input"
        )

        per_capita_citation_input = st.text_area(
            "Full citation (required):",
            placeholder="e.g., Jones, A., Smith, B. (2024). 'Per Capita Fuel Consumption Patterns.' Energy Economics, 78(2), 45-67. DOI: 10.xxxx/xxxxx",
            help="Include authors, year, title, journal/source, volume/issue, pages, and DOI/URL if available",
            height=100,
            key="per_capita_full_citation"
        )

        # Check if source info is provided
        per_capita_source_complete = (per_capita_source_desc and len(per_capita_source_desc.strip()) > 0 and
                                      per_capita_citation_input and len(per_capita_citation_input.strip()) > 0)

        # STEP 2: File upload (enabled only if source info provided)
        st.markdown("---")
        st.markdown("### 📁 Step 2: Upload Your Data File")

        if not per_capita_source_complete:
            st.info("ℹ️ Please complete Step 1 above before uploading your file.")

        st.markdown("#### Required Columns:")
        st.code("iso3, country, area, fuel, per_capita_tons")
        st.caption("Note: 'area' should be 'Urban' or 'Rural', 'fuel' should match fuel types in your dataset")

        # File uploader (always shown, but disabled until source info provided)
        uploaded_per_capita_file = st.file_uploader(
            "Choose CSV or Excel file",
            type=['csv', 'xlsx'],
            help="Must contain all required columns listed above",
            disabled=not per_capita_source_complete,
            key="per_capita_file_uploader"
        )

        # STEP 3: Preview and validation
        if uploaded_per_capita_file and per_capita_source_complete:
            st.success(f"✅ File '{uploaded_per_capita_file.name}' uploaded")

            # Show preview
            try:
                if uploaded_per_capita_file.name.endswith('.csv'):
                    preview_per_capita_df = pd.read_csv(uploaded_per_capita_file)
                else:
                    preview_per_capita_df = pd.read_excel(uploaded_per_capita_file)

                st.markdown("---")
                st.markdown("### 📊 Step 3: Preview & Validate")
                st.markdown("#### Data Preview (first 10 rows):")
                st.dataframe(preview_per_capita_df.head(10), use_container_width=True)

                # Validate columns
                required_cols = ['iso3', 'country', 'area', 'fuel', 'per_capita_tons']
                # Make column check case-insensitive
                preview_cols_lower = [c.lower() for c in preview_per_capita_df.columns]
                missing_cols = [col for col in required_cols if col.lower() not in preview_cols_lower]

                if missing_cols:
                    st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                else:
                    st.success("✅ All required columns found")

                    # Action buttons
                    st.markdown("---")
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        if st.button("✅ Load Custom Per Capita Data", type="primary", use_container_width=True):
                            # Load the data
                            uploaded_per_capita_file.seek(0)  # Reset file pointer
                            if uploaded_per_capita_file.name.endswith('.csv'):
                                st.session_state.per_capita_data = pd.read_csv(uploaded_per_capita_file)
                            else:
                                st.session_state.per_capita_data = pd.read_excel(uploaded_per_capita_file)

                            # Store metadata
                            st.session_state.data_source_per_capita = per_capita_source_desc.strip()
                            st.session_state.per_capita_source_description = per_capita_source_desc.strip()
                            st.session_state.per_capita_citation = per_capita_citation_input.strip()
                            st.session_state.show_per_capita_modal = False

                            st.success("✅ Custom per capita data loaded successfully!")
                            st.rerun()

                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            st.session_state.show_per_capita_modal = False
                            st.rerun()

            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")

        # Show close button if no file uploaded yet
        if not uploaded_per_capita_file:
            st.markdown("---")
            if st.button("❌ Close", use_container_width=True):
                st.session_state.show_per_capita_modal = False
                st.rerun()

    show_per_capita_modal()

# Modal for customizing year projections
if end_year > 2025 and 'show_projection_modal' in st.session_state and st.session_state.show_projection_modal:
    @st.dialog(f"Customize Year Projections", width="large")
    def show_projection_modal():
        st.markdown(f"### Enter percentage values for any year in your selected range")

        # Year selector
        selected_custom_year = st.selectbox(
            "Select year to customize:",
            options=list(range(start_year, end_year + 1)),
            index=end_year - start_year,  # Default to end year
            help="Choose the year for which you want to enter custom values"
        )

        st.markdown(f"All years will be **scaled proportionally** based on your custom values for {selected_custom_year}.")
        st.caption("Example: Changing a value from 30% to 60% (2× increase) will double all years for that fuel/area combination.")

        st.warning("⚠️ **Data Quality Notice**: Custom projections should be based on robust data supported by peer-reviewed literature, official statistics, or reputable organizations.")

        # Generate template based on selected countries, fuels, and areas
        if selected_countries and selected_fuels and selected_areas:
            # Get baseline data for the selected custom year
            baseline_df = st.session_state.population_share_per_fuel_df
            baseline_custom_year = baseline_df[
                (baseline_df['year'] == selected_custom_year) &
                (baseline_df['country'].isin(selected_countries)) &
                (baseline_df['fuel'].isin(selected_fuels)) &
                (baseline_df['area'].isin(selected_areas))
            ][['iso3', 'country', 'region', 'area', 'fuel', 'percent_median']].copy()

            if len(baseline_custom_year) == 0:
                st.error(f"No baseline data found for {selected_custom_year} for the selected countries, fuels, and areas.")
                if st.button("Close"):
                    st.session_state.show_projection_modal = False
                    st.rerun()
                return

            # Create template with default values for the custom year
            template_df = baseline_custom_year.copy()
            template_df['percent_median'] = template_df['percent_median'].round(2)

            st.markdown("---")
            st.markdown(f"**{len(template_df)} combinations** found for your selected countries, fuels, and areas.")

            # Two input options: Data Editor or CSV Upload
            input_method = st.radio("Choose input method:", ["Data Editor", "Upload CSV"], horizontal=True)

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
                            f"Percent for {selected_custom_year}",
                            help="Enter percentage value (0-1)",
                            min_value=0.0,
                            max_value=1.0,
                            step=0.01,
                            format="%.2f"
                        )
                    }
                )

                # Source citation input
                st.markdown("---")
                st.markdown("**📚 Data Source Citation (Required)**")
                data_source_citation = st.text_area(
                    "Provide citation for your custom data:",
                    placeholder="e.g., Smith et al. (2024). 'Cooking Fuel Projections for Sub-Saharan Africa.' Energy Policy Journal. DOI: 10.xxxx/xxxxx",
                    help="Include author, year, title, publication, and DOI/URL if available",
                    height=100,
                    key="custom_projection_citation"
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
                        elif not data_source_citation or len(data_source_citation.strip()) == 0:
                            st.error("❌ Please provide a data source citation for your custom projections.")
                        else:
                            # Store custom data, custom year, source, and mark as using custom projections
                            st.session_state.custom_year_data = edited_data
                            st.session_state.custom_year = selected_custom_year
                            st.session_state.custom_projection_source = data_source_citation.strip()
                            st.session_state.use_custom_projections = True
                            st.session_state.data_source_population_share = f"UN WHO Data from Stoner et al. 2021 with Custom Projections (Year {selected_custom_year})"
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
                    file_name=f"projection_template_{selected_custom_year}.csv",
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

                                # Source citation input
                                st.markdown("---")
                                st.markdown("**📚 Data Source Citation (Required)**")
                                csv_data_source_citation = st.text_area(
                                    "Provide citation for your custom data:",
                                    placeholder="e.g., Smith et al. (2024). 'Cooking Fuel Projections for Sub-Saharan Africa.' Energy Policy Journal. DOI: 10.xxxx/xxxxx",
                                    help="Include author, year, title, publication, and DOI/URL if available",
                                    height=100,
                                    key="custom_projection_citation_csv"
                                )

                                col1, col2 = st.columns([1, 1])
                                with col1:
                                    if st.button("✅ Apply Custom Projections", type="primary", use_container_width=True):
                                        if not csv_data_source_citation or len(csv_data_source_citation.strip()) == 0:
                                            st.error("❌ Please provide a data source citation for your custom projections.")
                                        else:
                                            st.session_state.custom_year_data = uploaded_df
                                            st.session_state.custom_year = selected_custom_year
                                            st.session_state.custom_projection_source = csv_data_source_citation.strip()
                                            st.session_state.use_custom_projections = True
                                            st.session_state.data_source_population_share = f"UN WHO Data from Stoner et al. 2021 with Custom Projections (Year {selected_custom_year})"
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
    # Prominent Data Source Ribbon
    st.markdown("---")
    data_source = st.session_state.get('data_source_population_share', 'UN WHO Data from Stoner et al. 2021')
    base_citation = st.session_state.get('data_source_base_citation')
    custom_citation = st.session_state.get('data_source_custom_citation') or st.session_state.get('custom_projection_source')
    has_custom_dataset = st.session_state.get('custom_source_description') is not None

    # Determine if using custom data
    is_custom = has_custom_dataset or "Custom" in data_source

    if is_custom:
        st.warning(f"📊 **Data Source**: {data_source}")
    else:
        st.info(f"📊 **Data Source**: {data_source}")

    # Show citations in expandable section
    with st.expander("📚 View Full Citations", expanded=False):
        # For full custom datasets, only show custom citation
        if has_custom_dataset:
            st.markdown("**Data Citation:**")
            st.markdown(custom_citation)
        # For custom projections on base data, show both
        elif "Stoner" in data_source:
            st.markdown("**Base Data Citation:**")
            st.markdown(base_citation)
            if custom_citation:  # Custom projections applied
                st.markdown("---")
                st.markdown("**Custom Projection Citation:**")
                st.markdown(custom_citation)

    st.markdown("---")

    # Show status indicator if using custom projections
    if st.session_state.get('use_custom_projections', False):
        custom_year = st.session_state.get('custom_year', 'N/A')
        st.success(f"✅ Using Custom Projections: All years scaled proportionally based on custom values for {custom_year}")

    st.header("Data Preview")

    # Use shifted data if custom projections are active
    if st.session_state.get('use_custom_projections', False) and st.session_state.get('custom_year_data') is not None:
        # Apply shift adjustments
        try:
            shifted_data = apply_custom_year_adjustments(
                st.session_state.population_share_per_fuel_df,
                st.session_state.custom_year_data,
                st.session_state.custom_year,
                start_year,
                end_year
            )
            pop_share_per_fuel_df = shifted_data
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
        # Per Capita Data Source Ribbon
        st.markdown("---")
        per_capita_source = st.session_state.get('data_source_per_capita', 'Default Per Capita Data (Placeholder)')
        per_capita_base_cite = st.session_state.get('per_capita_base_citation')
        per_capita_custom_cite = st.session_state.get('per_capita_citation')
        has_custom_per_capita = st.session_state.get('per_capita_source_description') is not None

        if has_custom_per_capita:
            st.warning(f"📊 **Per Capita Data Source**: {per_capita_source}")
        else:
            st.info(f"📊 **Per Capita Data Source**: {per_capita_source}")

        # Show per capita citations
        with st.expander("📚 View Per Capita Citation", expanded=False):
            if has_custom_per_capita:
                st.markdown("**Per Capita Data Citation:**")
                st.markdown(per_capita_custom_cite)
            else:
                st.markdown("**Default Per Capita Data:**")
                st.markdown(per_capita_base_cite)

        st.markdown("---")

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
                    # Create metadata sheet
                    # Determine which citations to include
                    data_src = st.session_state.get('data_source_population_share', 'UN WHO Data from Stoner et al. 2021')
                    citations_list = []

                    # Add base citation if Stoner data is used
                    if 'Stoner' in data_src:
                        citations_list.append(st.session_state.get('data_source_base_citation', 'N/A'))

                    # Add custom citation if exists
                    custom_cite = st.session_state.get('data_source_custom_citation') or st.session_state.get('custom_projection_source')
                    if custom_cite:
                        citations_list.append(custom_cite)

                    # Combine citations
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
                            'Full Citations',
                            'Per Capita Data Source',
                            'Per Capita Citation',
                            'Notes'
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
                            st.session_state.get('data_source_per_capita', 'Default Placeholder Data'),
                            st.session_state.get('per_capita_citation', 'N/A'),
                            'All custom data should be supported by peer-reviewed literature or official statistics.'
                        ]
                    }
                    metadata_df = pd.DataFrame(metadata_dict)
                    metadata_df.to_excel(writer, index=False, sheet_name='Metadata & Sources')

                    # Add data sheets
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
