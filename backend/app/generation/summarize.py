"""Write a claim summary from adjuster notes — the thing Week 6 measures.

    python -m app.generation.summarize --notes-file notes.txt
    python -m app.generation.summarize --case w6-004 --json

This is a SECOND generation path, not a change to Week 5's answer(). The Q&A
prompt keeps its own version so every Week 5 trace stays replayable; this one
carries `claims-summary-v1`.

The output is labelled lines followed by prose. That shape exists so the four
mechanical facts a claims file must carry — claim number, date of loss,
deductible, and the exclusion code behind any denial — land somewhere a regex
can check them. It is deliberately NOT a JSON schema the model is forced into:
a model that cannot find the date of loss must be able to leave the line wrong,
or the assertion measures the parser rather than the app.
"""
import argparse
import json
import re
import time


from .. import config
from ..llm import complete
from ..retrieval.search import get_chunk, search
from ..tracing import trace as tracing

CITATION_RE = re.compile(r"\[([^\]|]+)\s*\|\s*([^\]|]+)\s*\|\s*([^\]]+)\]")

SYSTEM = """You are a claims assistant. You read an adjuster's raw notes on a
homeowners, dwelling-fire or condominium claim and write the claim summary that
goes on the file.

You answer ONLY from the numbered policy context supplied with the notes, plus
the facts stated in the notes themselves. You may not use general insurance
knowledge, another carrier's wording, or a similar clause from a different form.

Write the summary in exactly this shape:

CLAIM: <the claim number, copied from the notes>
DATE OF LOSS: <the date of loss, as YYYY-MM-DD>
POLICY LINE: <homeowners | dwelling_fire | condo>
GOVERNING FORM: <form number and edition, e.g. HO-0304 ed. 03-24>
COVERAGE POSITION: <COVERED | DENIED | PARTIAL | UNDETERMINED>
DEDUCTIBLE: <the dollar amount applied to this loss>
EXCLUSIONS APPLIED: <exclusion codes relied on, e.g. E-19; or NONE>
SUMMARY: <two to four sentences. Every statement about what the policy says
ends with a citation in the exact form [chunk_id | form_number | clause],
copied verbatim from the chunk header.>

Rules that are not preferences:
1. The policy line in the notes decides which form governs. A homeowners claim
   is not adjusted on dwelling-fire wording and a condo claim is not adjusted on
   either, even where the two forms share an exclusion code.
2. If the context does not settle the coverage position, write UNDETERMINED and
   say in the summary what wording you would need. Do not guess a position.
3. A denial requires the exclusion code that produces it. "Not covered" with no
   code is not a claim decision.
4. Never invent a chunk_id, a form number, a clause, an amount or a date.
"""

PROMPT = """Policy context chunks:

{context}

---
Adjuster notes:

{notes}

---
Write the claim summary in the required shape, from the context and the notes only."""


def _format_context(hits: list[dict]) -> str:
    return "\n\n".join(
        f"[{h['chunk_id']} | {h['form_number']} ed. {h['edition_date']} | {h['clause']}]\n{h['text']}"
        for h in hits
    )


def summarize(
    notes: str,
    strategy: str = "structure_aware",
    k: int = config.TOP_K,
    retriever: str = config.SHIPPED_RETRIEVER,
    trace: bool = True,
    source: str = "summary",
    case_id: str | None = None,
) -> dict:
    """Notes in, claim summary out. The retrieval query is the notes themselves —
    the app does not get told which form governs, because in production nobody
    tells it either. That is where half of Week 5's failure modes live."""
    from .answer import MissingAPIKey

    hits = search(notes, strategy, k, retriever=retriever)
    if not config.LLM_API_KEY:
        raise MissingAPIKey("LLM_API_KEY is not set — copy .env.example to .env and fill it in.")

    rendered_prompt = PROMPT.format(context=_format_context(hits), notes=notes)
    params = {"temperature": 0, "max_tokens": 1024}

    t0 = time.perf_counter()
    text, _ = complete(model=config.LLM_MODEL, system=SYSTEM, user=rendered_prompt, params=params)
    latency_ms = (time.perf_counter() - t0) * 1000

    citations = []
    for cid, form, clause in CITATION_RE.findall(text):
        chunk = get_chunk(cid.strip(), strategy)
        citations.append(
            {
                "chunk_id": cid.strip(),
                "form_number": form.strip(),
                "clause": clause.strip(),
                "resolves": chunk is not None,
            }
        )

    record = None
    if trace:
        t = tracing.build_trace(
            question=notes,
            output=text,
            system_prompt=SYSTEM,
            rendered_prompt=rendered_prompt,
            retrieved=hits,
            model=config.LLM_MODEL,
            params=params,
            strategy=strategy,
            retriever=retriever,
            k=k,
            latency_ms=latency_ms,
            refused=None,
            citations=citations,
            source=source,
        )
        # Overwrite the version the Q&A path stamps: this is a different prompt
        # and a trace that names the wrong one cannot be replayed honestly.
        t["prompt_version"] = config.SUMMARY_PROMPT_VERSION
        t["case_id"] = case_id
        record = tracing.write(t)

    return {
        "case_id": case_id,
        "notes": notes,
        "strategy": strategy,
        "retriever": retriever,
        "k": k,
        "summary": text,
        "citations": citations,
        "unresolvable_citations": [c["chunk_id"] for c in citations if not c["resolves"]],
        "retrieved": [
            {kk: h[kk] for kk in ("rank", "chunk_id", "score", "form_number", "policy_line")}
            for h in hits
        ],
        "latency_ms": round(latency_ms, 1),
        "trace_id": record["trace_id"] if record else None,
    }


# --- reading the labelled lines back out -------------------------------------
# Parsing is separate from generating on purpose: the assertions in
# app.evals.assertions run on THIS, and a parser that silently repairs a missing
# line would hand every assertion a pass it did not earn.

FIELDS = (
    "CLAIM", "DATE OF LOSS", "POLICY LINE", "GOVERNING FORM",
    "COVERAGE POSITION", "DEDUCTIBLE", "EXCLUSIONS APPLIED", "SUMMARY",
)


def parse(summary: str) -> dict:
    """-> {field: raw value or None}. Missing means missing; nothing is guessed."""
    out = {f: None for f in FIELDS}
    current = None
    for line in summary.splitlines():
        m = re.match(r"^\s*([A-Z][A-Z ]+?)\s*:\s*(.*)$", line)
        if m and m.group(1).strip() in FIELDS:
            current = m.group(1).strip()
            out[current] = m.group(2).strip()
        elif current == "SUMMARY" and line.strip():
            out["SUMMARY"] = f"{out['SUMMARY']} {line.strip()}".strip()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", help="adjuster notes as a string")
    ap.add_argument("--notes-file")
    ap.add_argument("--case", help="a case id from evals/w6/eval_set.jsonl")
    ap.add_argument("--strategy", choices=config.STRATEGIES, default="structure_aware")
    ap.add_argument("--retriever", choices=config.RETRIEVERS, default=config.SHIPPED_RETRIEVER)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-trace", dest="trace", action="store_false")
    a = ap.parse_args()

    if a.case:
        from ..evals.cases import by_id as case_by_id

        case = case_by_id(a.case)
        notes, cid = case["notes"], case["id"]
    elif a.notes_file:
        from pathlib import Path

        notes, cid = Path(a.notes_file).read_text(), None
    elif a.notes:
        notes, cid = a.notes, None
    else:
        raise SystemExit("give --notes, --notes-file or --case")

    r = summarize(notes, a.strategy, config.TOP_K, a.retriever, trace=a.trace, case_id=cid)
    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(r["summary"])
        print(f"\ntrace_id={r['trace_id']}  citations={len(r['citations'])}", end="")
        print(
            f"  !! UNRESOLVABLE: {r['unresolvable_citations']}"
            if r["unresolvable_citations"] else "  (all resolve)"
        )
