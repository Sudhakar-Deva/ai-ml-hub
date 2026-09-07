"""The inspection view — question, what was fetched, what was answered, in one
place, so a failure can be labelled instead of guessed at.

    python -m app.retrieval.inspect --retriever dense --markdown          # retrieval evidence
    python -m app.retrieval.inspect --retriever dense --answers --markdown  # + the answer pass

Labels, and the ONLY evidence that justifies each:

  R                — the gold chunk is not in the top-3. The model never saw it.
  G                — the gold chunk IS in the top-3 and the answer is still wrong.
                     No retrieval change fixes this one.
  Not-In-Corpus    — the gold chunk does not resolve in the store at all.

The distinction R vs G is the whole point of the week, so it is computed from
the retrieved list, never from whether the answer 'felt' wrong: a coverage
answer can be wrong with the E-17 row sitting at rank 1, and that is a G.
"""
import argparse
import json
from datetime import datetime, timezone

from .. import config
from .hitrate import load_golden_set
from .search import get_chunk, search

LABELS = ("R", "G", "Not-In-Corpus", "pass")


def answer_is_correct(text: str, q: dict) -> bool:
    """Cheap gate over the answer text, using the known answer's load-bearing
    tokens. It decides nothing on its own — every G in the write-up was read by
    a human first; this only stops a 12-question pass from being done by vibes."""
    low = text.lower()
    if not all(t.lower() in low for t in q.get("answer_must_contain", [])):
        return False
    return not any(t.lower() in low for t in q.get("answer_must_not_contain", []))


def inspect_one(
    q: dict,
    retriever: str = "dense",
    strategy: str = config.BASELINE_STRATEGY,
    k: int = config.EVAL_K,
    with_answer: bool = False,
) -> dict:
    hits = search(q["question"], strategy, k, retriever=retriever)
    gold_rank = next((h["rank"] for h in hits if h["chunk_id"] == q["gold_chunk_id"]), None)
    in_corpus = get_chunk(q["gold_chunk_id"], strategy) is not None

    generation = None
    if with_answer:
        from ..generation.answer import MissingAPIKey, answer

        try:
            # Same retriever, same k as the list above — the label is about what
            # the model was actually handed, so it must be the same context.
            # source="eval" keeps these out of the Week 5 traffic population: an
            # experiment run in a loop is not a week of adjuster questions, and
            # sampling the two together reports a frequency of nothing.
            generation = answer(q["question"], strategy, k, retriever, source="eval")
            generation["correct"] = answer_is_correct(generation["answer"], q)
        except MissingAPIKey as e:
            generation = {"error": str(e)}

    if not in_corpus:
        label = "Not-In-Corpus"
        evidence = (
            f"gold chunk {q['gold_chunk_id']} does not resolve in the `{strategy}` store — "
            "nothing was ever indexed that answers this."
        )
    elif gold_rank is None:
        slots = " / ".join(f"{h['form_number']} {h['clause']}" for h in hits)
        label = "R"
        evidence = (
            f"gold {q['gold_chunk_id']} absent from top-{k}; the {k} slots went to {slots}"
        )
    elif generation and "error" not in generation and not generation["correct"]:
        label = "G"
        evidence = (
            f"gold chunk sat at rank #{gold_rank} and the answer still reads: "
            f"{' '.join(generation['answer'].split())[:160]}…"
        )
    else:
        label = "pass"
        evidence = f"gold chunk retrieved at rank #{gold_rank}"

    return {
        "id": q["id"],
        "question": q["question"],
        "retriever": retriever,
        "exact_token": q.get("exact_token", False),
        "gold_chunk_id": q["gold_chunk_id"],
        "gold_clause": q.get("clause", ""),
        "gold_in_corpus": in_corpus,
        "gold_rank": gold_rank,
        "hit": gold_rank is not None,
        "label": label,
        "evidence": evidence,
        "top_k": [
            {
                "rank": h["rank"],
                "chunk_id": h["chunk_id"],
                "score": h["score"],
                "score_kind": h.get("score_kind", "cosine"),
                "dense_rank": h.get("dense_rank"),
                "bm25_rank": h.get("bm25_rank"),
                "form_number": h["form_number"],
                "edition_date": h["edition_date"],
                "clause": h["clause"],
                "is_gold": h["chunk_id"] == q["gold_chunk_id"],
                "snippet": " ".join(h["text"].split())[:280],
            }
            for h in hits
        ],
        "generation": generation,
    }


def inspect_all(
    retriever: str = "dense",
    strategy: str = config.BASELINE_STRATEGY,
    k: int = config.EVAL_K,
    with_answer: bool = False,
) -> dict:
    rows = [inspect_one(q, retriever, strategy, k, with_answer) for q in load_golden_set()]
    tally = {label: sum(r["label"] == label for r in rows) for label in LABELS}
    return {
        "retriever": retriever,
        "strategy": strategy,
        "k": k,
        "answers_generated": with_answer,
        "tally": tally,
        "rows": rows,
    }


def markdown_tally(report: dict) -> str:
    t = report["tally"]
    failures = [r for r in report["rows"] if r["label"] != "pass"]
    lines = [
        f"**Tally — `{report['retriever']}`, top-{report['k']}:** "
        f"R = {t['R']} · G = {t['G']} · Not-In-Corpus = {t['Not-In-Corpus']} · "
        f"passed = {t['pass']} (of {len(report['rows'])})",
        "",
        "| # | Question | Label | Evidence (one line, from the inspection view) |",
        "| - | -------- | ----- | --------------------------------------------- |",
    ]
    for r in failures:
        q = r["question"][:70] + ("…" if len(r["question"]) > 70 else "")
        lines.append(f"| {r['id']} | {q} | **{r['label']}** | {r['evidence']} |")
    if not failures:
        lines.append("| — | — | — | no failures |")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", choices=list(config.RETRIEVERS), default="dense")
    ap.add_argument("--strategy", choices=config.STRATEGIES, default=config.BASELINE_STRATEGY)
    ap.add_argument("--k", type=int, default=config.EVAL_K)
    ap.add_argument("--answers", action="store_true", help="run the LLM pass so G is decidable")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()

    report = inspect_all(a.retriever, a.strategy, a.k, a.answers)

    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = config.RUNS_DIR / f"labels_{a.retriever}_{stamp}.json"
    path.write_text(json.dumps(report, indent=2))
    config.LABELS_FILE.write_text(json.dumps(report, indent=2))
    print(f"{report['tally']}  ->  {path.relative_to(config.ROOT)}")

    if a.markdown:
        md = markdown_tally(report)
        (config.RUNS_DIR / f"labels_{a.retriever}_{stamp}.md").write_text(md)
        print("\n" + md)
