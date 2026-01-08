import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(page_title="Offer Tracker Dashboard", layout="wide", initial_sidebar_state="expanded")

# Custom CSS
st.markdown("""
<style>
    .stMetric > label {
        font-size: 14px !important;
        color: #555 !important;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Load and Preprocess Data
# ----------------------------

@st.cache_data


@st.cache_data
def load_data(file_path_or_buffer=None):
    """
    Load and preprocess offer tracker data.
    - If file_path_or_buffer is None: reads from default file
    - If it's a file-like object (e.g., UploadedFile): reads from it
    """

    df = pd.read_excel(file_path_or_buffer, sheet_name="Sheet1")
    
    df['Offer Date'] = pd.to_datetime(df['Offer Date'], errors='coerce')
    df = df.dropna(subset=['Offer Date'])
    df['Month'] = df['Offer Date'].dt.strftime('%b %Y')
    df['Year-Month'] = df['Offer Date'].dt.to_period('M').astype(str)
    
    # CTC cleaning
    for col in ['Current Fixed CTC (In Lacs)', 'Offered (In Lacs)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # % Hike
    valid = (
        df['Current Fixed CTC (In Lacs)'].notna() &
        df['Offered (In Lacs)'].notna() &
        (df['Current Fixed CTC (In Lacs)'] > 0)
    )
    df['% Hike Calculated'] = pd.NA
    df.loc[valid, '% Hike Calculated'] = (
        (df.loc[valid, 'Offered (In Lacs)'] - df.loc[valid, 'Current Fixed CTC (In Lacs)']) 
        / df.loc[valid, 'Current Fixed CTC (In Lacs)']
    ) * 100

    # CTC Bins
    def ctc_bin(ctc):
        if pd.isna(ctc):
            return "Unknown"
        elif ctc < 10:
            return "<10L"
        elif ctc < 20:
            return "10-20L"
        elif ctc < 30:
            return "20-30L"
        else:
            return "≥30L"
    df['CTC Bin'] = df['Offered (In Lacs)'].apply(ctc_bin)

    # Source classification
    internal_sources = ['Employee Referral', 'Internal Sourcing', 'Direct']
    df['Source Type'] = df['Source'].apply(lambda x: 'Internal' if x in internal_sources else 'External')
    
    return df

# ----------------------------
# Sidebar: Only Date/Month Filter
# ----------------------------

#U pload custom Excel file
uploaded_file = st.sidebar.file_uploader(
    "📁 Upload Offer Tracker Excel",
    type=["xlsx"],
    help="Must contain 'Sheet1' with same structure as default tracker"
)

# Load data: use uploaded file 
if uploaded_file is None:
    st.warning("⚠️ Please upload an Excel file to proceed.")
    st.stop()  # Halt execution until file is uploaded

st.sidebar.header("🔍 Period Filter")

filter_type = st.sidebar.radio("Filter by:", ("Date Range", "Select Months"), index=1)

if filter_type == "Date Range":
    min_date = df['Offer Date'].min().date()
    max_date = df['Offer Date'].max().date()
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df[
            (df['Offer Date'].dt.date >= start_date) &
            (df['Offer Date'].dt.date <= end_date)
        ].copy()
    else:
        df_filtered = df.copy()
else:
    all_months = sorted(df['Month'].unique())
    selected_months = st.sidebar.multiselect(
        "Select Month(s)",
        options=all_months,
        default=all_months
    )
    df_filtered = df[df['Month'].isin(selected_months)].copy() if selected_months else df.copy()

df_filtered = df_filtered.reset_index(drop=True)

# ----------------------------
# Main Dashboard
# ----------------------------

st.title("Offer Tracker Dashboard 2025")
st.markdown("### Recruitment Performance Analytics for Selected Period")

# KPIs - Based on filtered period
total_offers = len(df_filtered)
joined = len(df_filtered[df_filtered['Status'] == 'Joined'])
join_rate = (joined / total_offers * 100) if total_offers > 0 else 0
avg_hike = df_filtered['% Hike Calculated'].mean()
hike_30_plus = len(df_filtered[df_filtered['% Hike Calculated'] >= 30])
internal_count = len(df_filtered[df_filtered['Source Type'] == 'Internal'])
external_count = len(df_filtered[df_filtered['Source Type'] == 'External'])

col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1: st.metric("Total Offers", total_offers)
with col2: st.metric("Onboarded", joined, f"{join_rate:.1f}% Join Rate")
with col3: st.metric("Avg % Hike", f"{avg_hike:.1f}%" if pd.notna(avg_hike) else "—")
with col4: st.metric("Hike ≥30%", hike_30_plus)
with col5: st.metric("Internal Sources", internal_count)
with col6: st.metric("External Sources", external_count)

st.markdown("---")

# ----------------------------
# Filtered Analysis Section
# ----------------------------

st.subheader("📈 Analysis for Selected Period")

col1, col2 = st.columns(2)

# Hike Distribution
with col1:
    st.markdown("#### % Hike Distribution")
    hike_data = df_filtered['% Hike Calculated'].dropna()
    if not hike_data.empty:
        bins = [-float('inf'), 0, 15, 30, 50, float('inf')]
        labels = ['<0%', '0-15%', '15-30%', '30-50%', '>50%']
        hike_binned = pd.cut(hike_data, bins=bins, labels=labels)
        hike_counts = hike_binned.value_counts().reindex(labels, fill_value=0)
        
        fig = px.bar(x=hike_counts.index, y=hike_counts.values,
                     color=hike_counts.index,
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(showlegend=False, xaxis_title="Hike Range", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No valid hike data.")

# Offered CTC Distribution
with col2:
    st.markdown("#### Offered CTC Distribution")
    ctc_counts = df_filtered['CTC Bin'].value_counts()
    if not ctc_counts.empty:
        fig = px.pie(values=ctc_counts.values, names=ctc_counts.index, hole=0.4,
                     color_discrete_sequence=px.colors.sequential.Purples)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No CTC data.")

# Onboarding Source Analysis (Filtered, Joined only)
st.markdown("#### Onboarding Source Analysis")

col3, col4 = st.columns(2)

with col3:
    st.markdown("**External vs Internal**")
    joined_df = df_filtered[df_filtered['Status'] == 'Joined']
    source_type_counts = joined_df['Source Type'].value_counts()
    if not source_type_counts.empty:
        fig = px.pie(values=source_type_counts.values, names=source_type_counts.index, hole=0.4,
                     color_discrete_sequence=["#A23B72", "#2E86AB"])
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No onboardings in selected period.")

with col4:
    st.markdown("**Internal Source Breakdown**")
    internal_joined = joined_df[joined_df['Source Type'] == 'Internal']
    if not internal_joined.empty:
        internal_counts = internal_joined['Source'].value_counts()
        fig = px.pie(values=internal_counts.values, names=internal_counts.index, hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No internal onboardings in selected period.")

st.markdown("---")

# ----------------------------
# UNFILTERED: Full Historical Trend 
# ----------------------------

st.subheader("📊 Full Historical Summary (All Data)")
st.markdown("#### Offers vs Onboarded Over Time")

full_trend = (
    df.groupby('Year-Month')
    .agg({'Offer Date': 'count', 'Status': lambda x: (x == 'Joined').sum()})
    .reset_index()
)
full_trend.columns = ['Month', 'Total Offers', 'Onboarded']
full_trend = full_trend.sort_values('Month')

if not full_trend.empty:
    fig = go.Figure()

    # Bar for Total Offers
    fig.add_trace(go.Bar(
        x=full_trend['Month'],
        y=full_trend['Total Offers'],
        name='Total Offers',
        marker_color='#636EFA',
        opacity=0.8
    ))

    # Line for Onboarded
    fig.add_trace(go.Scatter(
        x=full_trend['Month'],
        y=full_trend['Onboarded'],
        mode='lines+markers',
        name='Onboarded',
        line=dict(color='#10B981', width=4),
        marker=dict(size=8)
    ))

    fig.update_layout(
            barmode='group',
            xaxis_title="",
            yaxis_title="Count",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50)
        )
    
    fig.data[0].name = "Total Offers"
    fig.data[1].name = "Onboarded"
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No historical data available.")

st.markdown("---")


st.markdown("#### Overall Status Distribution")
status_all = df['Status'].value_counts()
fig = px.bar(x=status_all.index, y=status_all.values,
            color=status_all.index,
            color_discrete_sequence=px.colors.qualitative.Safe)
fig.update_layout(
    showlegend=False,
    xaxis_title="",
    yaxis_title=""
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
