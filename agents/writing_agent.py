from langgraph.graph import StateGraph, START, END
from state import GrantPilotState
from tools.draft_section import draft_section
from concurrent.futures import ThreadPoolExecutor, as_completed


def writing_node(state: GrantPilotState) -> dict:
    """Writing Agent node drafts grant sections using funder reqs + org profile.

    Reads from state: funder_reqs, org_profile, revision_feedback
    Writes to state: drafted_sections, status
    """

    sections_to_draft = [
        "project_narrative",
        "needs_statement",
        "goals_objectives",
        "evaluation_plan",
        "org_background",
    ]

    drafted_sections = {}

    with ThreadPoolExecutor(max_workers=len(sections_to_draft)) as executor:
        future_to_section = {
            executor.submit(
                draft_section,
                section_type=section_type,
                funder_reqs=state["funder_reqs"],
                org_profile=state["org_profile"],
                revision_feedback=state["revision_feedback"] or None,
            ): section_type
            for section_type in sections_to_draft
        }

        for future in as_completed(future_to_section):
            section_type = future_to_section[future]
            result = future.result()
            drafted_sections[section_type] = result
            print(f"  Drafted {section_type} ({result['word_count']} words)")

    return {"drafted_sections": drafted_sections, "status": "writing"}


workflow = StateGraph(GrantPilotState)
workflow.add_node("writing_node", writing_node)
workflow.add_edge(START, "writing_node")
workflow.add_edge("writing_node", END)
writing_agent_app = workflow.compile()