"""Extraction accuracy scorer.

Runs research_funder() on each extraction test case and compares
output against gold_labels field by field.

Scoring approach:
- String fields: LLM-as-judge binary semantic match
- List fields: LLM-as-judge precision/recall with fuzzy matching
- Dict fields: LLM-as-judge key-value comparison
- couldn't_determine: exact match (both must agree)

This is the most interesting eval from an AI engineering perspective —
every comparison uses LLM-as-judge because the agent will phrase
things differently from the gold labels.

Usage:
    python eval/run_extraction_eval.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_utils import (
    load_test_cases, get_judge_client,
    llm_judge_semantic_match, llm_judge_list_field, llm_judge_dict_field,
    print_header, print_subheader, print_pass, print_fail, print_warn,
    print_info, print_score, print_timer,
)
from tools.research_funder import research_funder


# Fields and their expected types
STRING_FIELDS = ["funder_name", "deadline", "funding_amount", "funder_overview"]
LIST_FIELDS = ["eligibility", "required_sections", "evaluation_criteria", "past_funded_projects"]
DICT_FIELDS = ["page_word_limits"]
ALL_FIELDS = STRING_FIELDS + LIST_FIELDS + DICT_FIELDS


def score_field(client, predicted_value, gold_value, field_name: str) -> dict:
    """Score a single field based on its type.

    Handles couldn't_determine for any field type, then dispatches to
    the right comparison method.

    Returns: {
        "status": "correct" | "incorrect" | "both_unknown" | "missed" | "extra",
        "details": str,
        ... (additional metrics for list/dict fields)
    }
    """
    pred_unknown = predicted_value == "couldn't_determine"
    gold_unknown = gold_value == "couldn't_determine"

    #noth couldn't determine, that's a correct match
    if pred_unknown and gold_unknown:
        return {"status": "both_unknown", "details": "Both correctly returned couldn't_determine"}

    #gold has a value but agent couldn't find it, a miss
    if pred_unknown and not gold_unknown:
        return {"status": "missed", "details": f"Agent returned couldn't_determine, gold has a value"}

    #agent found something but gold says couldn't_determine, might be hallucinated, or the agent found something the gold-labeler missed
    if not pred_unknown and gold_unknown:
        return {
            "status": "extra",
            "details": f"Agent returned a value but gold says couldn't_determine. "
                        f"Review manually — could be hallucination or a good find. "
                        f"Agent said: {str(predicted_value)[:100]}",
        }

    #both have real values, compare by type

    if field_name in STRING_FIELDS:
        result = llm_judge_semantic_match(client, str(predicted_value), str(gold_value), field_name)
        match = result.get("match", False)
        return {
            "status": "correct" if match else "incorrect",
            "details": result.get("reasoning", ""),
        }

    elif field_name in LIST_FIELDS:
        #both should be lists at this point
        if not isinstance(predicted_value, list):
            return {"status": "incorrect", "details": f"Expected list, got {type(predicted_value).__name__}"}
        if not isinstance(gold_value, list):
            return {"status": "incorrect", "details": f"Gold is not a list: {type(gold_value).__name__}"}

        result = llm_judge_list_field(client, predicted_value, gold_value, field_name)
        #consider it "correct" if recall >= 0.7 (catches most gold items)
        status = "correct" if result["recall"] >= 0.7 else "incorrect"
        details = f"P={result['precision']:.0%} R={result['recall']:.0%} ({result['gold_matched']}/{result['gold_total']} gold matched)"
        return {
            "status": status,
            **result,
            "details": details,
        }

    elif field_name in DICT_FIELDS:
        if not isinstance(predicted_value, dict):
            return {"status": "incorrect", "details": f"Expected dict, got {type(predicted_value).__name__}"}
        if not isinstance(gold_value, dict):
            return {"status": "incorrect", "details": f"Gold is not a dict: {type(gold_value).__name__}"}

        result = llm_judge_dict_field(client, predicted_value, gold_value, field_name)
        status = "correct" if result["recall"] >= 0.7 else "incorrect"
        details = f"P={result['precision']:.0%} R={result['recall']:.0%} ({result['matched']}/{result['gold_total']} matched)"
        return {
            "status": status,
            **result,
            "details": details,
        }

    return {"status": "incorrect", "details": f"Unknown field type for {field_name}"}


def run():
    print_header("EXTRACTION ACCURACY EVAL")

    test_cases = load_test_cases("extraction")
    print(f"  Loaded {len(test_cases)} extraction test cases")
    print(f"  ⚠️  URL-based tests will hit the Tavily API\n")

    client = get_judge_client()

    #aggregate scores per field across all test cases
    field_scores = {f: {"correct": 0, "incorrect": 0, "missed": 0,
                        "both_unknown": 0, "extra": 0, "total": 0}
                    for f in ALL_FIELDS}

    for tc in test_cases:
        test_id = tc["test_id"]
        input_data = tc["input"]
        gold = tc["gold_labels"]

        #determine input type for display
        has_url = bool(input_data.get("funder_url"))
        has_text = bool(input_data.get("raw_grant_text"))
        input_type = "URL + text" if has_url and has_text else "URL" if has_url else "pasted text"

        print_subheader(f"Test: {test_id} ({input_type})")
        print_info(tc.get("description", ""))

        #run research_funder
        print(f"\n    Running research_funder...")
        start = time.time()
        try:
            result = research_funder(
                funder_url=input_data.get("funder_url") or None,
                raw_grant_text=input_data.get("raw_grant_text") or None,
            )
        except Exception as e:
            print_fail(f"research_funder crashed: {e}")
            print_info("Skipping this test case.\n")
            continue
        elapsed = time.time() - start
        print_timer("research_funder", elapsed)

        #ccore each field
        print(f"\n    Field-by-field scoring:")
        for field_name in ALL_FIELDS:
            gold_value = gold.get(field_name, "couldn't_determine")
            predicted_value = result.get(field_name, "couldn't_determine")

            try:
                score = score_field(client, predicted_value, gold_value, field_name)
            except Exception as e:
                score = {"status": "incorrect", "details": f"Scoring error: {e}"}

            status = score["status"]
            field_scores[field_name][status] = field_scores[field_name].get(status, 0) + 1
            field_scores[field_name]["total"] += 1

            if status == "correct" or status == "both_unknown":
                print_pass(field_name, score["details"])
            elif status == "extra":
                print_warn(field_name, score["details"])
            else:
                print_fail(field_name, score["details"])

            #print missed gold items and extra predictions for list fields
            if "missed_gold" in score and score["missed_gold"]:
                for m in score["missed_gold"]:
                    print_info(f"  {m}")
            if "extra_pred" in score and score["extra_pred"]:
                for e in score["extra_pred"]:
                    print_info(f"  {e}")

    #summary
    print_header("EXTRACTION EVAL SUMMARY PER FIELD")

    for field_name in ALL_FIELDS:
        scores = field_scores[field_name]
        total = scores["total"]
        if total == 0:
            continue

        correct = scores["correct"] + scores["both_unknown"]
        incorrect = scores["incorrect"] + scores["missed"]

        accuracy = correct / total if total > 0 else 0
        status_parts = []
        if scores["correct"]:
            status_parts.append(f"{scores['correct']} correct")
        if scores["both_unknown"]:
            status_parts.append(f"{scores['both_unknown']} both_unknown")
        if scores["incorrect"]:
            status_parts.append(f"{scores['incorrect']} incorrect")
        if scores["missed"]:
            status_parts.append(f"{scores['missed']} missed")
        if scores["extra"]:
            status_parts.append(f"{scores['extra']} extra (review)")

        print_score(f"{field_name}", f"{accuracy:.0%} ({', '.join(status_parts)})")

    #overall accuracy
    total_all = sum(s["total"] for s in field_scores.values())
    correct_all = sum(s["correct"] + s["both_unknown"] for s in field_scores.values())
    if total_all > 0:
        print(f"\n    ────────────────────────────────────────")
        print_score("OVERALL ACCURACY", f"{correct_all}/{total_all} = {correct_all/total_all:.0%}")

    print()


if __name__ == "__main__":
    run()