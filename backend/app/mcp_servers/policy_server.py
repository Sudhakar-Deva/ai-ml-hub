"""Server one: the policy-document server. OUR code, over MCP stdio.

    python -m app.mcp_servers.policy_server          # speaks JSON-RPC on stdin/stdout

Tools (model-invoked):
  search_policy  the Week 4 shipped retriever, filtered to one policy line
  get_clause     one clause's exact wording, by form number + clause id

Resources (app-attached, never a tool):
  policy://exclusions/<policy_line>   the exclusions schedule for a line. The
  host attaches it to the model's context up front, so the model is never made
  to call out for a list it should already have been given.

No LLM call anywhere in this file. The server exposes a capability; the host
runs the model.
"""
import re
import sys

from mcp.server.fastmcp import FastMCP

from .. import config

POLICY_LINES = ("homeowners", "dwelling_fire", "condo")

mcp = FastMCP("policy-docs")


# --- the corpus, parsed once --------------------------------------------------

def _forms() -> dict[str, dict]:
    out = {}
    for f in sorted(config.DOCS_DIR.glob("*-ed-*.md")):
        text = f.read_text()
        form = text.split()[0]                                    # "HO-0521"
        line = re.search(r"^Policy_line:\s*(\w+)", text, re.M).group(1)
        codes = {m.group(1): m.group(0).strip()
                 for m in re.finditer(r"^\|\s*(E-\d+)\s*\|.*$", text, re.M)}
        # lettered sections ("B. Other special limits") run to the next heading
        sections, cur = {}, None
        for ln in text.splitlines():
            m = re.match(r"^([A-H])\.\s+\S", ln)
            if m:
                cur = m.group(1)
                sections[cur] = [ln]
            elif re.match(r"^SECTION [IVX]+", ln):
                cur = None
            elif cur:
                sections[cur].append(ln)
        out[form] = {"policy_line": line, "edition": text.splitlines()[0], "codes": codes,
                     "sections": {k: "\n".join(v).strip() for k, v in sections.items()}}
    return out


FORMS = _forms()


# --- tools ----------------------------------------------------------------------

@mcp.tool()
def search_policy(query: str, policy_line: str, k: int = 5) -> dict:
    """Search the endorsement wording of ONE policy line (homeowners, dwelling_fire
    or condo) and return the best-matching clauses, each with its chunk_id, form
    number and clause heading. Policy text only: it knows nothing about any claim."""
    from ..retrieval.search import search

    if policy_line not in POLICY_LINES:
        raise ValueError(f"policy_line {policy_line!r} is not one of {', '.join(POLICY_LINES)}")
    hits = search(query, "structure_aware", max(1, min(int(k), 8)), policy_line=policy_line,
                  retriever=config.SHIPPED_RETRIEVER)
    return {"results": [{"chunk_id": h["chunk_id"], "form_number": f"{h['form_number']} ed. {h['edition_date']}",
                         "clause": h["clause"], "text": h["text"]} for h in hits]}


@mcp.tool()
def get_clause(form_number: str, clause: str) -> str:
    """Return the exact wording of ONE clause from ONE endorsement form, verbatim.

    Use this when you already know which form and clause you need (a search_policy
    result or the user named it) and must quote it exactly. To find out WHICH
    clause applies, call search_policy instead; this tool does not search.

    form_number: the bare form number, two letters, a dash and four digits:
        "HO-0304", "DP-0110", "CO-0715". NOT the edition string search_policy
        prints ("HO-0304 ed. 03-24"); drop the " ed. MM-YY" part.
    clause: an exclusion code such as "E-17", or the letter of a lettered
        section such as "B" (HO-0521 B is the special-limits table). NOT a
        heading such as "SECTION I — EXCLUSIONS / E-17".

    Returns the form's edition line, then the clause text. If the form or clause
    does not exist, the error names the bad value and lists the valid ones;
    correct that argument and call again. Do not quote a clause you did not get.
    """
    f = FORMS.get(form_number)
    if f is None:
        raise ValueError(_unknown_form(form_number))
    text = f["codes"].get(clause) or f["sections"].get(clause)
    if text is None:
        valid = sorted(f["codes"]) + [f"section {s}" for s in sorted(f["sections"])]
        raise ValueError(
            f"clause {clause!r} not found on {form_number}: clause is an exclusion code like 'E-17' "
            f"or a section letter like 'B'. Clauses on {form_number}: {', '.join(valid) or 'none'}.")
    return f"{f['edition']} · {clause}\n{text}"


def _unknown_form(given: str) -> str:
    """The recoverable version of 'Error 3': what was wrong, what is valid, and the
    likely intended form when one can be read out of the bad value."""
    on_file = ", ".join(f"{k} ({v['policy_line']})" for k, v in FORMS.items())
    msg = (f"form {given!r} not found: form_number is the bare form number, two letters, "
           f"a dash and four digits (like 'HO-0304'), with no edition suffix. Forms on file: {on_file}.")
    m = re.match(r"\s*([A-Za-z]{2})-?(\d{1,4})", given)
    if m:
        guess = f"{m.group(1).upper()}-{int(m.group(2)):04d}"
        if guess in FORMS and guess != given:
            msg += f" Did you mean {guess!r}?"
    return msg


# --- resources (app-attached context) -------------------------------------------

def _exclusions_schedule(line: str) -> str:
    rows = [f"{form} ({f['edition']}): {row}" for form, f in FORMS.items()
            if f["policy_line"] == line for row in f["codes"].values()]
    return f"Exclusions schedule, policy_line={line}\n" + "\n".join(rows)


def _register(line: str) -> None:
    def read() -> str:
        return _exclusions_schedule(line)
    mcp.resource(f"policy://exclusions/{line}", name=f"exclusions-{line}",
                 description=f"Every exclusion row on the {line} forms, verbatim.",
                 mime_type="text/plain")(read)


for _line in POLICY_LINES:
    _register(_line)


if __name__ == "__main__":
    # stdout IS the JSON-RPC channel: anything a library prints there corrupts it.
    sys.stdout.reconfigure(line_buffering=True)
    mcp.run("stdio")
