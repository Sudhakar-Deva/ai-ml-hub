from fastapi import APIRouter, HTTPException

from .. import config
from ..models.schemas import AskRequest, SearchRequest
from ..retrieval.evaluate import evaluate, load_eval_set
from ..retrieval.search import get_chunk, search

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {
        "ok": True,
        "strategies": list(config.STRATEGIES),
        "embed_model": config.EMBEDDING_MODEL,
        "gen_model": config.LLM_MODEL,
    }


@router.post("/search")
def api_search(req: SearchRequest):
    """Search-only — powers the unfiltered vs filtered side-by-side."""
    return {
        "results": search(req.query, req.strategy, req.k, req.policy_line, req.form_number)
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
        return answer(req.question, req.strategy)
    except MissingAPIKey as e:
        raise HTTPException(503, str(e)) from e


@router.get("/evaluate")
def api_evaluate():
    questions, expected = load_eval_set()
    return {s: evaluate(s, questions, expected) for s in config.STRATEGIES}
