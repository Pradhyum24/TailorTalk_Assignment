# backend/calendar_utils.py

from googleapiclient.errors import HttpError
import datetime
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from zoneinfo import ZoneInfo 
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    creds = None
    token_path = "token.pickle"
    creds_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "credentials", "credentials.json"))

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)
    return service

def check_availability(start_time, end_time):
    service = get_calendar_service()

    time_min = start_time.isoformat()
    time_max = end_time.isoformat()

    print(f"🔍 Checking availability from {time_min} to {time_max}")

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])

        if events:
            print(f"⛔ Conflict found with {len(events)} event(s):")
            for event in events:
                summary = event.get("summary", "No title")
                event_start = event.get("start", {}).get("dateTime", "Unknown")
                event_end = event.get("end", {}).get("dateTime", "Unknown")
                print(f" → Event: {summary} | {event_start} to {event_end}")
            return False

        print("✅ No conflict, slot is free.")
        return True

    except HttpError as error:
        print("❌ Google Calendar API error:", error)
        return False


def create_event(start_time, end_time, summary="Meeting with user"):
    service = get_calendar_service()
    event = {
        "summary": summary,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "Asia/Kolkata"
        }
    }
    event = service.events().insert(calendarId="primary", body=event).execute()
    print("✅ Event created:", event.get("htmlLink"))
    return event.get("htmlLink")

def suggest_alternate_slots(start, duration=30, window=120):
    suggestions = []
    end = start + datetime.timedelta(minutes=window)

    while start < end:
        next_end = start + datetime.timedelta(minutes=duration)
        if check_availability(start, next_end):
            suggestions.append(start.strftime("%H:%M"))
            if len(suggestions) >= 3:
                break
        start += datetime.timedelta(minutes=15)

    return suggestions

def get_available_slots(date_str, duration=30):
    service = get_calendar_service()
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    tz = ZoneInfo("Asia/Kolkata")

    slots = []
    start_time = datetime.datetime.combine(date, datetime.time(9, 0)).replace(tzinfo=tz)
    end_time = datetime.datetime.combine(date, datetime.time(18, 0)).replace(tzinfo=tz)

    while start_time + datetime.timedelta(minutes=duration) <= end_time:
        slot_end = start_time + datetime.timedelta(minutes=duration)

        if start_time > now and check_availability(start_time, slot_end):
            slots.append(start_time.strftime("%H:%M"))

        start_time += datetime.timedelta(minutes=30)

    return slots

def delete_event(date_str, time_str, expected_name=None):
    service = get_calendar_service()
    start = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    end = start + datetime.timedelta(minutes=30)

    print(f"🗑️ Looking for event to delete from {start} to {end} with name: {expected_name}")

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True
        ).execute()

        events = events_result.get("items", [])
        for event in events:
            summary = event.get("summary", "")
            if expected_name and expected_name.lower() not in summary.lower():
                continue
            print("🗑️ Deleting event:", summary)
            service.events().delete(calendarId="primary", eventId=event["id"]).execute()
            return True

        print("⚠️ No matching event found.")
        return False

    except HttpError as error:
        print("❌ Google Calendar API error during deletion:", error)
        return False

    except HttpError as error:
        print("❌ Google Calendar API error during deletion:", error)
        return False