import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.loader import load_document  # noqa: E402

HEADER = """HO-0304 ed. 03-24
Policy_line: homeowners
Effective: 2024-03-01

SECTION I — EXCLUSIONS
body text
"""


def test_metadata_parsed_from_header(tmp_path):
    p = tmp_path / "HO-0304-ed-03-24.txt"
    p.write_text(HEADER)
    doc = load_document(p)
    assert doc.form_number == "HO-0304"
    assert doc.edition_date == "03-24"
    assert doc.policy_line == "homeowners"
    assert doc.source_file == "HO-0304-ed-03-24.txt"


def test_falls_back_to_filename_when_header_is_bare(tmp_path):
    p = tmp_path / "HO-0517-ed-06-24.txt"
    p.write_text("some endorsement text with no header at all")
    doc = load_document(p)
    assert doc.form_number == "HO-0517"
    assert doc.edition_date == "06-24"
