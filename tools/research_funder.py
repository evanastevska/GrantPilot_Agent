def research_funder(
    funder_url: str | None = None,
    raw_grant_text: str | None = None,
) -> dict:
    """Research a funder and extract structured grant requirements.

    Accepts a funder URL, pasted grant text, or both. At least one
    must be provided.

    - If raw_grant_text is provided: skip the fetch, go straight to
      LLM extraction (faster, more reliable the user probably has
      the RFP open already).
    - If funder_url is provided: fetch the page, then extract.
    - If both: use pasted text as primary, URL as supplementary.

    Any requirement that can't be found gets a "couldn't_determine"
    value instead of being silently omitted. Silent omission makes
    the research look complete when it isn't.

    Returns:
        dict with keys like:
        - funder_name: str
        - deadline: str or "couldn't_determine"
        - funding_amount: str or "couldn't_determine"
        - eligibility: list[str] or "couldn't_determine"
        - page_word_limits: dict or "couldn't_determine"
        - required_sections: list[str] or "couldn't_determine"
        - evaluation_criteria: list[str] or "couldn't_determine"
        - past_funded_projects: list[str] or "couldn't_determine"
        - funder_overview: str
    """
    raise NotImplementedError("Day 3: implement research_funder")