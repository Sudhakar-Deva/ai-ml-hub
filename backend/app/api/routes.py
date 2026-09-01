from fastapi import APIRouter, HTTPException

from .. import config
from ..models.schemas import AskRequest, InspectRequest, SearchRequest
from ..retrieval.evaluate import evaluate, load_eval_set
from ..retrieval.hitrate import load_golden_set, run
from ..retrieval.inspect import inspect_all
from ..retrieval.search import get_chunk, search

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {
        "ok": True,
        "strategies": list(config.STRATEGIES),
        "retrievers": list(config.RETRIEVERS),
        "embed_model": config.EMBEDDING_MODEL,
        "gen_model": config.LLM_MODEL,
        "has_llm_key": bool(config.LLM_API_KEY),
    }


@router.post("/search")
def api_search(req: SearchRequest):
    """Search-only — powers the unfiltered vs filtered side-by-side."""
    return {
        "results": search(
            req.query, req.strategy, req.k, req.policy_line, req.form_number, req.retriever
        )
    }


@router.get("/chunk/{strategy}/{chunk_id:path}")
def api_chunk(strategy: str, chunk_id: str):
    """Makes a citation clickable — resolves chunk_id back to its text."""
    chunk = get_chunk(chunk_id, strategy)
    if chunk is None:
        raise HTTPException(404, f"no chunk {chunk_id} in {strategy}")
    return chunk


@router.post("/ask")
def api_ask(req: AskRequest):
    from ..generation.answer import MissingAPIKey, answer  # lazy: search needs no key

    try:
        return answer(req.question, req.strategy, config.TOP_K, req.retriever)
    except MissingAPIKey as e:
        raise HTTPException(503, str(e)) from e


@router.get("/evaluate")
def api_evaluate():
    """Week 3's bench: hit-in-top-5, both chunkers. Left exactly as it was."""
    questions, expected = load_eval_set()
    return {s: evaluate(s, questions, expected) for s in config.STRATEGIES}


@router.get("/golden-set")
def api_golden_set():
    return {"questions": load_golden_set()}


@router.post("/inspect")
def api_inspect(req: InspectRequest):
    """The inspection view: per golden question — what was fetched, whether the
    gold chunk was in it, what was answered, and the R/G/Not-In-Corpus label."""
    return inspect_all(req.retriever, req.strategy, req.k, req.answers)


@router.get("/hitrate")
def api_hitrate(retrievers: str = "dense,hybrid", k: int = config.EVAL_K):
    """hit-rate@k + p50 latency per retriever, over the same 12 questions."""
    questions = load_golden_set()
    names = [r.strip() for r in retrievers.split(",") if r.strip()]
    bad = [r for r in names if r not in config.RETRIEVERS]
    if bad:
        raise HTTPException(400, f"unknown retriever(s) {bad}; expected {list(config.RETRIEVERS)}")
    return {r: run(r, questions, k=k) for r in names}
