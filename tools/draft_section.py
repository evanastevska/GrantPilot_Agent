def draft_section(
    section_type: str,
    funder_reqs: dict,
    org_profile: dict,
    revision_feedback: str | None = None,
) -> dict:
    """Draft one section of a grant application.

    Each section type gets its own prompt template with best practices
    for that section. The draft references specific funder priorities
    and org data no generic filler.

    Args:
        section_type: one of "project_narrative", "needs_statement",
            "goals_objectives", "evaluation_plan",
            "budget_justification", "org_background"
        funder_reqs: structured requirements from the Research Agent
        org_profile: Cinema Verde's verified org data
        revision_feedback: specific feedback from the Review Agent
            on what to fix (None on the first pass)

    Returns:
        dict with keys:
        - section_type: str (echoes input)
        - content: str (the drafted text)
        - word_count: int
    """
    raise NotImplementedError("Day 4: implement draft_section")