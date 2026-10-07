from dotenv import load_dotenv
load_dotenv()

from tools.save_to_google_docs import save_to_google_docs

url = save_to_google_docs(
    funder_reqs={
        "funder_name": "Test Grant",
        "deadline": "July 10, 2027",
        "funding_amount": "$25,000",
        "eligibility": ["Must be a nonprofit", "Must be in Florida"],
        "required_sections": ["project description", "budget"],
        "evaluation_criteria": "couldn't_determine",
    },
    drafted_sections={
        "project_narrative": {
            "content": "This is a test draft section.",
            "word_count": 7,
        }
    },
    compliance_report={
        "overall_status": "approved",
        "programmatic_checks": {"word_count": [], "deadline": "July 10, 2027"},
        "revision_feedback": "",
        "verify_manually": ["UEI number not found in org profile"],
    },
)

print(url)