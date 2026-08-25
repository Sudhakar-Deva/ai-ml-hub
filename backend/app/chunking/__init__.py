from . import current_chunker, structure_aware_chunker

CHUNKERS = {
    current_chunker.STRATEGY: current_chunker.chunk,
    structure_aware_chunker.STRATEGY: structure_aware_chunker.chunk,
}

__all__ = ["CHUNKERS", "current_chunker", "structure_aware_chunker"]
