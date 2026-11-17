"""The two local tools that read the policy register: no model, no network.

lookup_policy            deductible, sub-limits and policy limit IN FORCE ON THE LOSS DATE,
                         as separate numbers, each naming the clause that sets it
check_coverage_in_force  was the policy in force on the loss date, and which endorsement
                         editions of its line were in force that day
"""
import json
from functools import lru_cache

from .. import config


@lru_cache(maxsize=1)
def _register() -> dict:
    return json.loads(config.POLICY_REGISTER_FILE.read_text())


@lru_cache(maxsize=1)
def _products() -> dict:
    return json.loads(config.PRODUCTS_FILE.read_text())


def _date(s: str) -> str:
    from ..retrieval.search import loss_date_int

    loss_date_int(s)          # raises on anything but YYYY-MM-DD
    return s.strip()


def _policy(policy_number: str) -> dict:
    p = _register().get(str(policy_number).strip().upper())
    if p is None or policy_number.startswith("_"):
        raise ValueError(f"policy {policy_number!r} not found in the policy register. Policy numbers look like "
                         f"'HO-781201', 'DP-552300' or 'CO-330912'; take it from the FNOL.")
    return p


def _in_window(item: dict, d: str) -> bool:
    return item["from"] <= d and (item["to"] is None or d <= item["to"])


def lookup_policy(policy_number: str, loss_date: str) -> dict:
    d, p = _date(loss_date), _policy(policy_number)
    prod = _products()[p["product"]]
    return {
        "policy_number": policy_number, "policy_line": p["policy_line"], "product": p["product"],
        "resolved_against_loss_date": d,
        "policy_deductible": p["deductible"],
        "peril_deductibles": [{k: x[k] for k in ("peril", "amount", "source")} for x in prod["peril_deductibles"] if _in_window(x, d)],
        "sub_limits": [{k: x[k] for k in ("peril", "amount", "source")} for x in prod["sub_limits"] if _in_window(x, d)],
        "policy_limit": p["policy_limit"],
        "note": "A sub-limit applies only to its peril; a peril deductible replaces the policy deductible for that peril.",
    }


def check_coverage_in_force(policy_number: str, loss_date: str) -> dict:
    from ..mcp_servers.policy_server import FORMS, _iso, edition_in_force

    d, p = _date(loss_date), _policy(policy_number)
    term = next((t for t in p["terms"] if t["from"] <= d <= t["to"]), None)
    editions = []
    for form, eds in FORMS.items():
        if eds[0]["policy_line"] == p["policy_line"]:
            e = edition_in_force(form, d)
            editions.append(f"{e['edition']} (in force {_iso(e['effective_from'])} to {_iso(e['effective_to'])})" if e
                            else f"{form}: no edition in force on {d}")
    return {
        "policy_number": policy_number, "loss_date": d, "in_force": term is not None,
        "term_covering_loss_date": term,
        **({} if term else {"terms_on_file": p["terms"]}),
        "endorsement_editions_in_force_on_loss_date": editions,
        "note": ("Policy was in force on the loss date." if term else
                 "NO policy term covers the loss date. Refer to an adjuster; do not apply wording or limits."),
    }


SPECS = [
    {"name": "lookup_policy",
     "description": "Policy record by policy number, as of the loss date: the policy deductible, any peril deductibles, the "
                    "sub-limits in force on that date (each naming the clause that sets it) and the policy limit. Three "
                    "different numbers; report them separately.",
     "input_schema": {"type": "object", "properties": {
         "policy_number": {"type": "string", "description": "e.g. HO-781201, from the FNOL"},
         "loss_date": {"type": "string", "description": "date of loss, YYYY-MM-DD"}},
         "required": ["policy_number", "loss_date"]}},
    {"name": "check_coverage_in_force",
     "description": "Was the policy in force on the loss date? Returns the term covering that date (or none) and the "
                    "endorsement editions of the policy's line that were in force on that date.",
     "input_schema": {"type": "object", "properties": {
         "policy_number": {"type": "string"}, "loss_date": {"type": "string", "description": "YYYY-MM-DD"}},
         "required": ["policy_number", "loss_date"]}},
]
LOCAL = {"lookup_policy": lookup_policy, "check_coverage_in_force": check_coverage_in_force}
