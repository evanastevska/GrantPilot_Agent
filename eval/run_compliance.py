"""Compliance checker accuracy scorer.

Runs check_compliance() on each compliance test case and checks:
- should_flag: did it catch each expected issue? (true positive rate)
- should_not_flag: did it stay clean? (false positive avoidance)

Scoring is mostly programmatic, parse the compliance output and check
whether the right flags appear. LLM fuzzy matching is only used for
unsupported_claims (matching human-readable tags to full claim text).

Usage:
    python eval/run_compliance_eval.py
"""

import sys
import time
from pathlib import Path

#add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_utils import (
    load_test_cases, resolve_org_profile, get_judge_client, call_judge,
    print_header, print_subheader, print_pass, print_fail, print_warn,
    print_info, print_score, print_timer,
)
from tools.check_compliance import check_compliance


#normalize category names
#test cases use "unsupported_claims" (plural) in should_not_flag but "unsupported_claim" (singular) in should_flag. Normalize.
CATEGORY_ALIASES = {
    "unsupported_claims": "unsupported_claim",
    "word_count_over_limit": "word_count_over_limit",
    "missing_section": "missing_section",
    "unaddressed_criterion": "unaddressed_criterion",
}


def extract_flagged_issues(result: dict) -> dict:
    """Parse compliance output into categorized flags.

    Returns dict: category -> list of detail strings.
    """
    flags = {
        "word_count_over_limit": [],
        "missing_section": [],
        "unaddressed_criterion": [],
        "unsupported_claim": [],
    }

    #programmatic: word count violations
    for wc in result.get("programmatic_checks", {}).get("word_count", []):
        if wc["status"] == "over_limit":
            flags["word_count_over_limit"].append(wc["section"])

    #LLM: missing sections
    for s in result.get("llm_checks", {}).get("sections_coverage", []):
        if s["status"] == "missing":
            normalized = s["required_section"].replace(" ", "_").lower()
            flags["missing_section"].append(normalized)

    #LLM: unaddressed criteria
    for c in result.get("llm_checks", {}).get("criteria_coverage", []):
        if not c["addressed"]:
            normalized = c["criterion"].replace(" ", "_").lower()
            flags["unaddressed_criterion"].append(normalized)

    #LLM: unsupported claims (store full claim text for fuzzy matching)
    for u in result.get("llm_checks", {}).get("unsupported_claims", []):
        flags["unsupported_claim"].append(u["claim"])

    return flags


def llm_match_claim_to_tag(client, claim_text: str, tag: str) -> bool:
    """Use LLM to check if a flagged claim corresponds to an expected tag.

    Example: tag="50000_attendees", claim="Cinema Verde attracted over 50,000
    attendees" → MATCH.
    """
    prompt = f"""Does this flagged claim correspond to the issue described by the tag?

TAG: {tag}
CLAIM: {claim_text}

The tag is a shorthand label (like "50000_attendees" meaning a false claim about 50,000 attendees).
The claim is the full text the compliance checker flagged.

Respond with ONLY one word: MATCH or NO_MATCH"""

    result = call_judge(client, prompt)
    return "MATCH" in result.strip().upper() and "NO_MATCH" not in result.strip().upper()


def check_should_flags(expected_flags: list, actual_flags: dict, client=None) -> list[dict]:
    """Check whether each expected flag was caught.

    For most categories: straightforward string matching.
    For unsupported_claim: LLM fuzzy matching between tag and claim text.
    """
    results = []

    for flag_str in expected_flags:
        parts = flag_str.split(":", 1)
        category = CATEGORY_ALIASES.get(parts[0], parts[0])
        detail = parts[1] if len(parts) > 1 else None

        caught = False
        match_info = ""

        if category == "word_count_over_limit" and detail:
            caught = detail in actual_flags.get("word_count_over_limit", [])

        elif category == "missing_section" and detail:
            #fuzzy substring match (the normalized section name might differ slightly)
            caught = any(detail in s for s in actual_flags.get("missing_section", []))

        elif category == "unaddressed_criterion" and detail:
            caught = any(detail in c for c in actual_flags.get("unaddressed_criterion", []))

        elif category == "unsupported_claim" and detail:
            #LLM fuzzy match: does any flagged claim match this tag?
            claims = actual_flags.get("unsupported_claim", [])
            if claims and client:
                for claim in claims:
                    if llm_match_claim_to_tag(client, claim, detail):
                        caught = True
                        match_info = f"matched to: '{claim[:80]}...'"
                        break
            elif claims:
                #fallback without LLM: at least one claim was flagged
                caught = True
                match_info = "claim flagged (no LLM verification)"

        results.append({
            "flag": flag_str,
            "caught": caught,
            "info": match_info,
        })

    return results


def check_should_not_flags(not_expected: list, actual_flags: dict) -> list[dict]:
    """Check that none of the should_not_flag categories fired."""
    results = []

    for category_str in not_expected:
        category = CATEGORY_ALIASES.get(category_str, category_str)
        items = actual_flags.get(category, [])
        clean = len(items) == 0

        results.append({
            "category": category_str,
            "clean": clean,
            "false_positives": items if not clean else [],
        })

    return results


def run():
    print_header("COMPLIANCE CHECKER EVAL")

    test_cases = load_test_cases("compliance")
    print(f"  Loaded {len(test_cases)} compliance test cases")

    client = get_judge_client()

    total_should_flag = 0
    caught_should_flag = 0
    total_should_not = 0
    clean_should_not = 0

    for tc in test_cases:
        test_id = tc["test_id"]
        print_subheader(f"Test: {test_id}")
        print_info(tc.get("description", ""))

        #load org profile if needed
        org_profile = resolve_org_profile(tc)

        #run compliance check
        print(f"\n    Running check_compliance...")
        start = time.time()
        try:
            result = check_compliance(
                drafted_sections=tc["drafted_sections"],
                funder_reqs=tc["funder_reqs"],
                org_profile=org_profile,
            )
        except Exception as e:
            print_fail(f"check_compliance crashed: {e}")
            continue
        elapsed = time.time() - start
        print_timer("check_compliance", elapsed)

        #show what it returned
        print_info(f"overall_status: {result['overall_status']}")
        if result["revision_feedback"]:
            # Truncate long feedback for readability
            fb = result["revision_feedback"]
            print_info(f"revision_feedback: {fb[:200]}{'...' if len(fb) > 200 else ''}")
        if result["verify_manually"]:
            print_info(f"verify_manually: {result['verify_manually']}")

        #extract what was actually flagged
        actual_flags = extract_flagged_issues(result)

        expected = tc["expected"]

        #check should_flag
        if expected["should_flag"]:
            print(f"\n    Should flag:")
            should_results = check_should_flags(expected["should_flag"], actual_flags, client)
            for r in should_results:
                total_should_flag += 1
                if r["caught"]:
                    caught_should_flag += 1
                    detail = r["info"] if r["info"] else ""
                    print_pass(f"Caught: {r['flag']}", detail)
                else:
                    print_fail(f"Missed: {r['flag']}")

        #check should_not_flag
        if expected["should_not_flag"]:
            print(f"\n    Should NOT flag:")
            not_results = check_should_not_flags(expected["should_not_flag"], actual_flags)
            for r in not_results:
                total_should_not += 1
                if r["clean"]:
                    clean_should_not += 1
                    print_pass(f"Clean: {r['category']}")
                else:
                    print_fail(
                        f"False positive: {r['category']}",
                        f"flagged: {[fp[:60] for fp in r['false_positives']]}"
                    )

        #clean baseline special check
        if not expected["should_flag"]:
            print(f"\n    Clean baseline check:")
            if result["overall_status"] == "approved":
                print_pass("overall_status = 'approved'")
            else:
                print_fail(f"overall_status = '{result['overall_status']}' (expected 'approved')")

    #summary
    print_header("COMPLIANCE EVAL SUMMARY")

    if total_should_flag > 0:
        rate = caught_should_flag / total_should_flag
        print_score("Detection rate (should_flag caught)",
                    f"{caught_should_flag}/{total_should_flag} = {rate:.0%}")
    else:
        print_score("Detection rate", "no should_flag items")

    if total_should_not > 0:
        rate = clean_should_not / total_should_not
        print_score("False positive avoidance (should_not_flag clean)",
                    f"{clean_should_not}/{total_should_not} = {rate:.0%}")
    else:
        print_score("False positive avoidance", "no should_not_flag items")

    print()


if __name__ == "__main__":
    run()