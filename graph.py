from langgraph.graph import StateGraph, START, END
from state import GrantPilotState
from agents.research_agent import research_node
from agents.writing_agent import writing_node
from agents.review_agent import review_node

def route_after_review(state: GrantPilotState) -> str:
    """Decide where to go after the Review Agent runs.

    Reads: compliance_report["overall_status"], revision_count
    Returns: "writing_node", "research_node", or "end"
    """
    #if revision_count >= 2, done to not be endless loop
    if state["revision_count"] >= 2:
        return "end"

    if state["compliance_report"]["overall_status"] == "approved":
        return "end"
    elif state["compliance_report"]["overall_status"] == "needs_revision":
        if state["compliance_report"]["revision_type"] == "writing":
            return "writing_node"
        elif state["compliance_report"]["revision_type"] == "research":
            return "research_node"

    return "end"

workflow = StateGraph(GrantPilotState)

workflow.add_node("research_node", research_node)
workflow.add_node("writing_node", writing_node)
workflow.add_node("review_node", review_node)

workflow.add_edge(START, "research_node")
workflow.add_edge("research_node", "writing_node")
workflow.add_edge("writing_node", "review_node")


workflow.add_conditional_edges(
    "review_node",          #the node this edge comes FROM
    route_after_review,     #the function that decides where to go
    {                       #mapping: when function returns this string, go to that node
        "writing_node": "writing_node",
        "research_node": "research_node",
        "end": END,
    }
)


#compile the graph
app = workflow.compile()
