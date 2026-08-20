"""D7 — the deal tracker. This is the working document.

Stages run sourced -> contacted -> responded -> data requested -> verifying ->
diligence -> offer -> closing -> closed / dead. The stage cell is a dropdown so
the pipeline can't drift into free text, and the file must stay usable without
editing code: re-running the pipeline adds newly promoted candidates and leaves
every human-entered cell — stage, dates, next action, notes — exactly as typed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ..models import Candidate
from .style import BORDER, autosize, write_header

STAGES = ["sourced", "contacted", "responded", "data requested", "verifying",
          "diligence", "offer", "closing", "closed", "dead"]

HEADERS = ["Candidate ID", "Name", "Source", "URL", "Stage", "Last contact",
           "Next action", "Next action date", "Asking price", "Score", "Flags", "Notes"]
WIDTHS = {"Candidate ID": 22, "Name": 28, "URL": 34, "Next action": 30,
          "Flags": 34, "Notes": 46}
HUMAN_COLUMNS = ("Stage", "Last contact", "Next action", "Next action date", "Notes")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_existing(path: Path) -> dict[str, dict[str, object]]:
    """Pull the human-owned cells out of an existing tracker so a re-run can put
    them straight back. Anything unreadable is treated as absent — the tracker
    is never destroyed, only rewritten alongside what it already held."""
    if not path.exists():
        return {}
    try:
        wb = load_workbook(path)
        ws = wb["Pipeline"] if "Pipeline" in wb.sheetnames else wb.active
    except Exception as exc:
        print(f"WARN tracker: could not read existing {path.name} ({exc}); "
              f"human-entered cells may be lost — check the backup before saving over it")
        return {}

    headers = [c.value for c in ws[1]]
    kept: dict[str, dict[str, object]] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        record = dict(zip(headers, row))
        key = record.get("Candidate ID")
        if key:
            kept[str(key)] = {col: record.get(col) for col in HUMAN_COLUMNS}
    return kept


def write(candidates: list[Candidate], path: str | Path) -> Path:
    path = Path(path)
    existing = _read_existing(path)

    wb = Workbook()
    ws = wb.active
    ws.title = "Pipeline"
    write_header(ws, HEADERS)

    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
    for r, c in enumerate(ranked, start=2):
        prior = existing.get(c.key, {})
        values = {
            "Candidate ID": c.key,
            "Name": c.name,
            "Source": c.source,
            "URL": c.url,
            "Stage": prior.get("Stage") or c.status or "sourced",
            "Last contact": prior.get("Last contact") or "",
            "Next action": prior.get("Next action") or "triage — four questions",
            "Next action date": prior.get("Next action date") or "",
            "Asking price": c.asking_price,
            "Score": c.score,
            "Flags": ", ".join(c.flag_names()),
            "Notes": prior.get("Notes") or "",
        }
        for col, title in enumerate(HEADERS, start=1):
            cell = ws.cell(row=r, column=col, value=values[title])
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=(title == "Notes"))
            if title == "Asking price":
                cell.number_format = '£#,##0'
        if c.url:
            link = ws.cell(row=r, column=4)
            link.hyperlink = c.url
            link.font = Font(color="0B62A4", underline="single")

    stage_col = get_column_letter(HEADERS.index("Stage") + 1)
    last_row = max(ws.max_row, 2)
    validation = DataValidation(
        type="list", formula1=f'"{",".join(STAGES)}"', allow_blank=False,
        showDropDown=False,     # openpyxl inverts this flag: False shows the arrow
        errorTitle="Not a pipeline stage",
        error="Pick one of: " + ", ".join(STAGES),
    )
    ws.add_data_validation(validation)
    validation.add(f"{stage_col}2:{stage_col}{max(last_row, 400)}")

    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{last_row}"
    autosize(ws, HEADERS, WIDTHS)

    # A short legend, so the stage list lives in the file rather than in the code.
    legend = wb.create_sheet("Stages")
    write_header(legend, ["Stage", "Meaning", "Kill condition"])
    meanings = [
        ("sourced", "Passed automated screening. Not yet looked at.", "—"),
        ("contacted", "Enquiry or cold approach sent.", "No reply after two follow-ups."),
        ("responded", "Seller replied.", "Refuses read-only verification without a reason."),
        ("data requested", "Asked for 12 months revenue, subscriber count, last 20 customers.",
         "Seller-built spreadsheet offered instead of processor data."),
        ("verifying", "Reconciling stated figures against primary sources.",
         "Any single unexplained discrepancy resets to triage."),
        ("diligence", "Financial, technical, legal, channel.",
         "Undocumented-API dependency, or channel is a person."),
        ("offer", "Valuation anchored on profit; 70/30 structure proposed.",
         "Payback over 36 months at the asking price."),
        ("closing", "Escrow funded, transfer sequence running.",
         "Processor cannot migrate subscriptions."),
        ("closed", "Escrow released after all transfer steps verified.", "—"),
        ("dead", "Stopped. Record why in Notes.", "—"),
    ]
    for r, row in enumerate(meanings, start=2):
        for col, value in enumerate(row, start=1):
            cell = legend.cell(row=r, column=col, value=value)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    autosize(legend, ["Stage", "Meaning", "Kill condition"],
             {"Meaning": 58, "Kill condition": 52})

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
