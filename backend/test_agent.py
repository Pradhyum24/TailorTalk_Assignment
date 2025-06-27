# backend/test_agent.py
from langgraph_agent import build_agent

graph = build_agent()
output = graph.invoke({"input": "Book a meeting tomorrow at 6 PM"})
print("🤖", output["output"])
