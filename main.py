from dotenv import load_dotenv
load_dotenv()

from graph import app
import json

test_input = {
    "funder_url": "https://www.southarts.org/grants-opportunities/southern-artist-spotlight-grant",
    "raw_grant_text": "",
    "funder_reqs": {},
    "org_profile": {},
    "drafted_sections": {},
    "compliance_report": {},
    "revision_feedback": "",
    "verify_manually": [],
    "revision_count": 0,
    "status": "researching",
}

print("=== RUNNING FULL GRAPH — Test 3: South Arts Spotlight Grant ===\n")
result = app.invoke(test_input)

print(f"\n=== FINAL STATUS ===")
print(f"Status: {result['status']}")
print(f"Revision count: {result['revision_count']}")

print(f"\n=== EXTRACTED FUNDER REQUIREMENTS ===")
print(json.dumps(result["funder_reqs"], indent=2))

print(f"\n=== DRAFTED SECTIONS ===")
for section_type, section in result["drafted_sections"].items():
    print(f"\n--- {section_type} ({section['word_count']} words) ---")
    print(section["content"][:500])
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