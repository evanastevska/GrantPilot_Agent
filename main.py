from dotenv import load_dotenv
load_dotenv()

from agents.research_agent import research_agent_app

test_input = {
    "funder_url": "https://www.arts.gov/grants/grants-for-arts-projects",
    "raw_grant_text": """Grants for Arts Projects (GAP) supports projects that extend the arts 
to underserved populations. Word limit: 3,000 words for the project narrative. 
Evaluation criteria include artistic excellence, organizational capacity, 
and reach to underserved communities. Past funded projects include the 
Appalachian Sound Archive and the Detroit Mural Initiative.""",
    "funder_reqs": {},
    "org_profile": {},
    "drafted_sections": {},
    "compliance_report": {},
    "revision_feedback": "",
    "revision_count": 0,
    "status": "starting",
}

result = research_agent_app.invoke(test_input)

print("\n=== FUNDER REQS ===")
for key, value in result["funder_reqs"].items():
    print(f"  {key}: {value}")

print(f"\n=== STATUS: {result['status']} ===")