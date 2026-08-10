import datetime
from googleapiclient.discovery import build

def list_upcoming_events(service):
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now).execute()
    return events_result.get('items', [])