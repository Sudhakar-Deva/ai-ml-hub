"""The output contract both systems must meet, the shared rules, and the grader.

Contract (one JSON object, nothing else):
    {"claim_number": "CLM-2026-10001",
     "decision": "COVERED" | "PARTIAL" | "DENIED" | "UNDETERMINED",
     "exclusion_codes": ["E-15", ...],
     "payable_amount": 7500.0,
     "reason": "<one or two sentences citing chunk_ids>"}

Pass = decision matches, every required exclusion code is cited and nothing
outside required+optional is, and payable_amount is within $1 of gold.
"""
import json
import re

DECISIONS = ("COVERED", "PARTIAL", "DENIED", "UNDETERMINED")

# The adjusting rules. Identical text goes into the agent's system prompt and the
# workflow's — a rule only one side gets is a variable in the race.
RULES = """You adjust homeowners, dwelling-fire and condominium claims. You decide
coverage ONLY from the policy wording returned by search_policy and the facts in the
claim file. You may not use general insurance knowledge or another form's wording.

Rules that are not preferences:
1. The claim's policy_line decides which wording governs. A dwelling-fire claim is
   not adjusted on homeowners wording even where the two share an exclusion code.
2. decision is one of COVERED, PARTIAL, DENIED, UNDETERMINED.
   PARTIAL = some of the claimed amount is not payable because of an exclusion or a
   special limit. DENIED = nothing is payable because of an exclusion.
3. A DENIED decision must list the exclusion code(s) that produce it. List only codes
   you actually rely on; list none for COVERED unless one applies.
4. If there are no adjuster notes, or the wording you have does not settle coverage,
   the decision is UNDETERMINED and payable_amount is 0. Never guess.
5. payable_amount comes from compute_payout. Use the deductible the governing wording
   sets for this type of loss; the claim's policy_excess applies unless the wording
   sets its own. A special limit is applied after the deductible."""

CONTRACT = """Return ONE JSON object and nothing else:
{"claim_number": "...", "decision": "COVERED|PARTIAL|DENIED|UNDETERMINED",
 "exclusion_codes": ["E-.."], "payable_amount": 0, "reason": "one or two sentences citing chunk_ids"}"""

_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse(text: str) -> dict | None:
    """Pull the contract object out of the model's text. Nothing is repaired: a
    missing field stays missing and grades as a fail."""
    m = _JSON_RE.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def undetermined(claim_number: str, reason: str) -> dict:
    return {"claim_number": claim_number, "decision": "UNDETERMINED",
            "exclusion_codes": [], "payable_amount": 0, "reason": reason}


def grade(output: dict | None, gold: dict) -> tuple[bool, list[str]]:
    if not output:
        return False, ["no parseable contract object"]
    why = []
    if output.get("decision") != gold["decision"]:
        why.append(f"decision {output.get('decision')} != {gold['decision']}")
    got = {str(c).strip().upper() for c in output.get("exclusion_codes") or []}
    req, opt = set(gold["exclusion_codes"]), set(gold.get("optional_codes", []))
    if not req <= got:
        why.append(f"missing exclusion {sorted(req - got)}")
    if got - req - opt:
        why.append(f"unsupported exclusion {sorted(got - req - opt)}")
    try:
        amt = float(output.get("payable_amount"))
    except (TypeError, ValueError):
        amt = None
    if amt is None or abs(amt - gold["payable_amount"]) > 1:
        why.append(f"payable {output.get('payable_amount')} != {gold['payable_amount']}")
    return not why, why
