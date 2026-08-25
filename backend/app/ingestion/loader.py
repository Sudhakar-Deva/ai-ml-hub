"""Read endorsement files and pull the four required metadata fields off the header."""
import re
from dataclasses import dataclass
from pathlib import Path

FORM_RE = re.compile(r"\b(HO-\d{4}|[A-Z]{2,3}-\d{3,4})\b")
EDITION_RE = re.compile(r"\bed\.?\s*[-]?\s*(\d{2}-\d{2})\b", re.I)
POLICY_LINE_RE = re.compile(r"^\s*policy[_ ]line\s*[:\-]\s*(.+)$", re.I | re.M)
EFFECTIVE_RE = re.compile(r"^\s*effective(?:\s+date)?\s*[:\-]\s*(.+)$", re.I | re.M)


@dataclass
class Document:
    source_file: str
    form_number: str
    policy_line: str
    edition_date: str
    text: str

    def metadata(self) -> dict:
        return {
            "source_file": self.source_file,
            "form_number": self.form_number,
            "policy_line": self.policy_line,
            "edition_date": self.edition_date,
        }


def _read(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def _guess_policy_line(text: str, filename: str) -> str:
    m = POLICY_LINE_RE.search(text)
    if m:
        return m.group(1).strip().lower()
    haystack = f"{filename} {text[:2000]}".lower()
    for needle, label in (
        ("homeowner", "homeowners"),
        ("ho-", "homeowners"),
        ("dwelling", "dwelling_fire"),
        ("renter", "renters"),
        ("condo", "condo"),
        ("auto", "auto"),
        ("umbrella", "umbrella"),
    ):
        if needle in haystack:
            return label
    return "unknown"


def load_document(path: Path) -> Document:
    text = _read(path)
    head = text[:1500]  # form number + edition live in the header
    form = FORM_RE.search(head) or FORM_RE.search(path.name)
    edition = EDITION_RE.search(head) or EDITION_RE.search(path.name)
    effective = EFFECTIVE_RE.search(head)
    return Document(
        source_file=path.name,
        form_number=form.group(1) if form else "UNKNOWN",
        policy_line=_guess_policy_line(text, path.name),
        edition_date=(
            edition.group(1)
            if edition
            else (effective.group(1).strip() if effective else "UNKNOWN")
        ),
        text=text,
    )


def load_all(docs_dir: Path) -> list[Document]:
    # README.md documents the corpus, it is not part of it — indexing it would
    # put a form number that never appears in a real endorsement into the store.
    paths = sorted(
        p
        for p in docs_dir.iterdir()
        if p.suffix.lower() in {".txt", ".md", ".pdf"}
        and not p.name.startswith(".")
        and p.stem.lower() != "readme"
    )
    if not paths:
        raise SystemExit(f"No endorsement files in {docs_dir} — drop the 6 supplied files there.")
    return [load_document(p) for p in paths]
