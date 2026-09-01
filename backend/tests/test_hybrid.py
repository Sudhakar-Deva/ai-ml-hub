"""The two invariants Week 4's one change rests on:

1. RRF fuses RANKS. Feeding it scores from two different scales is the mistake
   that makes a hybrid retriever quietly become whichever arm has bigger numbers.
2. The lexical arm keeps an exclusion code whole. A tokenizer that splits E-17
   into ('e', '17') gives back exactly the dense failure BM25 was added to fix.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.retrieval.hybrid import rrf_fuse  # noqa: E402
from app.retrieval.lexical import tokenize  # noqa: E402


def test_tokenizer_keeps_codes_and_form_numbers_whole():
    tokens = tokenize("Does E-17 apply under HO-0304 ed. 03-24?")
    assert "e-17" in tokens
    assert "ho-0304" in tokens
    assert "03-24" in tokens


def test_tokenizer_also_indexes_the_parts():
    # so 'HO 0304' typed without the hyphen still reaches the same chunk
    tokens = tokenize("HO-0304")
    assert "ho" in tokens and "0304" in tokens


def test_rrf_uses_rank_not_score():
    # Arm A ranks x first; arm B ranks y first but would swamp any score-based
    # fusion if its raw magnitudes were added in. Rank is all RRF sees.
    fused = dict(rrf_fuse([["x", "y"], ["y", "x"]], k=60))
    assert fused["x"] == fused["y"]


def test_rrf_rewards_agreement_between_arms():
    fused = rrf_fuse([["a", "b", "c"], ["a", "c", "b"]], k=60)
    assert fused[0][0] == "a"


def test_rrf_promotes_a_chunk_only_one_arm_found():
    # The E-17 case: dense never returns it, BM25 has it at #1. It must still
    # outrank a chunk both arms put near the bottom.
    dense = ["prose1", "prose2", "prose3", "prose4"]
    bm25 = ["e17row", "prose4"]
    fused = dict(rrf_fuse([dense, bm25], k=60))
    assert fused["e17row"] > fused["prose3"]


def test_rrf_k_damps_a_single_arms_top_hit():
    # With k=60 one arm's #1 (1/61) loses to both arms agreeing at #2
    # (1/62 + 1/62). That damping is what k is for.
    fused = dict(rrf_fuse([["solo", "both"], ["other", "both"]], k=60))
    assert fused["both"] > fused["solo"]
