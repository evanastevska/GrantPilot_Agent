def _check_word_counts(drafted_sections: dict, funder_reqs: dict) -> list:
    """Compare each section's word count against funder limits.
    
    funder_reqs["page_word_limits"] looks like: {"project narrative": "max 3 pages"}
    Approximate 350 words per page when the limit is in pages.
    
    Returns a list of dicts, one per section that HAS a limit:
        {"section": str, "word_count": int, "limit": int, "status": "within_limit" | "over_limit"}
    """
    results = []

    page_word_limits = funder_reqs.get("page_word_limits", {})

    if page_word_limits == "couldn't_determine":
        return []

    for section_name, limit_string in page_word_limits.items():
        #parse the number out of strings like "max 3 pages"
        limit_words = None
        for word in limit_string.split():
            try:
                num = int(word)
                if "page" in limit_string.lower():
                    limit_words = num * 350
                else:
                    limit_words = num
                break
            except ValueError:
                continue

        if limit_words is None:
            continue

        #normalize "project narrative" → "project_narrative" to match drafted_sections keys
        normalized = section_name.replace(" ", "_").lower()

        if normalized in drafted_sections:
            word_count = drafted_sections[normalized]["word_count"]
            results.append({
                "section": normalized,
                "word_count": word_count,
                "limit": limit_words,
                "status": "over_limit" if word_count > limit_words else "within_limit",
            })

    return results


def _check_required_sections(drafted_sections: dict, funder_reqs: dict) -> list:
    """Check if all funder-required sections are present in the drafts.
    
    funder_reqs["required_sections"] looks like: 
        ["project narrative", "budget justification", "organizational background", ...]
    drafted_sections keys look like: 
        "project_narrative", "needs_statement", "goals_objectives", ...
    
    Returns a list of section names that are required but missing from drafts.
    """
    required = funder_reqs.get("required_sections", [])

    if required == "couldn't_determine":
        return []

    missing = []
    for section_name in required:
        normalized = section_name.replace(" ", "_").lower()
        if normalized not in drafted_sections:
            missing.append(section_name)

    return missing


def _check_deadline(funder_reqs: dict) -> str | None:
    """Surface the deadline so the user sees it in the report.
    
    This isn't a pass/fail check just pulls the deadline out
    of funder_reqs so it's visible in the compliance report.
    
    Returns the deadline string, or None if couldn't_determine.
    """
    deadline = funder_reqs.get("deadline", "couldn't_determine")
    if deadline == "couldn't_determine":
        return None
    return deadline