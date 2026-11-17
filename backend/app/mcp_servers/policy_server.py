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

from mcp.server.fastmcp import Context, FastMCP

from .. import config

POLICY_LINES = ("homeowners", "dwelling_fire", "condo")

mcp = FastMCP("policy-docs")


# --- the corpus, parsed once --------------------------------------------------
# Week 12: a form can have several editions (HO-0304 ed. 01-23 / 03-24 / 04-25).
# FORMS[form] is the list of its editions, oldest first. Under triage-v1 a lookup
# without a date gets the LAST edition loaded, which is what the Week 9 dict did
# by accident (seam S3); under triage-v2 the edition is resolved by the loss date.

def _parse(f) -> dict:
    from ..ingestion.loader import effective_int

    text = f.read_text()
    lines = text.splitlines()
    line = re.search(r"^Policy_line:\s*(\w+)", text, re.M).group(1)
    eff = re.search(r"^Effective:\s*(\S+)", text, re.M)
    codes, code_lines = {}, {}
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^\|\s*(E-\d+)\s*\|.*$", ln)
        if m:
            codes[m.group(1)], code_lines[m.group(1)] = ln.strip(), i
    # lettered sections ("B. Other special limits") run to the next heading
    sections, sec_lines, cur = {}, {}, None
    for i, ln in enumerate(lines, 1):
        m = re.match(r"^([A-H])\.\s+\S", ln)
        if m:
            cur = m.group(1)
            sections[cur], sec_lines[cur] = [ln], i
        elif re.match(r"^SECTION [IVX]+", ln):
            cur = None
        elif cur:
            sections[cur].append(ln)
    return {"form": text.split()[0], "policy_line": line, "edition": lines[0], "edition_date": lines[0].split("ed.")[-1].strip(),
            "source_file": f.name, "effective_from": effective_int(eff.group(1)) if eff else 0,
            "codes": codes, "sections": {k: "\n".join(v).strip() for k, v in sections.items()},
            "lines": {**code_lines, **sec_lines}}


def _forms() -> dict[str, list[dict]]:
    from ..ingestion.ingest import effective_windows
    from ..ingestion.loader import load_all

    windows = effective_windows(load_all(config.DOCS_DIR))
    out: dict[str, list[dict]] = {}
    for f in sorted(config.DOCS_DIR.glob("*-ed-*.md")):
        ed = _parse(f)
        ed["effective_from"], ed["effective_to"] = windows[f.name]
        out.setdefault(ed["form"], []).append(ed)
    for eds in out.values():
        eds.sort(key=lambda e: e["effective_from"])
    return out


FORMS = _forms()


def _iso(d: int) -> str:
    s = str(d)
    return "open" if d >= 99991231 else f"{s[:4]}-{s[4:6]}-{s[6:]}"


def edition_in_force(form: str, loss_date: str) -> dict | None:
    from ..retrieval.search import loss_date_int

    d = loss_date_int(loss_date)
    return next((e for e in FORMS.get(form, []) if e["effective_from"] <= d <= e["effective_to"]), None)


# --- Week 12: one span per tool call, under the caller's trace id ---------------
# The trace id arrives in the MCP request's _meta, set by the host. It is never a
# tool argument, so the model neither sees it nor can drop it.

def _span(ctx, tool: str, args: dict, t0: float, result_ids: list[str], error: str | None = None) -> None:
    import json
    import time
    from datetime import datetime, timezone

    from ..tracing.redact import redact_deep

    meta = getattr(getattr(ctx, "request_context", None), "meta", None) if ctx is not None else None
    trace_id = getattr(meta, "trace_id", None) if meta is not None else None
    if not trace_id:
        return
    clean_args, hits = redact_deep(args)
    rec = {"trace_id": trace_id, "span": f"mcp.policy-docs.{tool}", "side": "server",
           "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
           "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "triage_version": config.TRIAGE_VERSION,
           "date_filter": config.DATE_FILTER, "args": clean_args, "returned_ids": result_ids,
           "error": error, "cost_usd": 0.0, "redaction": hits}
    config.W12_MCP_SPAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with config.W12_MCP_SPAN_FILE.open("a") as f:
        f.write(json.dumps(rec) + "\n")


def _compact(text: str) -> str:
    """Week 12: the stamp line repeats form/edition (already in the result) and the table
    header repeats on every exclusion row. Both are re-sent on every agent lap."""
    keep = [ln for ln in text.splitlines()
            if not ln.startswith("[") and not re.match(r"^\|\s*(Code|-+)\s*\|", ln)]
    return "\n".join(keep)[:450]


def _search(query: str, policy_line: str, k: int, loss_date: str | None) -> dict:
    from ..retrieval.search import search

    if policy_line not in POLICY_LINES:
        raise ValueError(f"policy_line {policy_line!r} is not one of {', '.join(POLICY_LINES)}")
    hits = search(query, "structure_aware", max(1, min(int(k), 8)), policy_line=policy_line,
                  retriever=config.SHIPPED_RETRIEVER, loss_date=loss_date)
    out = []
    for h in hits:
        ed = next((e for e in FORMS.get(h["form_number"], []) if e["source_file"] == h["source_file"]), None)
        out.append({"chunk_id": h["chunk_id"], "form_number": f"{h['form_number']} ed. {h['edition_date']}",
                    "in_force": f"{_iso(ed['effective_from'])} to {_iso(ed['effective_to'])}" if ed else "unknown",
                    "clause": h["clause"], "text": _compact(h["text"])})
    return {"resolved_against_loss_date": loss_date, "results": out}


# --- tools ----------------------------------------------------------------------

if config.DATE_FILTER:
    @mcp.tool()
    def search_policy(query: str, policy_line: str, loss_date: str, k: int = 5, ctx: Context = None) -> dict:
        """Search the endorsement wording of ONE policy line (homeowners, dwelling_fire
        or condo) as it stood ON THE LOSS DATE (YYYY-MM-DD): only editions in force on
        that date are searched, enforced in the store query. Returns the best-matching
        clauses with form number and edition. Knows nothing about any claim."""
        import time

        t0 = time.perf_counter()
        try:
            res = _search(query, policy_line, k, loss_date)
        except Exception as e:
            _span(ctx, "search_policy", {"query": query, "policy_line": policy_line, "loss_date": loss_date, "k": k}, t0, [], str(e))
            raise
        _span(ctx, "search_policy", {"query": query, "policy_line": policy_line, "loss_date": loss_date, "k": k}, t0,
              [r["chunk_id"] for r in res["results"]])
        return res
else:
    @mcp.tool()
    def search_policy(query: str, policy_line: str, k: int = 5, ctx: Context = None) -> dict:
        """Search the endorsement wording of ONE policy line (homeowners, dwelling_fire
        or condo) and return the best-matching clauses, each with its chunk_id, form
        number and clause heading. Policy text only: it knows nothing about any claim."""
        import time

        t0 = time.perf_counter()
        res = _search(query, policy_line, k, None)
        _span(ctx, "search_policy", {"query": query, "policy_line": policy_line, "k": k}, t0,
              [r["chunk_id"] for r in res["results"]])
        return res


@mcp.tool()
def get_clause(form_number: str, clause: str, loss_date: str = "", ctx: Context = None) -> str:
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
    loss_date: YYYY-MM-DD. A form can have several editions; the edition returned
        is the one in force on this date.

    Returns the form's edition line, then the clause text. If the form or clause
    does not exist, the error names the bad value and lists the valid ones;
    correct that argument and call again. Do not quote a clause you did not get.
    """
    import time

    t0 = time.perf_counter()
    eds = FORMS.get(form_number)
    if eds is None:
        raise ValueError(_unknown_form(form_number))
    if loss_date:
        f = edition_in_force(form_number, loss_date)
        if f is None:
            raise ValueError(f"no edition of {form_number} was in force on {loss_date}. Editions: "
                             + ", ".join(f"{e['edition']} ({_iso(e['effective_from'])} to {_iso(e['effective_to'])})" for e in eds))
    elif config.DATE_FILTER and len(eds) > 1:
        raise ValueError(f"{form_number} has {len(eds)} editions; pass loss_date (YYYY-MM-DD) so the edition in force "
                         f"on that date is returned: " + ", ".join(e["edition"] for e in eds))
    else:
        f = eds[-1]       # triage-v1: whichever edition loaded last (seam S3)
    text = f["codes"].get(clause) or f["sections"].get(clause)
    if text is None:
        valid = sorted(f["codes"]) + [f"section {s}" for s in sorted(f["sections"])]
        raise ValueError(
            f"clause {clause!r} not found on {form_number}: clause is an exclusion code like 'E-17' "
            f"or a section letter like 'B'. Clauses on {form_number}: {', '.join(valid) or 'none'}.")
    _span(ctx, "get_clause", {"form_number": form_number, "clause": clause, "loss_date": loss_date}, t0,
          [f"{f['edition']} · {clause}"])
    return (f"{f['edition']} · {clause} (in force {_iso(f['effective_from'])} to {_iso(f['effective_to'])})\n{text}")


def _unknown_form(given: str) -> str:
    """The recoverable version of 'Error 3': what was wrong, what is valid, and the
    likely intended form when one can be read out of the bad value."""
    on_file = ", ".join(f"{k} ({v[0]['policy_line']})" for k, v in FORMS.items())
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
    rows = [f"{form} ({f['edition']}, in force {_iso(f['effective_from'])} to {_iso(f['effective_to'])}): {row}"
            for form, eds in FORMS.items() for f in eds if f["policy_line"] == line for row in f["codes"].values()]
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
    # Week 12: load the embedder before the first request, so a claim's search span
    # measures the search, not a cold model load (Week 11's 5.5 s retrieval span).
    try:
        _search("warm up", "homeowners", 1, None)
    except Exception:
        pass
    mcp.run("stdio")
