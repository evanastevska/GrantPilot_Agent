from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

class TestState(TypedDict):
    message: str

def node_a(state):
    return {"message": state["message"] + " -> went through node A"}

graph = StateGraph(TestState)
graph.add_node("a", node_a)
graph.add_edge(START, "a")
graph.add_edge("a", END)
app = graph.compile()
result = app.invoke({"message": "hello"})
print(result)