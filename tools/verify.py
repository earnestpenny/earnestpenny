#!/usr/bin/env python3
"""Recompute and verify this venture's public Open Agent Books claims.

Default inputs, relative to the agent directory:

* books/ledger.jsonl, one OAB monetary event per line (or {"event": ...})
* books/treasury.json, with a ``treasuries`` array

A treasury entry uses ``network``, ``address``, and ``assets``. Optional
``opening_balances`` and ``tolerances`` objects are keyed by asset. Example:

    {"treasuries": [{"network": "base", "address": "0x...",
      "assets": ["ETH", "USDC"], "opening_balances": {"USDC": "0"}}]}

An absent ledger and absent treasury config describe a new venture with no events;
that state passes honestly without making a network request.
"""

from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib import error, request
from urllib.parse import urlsplit

TOOLS_ROOT = Path(__file__).resolve().parent
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from census.census_refresh import (
    BASE_RPC,
    SOLANA_RPC,
    RpcError,
    fetch_base_balances,
    fetch_solana_balances,
)


AGENT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = AGENT_ROOT / "books" / "ledger.jsonl"
DEFAULT_TREASURY = AGENT_ROOT / "books" / "treasury.json"
USER_AGENT = "OpenAgentBooksVerifier/0.1 (+https://github.com/)"
REQUIRED_EVENT_FIELDS = {
    "id",
    "timestamp",
    "amount",
    "asset",
    "direction",
    "source",
    "destination",
    "claimed_category",
    "evidence",
    "status",
}
STATUSES = {"chain_verified", "receipt_bound", "operator_attested", "unclassified", "conflicted"}
EVIDENCE_TYPES = {"chain_transaction", "receipt", "invoice", "operator_statement", "other"}
STATUS_EVIDENCE = {
    "chain_verified": {"chain_transaction"},
    "receipt_bound": {"receipt", "invoice"},
    "operator_attested": {"operator_statement"},
    "unclassified": EVIDENCE_TYPES,
    "conflicted": EVIDENCE_TYPES,
}
NETWORK_ALIASES = {
    "solana": "solana",
    "solana-mainnet": "solana",
    "solana_mainnet": "solana",
    "base": "base",
    "base-mainnet": "base",
    "base_mainnet": "base",
}
DEFAULT_ASSETS = {"solana": ["SOL", "USDC"], "base": ["ETH", "USDC"]}


class VerificationError(ValueError):
    pass


class Reporter:
    def __init__(self) -> None:
        self.failures = 0

    def passed(self, claim: str, reason: str) -> None:
        print(f"PASS {claim}: {reason}")

    def failed(self, claim: str, reason: str) -> None:
        self.failures += 1
        print(f"FAIL {claim}: {reason}")


def decimal_value(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise VerificationError(f"{label} is not a decimal")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise VerificationError(f"{label} is not a decimal") from exc
    if not result.is_finite() or result < 0:
        raise VerificationError(f"{label} must be finite and non-negative")
    return result


def normalized_network(value: Any) -> str:
    if not isinstance(value, str) or value.strip().lower() not in NETWORK_ALIASES:
        raise VerificationError(f"unsupported network {value!r}")
    return NETWORK_ALIASES[value.strip().lower()]


def read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VerificationError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if isinstance(item, dict) and isinstance(item.get("event"), dict):
            item = item["event"]
        if not isinstance(item, dict):
            raise VerificationError(f"{path}:{line_number}: each line must contain an event object")
        events.append(item)
    return events


def read_treasury_config(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{path}: invalid JSON: {exc.msg}") from exc
    if isinstance(data, dict):
        data = data.get("treasuries")
    if not isinstance(data, list):
        raise VerificationError(f"{path}: expected an array or an object containing treasuries")
    if any(not isinstance(item, dict) for item in data):
        raise VerificationError(f"{path}: each treasury must be an object")
    return data


def event_shape_errors(event: dict[str, Any], seen_ids: set[str]) -> list[str]:
    problems: list[str] = []
    missing = sorted(REQUIRED_EVENT_FIELDS - set(event))
    if missing:
        problems.append("missing " + ", ".join(missing))
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id.strip():
        problems.append("id must be a non-empty string")
    elif event_id in seen_ids:
        problems.append("duplicate id")
    else:
        seen_ids.add(event_id)
    timestamp = event.get("timestamp")
    if not isinstance(timestamp, str):
        problems.append("timestamp must be an RFC 3339 string")
    else:
        candidate = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
        try:
            parsed = dt.datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            problems.append("timestamp must include a valid UTC offset or Z")
    try:
        decimal_value(event.get("amount"), "amount")
    except VerificationError as exc:
        problems.append(str(exc))
    if event.get("direction") not in {"incoming", "outgoing"}:
        problems.append("direction must be incoming or outgoing")
    for field in ("asset", "source", "destination", "claimed_category"):
        if not isinstance(event.get(field), str) or not event[field].strip():
            problems.append(f"{field} must be a non-empty string")
    if event.get("status") not in STATUSES:
        problems.append("status is not an OAB v0.1 evidence status")
    evidence = event.get("evidence")
    if not isinstance(evidence, dict):
        problems.append("evidence must be an object")
    elif evidence.get("type") not in EVIDENCE_TYPES:
        problems.append("evidence.type is not an OAB v0.1 evidence type")
    return problems


def status_error(event: dict[str, Any]) -> str | None:
    status = event.get("status")
    evidence = event.get("evidence")
    evidence_type = evidence.get("type") if isinstance(evidence, dict) else None
    if status not in STATUS_EVIDENCE or evidence_type not in STATUS_EVIDENCE[status]:
        return f"status {status!r} does not match evidence type {evidence_type!r}"
    if status == "chain_verified":
        if not isinstance(event.get("network"), str) or not event["network"].strip():
            return "chain_verified requires network"
        if not isinstance(event.get("transaction_hash"), str) or not event["transaction_hash"].strip():
            return "chain_verified requires transaction_hash"
    return None


def evidence_url(event: dict[str, Any]) -> str | None:
    evidence = event.get("evidence")
    return evidence.get("url") if isinstance(evidence, dict) and isinstance(evidence.get("url"), str) else None


def head_url(url: str, timeout: float, retries: int = 1) -> int:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VerificationError("evidence URL must be absolute HTTP or HTTPS")
    last_error = "unreachable"
    for attempt in range(retries + 1):
        req = request.Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
        try:
            with request.urlopen(req, timeout=timeout) as response:
                status = int(response.status)
            if status >= 400:
                raise VerificationError(f"HTTP {status}")
            return status
        except (error.URLError, error.HTTPError, TimeoutError, VerificationError) as exc:
            status = getattr(exc, "code", None)
            last_error = f"HTTP {status}" if status is not None else str(getattr(exc, "reason", exc))
            if attempt < retries:
                time.sleep(0.25)
    raise VerificationError(last_error)


def validate_events(events: list[dict[str, Any]], reporter: Reporter, timeout: float) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, event in enumerate(events, start=1):
        label = str(event.get("id") or f"line-{index}")
        shape = event_shape_errors(event, seen_ids)
        if shape:
            reporter.failed(f"event {label}", "; ".join(shape))
        else:
            reporter.passed(f"event {label}", "OAB event fields are well formed")
            valid.append(event)
        mismatch = status_error(event)
        if mismatch:
            reporter.failed(f"status {label}", mismatch)
        else:
            reporter.passed(f"status {label}", "status matches its evidence type")
        url = evidence_url(event)
        if not url:
            reporter.failed(f"evidence {label}", "evidence.url is required for a resolvable public claim")
        else:
            try:
                status = head_url(url, timeout)
                reporter.passed(f"evidence {label}", f"HEAD resolved with HTTP {status}")
            except VerificationError as exc:
                reporter.failed(f"evidence {label}", str(exc))
    return valid


def prepare_treasuries(
    treasuries: list[dict[str, Any]], reporter: Reporter
) -> tuple[dict[tuple[str, str], Decimal], dict[tuple[str, str], Decimal], list[dict[str, Any]]]:
    expected: dict[tuple[str, str], Decimal] = {}
    tolerances: dict[tuple[str, str], Decimal] = {}
    prepared: list[dict[str, Any]] = []
    for index, item in enumerate(treasuries, start=1):
        try:
            network = normalized_network(item.get("network", item.get("chain")))
            address = item.get("address")
            if not isinstance(address, str) or not address.strip():
                raise VerificationError("address must be a non-empty string")
            assets = item.get("assets", DEFAULT_ASSETS[network])
            if not isinstance(assets, list) or not assets or any(not isinstance(asset, str) for asset in assets):
                raise VerificationError("assets must be a non-empty string array")
            assets = [asset.upper() for asset in assets]
            invalid_assets = sorted(set(assets) - set(DEFAULT_ASSETS[network]))
            if invalid_assets:
                raise VerificationError(f"unsupported {network} assets: {', '.join(invalid_assets)}")
            opening = item.get("opening_balances", {})
            tolerance_values = item.get("tolerances", {})
            if not isinstance(opening, dict) or not isinstance(tolerance_values, dict):
                raise VerificationError("opening_balances and tolerances must be objects")
            for asset in assets:
                key = (network, asset)
                expected[key] = expected.get(key, Decimal(0)) + decimal_value(opening.get(asset, "0"), f"opening {asset}")
                tolerance = decimal_value(tolerance_values.get(asset, "0"), f"tolerance {asset}")
                tolerances[key] = max(tolerances.get(key, Decimal(0)), tolerance)
            prepared.append({"network": network, "address": address, "assets": assets})
            reporter.passed(f"treasury {index}", f"configured {network} address with {', '.join(assets)}")
        except VerificationError as exc:
            reporter.failed(f"treasury {index}", str(exc))
    return expected, tolerances, prepared


def apply_ledger(
    events: list[dict[str, Any]], expected: dict[tuple[str, str], Decimal], reporter: Reporter
) -> None:
    for event in events:
        event_id = str(event.get("id", "unknown"))
        asset = str(event.get("asset", "")).upper()
        if event.get("claimed_category") == "internal_transfer":
            reporter.passed(f"reconciliation input {event_id}", "internal transfer has zero aggregate treasury effect")
            continue
        if event.get("network") is not None:
            try:
                key = (normalized_network(event["network"]), asset)
            except VerificationError as exc:
                reporter.failed(f"reconciliation input {event_id}", str(exc))
                continue
            if key not in expected:
                reporter.failed(f"reconciliation input {event_id}", f"no configured treasury tracks {key[0]} {key[1]}")
                continue
        else:
            candidates = [key for key in expected if key[1] == asset]
            if not candidates:
                reporter.passed(f"reconciliation input {event_id}", f"{asset} is an off-chain asset not tracked by treasury RPC")
                continue
            if len(candidates) > 1:
                reporter.failed(f"reconciliation input {event_id}", f"network is required because multiple treasuries track {asset}")
                continue
            key = candidates[0]
        try:
            amount = decimal_value(event.get("amount"), f"event {event_id} amount")
        except VerificationError as exc:
            reporter.failed(f"reconciliation input {event_id}", str(exc))
            continue
        expected[key] += amount if event.get("direction") == "incoming" else -amount
        reporter.passed(f"reconciliation input {event_id}", f"applied to {key[0]} {key[1]}")


def fetch_actual(
    prepared: list[dict[str, Any]], solana_rpc: str, base_rpc: str, timeout: float
) -> dict[tuple[str, str], Decimal]:
    actual: dict[tuple[str, str], Decimal] = {}
    for item in prepared:
        if item["network"] == "solana":
            balances = fetch_solana_balances(item["address"], solana_rpc, timeout)
        else:
            balances = fetch_base_balances(item["address"], base_rpc, timeout)
        for asset in item["assets"]:
            key = (item["network"], asset)
            actual[key] = actual.get(key, Decimal(0)) + Decimal(balances[asset])
    return actual


def reconcile(
    events: list[dict[str, Any]],
    treasuries: list[dict[str, Any]] | None,
    reporter: Reporter,
    *,
    solana_rpc: str,
    base_rpc: str,
    timeout: float,
) -> None:
    if treasuries is None:
        if events:
            reporter.failed("treasury reconciliation", "treasury config is missing for a non-empty ledger")
        else:
            reporter.passed("treasury reconciliation", "no events and no treasury exist yet")
        return
    expected, tolerances, prepared = prepare_treasuries(treasuries, reporter)
    apply_ledger(events, expected, reporter)
    if not prepared:
        if events:
            reporter.failed("treasury reconciliation", "no valid treasury is available for a non-empty ledger")
        else:
            reporter.passed("treasury reconciliation", "empty ledger and empty treasury list reconcile at zero")
        return
    negative = False
    for key, amount in expected.items():
        if amount < 0:
            reporter.failed(f"balance {key[0]} {key[1]}", f"ledger-derived expectation is negative ({amount})")
            negative = True
    if negative:
        return
    try:
        actual = fetch_actual(prepared, solana_rpc, base_rpc, timeout)
    except (OSError, ValueError, RpcError, InvalidOperation) as exc:
        reporter.failed("treasury reconciliation", f"chain balance unavailable: {exc}")
        return
    for key in sorted(expected):
        observed = actual.get(key, Decimal(0))
        wanted = expected[key]
        tolerance = tolerances.get(key, Decimal(0))
        difference = abs(observed - wanted)
        if difference <= tolerance:
            reporter.passed(
                f"balance {key[0]} {key[1]}",
                f"chain {observed} matches ledger {wanted} within tolerance {tolerance}",
            )
        else:
            reporter.failed(
                f"balance {key[0]} {key[1]}",
                f"chain {observed} does not match ledger {wanted}; difference {difference}",
            )


def verify(
    ledger_path: Path,
    treasury_path: Path,
    *,
    solana_rpc: str = SOLANA_RPC,
    base_rpc: str = BASE_RPC,
    timeout: float = 6.0,
) -> int:
    reporter = Reporter()
    try:
        events = read_ledger(ledger_path)
        treasuries = read_treasury_config(treasury_path)
    except (OSError, VerificationError) as exc:
        reporter.failed("input", str(exc))
        return 1
    reporter.passed("ledger", f"parsed {len(events)} event(s)")
    if not events:
        reporter.passed("claims", "empty ledger contains no monetary claims")
    valid_events = validate_events(events, reporter, timeout)
    reconcile(
        valid_events,
        treasuries,
        reporter,
        solana_rpc=solana_rpc,
        base_rpc=base_rpc,
        timeout=timeout,
    )
    if reporter.failures:
        print(f"FAIL summary: {reporter.failures} claim(s) failed")
        return 1
    print("PASS summary: every disclosed claim verified")
    return 0


def self_test() -> None:
    assert status_error(
        {
            "status": "chain_verified",
            "evidence": {"type": "chain_transaction"},
            "network": "base",
            "transaction_hash": "0x1",
        }
    ) is None
    assert status_error({"status": "receipt_bound", "evidence": {"type": "operator_statement"}})
    assert decimal_value("1.250", "fixture") == Decimal("1.250")
    print("PASS: verifier self-test checked evidence mappings and exact decimal parsing")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify OAB event evidence and reconcile treasury balances.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--treasury", type=Path, default=DEFAULT_TREASURY)
    parser.add_argument("--solana-rpc", default=SOLANA_RPC)
    parser.add_argument("--base-rpc", default=BASE_RPC)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if not 0 < args.timeout <= 30:
        print("FAIL input: timeout must be greater than 0 and no more than 30 seconds")
        return 2
    return verify(
        args.ledger,
        args.treasury,
        solana_rpc=args.solana_rpc,
        base_rpc=args.base_rpc,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
