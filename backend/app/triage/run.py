"""The ONE entry point: FNOL in -> referral out, one trace id across every hop.

    python -m app.triage CLM-2024-20001                # one claim, printed + traced
    TRIAGE_VERSION=triage-v1 python -m app.triage ...  # the parts as they were (no date filter)
    python -m app.triage --list-tools                  # what MCP discovery found

Hops, in order, all under one trace id:
  1. intake   claims-system MCP server (vendored): claim status + adjuster notes
  2. redact   names, addresses and injuries out BEFORE the model or any log sees the notes
  3. agent    the Week 7 hand-built loop, budgets enforced. Local tools (policy register)
              + every tool MCP discovery returns (policy-docs: the Week 3-4 retriever).
              The trace id rides in each MCP request's _meta; the policy-docs server
              logs its own span under it.
  4. refer    the loop ends only through refer_to_adjuster. There is no decision field.
  5. guard    decision words are removed from the referral IN CODE (not by prompt), and
              every citation's edition is checked against the edition in force on the
              loss date.
  6. trace    one record per request, redacted on write, server spans merged in.
"""
import argparse
import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from .. import llm as provider
from ..agents import llm as agent_llm
from ..agents.budget import Budget, BudgetExceeded, price
from ..llm import DailyLimit, LLMTimeout
from ..mcphost.agent import Host
from ..tracing.redact import redact, redact_deep
from . import policies

SYSTEM = """You triage first notices of loss (FNOL) for a property insurer for a human
adjuster. You never decide coverage; the adjuster decides. Never state or imply a
coverage decision; never write "covered", "denied", "approved", "declined", "payable".
1. Call check_coverage_in_force and lookup_policy with the FNOL's policy number and
   loss date, and search the policy wording for the facts in the notes.
2. Cite only clauses a tool returned, by form, edition and clause.
3. Call refer_to_adjuster once, with deductible, sub-limit and policy limit as three
   separate numbers (sub_limit null if none applies to this loss). If the policy was
   not in force on the loss date, say so.
Use only what the tools return, never general insurance knowledge."""

REFER = {
    "name": "refer_to_adjuster",
    "description": "Hand the claim to a human adjuster: facts, the wording that bears on it, three money numbers. "
                   "The ONLY way to finish. Records no decision.",
    "input_schema": {"type": "object", "properties": {
        "claim_number": {"type": "string"},
        "loss_date": {"type": "string", "description": "YYYY-MM-DD"},
        "in_force": {"type": "boolean", "description": "from check_coverage_in_force"},
        "in_force_basis": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "object", "properties": {
            "form": {"type": "string", "description": "e.g. HO-0304"},
            "edition": {"type": "string", "description": "MM-YY, e.g. 03-24"},
            "clause": {"type": "string", "description": "E-15, or a section letter"},
            "relevance": {"type": "string", "description": "the fact it bears on"}},
            "required": ["form", "edition", "clause", "relevance"]}},
        "deductible": {"type": ["number", "null"]},
        "deductible_basis": {"type": "string"},
        "sub_limit": {"type": ["number", "null"], "description": "null if none applies to this loss"},
        "sub_limit_basis": {"type": "string"},
        "policy_limit": {"type": ["number", "null"]},
        "facts_for_adjuster": {"type": "string"},
        "open_questions": {"type": "array", "items": {"type": "string"}}},
        "required": ["claim_number", "loss_date", "in_force", "citations", "deductible", "sub_limit", "policy_limit",
                     "facts_for_adjuster"]},
}
NUDGE = "You have not referred the claim. Call refer_to_adjuster now with what the tools returned."

# The compliance rule, enforced in code. Checked on every free-text field the system writes.
BANNED = re.compile(r"\b(covered|uncovered|denied|deny|denies|declined?|approved?|payable)\b", re.I)
GUARD_FIELDS = ("in_force_basis", "deductible_basis", "sub_limit_basis", "facts_for_adjuster")
REMOVED = "[removed by the decision-language guard]"


def prompt_sha() -> str:
    """Pins the exact instructions a run used: system prompt + local and refer tool specs."""
    blob = json.dumps([SYSTEM, policies.SPECS, REFER], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# --- guard + citation check (code, not prompt) ----------------------------------

def _scrub(text: str) -> tuple[str, list[str]]:
    hits, out = [], []
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        m = BANNED.search(sent)
        if m:
            hits.append(m.group(1).lower())
            out.append(REMOVED)
        else:
            out.append(sent)
    return " ".join(out), hits


def guard(referral: dict) -> tuple[dict, list[dict]]:
    """-> (referral with every sentence carrying a decision word removed, what fired)."""
    r, fired = json.loads(json.dumps(referral)), []
    for f in GUARD_FIELDS:
        if isinstance(r.get(f), str):
            r[f], hits = _scrub(r[f])
            fired += [{"field": f, "word": w} for w in hits]
    for i, q in enumerate(r.get("open_questions") or []):
        r["open_questions"][i], hits = _scrub(str(q))
        fired += [{"field": f"open_questions[{i}]", "word": w} for w in hits]
    for i, c in enumerate(r.get("citations") or []):
        c["relevance"], hits = _scrub(str(c.get("relevance", "")))
        fired += [{"field": f"citations[{i}].relevance", "word": w} for w in hits]
    return r, fired


def _norm_edition(e: str) -> str:
    m = re.search(r"(\d{2})\s*[-/]\s*(\d{2})(?!\d)", str(e))
    return f"{m.group(1)}-{m.group(2)}" if m else str(e).strip()


def _norm_clause(raw: str) -> str:
    """The chunker labels a chunk "SECTION I — EXCLUSIONS / E-15"; the model often copies
    that whole heading. The clause it names is the code (or section letter) at the end."""
    m = re.search(r"\b(E-\d+)\b", raw, re.I)
    if m:
        return m.group(1).upper()
    m = (re.fullmatch(r"\s*(?:section\s+)?([A-H])\.?\s*", raw, re.I) or re.search(r"/\s*([A-H])\.\s", raw)
         or re.match(r"\s*([A-H])\.\s+\S", raw))       # "B. Other special limits"
    return m.group(1).upper() if m else raw.upper()


def _is_heading(doc: dict, raw: str) -> bool:
    """A prose chunk ("APPLICATION OF THESE EXCLUSIONS") is real wording too: it exists if
    that heading is in that edition's text."""
    from ..mcp_servers.policy_server import config as _c

    head = raw.split("/")[-1].strip()
    return len(head) > 6 and head.upper() in (_c.DOCS_DIR / doc["source_file"]).read_text().upper()


def _heading_line(doc: dict, raw: str) -> int | None:
    from ..mcp_servers.policy_server import config as _c

    head = raw.split("/")[-1].strip().upper()
    for i, ln in enumerate((_c.DOCS_DIR / doc["source_file"]).read_text().splitlines(), 1):
        if head and head in ln.upper():
            return i
    return None


def check_citations(citations: list[dict], loss_date: str) -> list[dict]:
    """For each citation: does that edition + clause exist, which edition was in force on
    the loss date, and the clickable source (file#line). Nothing is corrected here."""
    from ..mcp_servers.policy_server import FORMS, edition_in_force

    out = []
    for c in citations or []:
        form = str(c.get("form", "")).split()[0].upper()
        ed = _norm_edition(c.get("edition", ""))
        raw_clause = str(c.get("clause", "")).strip()
        clause = _norm_clause(raw_clause)
        doc = next((e for e in FORMS.get(form, []) if e["edition_date"] == ed), None)
        try:
            in_force = edition_in_force(form, loss_date)
        except ValueError:
            in_force = None
        exists = bool(doc and (clause in doc["codes"] or clause in doc["sections"] or _is_heading(doc, raw_clause)))
        line = (doc["lines"].get(clause) or _heading_line(doc, raw_clause)) if doc else None
        out.append({**c, "form": form, "edition": ed, "clause": clause, "clause_as_cited": raw_clause, "exists": exists,
                    "edition_in_force": in_force["edition_date"] if in_force else None,
                    "wrong_version": bool(in_force) and ed != in_force["edition_date"],
                    "resolved_against_loss_date": loss_date,
                    "source": (f"data/endorsements/{doc['source_file']}#L{line}" if doc and line else None)})
    return out


def render(rec: dict) -> str:
    r, lines = rec["referral"], []
    lines.append("REFERRAL TO ADJUSTER: no coverage decision has been made by this system")
    lines.append(f"trace {rec['trace_id']} · {rec['triage_version']} · loss date {rec['loss_date']}")
    if r is None:
        lines.append("The agent did not produce a referral. Refer manually; see the trace.")
        return "\n".join(lines)
    inf = "YES" if r.get("in_force") else "NO"
    lines.append(f"In force on the loss date: {inf}. {r.get('in_force_basis', '')}".strip())
    lines.append(f"Wording cited, each resolved against loss date {rec['loss_date']}:")
    for c in rec["citations"]:
        label = f"{c['form']} ed. {c['edition']} · {c['clause']}"
        link = f"[{label}](../{c['source']})" if c["source"] else f"{label} (NOT FOUND in that edition)"
        flag = "" if not c["wrong_version"] else f"  ⚠ edition in force on the loss date was ed. {c['edition_in_force']}"
        lines.append(f"  - {link}: {c.get('relevance', '')}{flag}")
    if not rec["citations"]:
        lines.append("  (none)")
    money = lambda v: "none" if v is None else f"${v:,.0f}"
    lines.append(f"Deductible: {money(r.get('deductible'))}   Sub-limit: {money(r.get('sub_limit'))}   "
                 f"Policy limit: {money(r.get('policy_limit'))}")
    for k in ("deductible_basis", "sub_limit_basis"):
        if r.get(k):
            lines.append(f"  {k.replace('_', ' ')}: {r[k]}")
    lines.append(f"Facts for the adjuster: {r.get('facts_for_adjuster', '')}")
    for q in r.get("open_questions") or []:
        lines.append(f"  ? {q}")
    if rec["guard_fired"]:
        lines.append(f"(decision-language guard removed {len(rec['guard_fired'])} sentence(s))")
    return "\n".join(lines)


# --- the request ------------------------------------------------------------------

def _call(budget: Budget, messages: list[dict], tools: list[dict]):
    """agents.llm.call with the triage model: budget checked before, charged after."""
    budget.check()
    resp, usage = provider.chat_with_tools(model=config.TRIAGE_MODEL, system=SYSTEM, messages=messages, tools=tools,
                                           max_tokens=config.AGENT_MAX_TOKENS_PER_CALL,
                                           timeout=max(1.0, budget.remaining_s()))
    budget.charge(config.TRIAGE_MODEL, usage["input_tokens"], usage["output_tokens"])
    return resp, usage


class Spans:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.items = []

    def add(self, span: str, t_start: float, **kw):
        self.items.append({"span": span, "side": "host", "start_ms": round((t_start - self.t0) * 1000, 1),
                           "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                           "tokens_in": kw.pop("tokens_in", 0), "tokens_out": kw.pop("tokens_out", 0),
                           "cost_usd": round(kw.pop("cost_usd", 0.0), 7), **kw})


def _fnol_text(status: dict, notes: list[dict]) -> str:
    # the FNOL-INTAKE note repeats the Reported line; only adjuster notes are sent
    body = "\n".join(f"- {n['date']} {n['author']}: {redact(n['note'])[0]}" for n in notes
                     if n["author"] != "FNOL-INTAKE") or "- (no adjuster notes on file)"
    return (f"FNOL\nClaim: {status['claim_number']}\nPolicy: {status['policy_number']} ({status['policy_line']})\n"
            f"Date of loss: {status['date_of_loss']}\nReported: {status['loss_type_reported']}, claimed "
            f"${status['claimed_amount']:,}\nNotes (names, addresses and injuries redacted at intake):\n{body}")


async def triage(host: Host, claim_number: str, *, write: bool = True) -> dict:
    trace_id = "tr_" + uuid.uuid4().hex[:12]
    meta = {"trace_id": trace_id}
    sp = Spans()
    started = _now()
    wait0 = provider.rate_limit_wait_s()

    # 1. intake over MCP (claims-system)
    t = time.perf_counter()
    status_txt, err1 = await host.call("claims-system__get_claim_status", {"claim_number": claim_number}, meta)
    sp.add("mcp.claims-system.get_claim_status", t, error=status_txt if err1 else None)
    if err1:
        raise SystemExit(f"intake failed: {status_txt}")
    t = time.perf_counter()
    notes_txt, err2 = await host.call("claims-system__get_adjuster_notes", {"claim_number": claim_number}, meta)
    sp.add("mcp.claims-system.get_adjuster_notes", t, error=notes_txt if err2 else None)
    status = json.loads(status_txt)
    notes = [] if err2 else json.loads(notes_txt)["notes"]

    # 2. redact before the model sees it
    t = time.perf_counter()
    fnol = _fnol_text(status, notes)
    pii_hits = sorted({h for n in notes for h in redact(n["note"])[1]})
    sp.add("redact.intake", t, redaction=pii_hits)

    # 3. the agent loop
    tools = policies.SPECS + host.tools + [REFER]
    budget = Budget(max_iters=config.TRIAGE_MAX_ITERS, wall_clock_s=config.TRIAGE_WALL_CLOCK_S)
    messages = [{"role": "user", "content": fnol}]
    steps, referral, status_out, nudged = [], None, "ok", False
    try:
        while referral is None:
            t = time.perf_counter()
            try:
                resp, usage = _call(budget, messages, tools)
            except LLMTimeout:
                raise BudgetExceeded("wall_clock", f"request timed out at {budget.elapsed():.1f}s")
            sp.add("llm.generation", t, lap=budget.iters, model=config.TRIAGE_MODEL, tokens_in=usage["input_tokens"],
                   tokens_out=usage["output_tokens"],
                   cost_usd=price(config.TRIAGE_MODEL, usage["input_tokens"], usage["output_tokens"]))
            messages.append({"role": "assistant", "content": [agent_llm.to_param(b) for b in resp.content]})
            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:
                if nudged:
                    status_out = "no_referral"
                    break
                nudged = True
                messages.append({"role": "user", "content": NUDGE})
                continue
            results = []
            for c in calls:
                t = time.perf_counter()
                if c.name == REFER["name"]:
                    referral = dict(c.input)
                    out_text, is_err = json.dumps({"referred": True, "trace_id": trace_id}), False
                    span = "tool.refer_to_adjuster"
                elif c.name in policies.LOCAL:
                    try:
                        out_text, is_err = json.dumps(policies.LOCAL[c.name](**c.input)), False
                    except (TypeError, ValueError) as e:
                        out_text, is_err = f"error: {e}", True
                    span = f"tool.{c.name}"
                else:
                    out_text, is_err = await host.call(c.name, c.input, meta)
                    server, _, tool = c.name.partition("__")
                    span = f"mcp.{server}.{tool}"
                sp.add(span, t, lap=budget.iters, error=out_text[:300] if is_err else None)
                steps.append(_step(budget.iters, c.name, c.input, out_text, is_err))
                results.append({"type": "tool_result", "tool_use_id": c.id, "content": out_text,
                                **({"is_error": True} if is_err else {})})
            messages.append({"role": "user", "content": results})
    except BudgetExceeded as e:
        status_out = f"budget_exhausted:{e.which}"
    except DailyLimit:
        raise

    # 4-5. guard + citation check
    t = time.perf_counter()
    guarded, fired = guard(referral) if referral else (None, [])
    loss_date = status["date_of_loss"]
    cites = check_citations((guarded or {}).get("citations"), loss_date)
    sp.add("guard.decision_language+citation_check", t, fired=len(fired))

    rec = {
        "trace_id": trace_id, "ts": started, "triage_version": config.TRIAGE_VERSION,
        "date_filter": config.DATE_FILTER, "model": config.TRIAGE_MODEL, "prompt_sha": prompt_sha(),
        "reasoning_effort": config.LLM_REASONING_EFFORT, "temperature": 0,
        "claim_ref": hashlib.sha256(claim_number.encode()).hexdigest()[:12],
        "claim_number": claim_number, "policy_line": status["policy_line"], "loss_date": loss_date,
        "status": status_out, "fnol_redacted": fnol, "intake_redaction": pii_hits,
        "tools_offered": [x["name"] for x in tools], "mcp_discovered": [x["name"] for x in host.tools],
        "steps": steps, "referral_raw": referral, "referral": guarded, "guard_fired": fired, "citations": cites,
        "spans": sp.items,
        "totals": {"latency_ms": round((time.perf_counter() - sp.t0) * 1000, 1), "laps": budget.iters,
                   "tokens_in": budget.input_tokens, "tokens_out": budget.output_tokens,
                   "cost_usd": round(budget.cost_usd, 7),
                   "rate_limit_wait_ms": round((provider.rate_limit_wait_s() - wait0) * 1000, 1)},
    }
    rec["spans"] += server_spans(trace_id)
    rec["rendered"] = render(rec)
    rec, hits = redact_deep(rec)
    rec["redaction"] = {"when": "pre-write", "hits": hits}
    if write:
        config.W12_TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with config.W12_TRACE_FILE.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    return rec


def server_spans(trace_id: str) -> list[dict]:
    p = config.W12_MCP_SPAN_FILE
    if not p.exists():
        return []
    return [r for r in map(json.loads, p.read_text().splitlines()) if r.get("trace_id") == trace_id]


def _step(lap: int, name: str, args: dict, out_text: str, is_err: bool) -> dict:
    step = {"lap": lap, "tool": name, "args": args, "error": out_text[:300] if is_err else None}
    if name.endswith("search_policy") and not is_err:
        try:
            res = json.loads(out_text)["results"]
            step["returned"] = [f"{r['form_number']} | {r['clause'].split('/')[-1].strip()}" for r in res]
            step["chunk_ids"] = [r["chunk_id"] for r in res]
        except (ValueError, KeyError):
            pass
    if name.endswith("get_clause") and not is_err:
        step["returned"] = [out_text.split("\n", 1)[0]]
    return step


# --- CLI ------------------------------------------------------------------------------

def open_host() -> Host:
    import os

    os.environ.setdefault("W12_MCP_SPAN_FILE", str(config.W12_MCP_SPAN_FILE))
    os.environ.setdefault("TRIAGE_VERSION", config.TRIAGE_VERSION)
    return Host(config.CAPSTONE_MCP_CONFIG)


def span_table(rec: dict) -> str:
    rows = [f"{'span':<44} {'side':<6} {'latency_ms':>10} {'tok_in':>7} {'tok_out':>7} {'cost_usd':>10}"]
    for s in rec["spans"]:
        rows.append(f"{s['span']:<44} {s['side']:<6} {s['latency_ms']:>10} {s.get('tokens_in', 0):>7} "
                    f"{s.get('tokens_out', 0):>7} {s.get('cost_usd', 0):>10.7f}")
    t = rec["totals"]
    rows.append(f"{'TOTAL':<44} {'':<6} {t['latency_ms']:>10} {t['tokens_in']:>7} {t['tokens_out']:>7} {t['cost_usd']:>10.7f}")
    return "\n".join(rows)


async def _main(a) -> None:
    async with open_host() as host:
        if a.list_tools:
            from ..mcphost.agent import discovery_report
            print(discovery_report(host))
            print("local tools:", [s["name"] for s in policies.SPECS] + [REFER["name"]])
            return
        rec = await triage(host, a.claim)
        print(rec["rendered"])
        print()
        print(span_table(rec))
        print(f"\ntrace {rec['trace_id']} -> {config.W12_TRACE_FILE.relative_to(config.ROOT)}")
        if a.json:
            Path(a.json).write_text(json.dumps(rec, indent=2) + "\n")


def quiet() -> None:
    import logging
    import os

    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    for name in ("httpx", "mcp", "chromadb", "FastMCP"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> None:
    quiet()
    ap = argparse.ArgumentParser(prog="python -m app.triage")
    ap.add_argument("claim", nargs="?", help="claim number, e.g. CLM-2024-20001")
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--json", help="also write the full trace record here")
    a = ap.parse_args()
    if not a.claim and not a.list_tools:
        ap.error("give a claim number, or --list-tools")
    asyncio.run(_main(a))


if __name__ == "__main__":
    main()
