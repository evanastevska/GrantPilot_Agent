from dotenv import load_dotenv
load_dotenv()

from agents.writing_agent import writing_agent_app
from tools.check_compliance import check_compliance
from tools.load_org_profile import load_org_profile

# --- Step 1: generate real drafts ---
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
        "funder_overview": "couldn't_determine",
    },
    "org_profile": load_org_profile(),
    "drafted_sections": {},
    "compliance_report": {},
    "revision_feedback": "",
    "revision_count": 0,
    "status": "researching",
}

print("=== RUNNING WRITING AGENT ===")
write_result = writing_agent_app.invoke(test_input)

# --- Step 2: run compliance check on real drafts ---
print("\n=== RUNNING COMPLIANCE CHECK ===")
result = check_compliance(
    drafted_sections=write_result["drafted_sections"],
    funder_reqs=test_input["funder_reqs"],
    org_profile=test_input["org_profile"],
)

print(f"\n=== PROGRAMMATIC CHECKS ===")
print(f"Word counts:")
for wc in result["programmatic_checks"]["word_count"]:
    print(f"  {wc['section']}: {wc['word_count']} words (limit {wc['limit']}) — {wc['status']}")
print(f"Deadline: {result['programmatic_checks']['deadline']}")

print(f"\n=== LLM CHECKS ===")
print(f"Sections coverage:")
for s in result["llm_checks"].get("sections_coverage", []):
    print(f"  {s['required_section']}: {s['status']} — {s['notes']}")
print(f"\nCriteria coverage:")
for c in result["llm_checks"].get("criteria_coverage", []):
    print(f"  {c['criterion']}: {'✓' if c['addressed'] else '✗'} — {c['notes']}")
print(f"\nEligibility:")
for e in result["llm_checks"].get("eligibility_coverage", []):
    print(f"  {e['criterion']}: {'✓' if e['demonstrated'] else '✗'} — {e['notes']}")
print(f"\nUnsupported claims:")
for u in result["llm_checks"].get("unsupported_claims", []):
    print(f"  [{u['section']}] {u['claim']} — {u['issue']}")

print(f"\n=== OVERALL ===")
print(f"Status: {result['overall_status']}")
print(f"Revision type: {result['revision_type']}")
print(f"Revision feedback: {result['revision_feedback']}")