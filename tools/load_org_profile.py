def load_org_profile() -> dict:
    """Load Cinema Verde's organization profile from the local JSON file.

    This grounds all writing in verified org data so the Writing Agent
    never makes up facts about the organization. Every claim about
    Cinema Verde in a drafted section should trace back to this file.

    Takes no arguments always reads from data/cinema_verde_profile.json.

    Returns:
        dict containing org name, mission, programs, impact metrics,
        budget, staff info, and other verified organization data.
    """
    raise NotImplementedError("Day 3: implement load_org_profile")