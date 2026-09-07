"""Seeded random sampling of traces.

    python -m app.tracing.sample --seed 20260907 --n 20

The seed is published in the write-up and the selection is a pure function of
(seed, sorted trace_ids, n), so anyone can redraw the identical 20. Two things
this deliberately refuses to do:

  * sample the traces you remember breaking — a curated sample gives you
    frequencies that are fiction, and frequency is half of the fix order;
  * sample without recording the population — 20 of 60 and 20 of 6000 are
    different claims about the world.

Sorting the ids before shuffling matters: file order depends on when each
request happened, so an unsorted population makes the "same" seed draw a
different sample tomorrow.
"""
import argparse
import json
import random
from datetime import datetime, timezone

from .. import config
from .trace import read_all


def draw(
    traces: list[dict],
    seed: int = config.SAMPLE_SEED,
    n: int = config.SAMPLE_SIZE,
    source: str | None = None,
) -> dict:
    pool = [t for t in traces if source is None or t.get("source") == source]
    ids = sorted(t["trace_id"] for t in pool)          # deterministic population order
    if len(ids) < n:
        raise SystemExit(
            f"Population is {len(ids)} traces, cannot draw {n}. "
            "Run more traffic before sampling — a short draw is not a random sample."
        )
    rng = random.Random(seed)
    picked = sorted(rng.sample(ids, n))
    return {
        "drawn_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "n": n,
        "source_filter": source,
        "population": len(ids),
        "population_sha": _population_sha(ids),
        "trace_ids": picked,
    }


def _population_sha(ids: list[str]) -> str:
    import hashlib

    return hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12]


def redraw(sample: dict, traces: list[dict]) -> list[str]:
    """Reproduce a recorded draw — the check that the seed claim is true."""
    return draw(traces, sample["seed"], sample["n"], sample.get("source_filter"))["trace_ids"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=config.SAMPLE_SEED)
    ap.add_argument("--n", type=int, default=config.SAMPLE_SIZE)
    ap.add_argument(
        "--source",
        default="traffic",
        help="population to draw from — 'traffic' (default) is the natural stream. "
             "'demo' is the curated review set; None mixes them with eval runs and "
             "makes the frequencies meaningless.",
    )
    ap.add_argument("--out", default=str(config.SAMPLE_FILE))
    a = ap.parse_args()

    traces = read_all()
    s = draw(traces, a.seed, a.n, a.source)

    from pathlib import Path

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(s, indent=2))

    print(f"seed={s['seed']}  n={s['n']}  population={s['population']} "
          f"(sha {s['population_sha']})  ->  {out.relative_to(config.ROOT)}")
    for i, tid in enumerate(s["trace_ids"], start=1):
        print(f"  {i:2d}. {tid}")
