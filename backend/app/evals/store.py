"""Where Week 6's artifacts live, and the fingerprints that tie them together.

The blind protocol is only worth something if the labels can be shown to be
about THESE summaries. So summaries.json is written once and frozen, its sha256
travels into labels_25.json, and every judge run records the same sha. If the
summaries are regenerated, every number computed against the old ones stops
matching and says so, rather than quietly comparing labels of one run against
verdicts of another.
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone

from .. import config


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha_file(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else None


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=config.ROOT, capture_output=True, text=True
    ).stdout.strip()


def committed_at(path) -> dict | None:
    """The commit that last touched `path`, and whether the working copy still
    matches it. This is the ordering evidence the rubric asks for — 25 points
    ride on it, so it is read out of git rather than asserted in prose."""
    rel = str(path.relative_to(config.ROOT))
    sha = git("log", "-1", "--format=%H", "--", rel)
    if not sha:
        return None
    dirty = git("status", "--porcelain", "--", rel)
    return {
        "path": rel,
        "commit": sha,
        "short": sha[:12],
        "committed_at": git("log", "-1", "--format=%cI", "--", rel),
        "subject": git("log", "-1", "--format=%s", "--", rel),
        "clean": not dirty,
    }


# --- summaries ---------------------------------------------------------------

def save_summaries(payload: dict) -> None:
    config.W6_DIR.mkdir(parents=True, exist_ok=True)
    config.W6_SUMMARIES_FILE.write_text(json.dumps(payload, indent=2) + "\n")


def load_summaries() -> dict:
    if not config.W6_SUMMARIES_FILE.exists():
        raise SystemExit(
            f"no summaries at {config.W6_SUMMARIES_FILE}\n"
            "  python -m app.evals.run --generate"
        )
    return json.loads(config.W6_SUMMARIES_FILE.read_text())


def summaries_sha() -> str:
    return sha_file(config.W6_SUMMARIES_FILE)


def summary_for(case_id: str) -> str:
    s = load_summaries()["summaries"]
    if case_id not in s:
        raise SystemExit(f"no summary for {case_id}")
    return s[case_id]["summary"]


# --- judge runs --------------------------------------------------------------

def save_run(kind: str, version: str, payload: dict):
    config.W6_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.W6_RUNS_DIR / f"{kind}_{version}_{stamp()}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def latest_run(kind: str, version: str) -> dict | None:
    if not config.W6_RUNS_DIR.exists():
        return None
    runs = sorted(config.W6_RUNS_DIR.glob(f"{kind}_{version}_*.json"))
    return json.loads(runs[-1].read_text()) if runs else None
