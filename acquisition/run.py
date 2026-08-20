#!/usr/bin/env python3
"""Micro-SaaS acquisition pipeline — command line entry point.

    python acquisition/run.py gate                    # Phase 1 + 2 acceptance tests
    python acquisition/run.py neglect                 # D3 WordPress.org off-market pull
    python acquisition/run.py marketplace             # D2 Flippa + TrustMRR pull
    python acquisition/run.py screen                  # D4/D5 re-screen everything stored
    python acquisition/run.py weekly                  # everything, then D6/D7 outputs
    python acquisition/run.py promote <id> contacted  # move a candidate along D7
    python acquisition/run.py diligence <id>          # D8 pack for a promoted candidate
    python acquisition/run.py outreach                # drafts for review (never sends)
    python acquisition/run.py show <id>               # one candidate, in full

Nothing here runs on a schedule and nothing sends anything. Scripts run on
demand; the human reviews once a week.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from acq.config import Config                                    # noqa: E402
from acq.fx import FixedRates, FxRates                           # noqa: E402
from acq.classify import get_classifier                          # noqa: E402
from acq.models import Candidate                                 # noqa: E402
from acq.normalise import normalise                              # noqa: E402
from acq.rules import RuleEngine                                 # noqa: E402
from acq.store import candidate_store, neglect_store             # noqa: E402
from acq.sources.base import SourceError                         # noqa: E402
from acq.sources.demo import (DEMO_FLIPPA, DEMO_TRUSTMRR,         # noqa: E402
                              wordpress_pages)
from acq.sources.fixture import FixtureSession                   # noqa: E402
from acq.sources.flippa import (ApifyActorBackend,               # noqa: E402
                                FlippaSource, JsonEndpointBackend)
from acq.sources.trustmrr import TrustMrrSource, cross_check     # noqa: E402
from acq.sources.wordpress import WordPressSource                # noqa: E402
from acq.outputs import candidates_xlsx, diligence, outreach, tracker_xlsx  # noqa: E402

PROMOTED_STAGES = {"contacted", "responded", "data requested", "verifying",
                   "diligence", "offer", "closing"}


# ----------------------------------------------------------------- utilities
def load_config(args) -> Config:
    return Config.load(args.config)


def load_fx(cfg: Config, args) -> FxRates:
    if getattr(args, "fx_rate", None):
        print(f"fx: pinned USD→GBP at {args.fx_rate}")
        return FixedRates({"USD": args.fx_rate, "GBP": 1.0})
    return FxRates.load(
        cfg.base_dir() / "data" / "fx_cache.json",
        max_age_hours=float(cfg.get("run.fx_cache_hours", 24)),
        offline=getattr(args, "offline", False),
    )


def engine_for(cfg: Config, args) -> RuleEngine:
    return RuleEngine(cfg, classifier=get_classifier(use_llm=getattr(args, "llm", False)))


def out_dir(cfg: Config) -> Path:
    d = cfg.path("paths.out_dir")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session(args):
    """A fixture session when --fixture is given, otherwise the real network."""
    return FixtureSession.from_file(args.fixture) if getattr(args, "fixture", None) else None


# ------------------------------------------------------------------ commands
def cmd_gate(args) -> int:
    """Phase 1 is the acceptance gate for the whole system."""
    failed = 0
    for script in ("tests/test_rules.py", "tests/test_extract.py",
                   "tests/test_wordpress.py", "tests/test_pipeline.py"):
        path = HERE / script
        if not path.exists():
            continue
        print(f"\n$ python {script}\n")
        failed |= subprocess.run([sys.executable, str(path)]).returncode
    return 1 if failed else 0


def cmd_neglect(args) -> int:
    cfg = load_config(args)
    src = WordPressSource(cfg, session=_session(args))
    try:
        found = src.fetch_neglect(limit=args.limit, pages=args.pages)
    except SourceError as exc:
        print(f"ERROR {exc}")
        return 2

    store = neglect_store(cfg)
    new = store.upsert(found)
    store.save()
    print(f"stored {len(store)} neglect candidates ({len(new)} new since last run)")

    for n in found[:args.top]:
        print(f"  {n.neglect_score:7.2f}  {n.active_installs:>9,} installs  "
              f"{n.months_since_update:>5.0f}mo  {n.rating}★  {n.name}")
        print(f"           {n.author_profile or n.url}")
    return 0


def cmd_marketplace(args) -> int:
    cfg = load_config(args)
    fx = load_fx(cfg, args)
    engine = engine_for(cfg, args)

    backend = (ApifyActorBackend(args.apify_actor) if args.apify_actor
               else JsonEndpointBackend())
    src = FlippaSource(cfg, session=_session(args), backend=backend, fx=fx)
    try:
        listings = src.fetch(limit=args.limit)
    except SourceError as exc:
        print(f"ERROR {exc}")
        return 2

    candidates = [normalise(l, fx) for l in listings]

    if args.trustmrr_actor:
        tm = TrustMrrSource(cfg, actor=args.trustmrr_actor)
        try:
            matched = cross_check(candidates, tm.records(), fx=fx)
            print(f"trustmrr: cross-checked {len(candidates)} candidates, {matched} matched")
        except SourceError as exc:
            print(f"WARN trustmrr cross-check skipped: {exc}")

    engine.screen_all(candidates)
    store = candidate_store(cfg)
    new = store.upsert(candidates)
    store.save()

    review = [c for c in candidates if c.disposition == "review"]
    print(f"screened {len(candidates)}: {len(review)} to review, "
          f"{len(candidates) - len(review)} rejected, {len(new)} new since last run")
    return 0


def cmd_screen(args) -> int:
    """Re-run the engine over everything stored. Use after a config change."""
    cfg = load_config(args)
    engine = engine_for(cfg, args)
    store = candidate_store(cfg)
    candidates = store.all()
    if not candidates:
        print("store is empty — run `marketplace` first")
        return 1

    engine.screen_all(candidates)
    store.upsert(candidates)
    store.save()
    review = [c for c in candidates if c.disposition == "review"]
    rejected = len(candidates) - len(review)
    rate = rejected / len(candidates) if candidates else 0
    print(f"re-screened {len(candidates)}: {len(review)} to review, {rejected} rejected "
          f"({rate:.0%} rejection — expect 95%+; that is the pipeline working)")
    return 0


def cmd_weekly(args) -> int:
    """The whole run: refresh what can be refreshed, then write the artefacts."""
    cfg = load_config(args)
    engine = engine_for(cfg, args)

    failed_pulls: list[str] = []
    if not args.no_pull:
        for name, fn in (("marketplace", cmd_marketplace), ("neglect", cmd_neglect)):
            print(f"\n── {name} ──")
            if fn(args) != 0:
                failed_pulls.append(name)
                print(f"WARN {name} pull failed; continuing with stored data")

    store = candidate_store(cfg)
    candidates = store.all()
    engine.screen_all(candidates)
    store.upsert(candidates)
    store.save()

    review = [c for c in candidates if c.disposition == "review"]
    rejected = [c for c in candidates if c.disposition == "reject"]

    print("\n── outputs ──")
    sheet = candidates_xlsx.write(review, out_dir(cfg) / "candidates.xlsx", rejected=rejected)
    print(f"D6 candidate sheet  → {sheet}  ({len(review)} shortlisted, {len(rejected)} rejected)")

    tracker = tracker_xlsx.write(review, out_dir(cfg) / "deal-tracker.xlsx")
    print(f"D7 deal tracker     → {tracker}")

    neglect = neglect_store(cfg).all()
    neglect.sort(key=lambda n: n.neglect_score, reverse=True)
    drafts = outreach.write(neglect[:args.outreach_count],
                            sorted(review, key=lambda c: c.score, reverse=True)[:args.outreach_count],
                            out_dir(cfg) / "outreach-drafts.md", sender=args.sender)
    print(f"   outreach drafts  → {drafts}  (review and send yourself)")

    packs = [diligence.write(c, out_dir(cfg) / "diligence")
             for c in candidates if c.status in PROMOTED_STAGES]
    print(f"D8 diligence packs  → {len(packs)} generated for promoted candidates")

    # A short list after a failed pull is not a quiet week, and the two must
    # never look alike in the summary a human skims.
    if failed_pulls:
        print(f"\nWARN this run is INCOMPLETE — {' and '.join(failed_pulls)} did not "
              f"return data. The sheet reflects stored data only; do not read a short "
              f"shortlist as a quiet week.")
        return 1
    return 0


def cmd_demo(args) -> int:
    """Rehearse a complete weekly run against a deterministic offline corpus.

    Same code path as `weekly` — same ingestion, same rule engine, same writers —
    but every source is replayed from fixtures and every path is redirected to a
    disposable directory. Use it to see what a run produces before trusting a
    live one, and to check a config change against known data.
    """
    import json

    base = load_config(args)
    cfg = (base
           .override("paths.store", "data/demo/candidates.json")
           .override("paths.neglect_store", "data/demo/neglect.json")
           .override("paths.out_dir", "out/demo"))
    fx = FixedRates({"USD": 0.79, "GBP": 1.0})     # pinned: a rehearsal must repeat
    engine = engine_for(cfg, args)
    print(f"DEMO RUN — offline corpus, USD→GBP pinned at 0.79\n{'=' * 72}")

    if args.fresh:
        for path in (cfg.path("paths.store"), cfg.path("paths.neglect_store")):
            path.unlink(missing_ok=True)

    print("\n── marketplace (replayed) ──")
    flippa = FlippaSource(cfg, session=FixtureSession.from_file(DEMO_FLIPPA), fx=fx)
    flippa.delay = 0
    candidates = [normalise(l, fx) for l in flippa.fetch()]

    records = [TrustMrrSource.to_record(r) for r in json.loads(DEMO_TRUSTMRR.read_text())]
    matched = cross_check(candidates, records, fx=fx)
    print(f"trustmrr: cross-checked {len(candidates)} candidates against "
          f"{len(records)} verified records, {matched} matched")

    engine.screen_all(candidates)
    store = candidate_store(cfg)
    new = store.upsert(candidates)
    store.save()

    print("\n── off-market (generated) ──")
    wp = WordPressSource(cfg, session=FixtureSession(wordpress_pages(args.plugins)))
    wp.delay = 0
    neglect = wp.fetch_neglect()
    nstore = neglect_store(cfg)
    nnew = nstore.upsert(neglect)
    nstore.save()
    print(f"stored {len(nstore)} neglect candidates ({len(nnew)} new since last run)")

    review = [c for c in candidates if c.disposition == "review"]
    rejected = [c for c in candidates if c.disposition == "reject"]
    rate = len(rejected) / len(candidates) if candidates else 0

    print(f"\n── screening ──")
    print(f"{len(candidates)} screened · {len(review)} to review · {len(rejected)} rejected "
          f"({rate:.0%}) · {len(new)} new since last run")
    for c in sorted(rejected, key=lambda c: c.name):
        print(f"  REJECT  {c.name[:42]:<42} {', '.join(c.reject_reasons())}")
    for c in sorted(review, key=lambda c: c.score, reverse=True):
        print(f"  REVIEW  {c.name[:42]:<42} score {c.score:>6.1f}  "
              f"{', '.join(c.flag_names()) or 'no flags'}")

    gaps = {rule: (n, t) for rule, (n, t) in RuleEngine.coverage(candidates).items() if n < t}
    if gaps:
        print("\n── rule coverage ──")
        print("  These rules could not be evaluated on every candidate, because the "
              "source\n  does not carry their inputs. Not-fired is not the same as "
              "found-nothing:")
        for rule, (n, t) in sorted(gaps.items(), key=lambda kv: kv[1][0]):
            need = ", ".join(RuleEngine.RULE_INPUTS[rule])
            print(f"  {rule:<26} evaluable on {n}/{t}   needs: {need}")

    print("\n── top off-market ──")
    for n in neglect[:5]:
        print(f"  {n.neglect_score:6.2f}  {n.active_installs:>8,} installs  "
              f"{n.months_since_update:>4.0f}mo  {n.rating}★  {n.name[:34]:<34} "
              f"{n.author_profile}")

    print("\n── outputs ──")
    d = out_dir(cfg)
    print(f"D6 candidate sheet  → {candidates_xlsx.write(review, d / 'candidates.xlsx', rejected=rejected)}")
    print(f"D7 deal tracker     → {tracker_xlsx.write(review, d / 'deal-tracker.xlsx')}")
    print(f"   outreach drafts  → {outreach.write(neglect[:args.outreach_count], sorted(review, key=lambda c: c.score, reverse=True)[:args.outreach_count], d / 'outreach-drafts.md', sender=args.sender)}")

    top = max(review, key=lambda c: c.score, default=None)
    if top is not None:
        store.set_status(top.key, "contacted")
        store.save()
        top.status = "contacted"
        print(f"D8 diligence pack   → {diligence.write(top, d / 'diligence')}")
        print(f"   (promoted the top candidate to `contacted` to exercise D8)")

    print(f"\nNothing was sent and no live endpoint was contacted. "
          f"Delete {d.parent}/demo and data/demo to reset.")
    return 0


def cmd_promote(args) -> int:
    cfg = load_config(args)
    store = candidate_store(cfg)
    if not store.set_status(args.candidate_id, args.stage):
        print(f"no candidate with id {args.candidate_id!r}")
        return 1
    store.save()
    print(f"{args.candidate_id} → {args.stage}")

    if args.stage in PROMOTED_STAGES:
        path = diligence.write(store.get(args.candidate_id), out_dir(cfg) / "diligence")
        print(f"diligence pack → {path}")
    return 0


def cmd_diligence(args) -> int:
    cfg = load_config(args)
    candidate = candidate_store(cfg).get(args.candidate_id)
    if candidate is None:
        print(f"no candidate with id {args.candidate_id!r}")
        return 1
    print(f"diligence pack → {diligence.write(candidate, out_dir(cfg) / 'diligence')}")
    return 0


def cmd_outreach(args) -> int:
    cfg = load_config(args)
    neglect = sorted(neglect_store(cfg).all(), key=lambda n: n.neglect_score, reverse=True)
    review = sorted([c for c in candidate_store(cfg).all() if c.disposition == "review"],
                    key=lambda c: c.score, reverse=True)
    path = outreach.write(neglect[:args.outreach_count], review[:args.outreach_count],
                          out_dir(cfg) / "outreach-drafts.md", sender=args.sender)
    print(f"drafts → {path}\nNothing has been sent. Edit each one before you send it.")
    return 0


def cmd_show(args) -> int:
    cfg = load_config(args)
    c: Candidate | None = candidate_store(cfg).get(args.candidate_id)
    if c is None:
        print(f"no candidate with id {args.candidate_id!r}")
        return 1
    print(f"{c.name}  [{c.key}]  {c.url}")
    print(f"  disposition {c.disposition}  score {c.score}  status {c.status}")
    for r in c.rejects:
        print(f"  REJECT {r['rule']}: {r['detail']}")
    for f in c.flags:
        print(f"  FLAG   {f['flag']}: {f['trigger']}")
        if f["evidence"]:
            print(f"         {f['evidence']}")
    return 0


# --------------------------------------------------------------------- parse
def _add_global_flags(parser: argparse.ArgumentParser, *, suppress: bool) -> None:
    """The same flags on the top-level parser and on every subparser.

    On the subparser copies the defaults are SUPPRESS, so an unset flag after the
    subcommand does not silently overwrite one that was set before it — which is
    the classic argparse trap where `--fx-rate 0.79 weekly` quietly reverts to
    live ECB rates.
    """
    d = (lambda v: argparse.SUPPRESS) if suppress else (lambda v: v)
    parser.add_argument("--config", default=d(None),
                        help="path to config.yaml (default: acquisition/config.yaml)")
    parser.add_argument("--fx-rate", type=float, default=d(None),
                        help="pin USD→GBP instead of fetching ECB rates (reproducible runs)")
    parser.add_argument("--offline", action="store_true", default=d(False),
                        help="never hit the network for FX")
    parser.add_argument("--llm", action="store_true", default=d(False),
                        help="use the Claude classifier for CHANNEL_RISK (default: heuristic)")
    parser.add_argument("--fixture", default=d(None),
                        help="replay a recorded API response instead of calling out")
    parser.add_argument("--sender", default=d("{your_name}"),
                        help="name to sign outreach drafts with")
    parser.add_argument("--outreach-count", type=int, default=d(10),
                        help="how many drafts to generate per stream (default 10)")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    _add_global_flags(common, suppress=True)

    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_global_flags(p, suppress=False)
    sub = p.add_subparsers(dest="command", required=True, parser_class=argparse.ArgumentParser)

    def add(name: str, help_: str):
        return sub.add_parser(name, help=help_, parents=[common])

    add("gate", "run the acceptance tests").set_defaults(fn=cmd_gate)

    n = add("neglect", "D3 — WordPress.org off-market pull")
    n.add_argument("--limit", type=int, help="cap on stored candidates")
    n.add_argument("--pages", type=int, help="pages to scan (100 plugins each)")
    n.add_argument("--top", type=int, default=15, help="how many to print")
    n.set_defaults(fn=cmd_neglect)

    m = add("marketplace", "D2 — Flippa pull with TrustMRR cross-check")
    m.add_argument("--limit", type=int)
    m.add_argument("--apify-actor", help="use an Apify actor instead of the JSON endpoint")
    m.add_argument("--trustmrr-actor", help="Apify actor id for the TrustMRR cross-check")
    m.set_defaults(fn=cmd_marketplace)

    add("screen", "re-run the rule engine over the store").set_defaults(fn=cmd_screen)

    dm = add("demo", "rehearse a full run against an offline corpus (no network)")
    dm.add_argument("--plugins", type=int, default=4000,
                    help="size of the generated WordPress corpus (default 4000)")
    dm.add_argument("--fresh", action="store_true",
                    help="clear the demo store first, so everything reads as new")
    dm.set_defaults(fn=cmd_demo)

    w = add("weekly", "full run: pull, screen, write D6/D7/D8")
    w.add_argument("--no-pull", action="store_true", help="use stored data only")
    w.add_argument("--limit", type=int)
    w.add_argument("--pages", type=int)
    w.add_argument("--top", type=int, default=10)
    w.add_argument("--apify-actor")
    w.add_argument("--trustmrr-actor")
    w.set_defaults(fn=cmd_weekly)

    pr = add("promote", "move a candidate to a pipeline stage")
    pr.add_argument("candidate_id")
    pr.add_argument("stage", choices=sorted(PROMOTED_STAGES | {"sourced", "closed", "dead"}))
    pr.set_defaults(fn=cmd_promote)

    d = add("diligence", "D8 — generate a diligence pack")
    d.add_argument("candidate_id")
    d.set_defaults(fn=cmd_diligence)

    add("outreach", "generate outreach drafts for review").set_defaults(fn=cmd_outreach)

    sh = add("show", "print one candidate in full")
    sh.add_argument("candidate_id")
    sh.set_defaults(fn=cmd_show)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
