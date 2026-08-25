"""Chroma-backed store. One collection per chunking strategy so both live side
by side and the same 8 questions can hit each."""
import chromadb
from chromadb.utils import embedding_functions

from .. import config

_client = None
_embedder = None


def client():
    global _client
    if _client is None:
        config.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(config.VECTOR_DB_PATH))
    return _client


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=config.EMBEDDING_MODEL
        )
    return _embedder


def get_collection(strategy: str, reset: bool = False):
    name = config.collection_name(strategy)
    c = client()
    if reset:
        try:
            c.delete_collection(name)
        except Exception:
            pass
    return c.get_or_create_collection(
        name=name,
        embedding_function=embedder(),
        metadata={"hnsw:space": "cosine", "embed_model": config.EMBEDDING_MODEL},
    )
