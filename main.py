from dotenv import load_dotenv
load_dotenv()

from graph import app

test_input = {
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
    "doc_url": ""
}

print("=== RUNNING FULL GRAPH — Test 2: Florida SCP ===\n")
result = app.invoke(test_input)

print(f"\n=== FINAL STATUS ===")
print(f"Status: {result['status']}")
print(f"Revision count: {result['revision_count']}")

print(f"\n=== EXTRACTED FUNDER REQUIREMENTS ===")
import json
print(json.dumps(result["funder_reqs"], indent=2))

print(f"\n=== DRAFTED SECTIONS ===")
for section_type, section in result["drafted_sections"].items():
    print(f"\n--- {section_type} ({section['word_count']} words) ---")
    print(section["content"])
    print("..." if len(section["content"]) > 500 else "")

print(f"\n=== COMPLIANCE REPORT ===")
report = result["compliance_report"]
print(f"Overall: {report['overall_status']}")
print(f"Revision type: {report.get('revision_type')}")
print(f"\nProgrammatic checks:")
print(json.dumps(report["programmatic_checks"], indent=2))
print(f"\nLLM checks:")
print(json.dumps(report["llm_checks"], indent=2))
print(f"\nRevision feedback: {report['revision_feedback']}")

print(f"\n=== VERIFY MANUALLY (applicant action items) ===")
for item in result["verify_manually"]:
    print(f"  • {item}")

print(f"\n=== GOOGLE DOC ===")
print(f"URL: {result.get('doc_url', 'not created')}")