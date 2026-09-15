"""Redaction, applied on the way INTO the trace file.

The ordering is the whole point and it is not a style preference: a trace file
that is scrubbed after the fact has already existed on disk unscrubbed, has
already been in a backup, and has already been readable by anyone with the box.
`redact()` runs inside the writer, before serialisation — see trace.py, where it
is not possible to reach the file handle without passing through here.

What this deliberately does NOT touch: form numbers, edition dates and exclusion
codes. `HO-0304`, `ed. 03-24`, `E-17` and `DP-0110` are the corpus vocabulary. A
redactor that eats them produces a trace nobody can read and nobody can replay,
which is a different way of losing the evidence.
"""
import re

# --- what gets removed -------------------------------------------------------
# Claim numbers: CLM-2024-88431, CLM 2024 88431, claim no. 2024-88431
CLAIM_RE = re.compile(r"\bCLM[-\s]?\d{4}[-\s]?\d{3,8}\b", re.I)
CLAIM_PHRASE_RE = re.compile(
    r"\bclaim\s*(?:no\.?|number|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{4,})\b", re.I
)
# Policy numbers carry 7+ digits. Form numbers (HO-0304) carry 4 — the digit
# count is what keeps the corpus readable while the policyholder stays out.
POLICY_RE = re.compile(r"\b[A-Z]{2,3}[-\s]?\d{7,12}\b")
POLICY_PHRASE_RE = re.compile(
    r"\bpolic(?:y|ies)\s*(?:no\.?|number|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{5,})\b", re.I
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
# The lookbehind rather than \b so an opening bracket is swallowed too:
# "(555) 212-9090" must not redact down to a stray "(".
PHONE_RE = re.compile(
    r"(?<![\w-])(?:\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?![\w-])"
)
# Named parties: a title, or a name introduced by a claims-file role word.
TITLE_NAME_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")
ROLE_NAME_RE = re.compile(
    r"\b(?:insured|claimant|policyholder|named insured|adjuster|contact)\b"
    r"(?:\s+(?:is|was|named|:))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"
)
ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Boulevard|Blvd)\b\.?",
    re.I,
)

RULES = [
    ("claim_number", CLAIM_RE, "[CLAIM_ID]"),
    ("claim_number", CLAIM_PHRASE_RE, None),   # None -> replace group 1 only
    ("policy_number", POLICY_RE, "[POLICY_ID]"),
    ("policy_number", POLICY_PHRASE_RE, None),
    ("ssn", SSN_RE, "[SSN]"),
    ("email", EMAIL_RE, "[EMAIL]"),
    ("phone", PHONE_RE, "[PHONE]"),
    ("address", ADDRESS_RE, "[ADDRESS]"),
    ("person_name", TITLE_NAME_RE, "[NAME]"),
    ("person_name", ROLE_NAME_RE, None),
]

PLACEHOLDER = {
    "claim_number": "[CLAIM_ID]",
    "policy_number": "[POLICY_ID]",
    "person_name": "[NAME]",
}


def redact(text: str) -> tuple[str, list[str]]:
    """-> (clean text, sorted list of the rule names that fired).

    The second value is recorded in the trace so a reader can tell 'nothing
    sensitive was present' apart from 'the redactor did not run'."""
    if not text:
        return text, []

    hits: set[str] = set()
    out = text

    for name, pattern, replacement in RULES:
        if replacement is None:
            # Phrase rules keep their lead-in ("claim number ...") and replace
            # only the identifier, so the sentence still reads.
            def sub(m, _n=name):
                hits.add(_n)
                return m.group(0).replace(m.group(1), PLACEHOLDER[_n])

            out = pattern.sub(sub, out)
        else:
            def sub(m, _n=name, _r=replacement):
                hits.add(_n)
                return _r

            out = pattern.sub(sub, out)

    return out, sorted(hits)


def redact_deep(value):
    """Redact every string inside a nested structure, collecting every hit."""
    hits: set[str] = set()

    def walk(v):
        if isinstance(v, str):
            clean, h = redact(v)
            hits.update(h)
            return clean
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [walk(x) for x in v]
        return v

    return walk(value), sorted(hits)
