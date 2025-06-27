# main.py

from fastapi import FastAPI
from langgraph_agent import build_agent

app = FastAPI()
agent = build_agent()

conversation_state = {}  # ← Global session memory

@app.post("/chat")
def chat(input: dict):
    user_message = input["message"]

    # Start with current state
    state = conversation_state.copy()
    state["input"] = user_message

    # Run the agent
    output = agent.invoke(state)

    # Update memory
    conversation_state.update(output)

    return {"response": output.get("output")}
