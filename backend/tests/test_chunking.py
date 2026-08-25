"""The one invariant the structure-aware chunker exists to hold:
an exclusion row is never separated from its table header or its form number.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chunking import current_chunker, structure_aware_chunker  # noqa: E402
from app.ingestion.loader import Document  # noqa: E402
from app.models.schemas import REQUIRED_METADATA  # noqa: E402

SAMPLE = Document(
    source_file="HO-0304-ed-03-24.txt",
    form_number="HO-0304",
    policy_line="homeowners",
    edition_date="03-24",
    text="""HO-0304 ed. 03-24
Policy_line: homeowners

SECTION I — EXCLUSIONS

We do not cover loss caused by any of the following, whether or not any other
cause contributed concurrently or in any sequence.

| Code | Peril | Applies |
| ---- | ----- | ------- |
| E-16 | Flood of surface water | Excluded |
| E-17 | Water damage from a burst supply line | Covered if sudden and accidental |
| E-18 | Continuous seepage over 14 days | Excluded |

A. DEFINITIONS

"Sudden and accidental" means an event that is both abrupt in onset and
unforeseen by the insured.
""",
)


@pytest.mark.parametrize("mod", [current_chunker, structure_aware_chunker])
def test_every_chunk_carries_required_metadata(mod):
    """A chunk with no source_file is a failed ingest — both chunkers must comply."""
    for c in mod.chunk(SAMPLE):
        for field in REQUIRED_METADATA:
            assert c["metadata"].get(field), f"{mod.STRATEGY} chunk missing {field}"


def test_exclusion_row_keeps_its_table_header_and_form_number():
    chunks = structure_aware_chunker.chunk(SAMPLE)
    e17 = [c for c in chunks if c["metadata"].get("exclusion_code") == "E-17"]
    assert len(e17) == 1, "E-17 should produce exactly one dedicated chunk"

    text = e17[0]["text"]
    assert "E-17" in text
    assert "burst supply line" in text
    assert "HO-0304" in text, "form number must travel with the row"
    assert "Peril" in text, "table header must travel with the row"


def test_chunk_ids_are_unique_and_stable():
    chunks = structure_aware_chunker.chunk(SAMPLE)
    ids = [c["metadata"]["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    assert ids == [c["metadata"]["chunk_id"] for c in structure_aware_chunker.chunk(SAMPLE)]


def test_current_chunker_is_structure_blind():
    """Guard the control: if this starts preserving structure, the comparison
    is no longer measuring anything."""
    chunks = current_chunker.chunk(SAMPLE, size=200, overlap=20)
    assert all(c["metadata"]["clause"] == "n/a" for c in chunks)
    assert not any(c["metadata"].get("exclusion_code") for c in chunks)
