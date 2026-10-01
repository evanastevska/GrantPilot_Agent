def check_compliance(
    drafted_sections: dict,
    funder_reqs: dict,
) -> dict:
    """Check drafted sections against funder requirements.

    Two types of checks:
    - Programmatic (in code, not LLM): word/page count vs limits,
      required sections present, deadline noted.
    - LLM-based (needs judgment): each eligibility criterion addressed,
      each evaluation criterion covered, claims grounded in org data
      or unsupported.

    The split between programmatic and LLM checks is deliberate
    deterministic where can be, LLM where need judgment.

    Also classifies each gap by source:
    - WRITING gap: requirement IS in the research but the draft
      doesn't address it → route to Writing Agent
    - RESEARCH gap: requirement NOT in the research at all →
      route to Research Agent

    Args:
        drafted_sections: dict keyed by section type, values are
            draft strings from the Writing Agent
        funder_reqs: structured requirements from the Research Agent

    Returns:
        dict with keys:
        - passed: list of requirements that are met
        - failed: list of dicts, each with "requirement", "gap_type"
            ("writing" or "research"), and "feedback" (specific
            explanation of what's wrong)
        - programmatic_results: dict of deterministic check results
        - overall_status: "approved" | "revise" | "research_needed"
    """
    raise NotImplementedError("Day 5: implement check_compliance")