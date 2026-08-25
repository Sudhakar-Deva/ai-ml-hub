"""Strategy B — splits on form/clause headers and never separates an exclusion
row from its table header or its form number.

Every chunk is stamped with [form_number ed. edition | policy_line | source_file]
so the scoping survives retrieval even when only one table row comes back.
"""
import re

from ..ingestion.loader import Document
from .common import pack

STRATEGY = "structure_aware"

# A form/clause header: "SECTION I — EXCLUSIONS", "3.1 Water Damage", "A. Definitions"
HEADER_RE = re.compile(
    r"^(?:"
    r"(?:SECTION\s+[IVX0-9]+.*)"
    r"|(?:[A-Z][A-Z \-&/']{4,}\s*)"
    r"|(?:\d+(?:\.\d+)*\.?\s+\S.*)"
    r"|(?:[A-Z]\.\s+\S.*)"
    r")$",
    re.M,
)
EXCLUSION_ROW_RE = re.compile(r"^\s*\|?\s*(E-\d{1,3})\b", re.I)
TABLE_LINE_RE = re.compile(r"^\s*\|.*\|\s*$")


def _split_on_headers(text: str) -> list[tuple[str, str]]:
    """-> [(clause_heading, body_including_heading), ...]"""
    marks = [(m.start(), m.group().strip()) for m in HEADER_RE.finditer(text)]
    if not marks:
        return [("document", text)]
    if marks[0][0] > 0:
        marks.insert(0, (0, "preamble"))
    sections = []
    for i, (pos, heading) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[pos:end]
        if body.strip():
            sections.append((heading, body))
    return sections


def _table_header(lines: list[str], row_idx: int) -> str:
    """Nearest preceding table header line(s) above an exclusion row.

    Without this the row reads 'E-17 | excluded' with nothing saying what the
    columns mean — precise retrieval, useless context.
    """
    header = []
    for j in range(row_idx - 1, max(-1, row_idx - 6), -1):
        line = lines[j]
        if not line.strip():
            break
        header.insert(0, line)
        if not (TABLE_LINE_RE.match(line) or "---" in line):
            break
    return "\n".join(header)


def _soft_split(body: str, max_chars: int) -> list[str]:
    if len(body) <= max_chars:
        return [body]
    pieces, current = [], ""
    for para in body.split("\n\n"):
        if len(current) + len(para) > max_chars and current:
            pieces.append(current)
            current = ""
        current += para + "\n\n"
    if current.strip():
        pieces.append(current)
    return pieces


def chunk(doc: Document, max_chars: int = 1800) -> list[dict]:
    out, idx = [], 0
    stamp = f"[{doc.form_number} ed. {doc.edition_date} | {doc.policy_line} | {doc.source_file}]"

    for heading, body in _split_on_headers(doc.text):
        lines = body.splitlines()
        rows = [i for i, ln in enumerate(lines) if EXCLUSION_ROW_RE.match(ln)]

        if rows:
            # One chunk per exclusion row, each carrying form number + the table
            # header it sits under.
            for i in rows:
                code = EXCLUSION_ROW_RE.match(lines[i]).group(1).upper()
                text = "\n".join(
                    filter(None, [stamp, heading, _table_header(lines, i), lines[i]])
                )
                c = pack(doc, STRATEGY, idx, text, clause=f"{heading} / {code}")
                c["metadata"]["exclusion_code"] = code
                out.append(c)
                idx += 1

            # Plus the section's surrounding prose, so the scoping language is
            # still retrievable on its own.
            row_set = set(rows)
            prose = "\n".join(ln for i, ln in enumerate(lines) if i not in row_set)
            if len(prose.strip()) > 80:
                out.append(pack(doc, STRATEGY, idx, f"{stamp}\n{prose}", clause=heading))
                idx += 1
            continue

        for piece in _soft_split(body, max_chars):
            out.append(pack(doc, STRATEGY, idx, f"{stamp}\n{piece}", clause=heading))
            idx += 1

    return out
