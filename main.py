from dotenv import load_dotenv
load_dotenv()

from graph import app
from tools.load_org_profile import load_org_profile

test_input = {
    "funder_url": "",
    "raw_grant_text": """The Green Arts Foundation awards grants of $5,000 to $15,000
to 501(c)(3) nonprofit organizations based in the Southeastern United States with
annual budgets under $500,000. Deadline: March 15, 2026. Required sections:
project narrative (max 3 pages), budget justification, organizational background,
and two letters of support. Evaluation criteria: environmental impact, community
engagement, artistic merit, and organizational capacity.""",
    "funder_reqs": {
        "funder_name": "The Green Arts Foundation",
        "deadline": "March 15, 2026",
        "funding_amount": "$5,000 to $15,000",
        "eligibility": ["501(c)(3) nonprofit organizations",
                        "based in the Southeastern United States",
                        "annual budgets under $500,000"],
        "page_word_limits": {"project narrative": "max 3 pages"},
        "required_sections": ["project narrative", "budget justification",
                              "organizational background", "two letters of support"],
        "evaluation_criteria": ["environmental impact", "community engagement",
                                "artistic merit", "organizational capacity"],
        "past_funded_projects": "couldn't_determine",
        "funder_overview": "couldn't_determine",
    },
    "org_profile": load_org_profile(),
    "drafted_sections": {},
    "compliance_report": {},
    "revision_feedback": "",
    "revision_count": 0,
    "status": "researching",
}

print("=== RUNNING FULL GRAPH ===\n")
result = app.invoke(test_input)

print(f"\n=== FINAL STATUS ===")
print(f"Status: {result['status']}")
print(f"Revision count: {result['revision_count']}")

print(f"\n=== DRAFTED SECTIONS ===")
for section_type, section in result["drafted_sections"].items():
    print(f"  {section_type} ({section['word_count']} words)")

report = result["compliance_report"]
print(f"\n=== COMPLIANCE REPORT ===")
print(f"Overall: {report['overall_status']}")
print(f"Revision feedback: {report['revision_feedback']}")