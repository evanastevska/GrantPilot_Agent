from typing import TypedDict


class GrantPilotState(TypedDict):
    """Shared state for the GrantPilot multi-agent graph.

    Every agent reads from and writes to this state. LangGraph merges
    each node's return dict into this state after the node runs.

    Design rule: each field should have ONE agent that writes it.
    Multiple agents can READ any field, but if two agents write to
    the same field, get race conditions and confusing bugs.
    """

    funder_url: str
    raw_grant_text: str
    funder_reqs: dict #structured requirements extracted from the funder
    org_profile: dict #Cinema Verde's data loaded from JSON file
    drafted_sections: dict #keyed by section type, values are draft strings
    compliance_report: dict #what passed/failed + why
    revision_feedback: str #specific feedback for the Writer to act on
    revision_count: int #capped at 2 conditional edge checks this
    status: str #researching, writing, reviewing, approved, max_revisions_reached