"""Shared utilities for the GrantPilot eval harness.

Handles test case loading, LLM-as-judge calls, and result formatting.

KEY DESIGN DECISION: All judge calls use GPT-4o-mini (OpenAI), NOT Gemini.
Gemini generates the agent outputs (research_funder, check_compliance,
draft_section). Using the same model to judge its own output creates
self-preference bias, same principle as using a separate Review Agent
from the Writer, and same as using a different model for the judge in
AboveDeck's eval harness.
"""

import json
import os
import sys
import time
from pathlib import Path

#add project root so we can import tools/ and utils.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from openai import OpenAI

TEST_CASES_DIR = Path(__file__).resolve().parent / "test_cases"
DATA_DIR = PROJECT_ROOT / "data"


#data loading

def load_test_cases(test_type: str) -> list[dict]:
    """Load all test cases matching a type prefix ('extraction' or 'compliance')."""
    cases = []
    for filepath in sorted(TEST_CASES_DIR.glob(f"{test_type}_*.json")):
        with open(filepath) as f:
            cases.append(json.load(f))
    return cases


def load_org_profile() -> dict:
    """Load Cinema Verde org profile."""
    with open(DATA_DIR / "cinema_verde_profile.json") as f:
        return json.load(f)


def resolve_org_profile(test_case: dict) -> dict:
    """If test case says LOAD_FROM_FILE, load it. Otherwise return as-is."""
    if test_case.get("org_profile") == "LOAD_FROM_FILE":
        return load_org_profile()
    return test_case["org_profile"]


#judge client (OpenAI GPT-4o-mini)
#separate model from Gemini to avoid self-preference bias.

def get_judge_client():
    """Create an OpenAI client for LLM-as-judge calls."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key)


def call_judge(client, prompt: str, parse_json: bool = False):
    """Call GPT-4o-mini as judge. Retry with backoff on failure.

    Uses a different model family (OpenAI) from the agent (Gemini)
    so the judge never evaluates its own outputs.
    """
    delays = [2, 5, 15]
    for attempt, delay in enumerate(delays):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            text = response.choices[0].message.content.strip()
            if parse_json:
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    text = text.rsplit("```", 1)[0].strip()
                return json.loads(text)
            return text
        except Exception as e:
            if attempt < len(delays) - 1:
                print(f"  Judge (GPT-4o-mini) error, retrying in {delay}s... ({e})")
                time.sleep(delay)
            else:
                raise e


#LLM-as-judge helpers

def llm_judge_semantic_match(client, predicted: str, gold: str, field_name: str) -> dict:
    """Binary semantic match: are two string values equivalent?

    Used for extraction scorer on string fields (funder_name, deadline, etc).

    Returns: {"match": bool, "reasoning": str}
    """
    prompt = f"""You are an evaluation judge comparing a system's extracted value against the ground truth for the field "{field_name}".

GROUND TRUTH: {gold}
SYSTEM OUTPUT: {predicted}

Rules:
- Different wording that captures the same core meaning = MATCH
- Missing key information from the ground truth = NO MATCH
- Extra detail that doesn't contradict = MATCH
- Both being "couldn't_determine" = MATCH
- One being "couldn't_determine" and the other having a real value = NO MATCH

Return ONLY this JSON (no other text):
{{"match": true, "reasoning": "one sentence"}}
or
{{"match": false, "reasoning": "one sentence"}}"""

    return call_judge(client, prompt, parse_json=True)


def llm_judge_list_field(client, predicted_list: list, gold_list: list, field_name: str) -> dict:
    """Compute precision/recall for a list field using LLM fuzzy matching.

    Sends all items in ONE call (efficient) instead of N*M pairwise calls.
    The LLM matches gold items to predicted items by meaning, not exact wording.

    Returns: {precision, recall, gold_matched, gold_total, pred_matched, pred_total, details}
    """
    gold_numbered = "\n".join(f"  G{i}: {item}" for i, item in enumerate(gold_list))
    pred_numbered = "\n".join(f"  P{i}: {item}" for i, item in enumerate(predicted_list))

    prompt = f"""You are an evaluation judge. Compare the SYSTEM's extracted list items against GROUND TRUTH items for the field "{field_name}".

Items may be worded differently but refer to the same requirement. Match by meaning, not exact wording.

GROUND TRUTH ITEMS:
{gold_numbered}

SYSTEM OUTPUT ITEMS:
{pred_numbered}

For each ground truth item, find the system item that best matches it (if any).
For each system item, determine if it corresponds to a ground truth item.

Return ONLY this JSON:
{{
    "gold_recall": [
        {{"gold_index": 0, "matched": true, "pred_index": 2}},
        {{"gold_index": 1, "matched": false, "pred_index": null}}
    ],
    "pred_precision": [
        {{"pred_index": 0, "matched": true, "gold_index": 1}},
        {{"pred_index": 1, "matched": false, "gold_index": null}}
    ]
}}"""

    result = call_judge(client, prompt, parse_json=True)

    gold_matched = sum(1 for g in result.get("gold_recall", []) if g["matched"])
    gold_total = len(gold_list)
    pred_matched = sum(1 for p in result.get("pred_precision", []) if p["matched"])
    pred_total = len(predicted_list)

    recall = gold_matched / gold_total if gold_total > 0 else 1.0
    precision = pred_matched / pred_total if pred_total > 0 else 1.0

    #build readable details
    missed_gold = [
        f"MISSED: G{g['gold_index']}: {gold_list[g['gold_index']]}"
        for g in result.get("gold_recall", [])
        if not g["matched"]
    ]
    extra_pred = [
        f"EXTRA:  P{p['pred_index']}: {predicted_list[p['pred_index']]}"
        for p in result.get("pred_precision", [])
        if not p["matched"]
    ]

    return {
        "precision": precision,
        "recall": recall,
        "gold_matched": gold_matched,
        "gold_total": gold_total,
        "pred_matched": pred_matched,
        "pred_total": pred_total,
        "missed_gold": missed_gold,
        "extra_pred": extra_pred,
    }


def llm_judge_dict_field(client, predicted_dict: dict, gold_dict: dict, field_name: str) -> dict:
    """Compare two dicts (like page_word_limits) using LLM for fuzzy key/value matching.

    Returns: {precision, recall, details}
    """
    prompt = f"""You are an evaluation judge. Compare the SYSTEM's extracted key-value pairs against GROUND TRUTH for the field "{field_name}".

Keys may be worded differently (e.g. "project narrative" vs "Project Narrative").
Values may be formatted differently (e.g. "max 3 pages" vs "3 pages, approximately 1050 words").

GROUND TRUTH:
{json.dumps(gold_dict, indent=2)}

SYSTEM OUTPUT:
{json.dumps(predicted_dict, indent=2)}

For each ground truth key-value pair, determine:
1. Does the system have a matching key? (fuzzy match on key name)
2. If yes, does the value convey the same limit/constraint?

Return ONLY this JSON:
{{
    "matches": [
        {{"gold_key": "project narrative", "matched_key": true, "matched_value": true, "system_key": "Project Narrative"}},
        {{"gold_key": "budget narrative", "matched_key": false, "matched_value": false, "system_key": null}}
    ]
}}"""

    result = call_judge(client, prompt, parse_json=True)

    matches = result.get("matches", [])
    gold_total = len(gold_dict)
    matched = sum(1 for m in matches if m.get("matched_key") and m.get("matched_value"))
    pred_total = len(predicted_dict)

    recall = matched / gold_total if gold_total > 0 else 1.0
    precision = matched / pred_total if pred_total > 0 else 1.0

    return {
        "precision": precision,
        "recall": recall,
        "matched": matched,
        "gold_total": gold_total,
        "pred_total": pred_total,
    }


def llm_judge_draft_quality(client, draft_content: str, section_type: str,
                            funder_reqs: dict, org_profile: dict) -> dict:
    """Score a draft section on a structured rubric.

    Rubric dimensions:
    - Relevance to funder priorities (1-5)
    - Org data grounding (1-5)
    - Section structure (1-5)

    Returns: dict with scores and justifications.
    """
    prompt = f"""You are a grant writing expert evaluating a draft section. Be critical — this is an evaluation, not praise.

SECTION TYPE: {section_type}

FUNDER REQUIREMENTS:
{json.dumps(funder_reqs, indent=2)}

ORGANIZATION PROFILE (verified facts the draft should draw from):
{json.dumps(org_profile, indent=2)}

DRAFT:
{draft_content}

Score this draft on each dimension:

1. Relevance to funder priorities (1-5): Does it address specific funder evaluation criteria, or is it generic boilerplate that could apply to any funder?
2. Org data grounding (1-5): Does it use specific facts/numbers from the org profile, or make vague claims?
3. Section structure (1-5): Does it follow expected grant section conventions for this section type?

Return ONLY this JSON:
{{
    "relevance_to_funder": {{"score": 3, "justification": "..."}},
    "org_data_grounding": {{"score": 4, "justification": "..."}},
    "section_structure": {{"score": 3, "justification": "..."}},
    "overall_notes": "Brief strengths and weaknesses"
}}"""

    return call_judge(client, prompt, parse_json=True)


#print helpers

def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_subheader(title: str):
    print(f"\n  ── {title} {'─' * max(1, 45 - len(title))}")


def print_pass(label: str, detail: str = ""):
    line = f"    ✅ {label}"
    if detail:
        line += f"  ({detail})"
    print(line)


def print_fail(label: str, detail: str = ""):
    line = f"    ❌ {label}"
    if detail:
        line += f"  ({detail})"
    print(line)


def print_warn(label: str, detail: str = ""):
    line = f"    ⚠️  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)


def print_info(text: str):
    print(f"       {text}")


def print_score(label: str, value):
    print(f"    📊 {label}: {value}")


def print_timer(label: str, seconds: float):
    print(f"    ⏱  {label}: {seconds:.1f}s")