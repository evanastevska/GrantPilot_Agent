def save_to_google_docs(
    funder_reqs: dict,
    drafted_sections: dict,
    compliance_report: dict,
) -> str:
    """Save the final output to a Google Doc.

    Creates a formatted Google Doc with three sections:
    1. Funder Research Summary — everything from research_funder,
       formatted clearly. Any "couldn't_determine" fields are
       flagged as "VERIFY MANUALLY" items.
    2. Draft Sections each with a "DRAFT edit as needed" header.
    3. Compliance Notes what passes, what Trish should double-check.

    Requires Google OAuth credentials to be configured.

    Args:
        funder_reqs: structured requirements from the Research Agent
        drafted_sections: dict of drafted section content
        compliance_report: final compliance check results

    Returns:
        str: URL of the created Google Doc
    """
    raise NotImplementedError("Day 11: implement save_to_google_docs")