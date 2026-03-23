# Purview Activity Dashboard - Design Spec

**Date:** 2026-03-12
**Goal:** Productivity monitoring dashboard for managers to track user activity across Microsoft 365 apps

## Overview

Build a Streamlit dashboard that processes Purview Audit Logs and displays user activity metrics with time breakdowns by app, session tracking, and offline/gap analysis.

## Data Source

- **Input:** `purviewAuditLogs.csv` (~50K records, 143MB)
- **Date Range:** 12 days of data (Mar 1-12, 2026)
- **Users:** ~163 total, filtered to real employees (`@transparentedge.com`)
- **Workloads:** Exchange, OneDrive, Azure AD, Teams, SharePoint

## Data Processing Pipeline

### 1. Parse & Filter
- Extract JSON from `AuditData` column
- Filter to real employees only (emails ending in `@transparentedge.com`)
- Exclude system accounts (GUIDs, phone numbers, service principals)

### 2. Normalize Apps
Map `ClientAppId` + `ActorInfoString` to friendly names:
- HubSpot Connect
- Outlook Web
- Outlook Desktop
- Microsoft Teams
- OneDrive
- SharePoint
- Other

### 3. Build Sessions
- Group events by user with 1-hour inactivity threshold
- Calculate session duration (first event to last event)
- Add estimated time per event type:
  - `MailItemsAccessed`: 2 min
  - `AttachmentAccess`: 3 min
  - `FileAccessed/Previewed`: 5 min
  - `Send`: 2 min
  - Other: 1 min

### 4. Output Schema
Processed DataFrame columns:
- `user` - Email address
- `date` - Activity date
- `app` - Normalized app name
- `session_id` - Unique session identifier
- `session_start` - Session start timestamp
- `session_end` - Session end timestamp
- `session_duration_min` - Duration in minutes
- `estimated_active_min` - Estimated active time based on event types
- `event_count` - Number of events in session
- `work_hours_active` - Time active during 8am-6pm
- `after_hours_active` - Time active outside 8am-6pm
- `gap_hours` - Inactive time during work hours

## Dashboard Layout

Single page, top-to-bottom layout (no sidebar):

### 1. Filters Bar (Top)
Horizontal row:
- Date range picker
- User dropdown (multi-select)
- App dropdown (multi-select)
- "Apply" button

### 2. Summary Cards
Row of 5 KPI cards:
- Total Active Hours
- Unique Users
- Total Sessions
- Avg Hours/User
- Most Used App

### 3. Charts Section
Three charts side by side:
- **Bar chart:** Hours per app
- **Bar chart:** Hours per user (top 10)
- **Line chart:** Daily activity trend

Plus one additional chart:
- **Bar chart:** Gap hours per user (identify most idle time)

### 4. Data Table (Bottom)
Full table with columns:
- User
- Date
- App
- Session Start
- Session End
- Duration (min)
- Events
- Estimated Active Time
- Work Hours Active
- After Hours Active
- Gap Hours

Features:
- Sortable columns
- Row highlighting for users with 2+ hour gaps (light yellow)
- Export to CSV button

## Offline/Gap Tracking

Three types of offline tracking:

1. **Intra-day gaps:** Time with no activity during work hours (8am-6pm)
2. **After-hours work:** Activity before 8am or after 6pm
3. **Full-day absences:** Days with zero events for a user

Visual indicators:
- Yellow row highlighting for significant gaps
- Gap hours column in table
- Dedicated gap chart

## Technical Implementation

### Files
- `activity_dashboard.py` - Main Streamlit app
- `data_processor.py` - Data loading and transformation logic

### Dependencies
```
streamlit
pandas
plotly
```

### Running
```bash
cd signin_report
streamlit run activity_dashboard.py
```

## Success Criteria

1. Dashboard loads within 5 seconds
2. Filters update charts and table reactively
3. Managers can identify:
   - Which apps each user spends time on
   - Users with significant idle gaps
   - After-hours work patterns
   - Daily activity trends
4. Data exportable to CSV for meetings/archiving
