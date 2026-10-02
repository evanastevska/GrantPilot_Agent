from langgraph.graph import StateGraph, START, END
from state import GrantPilotState
from tools.check_compliance import check_compliance


def review_node(state: GrantPilotState) -> dict:
    """Review Agent node, checks draft compliance against funder requirements.

    Reads from state: drafted_sections, funder_reqs, org_profile
    Writes to state: compliance_report, revision_feedback, status

    CRITICAL: does NOT read compliance_report or revision_feedback from state.
    This is the reviewer bias fix, the reviewer evaluates fresh against
    funder requirements, never against its own prior feedback.
    """

    compliance_report = check_compliance(drafted_sections = state["drafted_sections"],
                    funder_reqs = state["funder_reqs"],
                    org_profile = state["org_profile"])

    return {
        "compliance_report": compliance_report,
        "revision_feedback": compliance_report["revision_feedback"],
        "status": compliance_report["overall_status"],
    }


workflow = StateGraph(GrantPilotState)
workflow.add_node("review_node", review_node)
workflow.add_edge(START, "review_node")
workflow.add_edge("review_node", END)
review_agent_app = workflow.compile()