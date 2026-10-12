# GrantPilot

Multi-agent grant research and drafting system built for [Cinema Verde](https://www.cinemaverde.org/), a nonprofit environmental film festival in Gainesville, FL.

Three agents (Research, Writer, Reviewer) run in a LangGraph state graph. The Research Agent extracts structured funder requirements from a URL, pasted grant text, or both. The Writing Agent drafts grant sections grounded in those requirements and Cinema Verde's verified org profile. The Review Agent checks compliance and routes revision feedback back to the right agent. Final output saves to a formatted Google Doc.

Requirements the Research Agent can't find (deadline, page limits, eligibility) come back as `"couldn't_determine"` instead of being silently omitted. These surface as "VERIFY MANUALLY" items in the Google Doc so the applicant knows what the research didn't cover.

## Architecture

```
User provides: funder URL  AND/OR  pasted grant text
          |
          v
+--------------------------------------+
|  LangGraph StateGraph                |
|                                      |
|  1. Research Agent          <----+   |
|     tools: research_funder,      |   |
|            load_org_profile      |   |
|     -> structured funder reqs    |   |
|     -> org profile loaded        |   |
|          |                       |   |
|          v                       |   |
|  2. Writing Agent           <--+ |   |
|     tool: draft_section        | |   |
|     -> drafts each section     | |   |
|          |                     | |   |
|          v                     | |   |
|  3. Review Agent               | |   |
|     tool: check_compliance     | |   |
|     -> compliance report       | |   |
|     -> if WRITING gap ---------+ |   |
|       (req in research,          |   |
|        missing from draft)       |   |
|     -> if RESEARCH gap ----------+   |
|       (req not in research           |
|        at all)                       |
|          |                           |
|          v (approved)                |
|  4. save_to_google_docs              |
+--------------------------------------+
          |
          v
Google Doc:
  1. Funder Research Summary
  2. Draft Sections (labeled as drafts)
  3. Compliance Notes + Verify Manually items
```

The Review Agent diagnoses where each gap is and the conditional edge routes to the right agent. A writing gap (requirement is in the research but missing from the draft) goes back to the Writer. A research gap (requirement isn't in the research output at all) goes back to the Research Agent. Capped at 2 revision cycles.

## Eval

Three-part evaluation, each targeting a different agent. All eval judge calls use GPT-4o via the OpenAI API, not Gemini, so the judge model is different from the model being evaluated.

**Extraction accuracy** (`run_extraction.py`): runs `research_funder()` on 5 real grant opportunities and compares field-by-field against hand-labeled gold data. Uses LLM-as-judge for semantic matching on strings and precision/recall with fuzzy matching on lists.

**Compliance checker accuracy** (`run_compliance.py`): runs `check_compliance()` against 5 test cases with intentional flaws (over word limit, missing section, unaddressed criterion, unsupported claims) plus a clean baseline.

**Draft quality** (`run_draft_quality.py`): LLM-as-judge scoring on relevance to funder priorities (1-5), org data grounding (1-5), and section structure (1-5). Includes a claims audit that categorizes every factual claim before scoring so the grounding dimension only penalizes actual unsupported claims.

### Results

| Eval | Baseline | Final | Target |
|------|----------|-------|--------|
| Compliance detection | 83% (5/6) | 100% (6/6) | 100% |
| Compliance false positive avoidance | 69% (9/13) | 100% (13/13) | Clean baseline passes |
| Extraction accuracy | 73% (33/45) | 87% (39/45) | 80%+ |
| Draft grounding (avg across 4 runs) | 3.6/5 | 4.2 +/- 0.2 | No hallucination |
| Graph convergence | max_revisions_reached | approved (3/4 runs) | Converges |

Full eval details, prompt iteration history, and known limitations in [`eval/FINDINGS.md`](eval/FINDINGS.md).

## Tech stack

| Component | Choice |
|-----------|--------|
| Agent framework | LangGraph |
| LLM | Gemini 3.5 Flash (Google GenAI SDK) |
| Eval judge | GPT-4o (OpenAI) |
| Web research | Tavily API |
| Document output | Google Docs API |
| Frontend | Flask |
| Deployment | Google Cloud Run |

## Live demo

Deployed at: https://grantpilot-812754705968.us-east1.run.app

Password-protected internal tool for Cinema Verde. Reach out if you want access or a walkthrough.

## Project structure

```
GrantPilot_Agent/
├── agents/
│   ├── research_agent.py      #extracts funder requirements, loads org profile
│   ├── writing_agent.py       #drafts grant sections concurrently
│   └── review_agent.py        #checks compliance, routes revision feedback
├── tools/
│   ├── research_funder.py     #dual input (URL + pasted text) -> structured reqs
│   ├── load_org_profile.py    #loads verified Cinema Verde data from JSON
│   ├── draft_section.py       #section-specific prompt templates
│   ├── check_compliance.py    #programmatic + LLM compliance checks
│   └── save_to_google_docs.py #formatted Google Doc output
├── eval/
│   ├── eval_utils.py          #LLM-as-judge helpers, scoring functions
│   ├── run_extraction.py      #extraction accuracy scorer
│   ├── run_compliance.py      #compliance checker accuracy scorer
│   ├── run_draft_quality.py   #draft quality LLM-as-judge scorer
│   ├── FINDINGS.md            #eval results and prompt iteration history
│   └── test_cases/            #gold-labeled test data
├── data/
│   └── cinema_verde_profile.json
├── graph.py                   #LangGraph StateGraph + conditional edges
├── state.py                   #shared state schema
├── app.py                     #Flask frontend + background job runner
├── utils.py                   #Gemini retry wrapper
├── Dockerfile                 #Cloud Run container config
└── requirements.txt
```

## Setup (local dev)

```bash
git clone https://github.com/evanastevska/GrantPilot_Agent.git
cd GrantPilot_Agent
pip install -r requirements.txt
```

Create a `.env` file:

```
GEMINI_API_KEY=your-gemini-api-key
TAVILY_API_KEY=your-tavily-api-key
OPENAI_API_KEY=your-openai-api-key          # for eval judge only
GOOGLE_DRIVE_FOLDER_ID=optional-folder-id
GOOGLE_DOCS_SHARE_EMAIL=optional-email
APP_PASSWORD_HASH=sha256-hash-of-your-password
FLASK_SECRET_KEY=any-random-string
```

Google Docs requires a Google Cloud project with Docs API + Drive API enabled and an OAuth client ID (Desktop app type). Download the credentials as `client_secret.json` in the project root. On first run, the app opens a browser for Google login and saves the token.

Run locally:

```bash
python app.py
```

Run the eval suite:

```bash
python eval/run_extraction.py
python eval/run_compliance.py
python eval/run_draft_quality.py
```
