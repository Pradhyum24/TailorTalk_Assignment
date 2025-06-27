from calendar_utils import create_event
import datetime

start = datetime.datetime.now() + datetime.timedelta(days=1, hours=1)
end = start + datetime.timedelta(minutes=30)

link = create_event(start, end)
print("📅 Event created:", link)
