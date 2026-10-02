from google import genai
import os
import json
import time

#PROGRAMMATIC CHECK
def _check_word_counts(drafted_sections: dict, funder_reqs: dict) -> list:
    """Compare each section's word count against funder limits.
    
    funder_reqs["page_word_limits"] looks like: {"project narrative": "max 3 pages"}
    Approximate 350 words per page when the limit is in pages.
    
    Returns a list of dicts, one per section that HAS a limit:
        {"section": str, "word_count": int, "limit": int, "status": "within_limit" | "over_limit"}
    """
    results = []

    page_word_limits = funder_reqs.get("page_word_limits", {})

    if page_word_limits == "couldn't_determine":
        return []

    for section_name, limit_string in page_word_limits.items():
        #parse the number out of strings like "max 3 pages"
        limit_words = None
        for word in limit_string.split():
            try:
                num = int(word)
                if "page" in limit_string.lower():
                    limit_words = num * 350
                else:
                    limit_words = num
                break
            except ValueError:
                continue

        if limit_words is None:
            continue

        #normalize "project narrative" → "project_narrative" to match drafted_sections keys
        normalized = section_name.replace(" ", "_").lower()

        if normalized in drafted_sections:
            word_count = drafted_sections[normalized]["word_count"]
            results.append({
                "section": normalized,
                "word_count": word_count,
                "limit": limit_words,
                "status": "over_limit" if word_count > limit_words else "within_limit",
            })

    return results


def _check_deadline(funder_reqs: dict) -> str | None:
    """Surface the deadline so the user sees it in the report.
    
    This isn't a pass/fail check just pulls the deadline out
    of funder_reqs so it's visible in the compliance report.
    
    Returns the deadline string, or None if couldn't_determine.
    """
    deadline = funder_reqs.get("deadline", "couldn't_determine")
    if deadline == "couldn't_determine":
        return None
    return deadline


#LLM CHECK
COMPLIANCE_EVAL_PROMPT = """You are a skeptical grant compliance reviewer. Your job is to find gaps and problems, not to praise the draft.

You are evaluating a grant application draft against the funder's requirements.

FUNDER REQUIREMENTS:
{funder_reqs}

ORGANIZATION PROFILE:
{org_profile}

DRAFTED SECTIONS:
{drafted_sections}

Evaluate the draft and return a JSON object with exactly these fields:

{{
    "sections_coverage": [
        {{
            "required_section": "name from funder requirements",
            "status": "covered" | "missing" | "not_a_draft_section",
            "matched_draft_section": "key from drafted sections that covers this, or null",
            "notes": "brief explanation"
        }}
    ],
    "criteria_coverage": [
        {{
            "criterion": "criterion from funder evaluation criteria",
            "addressed": true | false,
            "sections_addressing": ["which draft sections address this"],
            "notes": "how it's addressed, or what's missing"
        }}
    ],
    "eligibility_coverage": [
        {{
            "criterion": "eligibility requirement from funder",
            "demonstrated": true | false,
            "notes": "how the draft demonstrates eligibility, or what's missing"
        }}
    ],
    "unsupported_claims": [
        {{
            "claim": "a specific claim made in the draft",
            "section": "which section it appears in",
            "issue": "why it's unsupported (not in org profile, or contradicts org data)"
        }}
    ]
}}

Rules:
- For sections_coverage: "not_a_draft_section" means the requirement isn't something you draft (like "letters of support" or "budget spreadsheet"), it's a supporting document.
- For criteria_coverage: "addressed" means the draft SUBSTANTIVELY engages with the criterion, not just mentions the word.
- For eligibility_coverage: check whether the draft demonstrates the organization meets each eligibility requirement, using evidence from the org profile.
- For unsupported_claims: only flag claims that are NOT supported by the organization profile data. Don't flag reasonable framing or standard grant language, only factual claims that can't be traced back to the org profile.
- Return ONLY the JSON object, no other text."""


def _run_llm_checks(drafted_sections: dict, funder_reqs: dict, org_profile: dict) -> dict:
    """Use Gemini to evaluate draft quality against funder requirements."""

    prompt = COMPLIANCE_EVAL_PROMPT.format(
        funder_reqs=str(funder_reqs),
        org_profile=str(org_profile),
        drafted_sections=str(drafted_sections),
    )

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
            )
            break
        except Exception as e:
            if attempt < 2:
                print(f"Gemini returned an error, retrying in 5 seconds... (attempt {attempt + 1}/3)")
                time.sleep(5)
            else:
                raise e

    response_text = response.text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0].strip()

    return json.loads(response_text)


def check_compliance(
    drafted_sections: dict,
    funder_reqs: dict,
    org_profile: dict,
) -> dict:
    #programmatic checks
    word_count_results = _check_word_counts(drafted_sections, funder_reqs)
    deadline = _check_deadline(funder_reqs)

    #LLM checks
    llm_checks = _run_llm_checks(drafted_sections, funder_reqs, org_profile)

    #build revision feedback from ALL checks
    feedback_parts = []

    #word count issues
    for wc in word_count_results:
        if wc["status"] == "over_limit":
            over_by = wc["word_count"] - wc["limit"]
            feedback_parts.append(f"{wc['section']} exceeds word limit by {over_by} words")

    #missing sections (from LLM)
    missing_sections = [
        s for s in llm_checks.get("sections_coverage", [])
        if s["status"] == "missing"
    ]
    if missing_sections:
        names = [s["required_section"] for s in missing_sections]
        feedback_parts.append(f"Missing required sections: {', '.join(names)}")

    #unaddressed evaluation criteria
    missed_criteria = [
        c for c in llm_checks.get("criteria_coverage", [])
        if not c["addressed"]
    ]
    for c in missed_criteria:
        feedback_parts.append(f"Evaluation criterion not addressed: {c['criterion']} — {c['notes']}")

    #undemonstrated eligibility
    missed_eligibility = [
        e for e in llm_checks.get("eligibility_coverage", [])
        if not e["demonstrated"]
    ]
    for e in missed_eligibility:
        feedback_parts.append(f"Eligibility not demonstrated: {e['criterion']} — {e['notes']}")

    #unsupported claims
    unsupported = llm_checks.get("unsupported_claims", [])
    for u in unsupported:
        feedback_parts.append(f"Unsupported claim in {u['section']}: {u['claim']} — {u['issue']}")

    #determine overall status
    if feedback_parts:
        overall_status = "needs_revision"
        revision_type = "writing"
        revision_feedback = ". ".join(feedback_parts) + "."
    else:
        overall_status = "approved"
        revision_type = None
        revision_feedback = ""

    return {
        "programmatic_checks": {
            "word_count": word_count_results,
            "deadline": deadline,
        },
        "llm_checks": llm_checks,
        "overall_status": overall_status,
        "revision_type": revision_type,
        "revision_feedback": revision_feedback,
    }