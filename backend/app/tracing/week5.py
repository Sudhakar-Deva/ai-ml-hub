"""One command for the unattended half of Week 5.

    python -m app.tracing.week5 --all

Runs the parts that are mechanical and stops at the part that is not:

  1. traffic   — 77 adjuster questions + 10 curated demo questions through the app
  2. replay    — one trace picked at random (same published seed), replayed from
                 the trace alone, evidence written to week5/replay.json
  3. sample    — the seeded random draw of 20, written to week5/sample.json
  4. notes     — regenerates notes.md from whatever exists so far

Then it stops. Open coding is 20 sentences of judgement about what you saw, and
clustering them into modes is the thing being graded. Neither can be automated
without turning the week into a description of an app nobody read.
"""
import argparse
import json
import random

from .. import config
from . import replay as replay_mod
from . import sample as sampling
from . import traffic as traffic_mod
from .trace import by_id, read_all


def step(n: int, title: str) -> None:
    print(f"\n{'=' * 70}\n{n}. {title}\n{'=' * 70}")


def run_traffic() -> None:
    step(1, "Traffic — the app answering, leaving traces behind")
    for bank in ("traffic", "demo"):
        print(traffic_mod.run(bank))


def draw_sample(seed: int, n: int) -> dict:
    step(3, "Seeded random sample")
    traces = read_all()
    s = sampling.draw(traces, seed, n, source="traffic")
    config.SAMPLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.SAMPLE_FILE.write_text(json.dumps(s, indent=2))
    print(f"seed={s['seed']}  n={s['n']}  population={s['population']} "
          f"(sha {s['population_sha']})")
    for i, tid in enumerate(s["trace_ids"], start=1):
        t = by_id(tid)
        print(f"  {i:2d}. {tid}  {t['question'][:70] if t else ''}")
    # the seed reproduces the draw, or the claim in the write-up is not true
    assert sampling.redraw(s, traces) == s["trace_ids"], "seed does not reproduce the draw"
    print("verified: redrawing with the same seed returns the identical 20")
    return s


def do_replay(seed: int) -> None:
    step(2, "Replay one trace, picked at random, from the trace alone")
    traces = [t for t in read_all() if t.get("source") == "traffic"]
    if not traces:
        raise SystemExit("no traffic traces yet")
    pick = random.Random(seed).choice(sorted(t["trace_id"] for t in traces))
    print(f"seed {seed} picked {pick}")

    t = by_id(pick)
    report = replay_mod.audit(t)
    print(json.dumps(report, indent=2))

    r = replay_mod.replay(t)
    config.WEEK5_DIR.mkdir(parents=True, exist_ok=True)
    (config.WEEK5_DIR / "replay.json").write_text(json.dumps(r, indent=2))
    print(f"\nidentical={r['identical']}  similarity={r['similarity']}")
    print(f"-> {(config.WEEK5_DIR / 'replay.json').relative_to(config.ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seed", type=int, default=config.SAMPLE_SEED)
    ap.add_argument("--n", type=int, default=config.SAMPLE_SIZE)
    ap.add_argument("--skip-traffic", action="store_true")
    a = ap.parse_args()

    if not a.skip_traffic:
        run_traffic()
    do_replay(a.seed)
    draw_sample(a.seed, a.n)

    step(4, "notes.md")
    from . import notes

    (config.ROOT / "notes.md").write_text(notes.build())
    print("-> notes.md")

    print(f"""
{'=' * 70}
Done with the mechanical half. What is left is the graded half:

  python -m app.tracing.opencode --start        # pins the code you are reading
  python -m app.tracing.opencode --next         # 20 times, one sentence each
  <write week5/modes.json — 4 to 7 named modes>
  python -m app.tracing.taxonomy --write
  <fill week5/prediction.md, git commit it BEFORE any fix>
  python -m app.tracing.notes --write
{'=' * 70}""")


if __name__ == "__main__":
    main()
