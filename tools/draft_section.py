from google import genai
import os
from utils import call_gemini_with_retry


#each section type gets its own template because they have different jobs.
#proj narrative = pitch, needs statement = why the work matters.
#generic "write a grant section" produces generic output, so dont want

SECTION_TEMPLATES = {
    "project_narrative": """You are an experienced grant writer drafting a project narrative.

A project narrative is the core pitch — what the project is, why it matters, and how it
connects to what this funder cares about. It should read as specific and grounded, not
generic.

FUNDER REQUIREMENTS:
{funder_reqs}

ORGANIZATION PROFILE:
{org_profile}

Instructions:
- Open with a clear, compelling description of the project
- Explicitly connect the project to each of the funder's evaluation criteria
- Reference specific org data: name real programs, real impact numbers, real partnerships.
  Do NOT fabricate any facts about the organization.
- If word or page limits are specified in the funder requirements, stay within them
- Write in a professional but human tone — avoid jargon-heavy grant boilerplate
- Label this as a draft meant to be edited by the applicant.
- Do NOT include a section listing the organization's registration statuses, vendor IDs,
  UEI numbers, or compliance with administrative requirements. If the funder requires these,
  they are administrative items the applicant handles separately, they do not belong in the
  project narrative. Focus on what the project IS and why it matters.
- Do not include commentary about your own revision process or changes from prior drafts.

Write the project narrative now.""",

    "needs_statement": """You are an experienced grant writer drafting a needs statement.

A needs statement argues WHY this work is needed — what gap or problem exists, who is
affected, and why this organization is positioned to address it. It must feel grounded
in real context, not abstract.

FUNDER REQUIREMENTS:
{funder_reqs}

ORGANIZATION PROFILE:
{org_profile}

Instructions:
- Describe the specific need or gap this project addresses
- Connect the need to the funder's mission and stated priorities
- Use the organization's track record (past festivals, community reach, years of
  operation) as evidence they understand and have engaged with this problem
- Reference real impact metrics from the org profile — never invent statistics
- If word or page limits are specified in the funder requirements, stay within them
- Keep the tone urgent but not melodramatic.
- Do NOT open with applicant details, funding amounts, or eligibility demonstrations. Open
  with the problem , what need exists, who is affected, and why this work matters.
- Do not include commentary about your own revision process or changes from prior drafts.

Write the needs statement now.""",

    "goals_objectives": """You are an experienced grant writer drafting a goals and objectives section.

Goals are broad outcomes. Objectives are specific, measurable steps toward those goals.
Funders want to see that the applicant can articulate what success looks like concretely.

FUNDER REQUIREMENTS:
{funder_reqs}

ORGANIZATION PROFILE:
{org_profile}

Instructions:
- State 2-3 clear goals for the project
- Under each goal, list 2-3 measurable objectives with realistic timelines
- Objectives should be specific enough to evaluate later (numbers, dates, deliverables)
- Ground the goals in what the organization already does — reference existing programs
  and metrics as a baseline
- Align goals to the funder's evaluation criteria wherever possible
- If word or page limits are specified in the funder requirements, stay within them.
- This section is about project goals and measurable objectives. Do NOT use this section
  to demonstrate eligibility or list the organization's registration statuses. Stay focused
  on what the project will accomplish and how success will be measured.
- Do not include commentary about your own revision process or changes from prior drafts.

Write the goals and objectives section now.""",

    "evaluation_plan": """You are an experienced grant writer drafting an evaluation plan.

An evaluation plan explains how the organization will measure whether the project
succeeded. Funders want to see that the applicant takes accountability seriously and
has thought about what evidence of success looks like.

FUNDER REQUIREMENTS:
{funder_reqs}

ORGANIZATION PROFILE:
{org_profile}

Instructions:
- Describe how each major objective will be measured
- Include both quantitative metrics (attendance numbers, films screened, participants
  served) and qualitative methods (surveys, interviews, case studies)
- Specify who will collect the data and when
- Reference any existing data collection the org already does (past festival metrics,
  audience data) as a foundation
- Connect evaluation criteria back to the funder's stated priorities
- If word or page limits are specified in the funder requirements, stay within them.
- This section is about how PROJECT SUCCESS will be measured. Do NOT include administrative
  compliance information, registration numbers, or eligibility demonstrations. Focus only
  on how the organization will evaluate whether the project achieved its goals.
- Do not include commentary about your own revision process or changes from prior drafts.

Write the evaluation plan now.""",

    "org_background": """You are an experienced grant writer drafting an organizational
background section.

This section establishes credibility — who the organization is, what they have
accomplished, and why they are capable of executing this project. It should lean heavily
on verified facts from the org profile.

FUNDER REQUIREMENTS:
{funder_reqs}

ORGANIZATION PROFILE:
{org_profile}

Instructions:
- Lead with the organization's mission and founding year
- Highlight key programs and their track records (years running, scale, reach)
- Include specific impact metrics: number of festivals held, filmmakers supported,
  countries represented, audience reach
- Mention notable partnerships and press coverage to establish credibility
- Reference the leadership team's qualifications
- Keep it factual — every claim should trace back to the org profile data.
  Do NOT fabricate accomplishments.
- If word or page limits are specified in the funder requirements, stay within them.
- NEVER assert facts about the organization that are not in the organization profile above.
  If the funder requires administrative compliance (UEI registration, vendor status, good
  standing with a specific agency), do NOT claim the organization has it unless the org
  profile explicitly confirms it. Those are applicant action items, not claims to make
  in the narrative.
- If the org profile does not contain data needed to make a specific claim, omit the claim
  entirely. Do not fabricate, assume, or infer. A shorter, honest section is better than
  a longer one with unsupported claims.
- Do not include commentary about your own revision process or changes from prior drafts.

Write the organizational background section now.""",
}




def draft_section(
    section_type: str,
    funder_reqs: dict,
    org_profile: dict,
    revision_feedback: str | None = None,
) -> dict:
    """Draft one section of a grant application."""

    #1.look up the template
    if section_type not in SECTION_TEMPLATES:
        raise ValueError(f"Unknown section type: {section_type}. Must be one of {list(SECTION_TEMPLATES.keys())}")

    template = SECTION_TEMPLATES[section_type]

    #2.put real data into the template placeholders
    prompt = template.format(funder_reqs=funder_reqs, org_profile=org_profile)

    #3.if revision feedback exists, append it to the prompt
    if revision_feedback is not None:
        prompt += f"""

The following feedback was provided by the reviewer. Address these issues in your revised draft:
{revision_feedback}"""

    #4.gemini output is prose, not JSON
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    content = call_gemini_with_retry(client, prompt)

    #5.count words and return
    return {
        "section_type": section_type,
        "content": content,
        "word_count": len(content.split()),
    }