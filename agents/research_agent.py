from langgraph.graph import StateGraph, START, END
from state import GrantPilotState
from tools.research_funder import research_funder
from tools.load_org_profile import load_org_profile


def research_node(state: GrantPilotState) -> dict:
    """Research Agent node — extracts funder requirements and loads org profile.
    
    Reads from state: funder_url, raw_grant_text
    Writes to state: funder_reqs, org_profile, status
    """

    research_funder_results = research_funder(state["funder_url"],state["raw_grant_text"])
    org_profile = load_org_profile()

    return {"funder_reqs":research_funder_results, "org_profile":org_profile, "status":"researching"}




#StateGraph using GrantPilotState
workflow = StateGraph(GrantPilotState)

#add research node as a node and add an edge from start to research mode, then research node to end
workflow.add_node("research_node", research_node)
workflow.add_edge(START, "research_node")
workflow.add_edge("research_node", END)
research_agent_app = workflow.compile()