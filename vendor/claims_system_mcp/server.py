"""claims-system MCP server, v0.4.1, maintained by the Claims Platform team.

THIRD-PARTY CODE. Vendored here as delivered; the assistant team does not edit it.

Exposes two read tools over MCP stdio:
  get_claim_status(claim_number)    status record for one claim
  get_adjuster_notes(claim_number)  full adjuster note history for one claim

Environment:
  CLAIMS_API_TOKEN   required. Bearer token for the claims platform. In this
                     build it is only checked for presence: any non-empty value
                     reads every claim in the store.
  CLAIMS_DATA        claims store (default: data/claims.json next to this file)
  CLAIMS_SYSTEM_LOG  access log (default: claims_system_access.log in the cwd)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
TOKEN = os.environ.get("CLAIMS_API_TOKEN", "")
STORE = Path(os.environ.get("CLAIMS_DATA", HERE / "data" / "claims.json"))
LOG = Path(os.environ.get("CLAIMS_SYSTEM_LOG", "claims_system_access.log"))

mcp = FastMCP("claims-system")


def _load() -> dict:
    return json.loads(STORE.read_text())


def _audit(tool: str, claim_number: str, found: bool) -> None:
    # one line per call: who (token prefix), what, which claim
    with LOG.open("a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "token": TOKEN[:6] + "...", "tool": tool,
                            "claim_number": claim_number, "found": found}) + "\n")


def _claim(tool: str, claim_number: str) -> dict:
    c = _load().get(claim_number.strip().upper())
    _audit(tool, claim_number, c is not None)
    if c is None:
        raise ValueError(f"claim {claim_number} not found in claims system")
    return c


@mcp.tool()
def get_claim_status(claim_number: str) -> dict:
    """Current status of one claim: policy number and line, status, date of loss,
    reported loss type, claimed amount, policy excess, assigned adjuster and the
    date it was last updated. claim_number looks like CLM-2026-10002."""
    c = _claim("get_claim_status", claim_number)
    return {k: v for k, v in c.items() if k != "notes"}


@mcp.tool()
def get_adjuster_notes(claim_number: str) -> dict:
    """Full adjuster note history for one claim, oldest first: each entry has a
    date, an author (adjuster id or intake) and the note text verbatim."""
    c = _claim("get_adjuster_notes", claim_number)
    return {"claim_number": c["claim_number"], "notes": c["notes"]}


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("claims-system: CLAIMS_API_TOKEN is not set")
    mcp.run("stdio")
