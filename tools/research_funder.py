from google import genai
from tavily import TavilyClient
import os
from utils import call_gemini_with_retry

def research_funder(
    funder_url: str | None = None,
    raw_grant_text: str | None = None,
) -> dict:
    """Research a funder and extract structured grant requirements.

    Accepts a funder URL, pasted grant text, or both. At least one
    must be provided.

    - If raw_grant_text is provided: skip the fetch, go straight to
      LLM extraction (faster, more reliable the user probably has
      the RFP open already).
    - If funder_url is provided: fetch the page, then extract.
    - If both: use pasted text as primary, URL as supplementary.

    Any requirement that can't be found gets a "couldn't_determine"
    value instead of being silently omitted. Silent omission makes
    the research look complete when it isn't.

    Returns:
        dict with keys like:
        - funder_name: str
        - deadline: str or "couldn't_determine"
        - funding_amount: str or "couldn't_determine"
        - eligibility: list[str] or "couldn't_determine"
        - page_word_limits: dict or "couldn't_determine"
        - required_sections: list[str] or "couldn't_determine"
        - evaluation_criteria: list[str] or "couldn't_determine"
        - past_funded_projects: list[str] or "couldn't_determine"
        - funder_overview: str
    """

    #1.get the text to analyze from what is given in input
    text_to_analyze = ""

    if raw_grant_text and funder_url:
        tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = tavily_client.extract(urls=[funder_url])
        fetched_text = response["results"][0]["raw_content"]
        text_to_analyze = (
            f"PRIMARY SOURCE (pasted grant text):\n{raw_grant_text}\n\n"
            f"SUPPLEMENTARY SOURCE (funder website):\n{fetched_text}"
        )
    elif raw_grant_text:
        text_to_analyze = raw_grant_text
    elif funder_url:
        tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = tavily_client.extract(urls=[funder_url])
        text_to_analyze = response["results"][0]["raw_content"]
    else:
        raise ValueError("Must provide funder_url or raw_grant_text (or both)")




    #2. LLM extraction
    extraction_prompt = f"""You are a grant requirements extraction assistant.
Read the following grant opportunity text and extract structured information.

Rules:
- Extract ONLY information explicitly stated in the text.
- If a field cannot be determined from the text, set its value to exactly "couldn't_determine".
- Do not guess, infer, or make assumptions.
- For required_sections: extract the most specific, individually named sections. If a parent category has named sub-items, list the sub-items, not the parent category.
- For evaluation_criteria: list each individually named criterion. If sub-criteria are named, list those separately, not just the parent category.
- For eligibility: include restrictions and limitations: fiscal agent rules, application limits per cycle, conflict of interest policies, residency requirements, deadlines for status corrections.
- Return valid JSON with exactly these fields:
- Do not guess, infer, or make assumptions.
- Return valid JSON with exactly these fields:

{{
    "funder_name": "Name of the funding organization",
    "deadline": "Application deadline or couldn't_determine",
    "funding_amount": "Grant amount/range or couldn't_determine",
    "eligibility": ["criterion 1", "criterion 2"] or "couldn't_determine",
    "page_word_limits": {{"section_name": "limit"}} or "couldn't_determine",
    "required_sections": ["section 1", "section 2"] or "couldn't_determine",
    "evaluation_criteria": ["criterion 1", "criterion 2"] or "couldn't_determine",
    "past_funded_projects": ["project 1", "project 2"] or "couldn't_determine",
    "funder_overview": "What is distinctive about this specific grant program? Include: program type, award process, and key requirements that make it different from other grants"
}}

Text to analyze:
{text_to_analyze}

Return ONLY the JSON object, no other text."""

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return call_gemini_with_retry(client, extraction_prompt, parse_json=True)

