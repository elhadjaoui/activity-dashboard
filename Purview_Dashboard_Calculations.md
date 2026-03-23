# Purview Activity Dashboard - Calculation Documentation

## Overview

This dashboard analyzes Microsoft 365 Purview Audit Logs to track user productivity across apps like Outlook, OneDrive, SharePoint, and Teams.

---

## Calculation Method: Distinct Time Blocks (20-minute)

We count **unique 20-minute blocks** with at least one human-triggered event per user per day. This provides more accurate activity tracking than counting whole hours.

### Configuration

```python
TIME_BLOCK_MINUTES = 20  # Can be adjusted (15, 20, 30, 60)
```

### How It Works

```
For each user, for each day:
1. Get all human-triggered events
2. Calculate the time block index for each event:
   - Block = (hour * 60 + minute) // TIME_BLOCK_MINUTES
   - Block 0 = 00:00-00:19, Block 1 = 00:20-00:39, Block 2 = 00:40-00:59, etc.
3. Count UNIQUE blocks with at least 1 event
4. Convert blocks to hours: (blocks * TIME_BLOCK_MINUTES) / 60
```

---

## Time Block Formula Explained

```python
time_block = (hour * 60 + minute) // 20
```

### Step by Step:

**1. `hour * 60`** - Convert the hour to minutes
```
9:00 AM → 9 * 60 = 540 minutes since midnight
14:00 (2pm) → 14 * 60 = 840 minutes since midnight
```

**2. `+ minute`** - Add the minutes
```
9:25 AM → (9 * 60) + 25 = 540 + 25 = 565 minutes since midnight
14:47 → (14 * 60) + 47 = 840 + 47 = 887 minutes since midnight
```

**3. `// 20`** - Integer division by 20 (get which 20-min block)
```
9:25 → 565 // 20 = 28  (block 28)
14:47 → 887 // 20 = 44  (block 44)
```

### Block Reference Table

| Block | Time Range |
|-------|------------|
| 0 | 00:00 - 00:19 |
| 1 | 00:20 - 00:39 |
| 2 | 00:40 - 00:59 |
| 3 | 01:00 - 01:19 |
| ... | ... |
| 27 | 09:00 - 09:19 (work hours start) |
| 28 | 09:20 - 09:39 |
| 29 | 09:40 - 09:59 |
| ... | ... |
| 53 | 17:40 - 17:59 (work hours end) |
| 54 | 18:00 - 18:19 (after hours) |
| ... | ... |
| 71 | 23:40 - 23:59 |

**Total blocks in a day:** 72 blocks (24 hours × 3 blocks per hour)

### Calculation Examples

```
09:05 → (9*60 + 5) // 20 = 545 // 20 = 27  → Block 27 (9:00-9:19)
09:25 → (9*60 + 25) // 20 = 565 // 20 = 28 → Block 28 (9:20-9:39)
09:45 → (9*60 + 45) // 20 = 585 // 20 = 29 → Block 29 (9:40-9:59)
10:00 → (10*60 + 0) // 20 = 600 // 20 = 30 → Block 30 (10:00-10:19)
```

### Example

```
Events at: 09:15, 09:45, 10:30, 14:00, 14:22, 14:55

Time blocks (20-min):
  09:15 → block 27 (9:00-9:19)
  09:45 → block 29 (9:40-9:59)
  10:30 → block 31 (10:20-10:39)
  14:00 → block 42 (14:00-14:19)
  14:22 → block 43 (14:20-14:39)
  14:55 → block 44 (14:40-14:59)

Unique blocks: {27, 29, 31, 42, 43, 44} = 6 blocks
Active hours: 6 × 0.33 = 2.0 hours
```

### Why Smaller Time Blocks Are More Accurate

| Scenario | 1-Hour | 30-Min | 20-Min |
|----------|--------|--------|--------|
| Events at 9:05 only | 1.0 hr | 0.5 hr | 0.33 hr |
| Events at 9:05 and 9:55 | 1.0 hr | 1.0 hr | 0.67 hr |
| Events at 9:05, 9:25, 9:45 | 1.0 hr | 1.0 hr | 1.0 hr |

The smaller the time block, the more precise the measurement.

---

## Dashboard Metrics

### Summary Cards

| Metric | Calculation |
|--------|-------------|
| **Total Active Hours** | Sum of all unique time blocks (converted to hours) across all users and days |
| **Unique Users** | Count of distinct user emails in the filtered data |
| **Total Events** | Sum of all human-triggered events |
| **Avg Hours/User/Day** | Mean of total_active_hours per user per day |
| **Most Used App** | App with the highest total event count across all users |

### Most Used App Calculation

```python
most_used_app = df.groupby('app')['event_count'].sum().idxmax()
```

This finds the app with the **most human-triggered events** (not hours). For example:
- Outlook Mobile: 5,000 events
- Outlook Web: 3,200 events
- Excel: 800 events

**Most Used App = Outlook Mobile** (highest event count)

---

## Human vs Automated Event Detection

### Human-Triggered Patterns (COUNTED)

| Pattern | Description |
|---------|-------------|
| `Outlook-iOS` | Outlook mobile app (iOS) |
| `Outlook-Android` | Outlook mobile app (Android) |
| `OWA` | Outlook Web App (browser) |
| `OneOutlook` | New Outlook desktop app |
| `Outlook/` | Classic Outlook desktop |
| `OUTLOOK.EXE` | Classic Outlook desktop (Windows) |
| `MacOutlook` | Outlook for Mac |
| `Mozilla/` | Browser (Firefox, etc.) |
| `Chrome/` | Chrome browser |
| `Safari/` | Safari browser |
| `Edge/` | Edge browser |
| `Teams` | Microsoft Teams |
| `TeamsMobile` | Teams mobile app |
| `Microsoft Office` | Office desktop apps (Word, Excel, PowerPoint, OneNote) |

### Human-Triggered Operations (COUNTED)

These operations are **always** counted as human activity regardless of client info:

| Operation | Workload | Description |
|-----------|----------|-------------|
| `MeetingParticipantDetail` | Teams | Meeting attendance |
| `MeetingDetail` | Teams | Meeting start/end |
| `TeamsSessionStarted` | Teams | Teams app launched |
| `CallParticipantDetail` | Teams | Voice/video calls |
| `MessageSent` | Teams | Message sent |
| `ReactedToMessage` | Teams | Emoji reaction |
| `MessageCreatedHasLink` | Teams | Message with link |
| `MessageUpdated` | Teams | Message edited |
| `CopilotInteraction` | Copilot | AI assistant usage |
| `TaskCreated` | To Do | Task created |
| `TaskUpdated` | To Do | Task modified |
| `Send` | Exchange | Email sent |
| `SendOnBehalf` | Exchange | Email sent on behalf |
| `FileDownloaded` | OneDrive | File download |
| `FileUploaded` | OneDrive | File upload |

### Automated Patterns (FILTERED OUT)

| Pattern | Description |
|---------|-------------|
| `RESTSystem` | System automation calls |
| `node[AppId=` | 3rd party API integrations |
| `Go-http-client` | API sync calls |
| `HubSpot` | HubSpot CRM email sync |
| `[NoUserAgent]` | Automated with no user agent |
| `Client=REST;;` | Plain REST calls |
| `SkyDriveSync` | OneDrive background sync |
| `MSWAC` | Web app companion (automated) |
| `MSOCS` | Office Online Server cache |
| `ODMTADocCache` | OneDrive cache operations |
| `MSExchangeRPC` | Internal Exchange server calls |
| `ActiveSync` | Mobile background sync protocol |
| `CoreStoreObjects` | Exchange internal storage |
| `CalendarService` | Exchange calendar automation |
| `Hub Transport` | Exchange mail routing |

---

## Time Per App Calculation

Each app gets credit for the 20-minute blocks where it had activity.

```python
# For each event, get its 20-minute block
time_block = (hour * 60 + minute) // 20

# Group by user, date, app, and count unique blocks
app_blocks = human_df.groupby(['user', 'date', 'app', 'time_block'])

# Convert blocks to hours
app_hours = num_blocks * (20 / 60)  # blocks × 0.33
```

### Example

```
User: john@company.com, Date: 03/10

Outlook events at: 9:05, 9:25, 10:15, 10:45
  → Blocks: 27, 28, 30, 32 → 4 unique blocks → 1.33 hours

Excel events at: 14:00, 14:10
  → Blocks: 42, 42 → 1 unique block → 0.33 hours
```

### Important: App Hours Can Overlap

If you use Outlook and Excel in the same 20-min block, **BOTH apps** get credit for that block. So app hours won't sum to total hours.

```
9:05 - Outlook event → Block 27
9:10 - Excel event   → Block 27

Outlook hours: 0.33 (1 block)
Excel hours: 0.33 (1 block)
Total active hours: 0.33 (1 unique block across all apps)
```

---

## Per-User Metrics

| Metric | Definition |
|--------|------------|
| **Active Hours** | Number of distinct 20-min blocks × 0.33, converted to hours |
| **Work Hours** | Active hours between 9:00 AM and 6:00 PM UTC |
| **After Hours** | Active hours before 9:00 AM or after 6:00 PM UTC |
| **Gap Hours** | 9 - Work Hours = time without activity during work hours |
| **Days Active** | Number of days with at least 1 human-triggered event |

---

## Work Hours Calculation

Work hours are defined as **9:00 AM to 6:00 PM UTC** (9 hours total).

**Note:** Purview Audit Logs are always in **UTC timezone**.

```python
WORK_START_HOUR = 9   # 9:00 AM UTC
WORK_END_HOUR = 18    # 6:00 PM UTC

# A time block is "work hours" if:
start_block = (9 * 60) // 20 = 27   # Block 27 = 9:00 AM
end_block = (18 * 60) // 20 = 54    # Block 54 = 6:00 PM

# Blocks 27-53 are work hours (27 blocks = 9 hours)
```

---

## Gap Hours Calculation

**Gap Hours** = Time during work hours (9am-6pm UTC) with NO activity.

```python
gap_hours = 9 - work_hours
```

### What Gap Hours Means

| Gap Hours | Interpretation |
|-----------|----------------|
| 0 | User was active every 20-min block during 9am-6pm |
| 2 | User was active 7 hours, idle 2 hours during work day |
| 5 | User was active 4 hours, idle 5 hours during work day |
| 9 | No activity during work hours at all |

### Example

```
User active during work hours at: 9:05, 10:30, 11:15, 14:00, 15:45

Blocks touched: 27, 31, 33, 42, 47 = 5 unique blocks
Work hours = 5 × 0.33 = 1.67 hours

Gap hours = 9 - 1.67 = 7.33 hours (idle time during 9am-6pm)
```

**Note:** High gap hours doesn't necessarily mean the user wasn't working - they could be in meetings, on calls, or doing work that doesn't generate M365 events.

---

## Data Sources

| Workload | Human Events Captured |
|----------|----------------------|
| Exchange | ~10,000+ |
| OneDrive | ~1,000+ |
| SharePoint | ~100+ |

---

## Important Notes

1. **Time block tracking** - We count distinct 20-min blocks, not continuous sessions
2. **Conservative filtering** - If an event doesn't match a known human pattern, it's excluded
3. **Work hours defined as 9 AM - 6 PM UTC** (9 hours)
4. **Timezone** - All Purview logs are in UTC
5. **Gap hours** represent potential idle time during work hours
6. **Max ~13 hours/day** typical with 20-min blocks (previously showed higher with 1-hour counting)

---

## Dashboard Layout

### Filters

| Filter | Description |
|--------|-------------|
| **Date Range** | Select start and end dates |
| **Group** | Filter by user group (e.g., Sales Team) or All Users |
| **Users** | Select individual users (auto-populated when group selected) |
| **Apps** | Filter by specific applications |

### User Groups

Groups are defined in `activity_dashboard.py`:

```python
USER_GROUPS = {
    'Sales Team': {
        'pmaccutcheon@transparentedge.com': 'Patrick MacCutcheon',
        'dblair@transparentedge.com': 'David Blair',
        # ... more users
    },
}
```

### Charts

| Chart | Description | Width |
|-------|-------------|-------|
| **Users by Activity** | Bar chart showing total hours per user | Full width |
| **Hours by App** | Horizontal bar chart of hours per application | Half width |
| **Work vs After Hours** | Pie chart comparing work hours (9am-6pm) to after hours | Half width |
| **Daily Activity Trend** | Bar chart showing total hours per day | Full width |
| **Time Spent per App by User** | Stacked horizontal bar showing each user's app breakdown | Full width |

---

## Files

| File | Purpose |
|------|---------|
| `data_processor.py` | Loads CSV, filters events, calculates metrics |
| `activity_dashboard.py` | Streamlit dashboard UI |
| `purviewAuditLogs.csv` | Raw Purview audit log data |

---

## Running the Dashboard

```bash
cd signin_report
streamlit run activity_dashboard.py
```

Dashboard available at: http://localhost:8501
