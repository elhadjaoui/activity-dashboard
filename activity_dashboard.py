"""
Purview Activity Dashboard
Streamlit app for productivity monitoring
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from data_processor import process_audit_logs
import os

# Page config
st.set_page_config(
    page_title="Activity Dashboard",
    page_icon=":bar_chart:",
    layout="wide"
)

st.title("User Activity Dashboard")
st.caption("Productivity monitoring from Microsoft 365 Purview Audit Logs")

# Info section
with st.expander("ℹ️ How this works", expanded=False):
    st.markdown("""
**Data Source:** Microsoft 365 Purview audit logs - tracks actions like sending emails, joining meetings, uploading files, etc.

**How hours are calculated:**
- The day is split into time blocks (default 20 min). If there's any activity in a block, it counts as active time.
- This prevents over-counting (50 emails in one hour = 1 hour, not 50).

**Why app hours > total hours:**
- If you use multiple apps in the same time block (e.g., Outlook + Teams open at once), each app gets credit for that block.
- But total hours only counts the block once. So app hours will add up to more than total - that's expected.

**What counts as activity:**
- Only human actions (sending, clicking, typing) - automated syncs are filtered out.

**Work hours:** 9am - 6pm UTC | **Gap hours:** Idle time during work hours (no M365 activity detected)
    """)
    st.caption("Outlook Desktop, Outlook Web, and Outlook Mobile are tracked separately - same email, different devices.")

# User groups for filtering
USER_GROUPS = {
    'Sales Team': {
        'pmaccutcheon@transparentedge.com': 'Patrick MacCutcheon',
        'dblair@transparentedge.com': 'David Blair',
        'ngardner@transparentedge.com': 'Nancy Gardner',
        'mvondle@transparentedge.com': 'Michael Vondle',
        'shuhn@transparentedge.com': 'Stephanie Huhn',
        'shorowitz@transparentedge.com': 'Sara Horowitz',
        'mmurphy@transparentedge.com': 'Michael Murphy',
        'bdufresne@transparentedge.com': 'Brian Dufresne',
        'gangelillo@transparentedge.com': 'Greg Angelillo',
    },
}


@st.cache_data(ttl=3600)
def load_data(time_block_minutes: int = 20):
    """Load and cache processed data with configurable time block size"""
    csv_path = os.path.join(os.path.dirname(__file__), 'purviewAuditLogs.csv')
    return process_audit_logs(csv_path, time_block_minutes)


# =============================================================================
# TIME BLOCK CONFIGURATION (affects all calculations)
# =============================================================================
st.sidebar.header("Settings")
time_block_options = {
    "10 minutes": 10,
    "15 minutes": 15,
    "20 minutes (default)": 20,
    "30 minutes": 30,
    "60 minutes (1 hour)": 60,
}
selected_time_block_label = st.sidebar.selectbox(
    "Time Block Size",
    options=list(time_block_options.keys()),
    index=2,  # Default to 20 minutes
    help="Size of time blocks for activity calculation. Smaller blocks = more precise tracking."
)
time_block_minutes = time_block_options[selected_time_block_label]

st.sidebar.caption(f"Activity is measured in {time_block_minutes}-minute blocks. "
                   f"Each block with activity counts as {time_block_minutes/60:.2f} hours.")

# Load data with selected time block size
with st.spinner(f"Loading and processing audit logs ({time_block_minutes}-min blocks)..."):
    df = load_data(time_block_minutes)

if df.empty:
    st.error("No data found. Please ensure purviewAuditLogs.csv exists.")
    st.stop()

# Convert date column to datetime for filtering
df['date'] = pd.to_datetime(df['date'])

# =============================================================================
# FILTERS BAR
# =============================================================================
st.markdown("---")

col1, col2, col3, col4, col5 = st.columns([2, 1.5, 2, 2, 1])

with col1:
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()
    date_range = st.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

with col2:
    # Group filter
    group_options = ['All Users'] + list(USER_GROUPS.keys())
    selected_group = st.selectbox(
        "Group",
        options=group_options,
        index=0
    )

with col3:
    all_users = sorted(df['user'].unique())
    # Show short names in dropdown
    user_options = {u.split('@')[0]: u for u in all_users}

    # If a group is selected, default to those users
    if selected_group != 'All Users':
        group_emails = list(USER_GROUPS[selected_group].keys())
        default_names = [u.split('@')[0] for u in group_emails if u in all_users]
    else:
        default_names = []

    selected_user_names = st.multiselect(
        "Users",
        options=list(user_options.keys()),
        default=default_names,
        placeholder="All users"
    )
    selected_users = [user_options[n] for n in selected_user_names]

with col4:
    all_apps = sorted(df['app'].unique())
    selected_apps = st.multiselect(
        "Apps",
        options=all_apps,
        default=[],
        placeholder="All apps"
    )

with col5:
    st.write("")  # Spacer
    st.write("")
    apply_filters = st.button("Apply", type="primary", use_container_width=True)

# Apply filters
filtered_df = df.copy()

# Date filter
if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_df = filtered_df[
        (filtered_df['date'].dt.date >= start_date) &
        (filtered_df['date'].dt.date <= end_date)
    ]

# User filter
if selected_users:
    filtered_df = filtered_df[filtered_df['user'].isin(selected_users)]

# App filter
if selected_apps:
    filtered_df = filtered_df[filtered_df['app'].isin(selected_apps)]

st.markdown("---")

# =============================================================================
# SUMMARY CARDS
# =============================================================================

# Get unique user/date totals (avoid double counting)
user_daily = filtered_df.groupby(['user', 'date']).agg({
    'total_active_hours': 'first',
    'work_hours': 'first',
    'after_hours': 'first',
    'gap_hours': 'first'
}).reset_index()

col1, col2, col3, col4, col5 = st.columns(5)

total_hours = user_daily['total_active_hours'].sum()
unique_users = filtered_df['user'].nunique()
total_events = filtered_df['event_count'].sum()
avg_hours_per_user = user_daily['total_active_hours'].mean() if len(user_daily) > 0 else 0
most_used_app = filtered_df.groupby('app')['event_count'].sum().idxmax() if not filtered_df.empty else "N/A"

with col1:
    st.metric("Total Active Hours", f"{total_hours:.0f}", help="Sum of all unique time blocks with activity, converted to hours")

with col2:
    st.metric("Unique Users", unique_users, help="Number of distinct users with activity in the selected period")

with col3:
    st.metric("Total Events", f"{total_events:,}", help="Total number of human-triggered events (emails, meetings, file actions, etc.)")

with col4:
    st.metric("Avg Hours/User/Day", f"{avg_hours_per_user:.1f}", help="Average active hours per user per day")

with col5:
    st.metric("Most Used App", most_used_app, help="App with the highest event count")

st.markdown("---")

# =============================================================================
# CHARTS
# =============================================================================

# Users by Activity - full width
user_hours = user_daily.groupby('user')['total_active_hours'].sum().reset_index()
user_hours.columns = ['user', 'hours']
user_hours = user_hours.sort_values('hours', ascending=False)
user_hours['user_short'] = user_hours['user'].str.split('@').str[0]

fig_users = px.bar(
    user_hours,
    x='user_short',
    y='hours',
    title="Users by Activity",
    labels={'hours': 'Hours', 'user_short': 'User'}
)
fig_users.update_layout(height=350, xaxis_tickangle=-45)
st.plotly_chart(fig_users, use_container_width=True)

# Second row - Hours by App
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    # Hours per App (using app_hours)
    app_hours = filtered_df.groupby('app')['app_hours'].sum().reset_index()
    app_hours.columns = ['app', 'hours']
    app_hours = app_hours.sort_values('hours', ascending=True)

    fig_apps = px.bar(
        app_hours,
        x='hours',
        y='app',
        orientation='h',
        title="Hours by App",
        labels={'hours': 'Hours', 'app': 'Application'}
    )
    fig_apps.update_layout(height=350)
    st.plotly_chart(fig_apps, use_container_width=True)

with chart_col2:
    # Work vs After Hours comparison
    work_total = user_daily['work_hours'].sum()
    after_total = user_daily['after_hours'].sum()

    fig_work_after = px.pie(
        values=[work_total, after_total],
        names=['Work Hours (9am-6pm)', 'After Hours'],
        title="Work Hours vs After Hours",
        color_discrete_sequence=['#636EFA', '#EF553B']
    )
    fig_work_after.update_layout(height=350)
    st.plotly_chart(fig_work_after, use_container_width=True)

# Third row - Daily activity trend (full width)
daily_hours = user_daily.groupby('date')['total_active_hours'].sum().reset_index()
daily_hours.columns = ['date', 'hours']
daily_hours['date_str'] = daily_hours['date'].dt.strftime('%m/%d')

fig_trend = px.bar(
    daily_hours,
    x='date_str',
    y='hours',
    title="Daily Activity Trend",
    labels={'hours': 'Total Hours', 'date_str': 'Date'},
)
fig_trend.update_layout(height=350, xaxis_tickangle=-45)
st.plotly_chart(fig_trend, use_container_width=True)

# Fourth row - User time per app (stacked bar)
st.subheader("Time Spent per App by User")
st.caption("Note: App hours can overlap (using multiple apps in same time block). Total bar length may exceed user's total hours.")

# Get hours per user per app
user_app_hours = filtered_df.groupby(['user', 'app'])['app_hours'].sum().reset_index()
user_app_hours.columns = ['user', 'app', 'hours']
user_app_hours['user_short'] = user_app_hours['user'].str.split('@').str[0]

# Get total hours per user for sorting
user_totals = user_app_hours.groupby('user_short')['hours'].sum().sort_values(ascending=True)
user_app_hours['user_short'] = pd.Categorical(
    user_app_hours['user_short'],
    categories=user_totals.index,
    ordered=True
)

fig_user_apps = px.bar(
    user_app_hours.sort_values('user_short'),
    y='user_short',
    x='hours',
    color='app',
    orientation='h',
    title="Hours by User and App",
    labels={'hours': 'Hours', 'user_short': 'User', 'app': 'App'}
)
fig_user_apps.update_layout(
    height=max(400, len(user_totals) * 25),
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
)
st.plotly_chart(fig_user_apps, use_container_width=True)

st.markdown("---")

# =============================================================================
# DATA TABLE
# =============================================================================
st.subheader("Activity Summary")

# Aggregate by user for the selected date range
summary_df = user_daily.groupby('user').agg({
    'total_active_hours': 'sum',
    'work_hours': 'sum',
    'after_hours': 'sum',
    'gap_hours': 'mean',  # average gap per day
}).reset_index()

# Get apps used by each user
apps_by_user = filtered_df.groupby('user')['app'].apply(
    lambda x: ', '.join(sorted(x.unique()))
).reset_index()
apps_by_user.columns = ['user', 'apps_used']

# Get days active
days_active = user_daily.groupby('user')['date'].nunique().reset_index()
days_active.columns = ['user', 'days_active']

summary_df = summary_df.merge(apps_by_user, on='user', how='left')
summary_df = summary_df.merge(days_active, on='user', how='left')

# Format user names
summary_df['user'] = summary_df['user'].str.split('@').str[0]

# Round numbers
summary_df['total_active_hours'] = summary_df['total_active_hours'].round(1)
summary_df['work_hours'] = summary_df['work_hours'].round(1)
summary_df['after_hours'] = summary_df['after_hours'].round(1)
summary_df['gap_hours'] = summary_df['gap_hours'].round(1)

# Rename columns
summary_df.columns = ['User', 'Total Hours', 'Work Hours', 'After Hours', 'Avg Gap/Day', 'Apps Used', 'Days Active']

# Reorder columns
summary_df = summary_df[['User', 'Days Active', 'Total Hours', 'Work Hours', 'After Hours', 'Avg Gap/Day', 'Apps Used']]

# Sort by total hours descending
summary_df = summary_df.sort_values('Total Hours', ascending=False).reset_index(drop=True)

# Display table
st.dataframe(
    summary_df,
    use_container_width=True,
    height=400,
    hide_index=True,
)

# Export button
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    csv = summary_df.to_csv(index=False)
    st.download_button(
        label="Export CSV",
        data=csv,
        file_name=f"activity_summary_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

with col2:
    st.write(f"{len(summary_df)} users")
