"""Grounded generation with a FORCED refusal.

The grounding prompt must never say "use your best judgement" — an invented
coverage answer read out to a policyholder is a bad-faith exposure. Refusal is
the default; answering is the exception that requires a resolvable citation.
"""
import argparse
import json
import re

import anthropic

from .. import config
from ..retrieval.search import get_chunk, search

REFUSAL_SENTINEL = "INSUFFICIENT_CONTEXT"
CITATION_RE = re.compile(r"\[([^\]|]+)\s*\|\s*([^\]|]+)\s*\|\s*([^\]]+)\]")


class MissingAPIKey(RuntimeError):
    """Raised instead of a bare KeyError so the API can answer 503, not 500."""

SYSTEM = f"""You are a claims-assistant answering questions about homeowners policy
endorsements. You answer ONLY from the numbered context chunks provided.

Hard rules — these are not preferences:
1. Every factual claim MUST end with a citation in the exact form
   [chunk_id | form_number | clause]. Copy those values verbatim from the chunk
   header; never construct, abbreviate, or guess one.
2. If the context does not contain the answer, reply with exactly this and nothing
   else: {REFUSAL_SENTINEL}: <one sentence naming what is missing and where it would live>.
3. You may not use general insurance knowledge, prior training, inference from
   similar clauses, or judgement to fill a gap. Absence of a clause in the context
   is not evidence about that clause; it means you cannot answer.
4. Partially answerable is not answerable. If any part of the claim is unsupported,
   refuse rather than hedge.
"""

PROMPT = """Context chunks:

{context}

---
Question: {question}

Answer using only the chunks above, citing each claim. If the chunks do not
contain the answer, output the {sentinel} line."""


def _format_context(hits: list[dict]) -> str:
    return "\n\n".join(
        f"[{h['chunk_id']} | {h['form_number']} ed. {h['edition_date']} | {h['clause']}]\n{h['text']}"
        for h in hits
    )


def answer(question: str, strategy: str = "structure_aware", k: int = config.TOP_K) -> dict:
    hits = search(question, strategy, k)
    if not config.LLM_API_KEY:
        raise MissingAPIKey("LLM_API_KEY is not set — copy .env.example to .env and fill it in.")
    client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    msg = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=1024,
        temperature=0,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": PROMPT.format(
                    context=_format_context(hits),
                    question=question,
                    sentinel=REFUSAL_SENTINEL,
                ),
            }
        ],
    )
    text = msg.content[0].text.strip()

    # Verify every citation resolves to a real chunk — an unresolvable citation
    # is a fabrication and fails the same as a wrong answer.
    citations = []
    for cid, form, clause in CITATION_RE.findall(text):
        chunk = get_chunk(cid.strip(), strategy)
        citations.append(
            {
                "chunk_id": cid.strip(),
                "form_number": form.strip(),
                "clause": clause.strip(),
                "resolves": chunk is not None,
                "chunk_text": chunk["text"] if chunk else None,
            }
        )

    return {
        "question": question,
        "strategy": strategy,
        "answer": text,
        "refused": text.startswith(REFUSAL_SENTINEL),
        "citations": citations,
        "unresolvable_citations": [c["chunk_id"] for c in citations if not c["resolves"]],
        "retrieved": [{k_: h[k_] for k_ in ("rank", "chunk_id", "score")} for h in hits],
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--strategy", choices=config.STRATEGIES, default="structure_aware")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    try:
        result = answer(a.question, a.strategy)
    except MissingAPIKey as e:
        raise SystemExit(str(e)) from e
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Q: {result['question']}\n")
        print(result["answer"])
        print(f"\nrefused={result['refused']}  citations={len(result['citations'])}", end="")
        print(
            f"  !! UNRESOLVABLE: {result['unresolvable_citations']}"
            if result["unresolvable_citations"]
            else "  (all resolve)"
        )
