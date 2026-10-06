"""Draft quality scorer via LLM-as-judge.

Scores draft sections on a structured rubric:
- Relevance to funder priorities (1-5)
- Org data grounding (1-5)
- Section structure (1-5)
- Word count compliance (pass/fail)

For Day 9: runs on the compliance test case drafts as a sanity check.
For Day 10: run on actual end-to-end outputs for real eval results.

This is the LOWEST PRIORITY scorer. Cut it if time is tight —
extraction + compliance evals are the ones that matter.

Usage:
    python eval/run_draft_quality_eval.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_utils import (
    load_test_cases, resolve_org_profile, get_judge_client,
    llm_judge_draft_quality,
    print_header, print_subheader, print_pass, print_fail,
    print_info, print_score, print_timer,
)


def check_word_count(section_content: str, word_count: int,
                     funder_reqs: dict, section_key: str) -> dict:
    """Check if a section is within its word limit.

    Returns: {"status": "pass"|"fail"|"no_limit", "detail": str}
    """
    limits = funder_reqs.get("page_word_limits", {})
    if limits == "couldn't_determine" or not limits:
        return {"status": "no_limit", "detail": "No word limits specified"}

    #find limit for this section (fuzzy key match)
    section_normalized = section_key.replace("_", " ").lower()
    limit_words = None

    for limit_key, limit_string in limits.items():
        if section_normalized in limit_key.lower() or limit_key.lower() in section_normalized:
            #parse the limit number
            for word in limit_string.split():
                try:
                    num = int(word)
                    if "page" in limit_string.lower():
                        limit_words = num * 350  #~350 words per page
                    else:
                        limit_words = num
                    break
                except ValueError:
                    continue
            break

    if limit_words is None:
        return {"status": "no_limit", "detail": "No limit found for this section"}

    if word_count <= limit_words:
        return {
            "status": "pass",
            "detail": f"{word_count} words (limit: {limit_words})",
        }
    else:
        over_by = word_count - limit_words
        return {
            "status": "fail",
            "detail": f"{word_count} words, {over_by} over limit of {limit_words}",
        }


def run():
    print_header("DRAFT QUALITY EVAL (LLM-as-Judge)")

    #use compliance test case drafts as input
    #(replace this with actual end-to-end outputs)
    test_cases = load_test_cases("compliance")
    print(f"  Running on {len(test_cases)} compliance test case drafts")
    print(f"  (Replace with end-to-end outputs on Day 10 for real results)\n")

    client = get_judge_client()

    all_scores = {
        "relevance_to_funder": [],
        "org_data_grounding": [],
        "section_structure": [],
    }
    word_count_results = {"pass": 0, "fail": 0, "no_limit": 0}

    for tc in test_cases:
        test_id = tc["test_id"]
        funder_reqs = tc["funder_reqs"]
        org_profile = resolve_org_profile(tc)
        drafted_sections = tc["drafted_sections"]

        #score each drafted section
        for section_key, section_data in drafted_sections.items():
            print_subheader(f"{test_id} / {section_key}")

            content = section_data.get("content", "")
            word_count = section_data.get("word_count", len(content.split()))
            section_type = section_data.get("section_type", section_key)

            #word count check (programmatic)
            wc_result = check_word_count(content, word_count, funder_reqs, section_key)
            word_count_results[wc_result["status"]] += 1
            if wc_result["status"] == "pass":
                print_pass(f"Word count: {wc_result['detail']}")
            elif wc_result["status"] == "fail":
                print_fail(f"Word count: {wc_result['detail']}")
            else:
                print_info(f"Word count: {wc_result['detail']}")

            #LLM rubric scoring
            print(f"    Scoring with LLM-as-judge...")
            start = time.time()
            try:
                rubric = llm_judge_draft_quality(
                    client, content, section_type, funder_reqs, org_profile
                )
            except Exception as e:
                print_fail(f"LLM judge error: {e}")
                continue
            elapsed = time.time() - start
            print_timer("LLM judge", elapsed)

            #print scores
            for dimension in ["relevance_to_funder", "org_data_grounding", "section_structure"]:
                dim_data = rubric.get(dimension, {})
                score = dim_data.get("score", "?")
                justification = dim_data.get("justification", "")
                all_scores[dimension].append(score if isinstance(score, (int, float)) else 0)
                print_score(f"{dimension}: {score}/5", justification[:100])

            if rubric.get("overall_notes"):
                print_info(f"Notes: {rubric['overall_notes'][:150]}")

    #summary
    print_header("DRAFT QUALITY EVAL SUMMARY")

    for dimension, scores in all_scores.items():
        if scores:
            avg = sum(scores) / len(scores)
            print_score(f"Avg {dimension}", f"{avg:.1f}/5 (n={len(scores)})")

    print()
    wc_total = sum(word_count_results.values())
    if wc_total > 0:
        print_score("Word count compliance",
                    f"{word_count_results['pass']} pass, "
                    f"{word_count_results['fail']} fail, "
                    f"{word_count_results['no_limit']} no limit set")

    print()


if __name__ == "__main__":
    run()