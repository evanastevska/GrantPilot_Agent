from dotenv import load_dotenv
load_dotenv()

from agents.writing_agent import writing_agent_app
from tools.load_org_profile import load_org_profile

test_input = {
    "funder_url": "",
    "raw_grant_text": "",
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
        "funder_overview": "couldn't_determine"
    },
    "org_profile": load_org_profile(),
    "drafted_sections": {},
    "compliance_report": {},
    "revision_feedback": "",
    "revision_count": 0,
    "status": "researching",
}

result = writing_agent_app.invoke(test_input)

print("\n=== DRAFTED SECTIONS ===")
for section_type, section in result["drafted_sections"].items():
    print(f"\n--- {section_type} ({section['word_count']} words) ---")
    print(section["content"])

print(f"\n=== STATUS: {result['status']} ===")