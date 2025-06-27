import os
import datetime
import json
from typing import TypedDict
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from groq import Groq

from calendar_utils import (
    create_event,
    check_availability,
    suggest_alternate_slots,
    get_available_slots,
    delete_event
)

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class AgentState(TypedDict, total=False):
    input: str
    intent: str
    date: str
    time: str
    output: str
    last_intent: str
    last_date: str
    last_time: str

def extract_intent(state: AgentState) -> AgentState:
    message = state["input"]
    print("🧠 Extracting intent for:", message)

    today = datetime.date.today().isoformat()
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Today's date is {today}. Extract the user's intent from their message.\n"
                    "Valid intents: book_meeting, cancel_meeting, show_slots, greeting.\n"
                    "Respond ONLY with a valid JSON object like this:\n"
                    '{"intent": "book_meeting", "date": "2025-06-28", "time": "13:30"}\n'
                    "All keys and string values must be in double quotes. Do not add extra commentary or formatting."
                )
            },
            {"role": "user", "content": message}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("📦 Raw response:", raw)

    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent", "unknown")
        date = parsed.get("date") or state.get("last_date")
        time = parsed.get("time") or state.get("last_time")

        # Carry forward intent if context exists
        if intent in ["unknown", "greeting"]:
            if (date or time) and state.get("last_intent") in ["book_meeting", "cancel_meeting"]:
                intent = state["last_intent"]

        return {
            "input": message,
            "intent": intent,
            "date": date,
            "time": time,
            "last_intent": intent,
            "last_date": date,
            "last_time": time
        }

    except Exception as e:
        print("❌ Parse error:", e)
        return {
            "input": message,
            "intent": "unknown",
            "last_intent": state.get("last_intent"),
            "last_date": state.get("last_date"),
            "last_time": state.get("last_time")
        }

def handle_booking(state: AgentState) -> AgentState:
    date_str = state.get("date")
    time_str = state.get("time")

    if not date_str or date_str.lower() == "unknown":
        return {"output": "⚠️ Please provide a valid date to book."}
    if not time_str or time_str.lower() == "unknown":
        return {"output": f"🕐 What time would you like to book on {date_str}?"}

    tz = ZoneInfo("Asia/Kolkata")
    try:
        start = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except ValueError:
        return {"output": "⚠️ Time must be in HH:MM format (e.g. 14:30 for 2:30 PM)."}

    end = start + datetime.timedelta(minutes=30)
    now = datetime.datetime.now(tz)

    if start <= now:
        return {"output": f"⚠️ That time is in the past. Please pick a future time."}
    if start.minute not in [0, 30]:
        return {"output": "⚠️ Appointments must start on the hour or half-hour (e.g., 10:00, 10:30)."}

    print(f"📅 Booking from {start} to {end}")

    if not check_availability(start, end):
        suggestions = suggest_alternate_slots(start)
        if suggestions:
            return {"output": f"❌ That time is booked. Try: {', '.join(suggestions)}?"}
        else:
            return {"output": "❌ That time is booked and no nearby slots are free."}

    create_event(start, end, summary="Appointment")
    return {
        "output": f"✅ Appointment booked on {date_str} at {time_str}."
    }

def handle_show_slots(state: AgentState) -> AgentState:
    date_str = state.get("date")
    if not date_str:
        return {"output": "⚠️ Please specify the date."}

    slots = get_available_slots(date_str)
    if not slots:
        return {"output": f"❌ No available slots on {date_str}."}
    return {"output": f"✅ Available slots on {date_str}: {', '.join(slots)}"}

def handle_cancellation(state: AgentState) -> AgentState:
    date_str = state.get("date") or state.get("last_date")
    time_str = state.get("time") or state.get("last_time")

    if not date_str or not time_str:
        return {"output": "⚠️ Please provide the date and time to cancel."}

    success = delete_event(date_str, time_str)
    if success:
        return {"output": f"✅ Appointment at {time_str} on {date_str} was cancelled."}
    else:
        return {"output": f"❌ No appointment found at that time."}

def fallback(state: AgentState) -> AgentState:
    input_text = state.get("input", "").lower()
    last_intent = state.get("last_intent")
    print("🧩 Fallback state:", state)

    if any(word in input_text for word in ["hi", "hello", "hey"]):
        return {"output": "👋 Hello! I can help you book, cancel, or show available appointment slots."}

    if last_intent == "book_meeting":
        date = state.get("date") or state.get("last_date")
        time = state.get("time") or state.get("last_time")

        if not date:
            return {"output": "📅 Please provide the date you'd like to book."}
        if not time:
            return {"output": f"🕐 What time would you like to book on {date}?"}

        return handle_booking({
            **state,
            "date": date,
            "time": time
        })

    if last_intent == "cancel_meeting":
        return handle_cancellation(state)

    return {"output": "🤖 Sorry, I didn't understand that. Try asking to book, cancel, or check slots."}

def build_agent():
    workflow = StateGraph(state_schema=AgentState)
    workflow.add_node("extract_intent", extract_intent)
    workflow.add_node("book_slot", handle_booking)
    workflow.add_node("show_slots", handle_show_slots)
    workflow.add_node("cancel_meeting", handle_cancellation)
    workflow.add_node("fallback", fallback)

    def route(state: AgentState) -> str:
        intent = state.get("intent")
        if intent == "book_meeting":
            return "book_slot"
        elif intent == "show_slots":
            return "show_slots"
        elif intent == "cancel_meeting":
            return "cancel_meeting"
        elif intent == "greeting":
            return "fallback"
        return "fallback"

    workflow.set_entry_point("extract_intent")
    workflow.add_conditional_edges("extract_intent", route)
    workflow.add_edge("book_slot", END)
    workflow.add_edge("show_slots", END)
    workflow.add_edge("cancel_meeting", END)
    workflow.add_edge("fallback", END)

    return workflow.compile()
