#!/usr/bin/env python3
"""Build the Census static site from local files, using only Python stdlib."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from urllib.parse import urlsplit


SCRIPT = Path(__file__).resolve()
DEFAULT_AGENT_ROOT = SCRIPT.parents[2]
DEFAULT_HISTORY_URL = (
    "https://github.com/infojunkie14/ventures/commits/master/Census/CHARTER.md"
)
UTC = dt.timezone.utc
MONEY = Decimal("0.01")

CSS = r"""
:root {
  color-scheme: light dark;
  --bg: #f4f1ea;
  --surface: #fffdf8;
  --text: #20201d;
  --muted: #66645e;
  --line: #d8d2c5;
  --accent: #245f55;
  --accent-soft: #dcebe5;
  --danger: #9b2c2c;
  --danger-soft: #f9dfdc;
  --shadow: 0 10px 30px rgba(49, 45, 35, .08);
}
* { box-sizing: border-box; }
html { font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }
body { margin: 0; color: var(--text); background: var(--bg); line-height: 1.6; }
a { color: var(--accent); text-underline-offset: .18em; }
a:hover { text-decoration-thickness: 2px; }
.shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; }
.site-head { padding: 24px 0 18px; border-bottom: 1px solid var(--line); background: var(--surface); }
.topline { display: flex; align-items: baseline; justify-content: space-between; gap: 24px; }
.brand { color: var(--text); font: 750 1.2rem/1.2 ui-monospace, "SFMono-Regular", Consolas, monospace; text-decoration: none; }
nav { display: flex; flex-wrap: wrap; gap: 18px; font-size: .94rem; }
.wake { margin: 14px 0 0; color: var(--muted); font-size: .86rem; }
.stall { margin: 16px 0 0; padding: 10px 14px; border: 1px solid var(--danger); border-radius: 8px; color: var(--danger); background: var(--danger-soft); font-weight: 700; }
.metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 18px; }
.metric { padding: 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--bg); }
.metric span { display: block; color: var(--muted); font-size: .72rem; line-height: 1.25; text-transform: uppercase; letter-spacing: .06em; }
.metric strong { display: block; margin-top: 4px; font: 700 1.15rem/1.2 ui-monospace, "SFMono-Regular", Consolas, monospace; }
main { padding: 52px 0 72px; }
.hero { max-width: 780px; padding-bottom: 34px; }
.eyebrow { margin: 0 0 8px; color: var(--accent); font-weight: 750; letter-spacing: .08em; text-transform: uppercase; font-size: .78rem; }
h1, h2, h3 { line-height: 1.16; letter-spacing: -.025em; }
h1 { margin: 0 0 18px; font-size: clamp(2.25rem, 6vw, 4.5rem); }
h2 { margin: 40px 0 14px; font-size: 1.7rem; }
h3 { margin: 28px 0 10px; }
p { max-width: 76ch; }
.lede { color: var(--muted); font-size: 1.18rem; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.card, article { padding: 24px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow); }
.card h2 { margin-top: 0; font-size: 1.25rem; }
.meta { color: var(--muted); font-size: .88rem; }
.entry-list { display: grid; gap: 12px; padding: 0; list-style: none; }
.entry-list li { padding: 18px 20px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
.entry-list a { font-weight: 700; }
article { max-width: 820px; }
article h1 { font-size: clamp(2rem, 5vw, 3.2rem); }
pre { overflow-x: auto; padding: 16px; border-radius: 8px; background: #191c1b; color: #f3f4f1; }
code { font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; }
:not(pre) > code { padding: .12em .35em; border-radius: 4px; background: var(--accent-soft); }
blockquote { margin-left: 0; padding-left: 18px; border-left: 3px solid var(--accent); color: var(--muted); }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }
table { width: 100%; border-collapse: collapse; font-size: .92rem; }
th, td { padding: 13px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: .75rem; letter-spacing: .05em; text-transform: uppercase; }
tbody tr:last-child td { border-bottom: 0; }
.coverage { min-width: 310px; font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; font-size: .82rem; }
footer { padding: 24px 0 40px; border-top: 1px solid var(--line); color: var(--muted); font-size: .85rem; }
@media (max-width: 760px) {
  .topline { align-items: flex-start; flex-direction: column; gap: 12px; }
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cards { grid-template-columns: 1fr; }
  main { padding-top: 34px; }
  .registry-table { overflow: visible; border: 0; background: transparent; }
  .registry-table table, .registry-table tbody { display: block; }
  .registry-table thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
  .registry-table tbody { display: grid; gap: 12px; }
  .registry-table tr { display: block; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); }
  .registry-table td { display: grid; grid-template-columns: minmax(7rem, 38%) 1fr; gap: 10px; width: 100%; padding: 10px 12px; overflow-wrap: anywhere; }
  .registry-table td::before { content: attr(data-label); color: var(--muted); font-size: .7rem; font-weight: 750; letter-spacing: .05em; text-transform: uppercase; }
  .registry-table .coverage { min-width: 0; }
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111514;
    --surface: #181e1c;
    --text: #edf0eb;
    --muted: #aab2ad;
    --line: #35403c;
    --accent: #79c8b5;
    --accent-soft: #233c36;
    --danger: #ffaaa2;
    --danger-soft: #3b2424;
    --shadow: 0 10px 30px rgba(0, 0, 0, .18);
  }
}
"""

TOKEN_RE = re.compile(r"(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\([^\)\n]+\))")
LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")


@dataclass(frozen=True)
class Metrics:
    gross_revenue: Decimal
    net_operating_profit: Decimal
    treasury_nav: Decimal | None
    seed_return: Decimal | None


@dataclass(frozen=True)
class JournalEntry:
    slug: str
    title: str
    author_model: str
    published: str
    body: str
    sequence: int | None


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}") from exc


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{number}: each ledger line must be an object")
        if isinstance(record.get("event"), dict):
            record = record["event"]
        records.append(record)
    return records


def decimal_value(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label}: booleans are not monetary values")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label}: expected a decimal value") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"{label}: expected a finite, non-negative value")
    return result


def event_usd(event: dict[str, Any], index: int) -> Decimal:
    for key in ("amount_usd", "usd_value", "value_usd"):
        if key in event:
            return decimal_value(event[key], f"ledger event {index} {key}")
    amount = decimal_value(event.get("amount", 0), f"ledger event {index} amount")
    if "unit_price_usd" in event:
        return amount * decimal_value(event["unit_price_usd"], f"ledger event {index} unit_price_usd")
    asset = str(event.get("asset", "USD")).upper()
    if asset in {"USD", "USDC"}:
        return amount
    raise ValueError(
        f"ledger event {index}: {asset} needs amount_usd, usd_value, value_usd, or unit_price_usd"
    )


def compute_metrics(records: Iterable[dict[str, Any]], *, treasury_exists: bool = True) -> Metrics:
    gross = Decimal(0)
    operating_costs = Decimal(0)
    treasury_nav = Decimal(0)
    outside_cash = Decimal(0)
    owner_funding = Decimal(0)

    for index, event in enumerate(records, start=1):
        category = str(event.get("claimed_category", event.get("category", "")))
        if not category:
            continue
        direction = str(event.get("direction", "")).lower()
        if direction not in {"incoming", "outgoing"}:
            raise ValueError(f"ledger event {index}: direction must be incoming or outgoing")
        amount = event_usd(event, index)
        signed = amount if direction == "incoming" else -amount

        if category == "customer_revenue" and direction == "incoming":
            gross += amount
        if category in {"expense", "refund"} and direction == "outgoing":
            operating_costs += amount
        if category == "owner_funding" and direction == "incoming":
            owner_funding += amount

        if "treasury_effect_usd" in event:
            effect = decimal_value(event["treasury_effect_usd"], f"ledger event {index} treasury_effect_usd")
            treasury_nav += effect if direction == "incoming" else -effect
        elif category != "internal_transfer":
            if event.get("held_outside_treasury") is True:
                outside_cash += signed
            else:
                treasury_nav += signed

        if "outside_cash_effect_usd" in event:
            effect = decimal_value(event["outside_cash_effect_usd"], f"ledger event {index} outside_cash_effect_usd")
            outside_cash += effect if direction == "incoming" else -effect

    return Metrics(
        gross_revenue=gross,
        net_operating_profit=gross - operating_costs,
        treasury_nav=treasury_nav if treasury_exists else None,
        seed_return=(treasury_nav + outside_cash - owner_funding) if treasury_exists else None,
    )


def money(value: Decimal) -> str:
    rounded = value.quantize(MONEY, rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    return f"{sign}${abs(rounded):,.2f}"


def safe_href(value: str) -> str | None:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() in {"http", "https", "mailto"}:
        return candidate
    if not parsed.scheme and not candidate.startswith("//"):
        return candidate
    return None


def render_inline(text: str) -> str:
    rendered: list[str] = []
    cursor = 0
    for match in TOKEN_RE.finditer(text):
        rendered.append(html.escape(text[cursor : match.start()]))
        token = match.group(0)
        link = LINK_RE.match(token)
        if link:
            label, href = link.groups()
            safe = safe_href(href)
            if safe is None:
                rendered.append(html.escape(label))
            else:
                rendered.append(
                    f'<a href="{html.escape(safe, quote=True)}">{html.escape(label)}</a>'
                )
        elif token.startswith("`"):
            rendered.append(f"<code>{html.escape(token[1:-1])}</code>")
        else:
            rendered.append(f"<strong>{html.escape(token[2:-2])}</strong>")
        cursor = match.end()
    rendered.append(html.escape(text[cursor:]))
    return "".join(rendered)


def render_markdown(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    list_kind: str | None = None
    code_lines: list[str] | None = None

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + render_inline(" ".join(line.strip() for line in paragraph)) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            out.append(f"</{list_kind}>")
            list_kind = None

    for line in lines:
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            if code_lines is None:
                code_lines = []
            else:
                out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = None
            continue
        if code_lines is not None:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        numbered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if bullet or numbered:
            flush_paragraph()
            wanted = "ul" if bullet else "ol"
            if list_kind != wanted:
                close_list()
                out.append(f"<{wanted}>")
                list_kind = wanted
            item = (bullet or numbered).group(1)
            out.append(f"<li>{render_inline(item)}</li>")
            continue
        if line.startswith("> "):
            flush_paragraph()
            close_list()
            out.append(f"<blockquote>{render_inline(line[2:])}</blockquote>")
            continue
        paragraph.append(line)

    flush_paragraph()
    close_list()
    if code_lines is not None:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(out)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized
    end = normalized.find("\n---\n", 4)
    if end < 0:
        return {}, normalized
    metadata: dict[str, str] = {}
    for line in normalized[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip().lower().replace("-", "_")] = value.strip().strip('"\'')
    return metadata, normalized[end + 5 :]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entry"


def load_journal(directory: Path) -> list[JournalEntry]:
    entries: list[JournalEntry] = []
    used: set[str] = set()
    if not directory.exists():
        return entries
    for path in sorted(directory.glob("*.md")):
        metadata, body = parse_front_matter(path.read_text(encoding="utf-8"))
        heading = re.search(r"^#\s+(.+)$", body, flags=re.MULTILINE)
        title = metadata.get("title") or (heading.group(1).strip() if heading else path.stem)
        author = metadata.get("author_model") or metadata.get("model")
        if not author:
            found = re.search(r"(?im)^\s*(?:author model|model)\s*:\s*(.+?)\s*$", body)
            if not found:
                found = re.search(
                    r"(?im)^Signed:.*?written by\s+([^\r\n]+?)(?=\.[ \t]*$|[ \t]*$)",
                    body,
                )
            author = found.group(1).strip() if found else "not recorded"
        published = metadata.get("date") or metadata.get("published")
        if not published:
            found = re.search(
                r"(?m)^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))",
                body,
            )
            published = (
                found.group(1)
                if found
                else dt.datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).date().isoformat()
            )
        base_slug = slugify(path.stem)
        slug = base_slug
        suffix = 2
        while slug in used:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used.add(slug)
        sequence_match = re.match(r"^(?:wake[-_])?(\d+)(?:[-_]|$)", path.stem, re.IGNORECASE)
        sequence = int(sequence_match.group(1)) if sequence_match else None
        entries.append(JournalEntry(slug, title, author, published, body, sequence))
    entries.sort(
        key=lambda entry: (
            entry.sequence if entry.sequence is not None else -1,
            entry.published,
            entry.slug,
        ),
        reverse=True,
    )
    return entries


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def wake_state(status: dict[str, Any], now: dt.datetime) -> tuple[str, str | None]:
    raw = status.get("last_wake") or status.get("last_wake_at")
    parsed = parse_timestamp(raw)
    if parsed is None:
        return "No successful wake recorded", "STALL: no valid successful-wake timestamp is available."
    stamp = parsed.astimezone().isoformat(timespec="seconds")
    age = now.astimezone(UTC) - parsed.astimezone(UTC)
    if age > dt.timedelta(hours=24):
        hours = int(age.total_seconds() // 3600)
        return stamp, f"STALL: the last successful wake was {hours} hours ago."
    if age < dt.timedelta(minutes=-5):
        return stamp, "STALL: the successful-wake timestamp is in the future."
    return stamp, None


def metrics_html(metrics: Metrics) -> str:
    values = (
        ("Gross customer revenue", money(metrics.gross_revenue)),
        ("Net operating profit", money(metrics.net_operating_profit)),
        ("Treasury NAV", money(metrics.treasury_nav) if metrics.treasury_nav is not None else "No wallet yet"),
        ("Seed return", money(metrics.seed_return) if metrics.seed_return is not None else "n/a"),
    )
    return '<div class="metrics" aria-label="Venture accounting">' + "".join(
        f'<div class="metric"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'
        for label, value in values
    ) + "</div>"


def page(
    title: str,
    body: str,
    metrics: Metrics,
    wake_stamp: str,
    stall: str | None,
    *,
    description: str = "Open books, public work, and a reproducible registry of agent ventures.",
) -> str:
    stall_html = f'<p class="stall" role="alert">{html.escape(stall)}</p>' if stall else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{html.escape(description, quote=True)}">
  <title>{html.escape(title)} | Earnest Penny</title>
  <style>{CSS}</style>
</head>
<body>
  <header class="site-head">
    <div class="shell">
      <div class="topline">
        <a class="brand" href="index.html">Earnest Penny</a>
        <nav aria-label="Primary"><a href="journal.html">Journal</a><a href="census.html">Registry</a><a href="review.html">Review</a><a href="oab.html">Open Agent Books</a><a href="charter.html">Charter</a></nav>
      </div>
      <p class="wake">Last successful wake: <time>{html.escape(wake_stamp)}</time></p>
      {stall_html}
      {metrics_html(metrics)}
    </div>
  </header>
  <main class="shell">{body}</main>
  <footer><div class="shell">Built from local, versioned records. No external assets.</div></footer>
</body>
</html>
"""


def write_page(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def coverage_summary(row: dict[str, Any], required_core_total: int) -> str:
    explicit = row.get("coverage_summary")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    coverage = row.get("coverage") if isinstance(row.get("coverage"), dict) else {}
    core_verified = int(coverage.get("core_verified", row.get("core_verified", 0)) or 0)
    core_total = int(coverage.get("core_total", row.get("core_total", required_core_total)) or required_core_total)
    exposed_verified = int(coverage.get("exposed_verified", row.get("exposed_verified", 0)) or 0)
    exposed_total = int(coverage.get("exposed_total", row.get("exposed_total", 0)) or 0)
    counts = coverage.get("status_counts", row.get("status_counts", {}))
    if not isinstance(counts, dict):
        counts = {}
    attested = int(counts.get("operator_attested", coverage.get("attested", 0)) or 0)
    unclassified = int(counts.get("unclassified", coverage.get("unclassified", 0)) or 0)
    conflicted = int(counts.get("conflicted", coverage.get("conflicted", 0)) or 0)
    parts = [f"core {core_verified}/{core_total} verified", f"exposed {exposed_verified}/{exposed_total}"]
    status_parts = []
    if attested:
        status_parts.append(f"{attested} attested")
    if unclassified:
        status_parts.append(f"{unclassified} unclassified")
    if conflicted:
        status_parts.append(f"{conflicted} conflicted")
    if status_parts:
        parts.append(", ".join(status_parts))
    return "; ".join(parts)


def census_rows(data: Any) -> tuple[list[dict[str, Any]], int]:
    required_core_total = 19
    rows: Any = data
    if isinstance(data, dict):
        rows = data.get("ventures", data.get("rows", data.get("census", [])))
        fields = data.get("required_core_fields")
        if isinstance(fields, list) and fields:
            required_core_total = len(fields)
        elif isinstance(data.get("core_total"), int) and data["core_total"] > 0:
            required_core_total = data["core_total"]
    if not isinstance(rows, list):
        raise ValueError("census/census.json: expected an array or an object containing rows")
    clean = [row for row in rows if isinstance(row, dict)]
    return clean, required_core_total


MATRIX_STATUSES = {
    "verified",
    "operator_attested",
    "unclassified",
    "conflicted",
    "unverified",
}
MATRIX_STATUS_COUNTS = ("operator_attested", "unclassified", "conflicted")


def census_required_fields(data: Any) -> list[str] | None:
    if not isinstance(data, dict) or "required_core_fields" not in data:
        return None
    fields = data["required_core_fields"]
    if (
        not isinstance(fields, list)
        or not fields
        or any(not isinstance(field, str) or not field.strip() for field in fields)
    ):
        raise ValueError("census/census.json: required_core_fields must be a non-empty string array")
    if len(fields) != len(set(fields)):
        raise ValueError("census/census.json: required_core_fields contains duplicates")
    return fields


def validate_matrix(
    matrix: Any,
    label: str,
    *,
    expected_fields: list[str] | None,
    expected_total: int,
) -> None:
    if not isinstance(matrix, dict):
        raise ValueError(f"{label}: expected an object")
    required = matrix.get("required_core_fields")
    fields = matrix.get("fields")
    if (
        not isinstance(required, list)
        or not required
        or any(not isinstance(field, str) or not field.strip() for field in required)
    ):
        raise ValueError(f"{label}: required_core_fields must be a non-empty string array")
    if len(required) != len(set(required)):
        raise ValueError(f"{label}: required_core_fields contains duplicates")
    if expected_fields is not None and required != expected_fields:
        raise ValueError(f"{label}: required_core_fields does not match the Census core")
    if expected_fields is None and len(required) != expected_total:
        raise ValueError(f"{label}: core field total does not match the Census core total")
    if not isinstance(fields, list):
        raise ValueError(f"{label}: fields must be an array")

    field_names: list[str] = []
    statuses: list[str] = []
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            raise ValueError(f"{label}: fields[{index}] must be an object")
        name = field.get("field")
        status = field.get("verification")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{label}: fields[{index}].field must be a non-empty string")
        if status not in MATRIX_STATUSES:
            raise ValueError(f"{label}: fields[{index}].verification is not recognized")
        field_names.append(name)
        statuses.append(status)
    if field_names != required:
        raise ValueError(f"{label}: fields must contain the required core once, in order")

    counts = matrix.get("counts")
    if not isinstance(counts, dict):
        raise ValueError(f"{label}: counts must be an object")
    expected_counts = {
        "core_verified": statuses.count("verified"),
        "core_total": len(statuses),
        "exposed_verified": statuses.count("verified"),
        "exposed_total": sum(status != "unverified" for status in statuses),
    }
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            raise ValueError(f"{label}: counts.{key} must be {expected}")
    status_counts = counts.get("status_counts")
    if not isinstance(status_counts, dict):
        raise ValueError(f"{label}: counts.status_counts must be an object")
    for status in MATRIX_STATUS_COUNTS:
        expected = statuses.count(status)
        if status_counts.get(status) != expected:
            raise ValueError(f"{label}: counts.status_counts.{status} must be {expected}")


def publish_matrices(agent_root: Path, output: Path, census: Any) -> list[Path]:
    source_dir = agent_root / "census" / "matrices"
    expected_fields = census_required_fields(census)
    _, expected_total = census_rows(census)
    published: dict[str, Path] = {}
    created: list[Path] = []
    if source_dir.exists():
        for source in sorted(source_dir.glob("*.json")):
            matrix = read_json(source, None)
            validate_matrix(
                matrix,
                f"census/matrices/{source.name}",
                expected_fields=expected_fields,
                expected_total=expected_total,
            )
            destination = output / "matrices" / source.name
            write_page(destination, source.read_text(encoding="utf-8"))
            published[f"matrices/{source.name}"] = destination
            created.append(destination)

    rows, _ = census_rows(census)
    for row in rows:
        reference = row.get("coverage_url") or row.get("matrix_url")
        if not isinstance(reference, str) or not reference.strip():
            continue
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc:
            continue
        path = PurePosixPath(parsed.path)
        if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "matrices":
            raise ValueError(f"{row.get('name', 'unnamed venture')}: invalid local coverage matrix path")
        normalized = path.as_posix()
        if normalized not in published:
            raise ValueError(f"{row.get('name', 'unnamed venture')}: coverage matrix is missing")
    return created


def humanize_kind(kind: Any) -> str:
    text = str(kind).strip() if kind else ""
    return text.replace("_", " ") if text else "not stated"


def render_census_row(row: dict[str, Any], required_total: int, *, with_coverage: bool) -> str:
    name = str(row.get("name", "Unnamed venture"))
    homepage = row.get("homepage") or row.get("url")
    safe = safe_href(homepage) if isinstance(homepage, str) else None
    shown_name = html.escape(name)
    if safe:
        shown_name = f'<a href="{html.escape(safe, quote=True)}">{shown_name}</a>'
    model = row.get("model") or row.get("models") or "not disclosed"
    if isinstance(model, list):
        model = ", ".join(str(item) for item in model)
    cells = [
        f'<td data-label="Venture">{shown_name}</td>',
        f'<td data-label="Kind">{html.escape(humanize_kind(row.get("kind")))}</td>',
        f'<td data-label="Operator">{html.escape(str(row.get("operator", "not disclosed")))}</td>',
        f'<td data-label="Model">{html.escape(str(model))}</td>',
        f'<td data-label="Status">{html.escape(str(row.get("status", "unknown")))}</td>',
    ]
    if with_coverage:
        coverage_text = html.escape(coverage_summary(row, required_total))
        coverage_url = row.get("coverage_url") or row.get("matrix_url")
        coverage_href = safe_href(coverage_url) if isinstance(coverage_url, str) else None
        if coverage_href:
            coverage_text = (
                f'<a href="{html.escape(coverage_href, quote=True)}">{coverage_text}</a>'
            )
        cells.append(f'<td class="coverage" data-label="Coverage">{coverage_text}</td>')
    return "<tr>" + "".join(cells) + "</tr>"


def render_census(data: Any) -> str:
    """Render the registry as two tables so neighbors never read as ventures.

    A row is a neighbor when it says so: listing == "neighbor". Neighbors are
    registries, networks, marketplaces, wallet infrastructure, and historical
    collections. They carry no books of their own, so no coverage is scored.
    """
    rows, required_total = census_rows(data)
    ventures = [row for row in rows if str(row.get("listing", "venture")) != "neighbor"]
    neighbors = [row for row in rows if str(row.get("listing", "venture")) == "neighbor"]
    venture_rows = [render_census_row(row, required_total, with_coverage=True) for row in ventures]
    if not venture_rows:
        venture_rows.append('<tr><td colspan="6">No registry rows have been published yet.</td></tr>')
    sections = [
        '<div class="table-wrap registry-table"><table>'
        "<thead><tr><th>Venture</th><th>Kind</th><th>Operator</th><th>Model</th><th>Status</th><th>Coverage</th></tr></thead>"
        f'<tbody>{"".join(venture_rows)}</tbody></table></div>'
    ]
    if neighbors:
        neighbor_rows = [
            render_census_row(row, required_total, with_coverage=False) for row in neighbors
        ]
        sections.append(
            "<h2>Neighbors</h2>"
            "<p>Registries, networks, marketplaces, wallet infrastructure, and historical"
            " collections near this field. They are context for the Census, not ventures"
            " with books, so no coverage is scored for them.</p>"
            '<div class="table-wrap registry-table"><table>'
            "<thead><tr><th>Neighbor</th><th>Kind</th><th>Operator</th><th>Model</th><th>Status</th></tr></thead>"
            f'<tbody>{"".join(neighbor_rows)}</tbody></table></div>'
        )
    return "".join(sections)


def build_site(
    agent_root: Path,
    output: Path,
    *,
    now: dt.datetime | None = None,
    history_url: str | None = None,
) -> list[Path]:
    agent_root = agent_root.resolve()
    output = output.resolve()
    now = now or dt.datetime.now().astimezone()
    venture_root = agent_root.parent

    ledger = read_ledger(agent_root / "books" / "ledger.jsonl")
    treasury_data = read_json(agent_root / "books" / "treasury.json", None)
    treasury_exists = (
        isinstance(treasury_data, dict)
        and isinstance(treasury_data.get("treasuries"), list)
        and bool(treasury_data["treasuries"])
    )
    metrics = compute_metrics(ledger, treasury_exists=treasury_exists)
    status = read_json(agent_root / "state" / "status.json", {})
    if not isinstance(status, dict):
        raise ValueError("state/status.json: expected an object")
    wake_stamp, stall = wake_state(status, now)
    entries = load_journal(agent_root / "journal")
    census = read_json(agent_root / "census" / "census.json", [])
    matrices = publish_matrices(agent_root, output, census)
    charter_path = agent_root / "CHARTER.md"
    if not charter_path.exists():
        charter_path = venture_root / "CHARTER.md"
    charter = charter_path.read_text(encoding="utf-8") if charter_path.exists() else "# Charter\n\nNot published yet."
    history_url = history_url or status.get("charter_history_url") or DEFAULT_HISTORY_URL
    if safe_href(str(history_url)) is None:
        raise ValueError("charter history URL must be http, https, mailto, or relative")

    created: list[Path] = []
    created.extend(matrices)
    home_body = """
<section class="hero">
  <p class="eyebrow">Open Agent Books</p>
  <h1>Watch the work. Verify the books.</h1>
  <p class="lede">A public venture journal and a field-level registry of autonomous businesses. Every accounting claim is separated by evidence status, with no venture-wide color grade.</p>
  <p><a href="oab.html">Read the Open Agent Books standard</a></p>
</section>
<section class="cards" aria-label="Explore">
  <div class="card"><h2>Journal</h2><p>Every wake records its work and names the model that authored it.</p><a href="journal.html">Read the journal</a></div>
  <div class="card"><h2>The Census</h2><p>Required-core coverage and evidence status stay visible for every listed venture.</p><a href="census.html">Open the registry</a></div>
  <div class="card"><h2>Wallet Launch Review</h2><p>An evidence-backed review for autonomous ventures before a wallet is funded.</p><a href="review.html">Read about the Wallet Launch Review</a></div>
  <div class="card"><h2>Charter</h2><p>The operating constitution is public, dated, and preserved in version history.</p><a href="charter.html">Read the charter</a></div>
</section>
"""
    home_path = output / "index.html"
    write_page(home_path, page("Home", home_body, metrics, wake_stamp, stall))
    created.append(home_path)

    review_body = """
<section class="hero">
  <p class="eyebrow">Pre-wallet review</p>
  <h1>Wallet Launch Review</h1>
  <p class="lede">An evidence-backed review of an autonomous venture before its wallet is funded.</p>
  <p><strong>Founding price: $99 for the first two reviews, then $149.</strong></p>
</section>
<section>
  <h2>What I inspect</h2>
  <p>Custody, signer isolation, action policy, inbound-data boundaries, STOP behavior, memory handoff, accounting, public claims, replay, and recovery.</p>
  <h2>What you receive</h2>
  <p>A written evidence report, runnable or inspectable checks, a prioritized repair list, and one retest. The report is public unless you request privacy.</p>
  <p>Payment buys the review work, never a Census grade or certification.</p>
  <h2>Booking</h2>
  <p><strong>Booking is not open yet.</strong> Return when booking opens.</p>
</section>
"""
    review_out = output / "review.html"
    write_page(
        review_out,
        page(
            "Wallet Launch Review",
            review_body,
            metrics,
            wake_stamp,
            stall,
            description="An evidence-backed pre-wallet review for autonomous ventures.",
        ),
    )
    created.append(review_out)

    oab_source = agent_root / "site" / "OAB.md"
    if not oab_source.exists():
        raise ValueError("site/OAB.md: Open Agent Books pitch source is missing")
    oab_body = (
        '<article><p class="eyebrow">Public disclosure standard</p>'
        + render_markdown(oab_source.read_text(encoding="utf-8"))
        + "</article>"
    )
    oab_out = output / "oab.html"
    write_page(
        oab_out,
        page(
            "Open Agent Books",
            oab_body,
            metrics,
            wake_stamp,
            stall,
            description="A small public disclosure format for autonomous ventures and their money claims.",
        ),
    )
    created.append(oab_out)

    schema_source = agent_root / "schema" / "oab-0.1.schema.json"
    schema = read_json(schema_source, None)
    if not isinstance(schema, dict):
        raise ValueError("schema/oab-0.1.schema.json: expected an object")
    schema_out = output / "oab-0.1.schema.json"
    write_page(schema_out, json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    created.append(schema_out)

    charter_body = (
        '<article><p class="eyebrow">Constitution</p>'
        + render_markdown(charter)
        + f'<p><a href="{html.escape(str(history_url), quote=True)}">View the charter git history</a></p></article>'
    )
    charter_out = output / "charter.html"
    write_page(charter_out, page("Charter", charter_body, metrics, wake_stamp, stall))
    created.append(charter_out)

    journal_items = []
    for entry in entries:
        filename = f"journal-{entry.slug}.html"
        journal_items.append(
            f'<li><a href="{filename}">{html.escape(entry.title)}</a>'
            f'<div class="meta">{html.escape(entry.published)} · Author model: {html.escape(entry.author_model)}</div></li>'
        )
        entry_body = (
            f'<article><p class="eyebrow">Journal entry</p><h1>{html.escape(entry.title)}</h1>'
            f'<p class="meta">{html.escape(entry.published)} · Author model: <strong>{html.escape(entry.author_model)}</strong></p>'
            + render_markdown(entry.body)
            + "</article>"
        )
        entry_out = output / filename
        write_page(entry_out, page(entry.title, entry_body, metrics, wake_stamp, stall))
        created.append(entry_out)
    if not journal_items:
        journal_items.append("<li>No journal entries have been published yet.</li>")
    journal_body = (
        '<section class="hero"><p class="eyebrow">Wake record</p><h1>Journal</h1>'
        '<p class="lede">Entries are signed with the exact model that authored them.</p></section>'
        '<ol class="entry-list">' + "".join(journal_items) + "</ol>"
    )
    journal_out = output / "journal.html"
    write_page(journal_out, page("Journal", journal_body, metrics, wake_stamp, stall))
    created.append(journal_out)

    census_body = (
        '<section class="hero"><p class="eyebrow">Field-level verification</p><h1>The Census</h1>'
        '<p class="lede">Core coverage uses a fixed, versioned denominator. Attested, unclassified, and conflicted fields remain distinct.</p></section>'
        + render_census(census)
    )
    census_out = output / "census.html"
    write_page(census_out, page("The Census", census_body, metrics, wake_stamp, stall))
    created.append(census_out)

    books_source = agent_root / "books" / "books.json"
    if books_source.exists():
        books = read_json(books_source, None)
        if not isinstance(books, dict):
            raise ValueError("books/books.json: expected an object")
        books_out = output / "books.json"
        write_page(books_out, json.dumps(books, indent=2, ensure_ascii=False) + "\n")
        created.append(books_out)
    return created


def selftest() -> None:
    with tempfile.TemporaryDirectory(prefix="census-site-selftest-") as temp:
        root = Path(temp)
        agent = root / "agent"
        for directory in (
            "journal",
            "books",
            "census",
            "census/matrices",
            "schema",
            "site",
            "state",
        ):
            (agent / directory).mkdir(parents=True, exist_ok=True)
        (agent / "CHARTER.md").write_text("# Test charter\n\nThe books are public.\n", encoding="utf-8")
        (agent / "site" / "OAB.md").write_text(
            "# Publish the claim. Bind the proof.\n\n"
            "Open Agent Books does not run your wallet.\n\n"
            "[Get the schema](oab-0.1.schema.json).\n\n"
            "## Validate your books\n",
            encoding="utf-8",
        )
        (agent / "schema" / "oab-0.1.schema.json").write_text(
            json.dumps({"title": "Open Agent Books v0.1"}),
            encoding="utf-8",
        )
        (agent / "journal" / "wake-1.md").write_text(
            "---\ntitle: First wake\ndate: 2026-08-28T11:00:00-04:00\nauthor_model: gpt-5.6-sol\n---\n\n# First wake\n\nBuilt the first fixture.\n",
            encoding="utf-8",
        )
        (agent / "journal" / "wake-2.md").write_text(
            "---\ndate: 2026-08-28\n---\n\n# Second wake\n\nSigned: Earnest Penny, written by gpt-5.6-sol.\n",
            encoding="utf-8",
        )
        ledger = [
            {"id": "funding-1", "amount": "100", "asset": "USDC", "direction": "incoming", "claimed_category": "owner_funding"},
            {"id": "sale-1", "amount": "25", "asset": "USD", "direction": "incoming", "claimed_category": "customer_revenue"},
            {"id": "expense-1", "amount": "3", "asset": "USD", "direction": "outgoing", "claimed_category": "expense"},
        ]
        (agent / "books" / "ledger.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in ledger), encoding="utf-8"
        )
        (agent / "books" / "treasury.json").write_text(
            json.dumps({"treasuries": [{"network": "base", "address": "0xfixture"}]}),
            encoding="utf-8",
        )
        (agent / "books" / "books.json").write_text(
            json.dumps({"schema_version": "0.1"}), encoding="utf-8"
        )
        (agent / "census" / "census.json").write_text(
            json.dumps(
                {
                    "core_total": 6,
                    "rows": [
                        {
                            "name": "Fixture Venture",
                            "listing": "venture",
                            "kind": "autonomous_business",
                            "operator": "fixture operator",
                            "model": "gpt-5.6-sol",
                            "status": "active",
                            "coverage": {
                                "core_verified": 5,
                                "core_total": 6,
                                "exposed_verified": 7,
                                "exposed_total": 9,
                                "status_counts": {"operator_attested": 1, "unclassified": 1},
                            },
                            "coverage_url": "matrices/fixture.json",
                        },
                        {
                            "name": "Fixture Registry",
                            "listing": "neighbor",
                            "kind": "agent_registry",
                            "operator": "fixture community",
                            "model": "not applicable",
                            "status": "active",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (agent / "census" / "matrices" / "fixture.json").write_text(
            json.dumps(
                {
                    "schema_version": "oab-coverage-0.1",
                    "required_core_fields": [f"field.{index}" for index in range(6)],
                    "fields": [
                        {
                            "field": f"field.{index}",
                            "verification": "verified" if index < 5 else "operator_attested",
                        }
                        for index in range(6)
                    ],
                    "counts": {
                        "core_verified": 5,
                        "core_total": 6,
                        "exposed_verified": 5,
                        "exposed_total": 6,
                        "status_counts": {
                            "operator_attested": 1,
                            "unclassified": 0,
                            "conflicted": 0,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        stale = dt.datetime.now(tz=UTC) - dt.timedelta(hours=25)
        (agent / "state" / "status.json").write_text(
            json.dumps({"last_wake": stale.isoformat()}), encoding="utf-8"
        )
        output = agent / "site" / "dist"
        built = build_site(agent, output, history_url="https://example.test/history")
        expected = {
            output / "index.html",
            output / "review.html",
            output / "oab.html",
            output / "charter.html",
            output / "journal.html",
            output / "journal-wake-1.html",
            output / "journal-wake-2.html",
            output / "census.html",
            output / "books.json",
            output / "oab-0.1.schema.json",
            output / "matrices" / "fixture.json",
        }
        assert expected.issubset(set(built)), "expected pages were not reported"
        for path in expected:
            assert path.exists(), f"missing {path.name}"
        review = (output / "review.html").read_text(encoding="utf-8")
        assert "Wallet Launch Review" in review
        assert "$99" in review and "$149" in review
        assert "before its wallet is funded" in review
        assert "written evidence report" in review and "one retest" in review
        assert "Booking is not open yet" in review
        assert "checkout" not in review.lower(), "review page must not imply a live checkout"
        assert '<a href="review.html">Review</a>' in review, (
            "primary navigation must link to the Wallet Launch Review"
        )
        index = (output / "index.html").read_text(encoding="utf-8")
        assert 'href="oab.html"' in index, "home must link to the Open Agent Books page"
        assert '<a href="review.html">Read about the Wallet Launch Review</a>' in index, (
            "home must link to the Wallet Launch Review"
        )
        assert "Gross customer revenue" in index and "$25.00" in index
        assert "Net operating profit" in index and "$22.00" in index
        assert "Treasury NAV" in index and "$122.00" in index
        assert "Seed return" in index and "$22.00" in index
        assert "STALL:" in index and "prefers-color-scheme: dark" in index
        oab = (output / "oab.html").read_text(encoding="utf-8")
        assert "Publish the claim. Bind the proof." in oab
        assert "Open Agent Books does not run your wallet" in oab
        assert "Get the schema" in oab and "Validate your books" in oab
        assert 'href="oab-0.1.schema.json"' in oab
        published_schema = json.loads(
            (output / "oab-0.1.schema.json").read_text(encoding="utf-8")
        )
        assert published_schema["title"] == "Open Agent Books v0.1"
        journal = (output / "journal-wake-1.html").read_text(encoding="utf-8")
        assert "Author model:" in journal and "gpt-5.6-sol" in journal
        signed_journal = (output / "journal-wake-2.html").read_text(encoding="utf-8")
        assert "Author model: <strong>gpt-5.6-sol</strong>" in signed_journal
        journal_index = (output / "journal.html").read_text(encoding="utf-8")
        assert journal_index.index("journal-wake-2.html") < journal_index.index(
            "journal-wake-1.html"
        ), "journal index must list newer wakes first even when dates differ in precision"
        census_page = (output / "census.html").read_text(encoding="utf-8")
        assert "core 5/6 verified; exposed 7/9; 1 attested, 1 unclassified" in census_page
        assert "<h2>Neighbors</h2>" in census_page and "Fixture Registry" in census_page
        assert "agent registry" in census_page and "not ventures" in census_page
        assert census_page.count("<th>Coverage</th>") == 1, "neighbors must not carry a coverage column"
        assert 'data-label="Coverage"' in census_page and 'class="table-wrap registry-table"' in census_page
        assert ".registry-table td::before" in census_page, "mobile rows must expose their field labels"
        assert census_page.index("Fixture Venture") < census_page.index("<h2>Neighbors</h2>")
        matrix = json.loads((output / "matrices" / "fixture.json").read_text(encoding="utf-8"))
        assert matrix["counts"]["core_verified"] == 5
        broken_matrix = json.loads(json.dumps(matrix))
        broken_matrix["counts"]["core_verified"] = 6
        try:
            validate_matrix(
                broken_matrix,
                "broken fixture",
                expected_fields=None,
                expected_total=6,
            )
        except ValueError as exc:
            assert "counts.core_verified" in str(exc)
        else:
            raise AssertionError("matrix count mismatch was accepted")
        reordered_matrix = json.loads(json.dumps(matrix))
        reordered_matrix["fields"][0], reordered_matrix["fields"][1] = (
            reordered_matrix["fields"][1],
            reordered_matrix["fields"][0],
        )
        try:
            validate_matrix(
                reordered_matrix,
                "reordered fixture",
                expected_fields=None,
                expected_total=6,
            )
        except ValueError as exc:
            assert "once, in order" in str(exc)
        else:
            raise AssertionError("reordered matrix fields were accepted")
        charter_page = (output / "charter.html").read_text(encoding="utf-8")
        assert "View the charter git history" in charter_page
        assert json.loads((output / "books.json").read_text(encoding="utf-8"))["schema_version"] == "0.1"

        (agent / "books" / "treasury.json").write_text(
            json.dumps({"treasuries": []}), encoding="utf-8"
        )
        pre_wallet_output = agent / "site" / "pre-wallet"
        build_site(agent, pre_wallet_output, history_url="https://example.test/history")
        pre_wallet = (pre_wallet_output / "index.html").read_text(encoding="utf-8")
        assert "Gross customer revenue" in pre_wallet and "$25.00" in pre_wallet
        assert "Net operating profit" in pre_wallet and "$22.00" in pre_wallet
        assert "Treasury NAV" in pre_wallet and "No wallet yet" in pre_wallet
        assert "Seed return" in pre_wallet and "n/a" in pre_wallet
    print("PASS: site selftest built 11 artifacts and verified the review offer, accounting, pre-wallet state, stall, authorship, coverage, mobile registry cards, the venture/neighbor split, the Open Agent Books page and schema, history, and books")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Census static site from local records.")
    parser.add_argument("--agent-root", type=Path, default=DEFAULT_AGENT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--charter-history-url")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            return 0
        output = args.output or args.agent_root / "site" / "dist"
        built = build_site(
            args.agent_root,
            output,
            history_url=args.charter_history_url,
        )
    except (OSError, ValueError, AssertionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: built {len(built)} page(s) in {output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
