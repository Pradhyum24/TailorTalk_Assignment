from fastapi import FastAPI

app = FastAPI()
conversation_state = {}

try:
    from langgraph_agent import build_agent
    agent = build_agent()
except Exception as e:
    print("❌ Agent initialization failed:", e)
    agent = None

@app.post("/chat")
def chat(input: dict):
    if agent is None:
        return {"response": "⚠️ Agent failed to load. Check backend logs."}

    user_message = input["message"]
    state = conversation_state.copy()
    state["input"] = user_message

    output = agent.invoke(state)
    conversation_state.update(output)

    return {"response": output.get("output")}
