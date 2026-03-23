"""
Data processor for Purview Audit Logs
Transforms raw audit events into session-based activity data
"""

import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Optional


# Work hours (in UTC - Purview logs are UTC)
WORK_START_HOUR = 9
WORK_END_HOUR = 18

# Default time block size in minutes (can be overridden via parameter)
DEFAULT_TIME_BLOCK_MINUTES = 20

# Patterns that indicate HUMAN-triggered events
HUMAN_TRIGGERS = [
    'Outlook-iOS',      # Mobile app
    'Outlook-Android',  # Mobile app
    'OWA',              # Outlook Web App (browser)
    'OneOutlook',       # New Outlook desktop
    'Outlook/',         # Classic Outlook desktop
    'OUTLOOK.EXE',      # Classic Outlook desktop (Windows)
    'MacOutlook',       # Outlook for Mac
    'Mozilla/',         # Browser
    'Chrome/',          # Browser
    'Safari/',          # Browser
    'Edge/',            # Browser
    'Teams',            # Teams app
    'TeamsMobile',      # Teams mobile
    'Microsoft Office', # Office desktop apps (Word, Excel, PowerPoint)
    'Microsoft Office/', # Office apps via UserAgent
]

# Operations that indicate HUMAN activity (regardless of client info)
HUMAN_OPERATIONS = [
    # Teams meetings & calls
    'MeetingParticipantDetail',
    'MeetingDetail',
    'TeamsSessionStarted',
    'CallParticipantDetail',
    # Teams messaging
    'MessageSent',
    'ReactedToMessage',
    'MessageCreatedHasLink',
    'MessageUpdated',
    'MessageCreatedNotification',
    # Copilot
    'CopilotInteraction',
    # Microsoft Todo
    'TaskCreated',
    'TaskUpdated',
    # Exchange - sending emails
    'Send',
    'SendOnBehalf',
    # OneDrive - file actions
    'FileDownloaded',
    'FileUploaded',
]

# Patterns that indicate AUTOMATED events (filter these OUT)
AUTOMATED_TRIGGERS = [
    'RESTSystem',       # System automation
    'node[AppId=',      # API integration / 3rd party sync
    'Go-http-client',   # API calls
    'HubSpot',          # HubSpot sync
    '[NoUserAgent]',    # Automated with no user agent
    'Client=REST;;',    # Plain REST call with no agent
    'SkyDriveSync',     # OneDrive background sync
    'MSWAC',            # Web app companion (automated)
    'MSOCS',            # Office Online Server (automated)
    'ODMTADocCache',    # OneDrive cache (automated)
    'MSExchangeRPC',    # Internal Exchange server calls
    'ActiveSync',       # Mobile background sync
    'CoreStoreObjects', # Exchange internal storage
    'CalendarService',  # Exchange calendar automation
    'Hub Transport',    # Exchange mail routing
]


def is_human_triggered(actor_info: str, client_info: str, user_agent: str = '', operation: str = '') -> bool:
    """
    Determine if an event was triggered by a human or automated.
    Returns True only if we can positively identify human activity.
    Checks ActorInfoString, ClientInfoString, UserAgent, and Operation fields.
    """
    actor = actor_info or ''
    client = client_info or ''
    ua = user_agent or ''
    op = operation or ''
    combined = actor + ' ' + client + ' ' + ua

    # First check: certain operations are ALWAYS human-triggered (highest priority)
    # These override automated patterns because you can't automate sending an email
    if op in HUMAN_OPERATIONS:
        return True

    # Second check: if it matches automated patterns, it's NOT human
    for pattern in AUTOMATED_TRIGGERS:
        if pattern in combined:
            return False

    # Third check: must match a human pattern to count
    for pattern in HUMAN_TRIGGERS:
        if pattern in combined:
            return True

    # If neither, default to NOT human (conservative)
    return False


def normalize_app_name(actor_info: str, client_info: str, workload: str, user_agent: str = '', operation: str = '') -> str:
    """Map raw client info to friendly app names"""
    actor = actor_info or ''
    client = client_info or ''
    ua = user_agent or ''
    op = operation or ''

    # Check UserAgent first for Office apps
    if 'Excel' in ua:
        return 'Excel'
    elif 'PowerPoint' in ua:
        return 'PowerPoint'
    elif 'OneNote' in ua:
        return 'OneNote'
    elif 'Word' in ua:
        return 'Word'

    # Check workload-specific apps
    if workload == 'Copilot':
        return 'Copilot'
    elif workload == 'MicrosoftTodo':
        return 'Microsoft To Do'

    # Then check client/actor patterns
    if 'Outlook-iOS' in actor or 'Outlook-Android' in actor:
        return 'Outlook Mobile'
    elif 'Outlook-iOS' in client or 'Outlook-Android' in client:
        return 'Outlook Mobile'
    elif 'OneOutlook' in actor or 'OneOutlook' in client:
        return 'Outlook Desktop'
    elif 'OWA' in client:
        return 'Outlook Web'
    elif 'OUTLOOK.EXE' in actor:
        return 'Outlook Desktop'
    elif 'MacOutlook' in client:
        return 'Outlook Desktop'
    elif 'Outlook' in actor:
        return 'Outlook Desktop'
    elif 'Teams' in actor or 'Teams' in ua or workload == 'MicrosoftTeams':
        return 'Microsoft Teams'
    elif workload == 'OneDrive':
        return 'OneDrive'
    elif workload == 'SharePoint':
        return 'SharePoint'
    elif workload == 'AzureActiveDirectory':
        return 'Azure AD'
    elif workload == 'Exchange':
        return 'Exchange'
    else:
        return workload or 'Other'


def is_real_employee(user_id: str) -> bool:
    """Filter to real employees only"""
    if not user_id:
        return False
    # Must be an email ending with company domain
    if '@transparentedge.com' not in user_id.lower():
        return False
    # Exclude system-looking accounts (GUIDs, etc)
    if len(user_id) == 36 and user_id.count('-') == 4:
        return False
    return True


def load_and_parse_audit_logs(csv_path: str) -> pd.DataFrame:
    """Load CSV and parse AuditData JSON into columns"""
    print(f"Loading {csv_path}...")

    # Read CSV
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  Loaded {len(df)} records")

    # Parse AuditData JSON
    records = []
    for idx, row in df.iterrows():
        try:
            audit = json.loads(row.get('AuditData', '{}'))
            user_id = row.get('UserId', '') or audit.get('UserId', '')

            # Filter to real employees
            if not is_real_employee(user_id):
                continue

            # Extract fields
            creation_time = audit.get('CreationTime', '')
            if creation_time:
                timestamp = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
            else:
                continue

            actor_info = audit.get('ActorInfoString', '')
            client_info = audit.get('ClientInfoString', '')
            user_agent = audit.get('UserAgent', '')
            operation = audit.get('Operation', '')

            app = normalize_app_name(actor_info, client_info, audit.get('Workload', ''), user_agent, operation)
            is_human = is_human_triggered(actor_info, client_info, user_agent, operation)

            records.append({
                'user': user_id.lower(),
                'timestamp': timestamp,
                'date': timestamp.date(),
                'hour': timestamp.hour,
                'operation': audit.get('Operation', 'Unknown'),
                'workload': audit.get('Workload', 'Unknown'),
                'app': app,
                'is_human': is_human,
                'ip_address': audit.get('ClientIPAddress', ''),
            })
        except Exception as e:
            continue

    result = pd.DataFrame(records)
    print(f"  Filtered to {len(result)} employee events")
    human_events = result[result['is_human']].shape[0]
    print(f"  Human activity events: {human_events}")
    return result


def get_time_block(timestamp, time_block_minutes=DEFAULT_TIME_BLOCK_MINUTES):
    """Get the time block index for a timestamp based on time_block_minutes."""
    hour = timestamp.hour
    minute = timestamp.minute
    total_minutes = hour * 60 + minute
    return total_minutes // time_block_minutes


def time_block_to_hours(num_blocks, time_block_minutes=DEFAULT_TIME_BLOCK_MINUTES):
    """Convert number of time blocks to hours."""
    return (num_blocks * time_block_minutes) / 60


def is_work_hours_block(block_index, time_block_minutes=DEFAULT_TIME_BLOCK_MINUTES):
    """Check if a time block falls within work hours (9am-6pm)."""
    start_block = (WORK_START_HOUR * 60) // time_block_minutes
    end_block = (WORK_END_HOUR * 60) // time_block_minutes
    return start_block <= block_index < end_block


def calculate_active_hours(df: pd.DataFrame, time_block_minutes: int = DEFAULT_TIME_BLOCK_MINUTES) -> pd.DataFrame:
    """
    Calculate active hours per user per day per app.
    Uses distinct time blocks (e.g., 20-min blocks) for more accuracy.

    Args:
        df: DataFrame with parsed audit events
        time_block_minutes: Size of time blocks in minutes (e.g., 15, 20, 30, 60)
    """
    if df.empty:
        return pd.DataFrame()

    # Filter to human activity only for primary metrics
    human_df = df[df['is_human']].copy()

    # Calculate time block for each event
    human_df['time_block'] = human_df['timestamp'].apply(
        lambda ts: get_time_block(ts, time_block_minutes)
    )

    # First, get distinct time blocks per user/date (across all apps)
    user_blocks = human_df.groupby(['user', 'date', 'time_block']).size().reset_index(name='count')

    # Calculate total distinct blocks per user/date, converted to hours
    user_daily_blocks = user_blocks.groupby(['user', 'date']).agg({
        'time_block': 'nunique'
    }).reset_index()
    user_daily_blocks.columns = ['user', 'date', 'total_blocks']
    user_daily_blocks['total_active_hours'] = user_daily_blocks['total_blocks'].apply(
        lambda b: time_block_to_hours(b, time_block_minutes)
    )

    # Calculate work hours blocks (9am-6pm) per user/date
    work_block_mask = user_blocks['time_block'].apply(
        lambda b: is_work_hours_block(b, time_block_minutes)
    )
    user_work_blocks = user_blocks[work_block_mask].groupby(['user', 'date'])['time_block'].nunique().reset_index()
    user_work_blocks.columns = ['user', 'date', 'work_blocks']
    user_work_blocks['work_hours'] = user_work_blocks['work_blocks'].apply(
        lambda b: time_block_to_hours(b, time_block_minutes)
    )

    # Calculate after hours blocks per user/date
    after_block_mask = ~user_blocks['time_block'].apply(
        lambda b: is_work_hours_block(b, time_block_minutes)
    )
    user_after_blocks = user_blocks[after_block_mask].groupby(['user', 'date'])['time_block'].nunique().reset_index()
    user_after_blocks.columns = ['user', 'date', 'after_blocks']
    user_after_blocks['after_hours'] = user_after_blocks['after_blocks'].apply(
        lambda b: time_block_to_hours(b, time_block_minutes)
    )

    # Now get per-app breakdown (for chart purposes)
    app_blocks = human_df.groupby(['user', 'date', 'app', 'time_block']).agg({
        'operation': 'count'
    }).reset_index()
    app_blocks.columns = ['user', 'date', 'app', 'time_block', 'events']

    daily_app = app_blocks.groupby(['user', 'date', 'app']).agg({
        'time_block': 'nunique',  # blocks in this app
        'events': 'sum'           # total events
    }).reset_index()
    daily_app.columns = ['user', 'date', 'app', 'app_blocks', 'event_count']
    daily_app['app_hours'] = daily_app['app_blocks'].apply(
        lambda b: time_block_to_hours(b, time_block_minutes)
    )

    # Merge user-level metrics
    daily_app = daily_app.merge(user_daily_blocks[['user', 'date', 'total_active_hours']], on=['user', 'date'], how='left')
    daily_app = daily_app.merge(user_work_blocks[['user', 'date', 'work_hours']], on=['user', 'date'], how='left')
    daily_app = daily_app.merge(user_after_blocks[['user', 'date', 'after_hours']], on=['user', 'date'], how='left')

    # Calculate gap hours (work day is 9 hours: 9am-6pm)
    daily_app['gap_hours'] = (WORK_END_HOUR - WORK_START_HOUR) - daily_app['work_hours'].fillna(0)
    daily_app['gap_hours'] = daily_app['gap_hours'].clip(lower=0)

    # Fill NaN
    daily_app = daily_app.fillna(0)

    # Round hours to 1 decimal
    for col in ['app_hours', 'total_active_hours', 'work_hours', 'after_hours', 'gap_hours']:
        if col in daily_app.columns:
            daily_app[col] = daily_app[col].round(1)

    # Keep event_count as int
    daily_app['event_count'] = daily_app['event_count'].astype(int)

    return daily_app


def get_summary_stats(df: pd.DataFrame) -> dict:
    """Get summary statistics for the dashboard"""
    if df.empty:
        return {}

    # Get unique user/date combinations for accurate avg
    user_daily = df.groupby(['user', 'date'])['total_active_hours'].first().reset_index()

    return {
        'total_active_hours': user_daily['total_active_hours'].sum(),
        'unique_users': df['user'].nunique(),
        'unique_days': df['date'].nunique(),
        'total_events': df['event_count'].sum(),
        'avg_hours_per_user_per_day': user_daily['total_active_hours'].mean(),
        'max_hours_in_day': user_daily['total_active_hours'].max(),
    }


def process_audit_logs(csv_path: str, time_block_minutes: int = DEFAULT_TIME_BLOCK_MINUTES) -> pd.DataFrame:
    """
    Main processing pipeline.

    Args:
        csv_path: Path to the Purview audit logs CSV file
        time_block_minutes: Size of time blocks in minutes (e.g., 15, 20, 30, 60)
    """
    # Load and parse
    events_df = load_and_parse_audit_logs(csv_path)

    if events_df.empty:
        print("No employee events found!")
        return pd.DataFrame()

    # Calculate active hours
    print(f"Calculating active hours (using {time_block_minutes}-minute blocks)...")
    result_df = calculate_active_hours(events_df, time_block_minutes)
    print(f"  Created {len(result_df)} daily app records")

    # Get summary
    stats = get_summary_stats(result_df)
    print(f"\nSummary:")
    print(f"  Total active hours: {stats.get('total_active_hours', 0):.0f}")
    print(f"  Unique users: {stats.get('unique_users', 0)}")
    print(f"  Avg hours/user/day: {stats.get('avg_hours_per_user_per_day', 0):.1f}")
    print(f"  Max hours in a day: {stats.get('max_hours_in_day', 0)}")

    return result_df


if __name__ == '__main__':
    # Test processing
    df = process_audit_logs('purviewAuditLogs.csv')
    if not df.empty:
        print("\nSample output:")
        print(df.head(20))

        print("\nDaily totals per user (first 15):")
        daily = df.groupby(['user', 'date']).agg({
            'total_active_hours': 'first',
            'work_hours': 'first',
            'after_hours': 'first',
            'gap_hours': 'first',
            'event_count': 'sum'
        }).reset_index()
        print(daily.head(15).to_string())

        print(f"\nMax active hours in a day: {daily['total_active_hours'].max()}")
