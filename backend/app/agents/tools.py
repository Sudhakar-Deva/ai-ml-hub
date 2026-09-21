"""The three tools, shared by the agent AND the workflow.

    python -m app.agents.tools --diff        # v1 -> v2, written to week7/tool_descriptions.diff
    python -m app.agents.tools --check       # the v2 spec is one-job, enum-typed, non-overlapping

The tool SPECS (name, description, schema) live in week7/tools_v*.json, not in
this file, so the description change is a diff a grader can read. v1 is the
two-tool loop as it shipped: get_claim "checks it against the policy" and
search_policy "checks coverage for a claim" — two tools claiming the same job,
which is where the thrash came from. v2 fixes that in the DESCRIPTIONS (not in
the system prompt) and adds compute_payout.
"""
import argparse
import difflib
import json

from .. import config

POLICY_LINES = ("homeowners", "dwelling_fire", "condo")
CLAIM_STATUSES = ("covered", "partial", "denied", "undetermined")


def load_specs(version: str = "v2") -> list[dict]:
    path = config.TOOLS_V1_FILE if version == "v1" else config.TOOLS_V2_FILE
    return json.loads(path.read_text())


# --- the claim file -----------------------------------------------------------

def _claims() -> dict[str, dict]:
    out = {}
    for line in config.W7_CLAIMS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            c = json.loads(line)
            out[c["claim_number"]] = c
    return out


def load_claims() -> list[dict]:
    return list(_claims().values())


CLAIM_FIELDS = (
    "claim_number", "policy_number", "policy_line", "date_of_loss",
    "loss_type_reported", "claimed_amount", "policy_excess", "adjuster_notes",
)


def get_claim(claim_number: str) -> dict:
    """The claim-file record. Never the gold, never the class label."""
    c = _claims().get(claim_number)
    if c is None:
        return {"error": f"no claim {claim_number}"}
    return {f: c.get(f) for f in CLAIM_FIELDS}


# --- the policy wording -------------------------------------------------------

def search_policy(query: str, policy_line: str, k: int = 5) -> dict:
    """Week 4's shipped retriever, filtered to one policy line. Same function the
    RAG app answers with — the agent does not get a better search than the app."""
    from ..retrieval.search import search

    if policy_line not in POLICY_LINES:
        return {"error": f"policy_line must be one of {POLICY_LINES}"}
    k = max(1, min(int(k), 8))
    hits = search(query, "structure_aware", k, policy_line=policy_line,
                  retriever=config.SHIPPED_RETRIEVER)
    return {
        "results": [
            {
                "chunk_id": h["chunk_id"],
                "form_number": f"{h['form_number']} ed. {h['edition_date']}",
                "clause": h["clause"],
                "text": h["text"],
            }
            for h in hits
        ]
    }


# --- the arithmetic -----------------------------------------------------------

def compute_payout(claim_status: str, covered_amount: float, excess: float,
                   special_limit: float | None = None) -> dict:
    """Excess first, then the special limit (HO-0521 §II 'Deductible first')."""
    if claim_status not in CLAIM_STATUSES:
        return {"error": f"claim_status must be one of {CLAIM_STATUSES}"}
    if claim_status in ("denied", "undetermined"):
        payable = 0.0
    else:
        payable = max(0.0, float(covered_amount) - float(excess))
        if special_limit is not None:
            payable = min(payable, float(special_limit))
    return {"payable_amount": round(payable, 2)}


REGISTRY = {"get_claim": get_claim, "search_policy": search_policy, "compute_payout": compute_payout}


def run_tool(name: str, args: dict) -> dict:
    fn = REGISTRY.get(name)
    if fn is None:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:  # bad/missing arguments go back to the model, not up the stack
        return {"error": f"bad arguments for {name}: {e}"}


# --- the description diff and its check ---------------------------------------

def render_diff() -> str:
    def lines(specs):
        out = []
        for s in specs:
            out.append(f"## {s['name']}")
            out.append(f"description: {s['description']}")
            out.extend(json.dumps(s["input_schema"], indent=2).splitlines())
            out.append("")
        return out

    return "\n".join(difflib.unified_diff(
        lines(load_specs("v1")), lines(load_specs("v2")),
        fromfile="week7/tools_v1.json", tofile="week7/tools_v2.json", lineterm="",
    ))


# Words that name a JOB. A description may claim one of these and must disclaim
# the others — "does not decide coverage" is how the overlap is closed.
JOBS = {
    "get_claim": "claim-file record",
    "search_policy": "endorsement wording",
    "compute_payout": "payable amount",
}


def check() -> list[str]:
    specs = {s["name"]: s for s in load_specs("v2")}
    problems = []
    if set(specs) != set(REGISTRY):
        problems.append(f"spec tools {sorted(specs)} != implemented {sorted(REGISTRY)}")
    for name, job in JOBS.items():
        d = specs[name]["description"].lower()
        if job not in d:
            problems.append(f"{name}: description does not name its job ({job!r})")
        for other, other_job in JOBS.items():
            if other != name and other_job in d:
                problems.append(f"{name}: description also claims {other}'s job ({other_job!r})")
    props = specs["compute_payout"]["input_schema"]["properties"]
    if props["claim_status"].get("enum") != list(CLAIM_STATUSES):
        problems.append("compute_payout.claim_status is not the claim-status enum")
    if specs["search_policy"]["input_schema"]["properties"]["policy_line"].get("enum") != list(POLICY_LINES):
        problems.append("search_policy.policy_line is not an enum")
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        p = check()
        print("\n".join(f"  - {x}" for x in p) if p else "ok — one job per tool, enums typed, no overlap")
        raise SystemExit(1 if p else 0)
    diff = render_diff()
    out = config.WEEK7_DIR / "tool_descriptions.diff"
    out.write_text(diff + "\n")
    print(diff)
    print(f"\n-> {out.relative_to(config.ROOT)}")
