"""Draft quality eval on REAL end-to-end outputs.

Runs the full LangGraph graph on a grant opportunity, captures the
drafted sections, and scores them with the LLM-as-judge rubric.

This gives meaningful draft quality scores (unlike the compliance
test case drafts, which just test the eval script itself).

Usage:
    python eval/run_draft_quality_e2e.py
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from graph import app
from eval.eval_utils import (
    load_org_profile, get_judge_client, llm_judge_draft_quality,
    print_header, print_subheader, print_pass, print_fail,
    print_info, print_score, print_timer,
)


# --- Define end-to-end test inputs ---
# Each entry runs the full graph on a real grant opportunity.

E2E_TESTS = [
    {
        "name": "florida_scp",
        "input": {
            "funder_url": "",
            "raw_grant_text": """Florida Division of Arts and Culture — Specific Cultural Projects (SCP) Grant

The Specific Cultural Project (SCP) grant is designed to fund a single cultural project, program, exhibition or series taking place within the grant period (July 1 – June 30). Maximum request: $25,000.

Eligibility:
- Applicant organization must be either a public entity or a Florida non-profit, tax-exempt corporation as of the application deadline.
- All current and previous grantees must be in good standing with the Division of Arts and Culture and the Department of State at the time of application.
- Applicant must have registered with the Division of Corporations, and their status must be "active" as of the application deadline.
- Applicant must be registered as a vendor with the Department of Financial Services.
- Applicant must have a UEI Number.
- Several discipline-based program areas have their own eligibility requirements.

Proposal types: Arts in Education, Discipline-Based cultural or artistic projects, Underserved Cultural Community Development, Individual Artist projects.

For discipline-based projects (Cinema Verde's category: Media Arts / Film):
- Required sections: project description, timeline, budget, organizational information
- Evaluation criteria: artistic excellence, managerial competence, accessibility, and impact on the community
- Applications are reviewed by panelists who are practicing artists and qualified professionals. Applications are scored during panel meetings conducted by teleconference.
- Matching requirement: dollar-for-dollar match required.

Application window: June 1 – July 10 annually.
Application system: DOSgrants.com""",
            "funder_reqs": {},
            "org_profile": {},
            "drafted_sections": {},
            "compliance_report": {},
            "revision_feedback": "",
            "revision_count": 0,
            "status": "researching",
            "verify_manually": [],
        },
    },
]


def run():
    print_header("DRAFT QUALITY EVAL — END-TO-END OUTPUTS")

    client = get_judge_client()
    org_profile = load_org_profile()

    all_scores = {
        "relevance_to_funder": [],
        "org_data_grounding": [],
        "section_structure": [],
    }

    for test in E2E_TESTS:
        print_subheader(f"Running full graph: {test['name']}")

        # Run the full graph
        start = time.time()
        try:
            result = app.invoke(test["input"])
        except Exception as e:
            print_fail(f"Graph failed: {e}")
            continue
        graph_time = time.time() - start
        print_timer("Full graph", graph_time)

        print_info(f"Status: {result['status']}")
        print_info(f"Revision count: {result['revision_count']}")

        funder_reqs = result.get("funder_reqs", {})
        drafted_sections = result.get("drafted_sections", {})

        if not drafted_sections:
            print_fail("No drafted sections in output")
            continue

        # Score each drafted section
        for section_key, section_data in drafted_sections.items():
            content = section_data.get("content", "")
            word_count = section_data.get("word_count", len(content.split()))
            section_type = section_data.get("section_type", section_key)

            print()
            print_info(f"--- {section_key} ({word_count} words) ---")
            print_info(f"Preview: {content[:200]}...")

            # Score with LLM-as-judge
            print(f"    Scoring with LLM-as-judge...")
            start = time.time()
            try:
                rubric = llm_judge_draft_quality(
                    client, content, section_type, funder_reqs, org_profile
                )
            except Exception as e:
                print_fail(f"LLM judge error: {e}")
                continue
            elapsed = time.time() - start
            print_timer("LLM judge", elapsed)

            for dimension in ["relevance_to_funder", "org_data_grounding", "section_structure"]:
                dim_data = rubric.get(dimension, {})
                score = dim_data.get("score", "?")
                justification = dim_data.get("justification", "")
                all_scores[dimension].append(score if isinstance(score, (int, float)) else 0)
                print_score(f"{dimension}: {score}/5", justification[:100])

            if rubric.get("overall_notes"):
                print_info(f"Notes: {rubric['overall_notes'][:200]}")

    # Summary
    print_header("END-TO-END DRAFT QUALITY SUMMARY")

    for dimension, scores in all_scores.items():
        if scores:
            avg = sum(scores) / len(scores)
            print_score(f"Avg {dimension}", f"{avg:.1f}/5 (n={len(scores)})")

    print()


if __name__ == "__main__":
    run()