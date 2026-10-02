from langgraph.graph import StateGraph, START, END
from state import GrantPilotState
from tools.draft_section import draft_section


def writing_node(state: GrantPilotState) -> dict:
    """Writing Agent node — drafts grant sections using funder reqs + org profile.

    Reads from state: funder_reqs, org_profile, revision_feedback
    Writes to state: drafted_sections, status
    """

    #defines what sections need to be drafted, rn hard coded but later will come from funder_reqs["required_sections"]
    sections_to_draft = [
        "project_narrative",
        "needs_statement",
        "goals_objectives",
        "evaluation_plan",
        "org_background",
    ]

    drafted_sections = {}
    for section_type in sections_to_draft:
        #this is everything that gets passed into the prompt
        result = draft_section(
            section_type = section_type,
            funder_reqs = state["funder_reqs"],
            org_profile = state["org_profile"],
            revision_feedback = state["revision_feedback"] or None,
        )
        #prose gets stored
        drafted_sections[section_type] = result
        print(f"  Drafted {section_type} ({result['word_count']} words)")

    return {"drafted_sections": drafted_sections, "status": "writing"}


workflow = StateGraph(GrantPilotState)
workflow.add_node("writing_node", writing_node)
workflow.add_edge(START, "writing_node")
workflow.add_edge("writing_node", END)
writing_agent_app = workflow.compile()