import datetime
import os
import re
import sys
import pytz

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# Authentication and reading credentials.json. Check if token.json exists first
def authenticate_google():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

# Reading user input to add an event
def parse_event_input(event_input):
    regex = r'(\d{1,2}:\d{2}) - (\d{1,2}:\d{2}), (\d{1,2}/\d{1,2}(?:/\d{2,4})?), (.+?)(?:\s*R)?$'
    match = re.match(regex, event_input)
    if not match:
        print("Invalid input format. Please use 'HH:MM - HH:MM, DD/MM/YY or DD/MM, Event Description R (optional)'")
        return None

    start_time, end_time, date_str, description = match.groups()

    current_year = datetime.datetime.now().year
    if len(date_str.split('/')) == 2:
        date_format = '%d/%m'
        event_date = datetime.datetime.strptime(date_str, date_format).replace(year=current_year)
        if event_date < datetime.datetime.now():
            event_date = event_date.replace(year=current_year + 1)
    else:
        date_format = '%d/%m/%y'
        event_date = datetime.datetime.strptime(date_str, date_format)

    start_datetime = datetime.datetime.combine(event_date.date(), datetime.datetime.strptime(start_time, '%H:%M').time())
    end_datetime = datetime.datetime.combine(event_date.date(), datetime.datetime.strptime(end_time, '%H:%M').time())

    is_recurring = event_input.strip().endswith('R')
    
    return start_datetime, end_datetime, description, is_recurring

# Using Irish timezone. Update this for your timezone.
def add_event_to_calendar(service, start_datetime, end_datetime, description, is_recurring):
    event = {
        'summary': description,
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'Europe/Dublin',  # Update time zone
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'Europe/Dublin',  # Update time zone
        },
    }

    if is_recurring:
        event['recurrence'] = [
            'RRULE:FREQ=WEEKLY'
        ]

    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")
    return event['id']

# For undoing. This could be expanded to remove other events from the calendar.
def remove_event_from_calendar(service, event_id):
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        print("Last event removed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

# List events for today, reading in UTC

def list_today_events(service):
    utc = pytz.UTC
    now = datetime.datetime.now(utc).isoformat()
    end_of_day = (datetime.datetime.now(utc) + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    events_result = service.events().list(calendarId='primary', timeMin=now, timeMax=end_of_day,
                                          singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found for today.')
    else:
        print('Today\'s events:')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))

            # Convert to datetime objects
            start_dt = datetime.datetime.fromisoformat(start)
            end_dt = datetime.datetime.fromisoformat(end)

            # Format date and time
            start_time_str = start_dt.strftime('%H:%M')
            end_time_str = end_dt.strftime('%H:%M')

            print(f"{event['summary']} from {start_time_str} to {end_time_str}")

# Recurring loop for adding events and checking for user input
def main():
    service = authenticate_google()
    last_event_id = None

    while True:
        event_input = input("Enter event (HH:MM - HH:MM, DD/MM/YY or DD/MM, Event Description R (optional)) or 'undo' to remove the last event or 'today' to list today's events or 'exit' to quit: ")
        if event_input.lower() == 'exit':
            break
        elif event_input.lower() == 'undo':
            if last_event_id:
                remove_event_from_calendar(service, last_event_id)
                last_event_id = None
            else:
                print("No event to undo.")
        elif event_input.lower() == 'today':
            list_today_events(service)
        else:
            event_data = parse_event_input(event_input)
            if event_data:
                start_datetime, end_datetime, description, is_recurring = event_data
                last_event_id = add_event_to_calendar(service, start_datetime, end_datetime, description, is_recurring)

if __name__ == '__main__':
    main()