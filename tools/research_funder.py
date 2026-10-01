from google import genai
from tavily import TavilyClient
import os
import json
import time

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
    "funder_overview": "Brief summary of the funder's mission and priorities"
}}

Text to analyze:
{text_to_analyze}

Return ONLY the JSON object, no other text."""

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=extraction_prompt,
            )
            break
        except Exception as e:
            if attempt < 2:
                print(f"Gemini returned an error, retrying in 5 seconds... (attempt {attempt + 1}/3)")
                time.sleep(5)
            else:
                raise e

    #Gemini sometimes wraps JSON in markdown code fences
    response_text = response.text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0].strip()

    return json.loads(response_text)

