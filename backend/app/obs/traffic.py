"""A day of claim-summary traffic, replayed as "yesterday".

    python -m app.obs.traffic --day 2026-11-15          # 20 requests -> week11/obs/requests.jsonl

The 10 claim files in evals/w7/claims.jsonl, each summarised twice by different
adjusters at different times of the day (a second adjuster re-opening a file is
the normal shape of claims traffic). Every request is a real call through
app.obs.app.handle(); only `ts` is set to yesterday's business hours.
"""
import argparse
import random
from datetime import datetime, timedelta, timezone

from ..agents.tools import load_claims
from .app import handle

USERS = ("ADJ-114", "ADJ-207", "ADJ-309", "ADJ-412")


def notes_for(c: dict) -> str:
    """The claim file as the summary path receives it: header facts + adjuster notes."""
    head = (f"Claim {c['claim_number']}. Policy {c['policy_number']} ({c['policy_line']} form). "
            f"Date of loss {c['date_of_loss']}. Reported: {c['loss_type_reported']}, claimed "
            f"${c['claimed_amount']:,}, policy excess ${c['policy_excess']:,}.")
    return head + "\n" + (c["adjuster_notes"] or "No adjuster notes on file yet.")


def main(day: str, seed: int = 20261115) -> None:
    from ..generation.summarize import retrieve

    retrieve("warm-up")            # embedder load stays out of the first request's retrieval span
    rnd = random.Random(seed)
    start = datetime.fromisoformat(day).replace(hour=8, minute=10, tzinfo=timezone.utc)
    jobs = [(c, u) for c in load_claims() for u in rnd.sample(USERS, 2)]
    rnd.shuffle(jobs)
    for i, (c, user) in enumerate(jobs):
        ts = (start + timedelta(minutes=29 * i + rnd.randint(0, 20))).isoformat(timespec="seconds")
        r = handle(notes_for(c), user, f"claim_summary:{c['policy_line']}", ts)
        print(f"{ts}  {r['request_id']}  {user}  {r['output']['coverage_position']:<13}  "
              f"{r['totals']['tokens']:>5} tok  ${r['totals']['cost_usd']:.5f}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True, help="YYYY-MM-DD, the 'yesterday' being replayed")
    main(ap.parse_args().day)
