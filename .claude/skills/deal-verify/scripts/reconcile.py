#!/usr/bin/env python3
"""Reconcile a processor export against a seller's stated figures.

    python reconcile.py export.csv --candidate flippa:11500001
    python reconcile.py export.csv --stated-ttm 9600 --stated-mrr 800 --currency USD

Reads a Stripe-style (or any) payments CSV, builds the trailing-twelve-month
revenue series, and prints it beside what the seller claimed. It does not
decide anything — putting the two columns next to each other is the job.

Column names differ between processors, so date and amount columns are detected
by header and the choice is printed. A run against the wrong column is worse
than no run, so that line is meant to be read.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "acquisition" / "src"))

GREEN, RED, YELLOW, DIM, RESET = ("\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m")

DATE_HINTS = ("created", "date", "paid_at", "timestamp", "period_start", "charge date")
AMOUNT_HINTS = ("amount_captured", "converted_amount", "net", "gross", "amount", "total",
                "value", "paid")
STATUS_HINTS = ("status", "state", "paid")
CUSTOMER_HINTS = ("customer", "customer_id", "customer email", "email", "account")
REFUND_HINTS = ("amount_refunded", "refunded", "refund")

OK_STATUSES = {"paid", "succeeded", "success", "complete", "completed", "true", "1", "active"}
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
                "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d")

# Variance beyond this is a discrepancy to ask about, not rounding.
TOLERANCE = 0.05


def pick_column(headers: list[str], hints: tuple[str, ...]) -> str | None:
    lowered = {h.lower().strip(): h for h in headers}
    for hint in hints:                                  # exact match first
        if hint in lowered:
            return lowered[hint]
    for hint in hints:                                  # then substring
        for low, original in lowered.items():
            if hint in low:
                return original
    return None


def parse_date(value: str) -> datetime | None:
    text = (value or "").strip().replace("Z", "")
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text[:len(datetime(2000, 1, 1).strftime(fmt))], fmt)
        except ValueError:
            continue
    try:                                                # ISO with offset, or epoch
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromtimestamp(float(text), tz=timezone.utc).replace(tzinfo=None)
    except (ValueError, OSError):
        return None


def parse_amount(value: str) -> float | None:
    text = (value or "").strip().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
    if not text or text in {"-", "—"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        amount = float(text)
    except ValueError:
        return None
    return -amount if negative else amount


def load_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def reconcile(path: Path):
    rows, headers = load_rows(path)
    if not rows:
        raise SystemExit(f"{path} has no data rows")

    date_col = pick_column(headers, DATE_HINTS)
    amount_col = pick_column(headers, AMOUNT_HINTS)
    status_col = pick_column(headers, STATUS_HINTS)
    customer_col = pick_column(headers, CUSTOMER_HINTS)
    refund_col = pick_column(headers, REFUND_HINTS)
    if refund_col == amount_col:
        refund_col = None

    if not date_col or not amount_col:
        raise SystemExit(
            f"could not find a date and an amount column in: {headers}\n"
            f"detected date={date_col!r} amount={amount_col!r}")

    by_month: dict[str, float] = defaultdict(float)
    by_customer: dict[str, float] = defaultdict(float)
    refunds = 0.0
    skipped = {"no date": 0, "no amount": 0, "not paid": 0}

    for row in rows:
        when = parse_date(row.get(date_col, ""))
        if when is None:
            skipped["no date"] += 1
            continue
        amount = parse_amount(row.get(amount_col, ""))
        if amount is None:
            skipped["no amount"] += 1
            continue
        if status_col:
            status = (row.get(status_col) or "").strip().lower()
            if status and status not in OK_STATUSES:
                skipped["not paid"] += 1
                continue
        if refund_col:
            refunded = parse_amount(row.get(refund_col, "")) or 0.0
            refunds += refunded
            amount -= refunded

        by_month[when.strftime("%Y-%m")] += amount
        if customer_col:
            by_customer[(row.get(customer_col) or "unknown").strip()] += amount

    return {
        "columns": {"date": date_col, "amount": amount_col, "status": status_col,
                    "customer": customer_col, "refund": refund_col},
        "rows": len(rows),
        "skipped": skipped,
        "refunds": refunds,
        "by_month": dict(sorted(by_month.items())),
        "by_customer": by_customer,
    }


def stated_from_candidate(candidate_id: str, config: str | None):
    from acq.config import Config
    from acq.store import candidate_store

    c = candidate_store(Config.load(config)).get(candidate_id)
    if c is None:
        raise SystemExit(f"no candidate with id {candidate_id!r} in the store")
    return c


def variance_line(label: str, stated: float | None, actual: float | None, unit: str = "£") -> str:
    if stated is None or actual is None:
        return (f"  {label:<26} stated {'—' if stated is None else f'{unit}{stated:,.0f}':>12}   "
                f"export {'—' if actual is None else f'{unit}{actual:,.0f}':>12}   "
                f"{DIM}not comparable{RESET}")
    delta = actual - stated
    pct = delta / stated if stated else 0
    mark = f"{GREEN}agrees{RESET}" if abs(pct) <= TOLERANCE else f"{RED}DISCREPANCY{RESET}"
    return (f"  {label:<26} stated {unit}{stated:>11,.0f}   export {unit}{actual:>11,.0f}   "
            f"{delta:+,.0f} ({pct:+.1%})  {mark}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=Path, help="processor CSV export")
    ap.add_argument("--candidate", help="candidate id to pull stated figures from the store")
    ap.add_argument("--config", help="path to acquisition/config.yaml")
    ap.add_argument("--stated-ttm", type=float, help="seller's stated TTM revenue")
    ap.add_argument("--stated-mrr", type=float, help="seller's stated MRR")
    ap.add_argument("--currency", default="£", help="symbol for display (default £)")
    args = ap.parse_args()

    result = reconcile(args.export)
    months = result["by_month"]
    trailing = list(months.items())[-12:]
    ttm = sum(v for _, v in trailing)
    recent = [v for _, v in trailing[-3:]]
    mrr = sum(recent) / len(recent) if recent else None

    stated_ttm, stated_mrr, name = args.stated_ttm, args.stated_mrr, args.export.name
    if args.candidate:
        c = stated_from_candidate(args.candidate, args.config)
        stated_ttm = stated_ttm if stated_ttm is not None else c.ttm_revenue
        stated_mrr = stated_mrr if stated_mrr is not None else c.mrr
        name = f"{c.name} [{c.key}]"

    cols = result["columns"]
    print(f"\nRECONCILIATION — {name}")
    print("=" * 78)
    print(f"{DIM}source: {args.export}  ({result['rows']} rows){RESET}")
    print(f"{DIM}columns used: date={cols['date']!r} amount={cols['amount']!r} "
          f"status={cols['status']!r} customer={cols['customer']!r}{RESET}")
    print(f"{DIM}  ^ check this line. A run against the wrong column is worse than none.{RESET}")
    dropped = {k: v for k, v in result["skipped"].items() if v}
    if dropped:
        print(f"{YELLOW}  skipped rows: {dropped}{RESET}")
    if result["refunds"]:
        print(f"{DIM}  refunds netted out: {args.currency}{result['refunds']:,.0f}{RESET}")

    print("\nMonthly revenue (trailing twelve)")
    if not trailing:
        print("  no dated rows parsed — check the date column")
    peak = max((v for _, v in trailing), default=1) or 1
    for month, value in trailing:
        bar = "█" * max(1, int(28 * value / peak)) if value > 0 else ""
        print(f"  {month}  {args.currency}{value:>10,.0f}  {bar}")

    print("\nAgainst the seller's figures")
    print(variance_line("TTM revenue", stated_ttm, ttm, args.currency))
    print(variance_line("MRR (3-month mean)", stated_mrr, mrr, args.currency))

    if len(trailing) >= 6:
        first_half = sum(v for _, v in trailing[:len(trailing) // 2])
        second_half = sum(v for _, v in trailing[len(trailing) // 2:])
        shape = ("growing" if second_half > first_half * 1.1
                 else "declining" if second_half < first_half * 0.9 else "flat")
        colour = RED if shape == "declining" else GREEN if shape == "growing" else ""
        print(f"\n  Shape: {colour}{shape}{RESET} — second half "
              f"{args.currency}{second_half:,.0f} against first half "
              f"{args.currency}{first_half:,.0f}")
        print(f"  {DIM}The series matters more than the total. A flat year and a collapsing "
              f"year can share a TTM figure.{RESET}")

    if result["by_customer"]:
        top = sorted(result["by_customer"].items(), key=lambda kv: kv[1], reverse=True)[:5]
        total = sum(result["by_customer"].values()) or 1
        print(f"\nCustomer concentration ({len(result['by_customer'])} customers)")
        for customer, value in top:
            share = value / total
            mark = f"  {RED}> 10% of revenue{RESET}" if share > 0.10 else ""
            print(f"  {customer[:38]:<38} {args.currency}{value:>10,.0f}  {share:>6.1%}{mark}")
        top_share = sum(v for _, v in top) / total
        print(f"  {DIM}top five = {top_share:.0%} of revenue{RESET}")

    if len(trailing) < 12:
        print(f"\n{YELLOW}Only {len(trailing)} months in the export. Ask for the rest "
              f"before reading anything into this.{RESET}")

    print(f"\n{DIM}Nothing here is a decision. Any single unexplained discrepancy resets "
          f"the deal to Stage 3 triage.{RESET}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
