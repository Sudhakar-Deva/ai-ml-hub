"""The deliverable: two hit-in-top-5 numbers over the SAME 8 questions, with a
per-question record — not a summary claim.

    python -m app.retrieval.evaluate --markdown

Writes a full search-only dump per strategy into evals/search-dumps/.
A question is a HIT when any chunk in the top-5 carries the expected
form_number AND satisfies the expected clause marker — metadata, not eyeballing.
"""
import argparse
import json
from datetime import datetime, timezone

from .. import config
from .search import search


def load_eval_set() -> tuple[list[dict], dict]:
    questions = json.loads(config.QUESTIONS_FILE.read_text())["questions"]
    expected = json.loads(config.EXPECTED_FILE.read_text())["expected"]
    if len(questions) != 8:
        raise SystemExit(f"Need exactly 8 questions, found {len(questions)}")
    missing = [q["id"] for q in questions if q["id"] not in expected]
    if missing:
        raise SystemExit(f"No expected answer recorded for: {missing}")
    return questions, expected


def is_hit(exp: dict, hit: dict) -> bool:
    if hit["form_number"] != exp["form_number"]:
        return False
    marker = str(exp.get("clause_contains", "")).lower()
    if not marker:
        return True
    return marker in f"{hit['clause']} {hit['text']}".lower()


def evaluate(strategy: str, questions: list[dict], expected: dict) -> dict:
    records = []
    for q in questions:
        exp = expected[q["id"]]
        hits = search(q["question"], strategy, k=config.TOP_K)
        ranks = [h["rank"] for h in hits if is_hit(exp, h)]
        records.append(
            {
                "id": q["id"],
                "question": q["question"],
                "expected": exp,
                "hit": bool(ranks),
                "hit_rank": ranks[0] if ranks else None,
                "top5": [
                    {
                        "rank": h["rank"],
                        "score": h["score"],
                        "form_number": h["form_number"],
                        "clause": h["clause"],
                        "chunk_id": h["chunk_id"],
                        "snippet": " ".join(h["text"].split())[:240],
                    }
                    for h in hits
                ],
            }
        )
    return {
        "strategy": strategy,
        "embed_model": config.EMBEDDING_MODEL,
        "k": config.TOP_K,
        "hits": sum(r["hit"] for r in records),
        "total": len(records),
        "records": records,
    }


def markdown_table(results: dict[str, dict]) -> str:
    strategies = list(results)
    head = results[strategies[0]]["records"]
    lines = [
        "| # | Question | Expected form · clause | " + " | ".join(strategies) + " |",
        "| - | -------- | ---------------------- | " + " | ".join("---" for _ in strategies) + " |",
    ]
    for i, rec in enumerate(head):
        cells = []
        for s in strategies:
            r = results[s]["records"][i]
            cells.append(f"✅ #{r['hit_rank']}" if r["hit"] else "❌ miss")
        exp = rec["expected"]
        lines.append(
            f"| {rec['id']} | {rec['question']} | `{exp['form_number']}` · "
            f"{exp.get('clause_contains', '—')} | " + " | ".join(cells) + " |"
        )
    lines += ["", "| Strategy | hit-in-top-5 |", "| -------- | ------------ |"]
    for s in strategies:
        lines.append(f"| `{s}` | **{results[s]['hits']}/{results[s]['total']}** |")
    lines += ["", f"_Same 8 questions, same embedding model (`{config.EMBEDDING_MODEL}`), k={config.TOP_K}._"]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", nargs="+", default=list(config.STRATEGIES))
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()

    questions, expected = load_eval_set()
    results = {s: evaluate(s, questions, expected) for s in a.strategies}

    config.DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for s, r in results.items():
        path = config.DUMPS_DIR / f"{s}_{stamp}.json"
        path.write_text(json.dumps(r, indent=2))
        print(f"{s}: {r['hits']}/{r['total']}  ->  {path.relative_to(config.ROOT)}")

    if a.markdown:
        md = markdown_table(results)
        (config.DUMPS_DIR / f"hit_table_{stamp}.md").write_text(md)
        print("\n" + md)
