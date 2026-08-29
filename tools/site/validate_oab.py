#!/usr/bin/env python3
"""Validate an Open Agent Books v0.1 document without third-party packages."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SCRIPT = Path(__file__).resolve()
DEFAULT_SCHEMA = SCRIPT.parents[2] / "schema" / "oab-0.1.schema.json"
DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Validator:
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def object(
        self,
        value: Any,
        path: str,
        required: set[str],
        allowed: set[str],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.error(path, "must be an object")
            return None
        keys = set(value)
        for key in sorted(required - keys):
            self.error(f"{path}.{key}", "is required")
        for key in sorted(keys - allowed):
            self.error(f"{path}.{key}", "is not allowed by schema v0.1")
        return value

    def string(self, value: Any, path: str, *, nonempty: bool = True) -> bool:
        if not isinstance(value, str):
            self.error(path, "must be a string")
            return False
        if nonempty and not value.strip():
            self.error(path, "must not be empty")
            return False
        return True

    def integer(self, value: Any, path: str) -> bool:
        if isinstance(value, bool) or not isinstance(value, int):
            self.error(path, "must be a non-negative integer")
            return False
        if value < 0:
            self.error(path, "must be a non-negative integer")
            return False
        return True

    def decimal(self, value: Any, path: str) -> bool:
        if isinstance(value, bool):
            self.error(path, "must be a non-negative number or decimal string")
            return False
        if isinstance(value, (int, float)):
            if not math.isfinite(value) or value < 0:
                self.error(path, "must be finite and non-negative")
                return False
            return True
        if isinstance(value, str) and DECIMAL_RE.fullmatch(value):
            return True
        self.error(path, "must be a non-negative number or plain decimal string")
        return False

    def timestamp(self, value: Any, path: str) -> bool:
        if not self.string(value, path):
            return False
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = dt.datetime.fromisoformat(candidate)
        except ValueError:
            self.error(path, "must be an RFC 3339 date-time")
            return False
        if parsed.tzinfo is None:
            self.error(path, "must include a UTC offset or Z")
            return False
        return True

    def uri(self, value: Any, path: str) -> bool:
        if not self.string(value, path):
            return False
        try:
            parsed = urlsplit(value)
        except ValueError:
            self.error(path, "must be a well-formed absolute URI")
            return False
        if not parsed.scheme:
            self.error(path, "must be an absolute URI")
            return False
        if parsed.scheme in {"http", "https"} and not parsed.netloc:
            self.error(path, "must include a host")
            return False
        return True

    def enum(self, value: Any, path: str, choices: set[str]) -> bool:
        if value not in choices:
            self.error(path, "must be one of: " + ", ".join(sorted(choices)))
            return False
        return True

    def string_array(
        self, value: Any, path: str, *, min_items: int = 0, unique: bool = False
    ) -> bool:
        if not isinstance(value, list):
            self.error(path, "must be an array")
            return False
        if len(value) < min_items:
            self.error(path, f"must contain at least {min_items} item(s)")
        for index, item in enumerate(value):
            self.string(item, f"{path}[{index}]")
        if unique and len(value) != len(set(item for item in value if isinstance(item, str))):
            self.error(path, "must not contain duplicates")
        return True

    def validate_venture(self, value: Any) -> None:
        required = {"name", "operator", "started_at"}
        allowed = required | {"homepage", "description"}
        obj = self.object(value, "$.venture", required, allowed)
        if obj is None:
            return
        if "name" in obj:
            self.string(obj["name"], "$.venture.name")
        if "operator" in obj:
            self.string(obj["operator"], "$.venture.operator")
        if "started_at" in obj:
            self.timestamp(obj["started_at"], "$.venture.started_at")
        if "homepage" in obj:
            self.uri(obj["homepage"], "$.venture.homepage")
        if "description" in obj:
            self.string(obj["description"], "$.venture.description", nonempty=False)

    def validate_treasuries(self, value: Any) -> None:
        if not isinstance(value, list):
            self.error("$.treasuries", "must be an array")
            return
        seen: set[tuple[str, str]] = set()
        for index, item in enumerate(value):
            path = f"$.treasuries[{index}]"
            required = {"network", "address"}
            allowed = required | {"label", "assets"}
            obj = self.object(item, path, required, allowed)
            if obj is None:
                continue
            for key in required:
                if key in obj:
                    self.string(obj[key], f"{path}.{key}")
            if "label" in obj:
                self.string(obj["label"], f"{path}.label", nonempty=False)
            if "assets" in obj:
                self.string_array(obj["assets"], f"{path}.assets", unique=True)
            if isinstance(obj.get("network"), str) and isinstance(obj.get("address"), str):
                identity = (obj["network"].casefold(), obj["address"].casefold())
                if identity in seen:
                    self.error(path, "duplicates an earlier network and address pair")
                seen.add(identity)

    def validate_evidence(self, value: Any, path: str) -> None:
        required = {"type"}
        allowed = {"type", "url", "hash"}
        obj = self.object(value, path, required, allowed)
        if obj is None:
            return
        if "type" in obj:
            self.enum(
                obj["type"],
                f"{path}.type",
                {"chain_transaction", "receipt", "invoice", "operator_statement", "other"},
            )
        if "url" in obj:
            self.uri(obj["url"], f"{path}.url")
        if "hash" in obj:
            self.string(obj["hash"], f"{path}.hash")
        if "url" not in obj and "hash" not in obj:
            self.error(path, "must contain a url or hash")

    def validate_events(self, value: Any) -> None:
        if not isinstance(value, list):
            self.error("$.monetary_events", "must be an array")
            return
        required = {
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
        allowed = required | {
            "network",
            "transaction_hash",
            "amount_usd",
            "unit_price_usd",
            "price_source",
            "note",
        }
        ids: set[str] = set()
        for index, item in enumerate(value):
            path = f"$.monetary_events[{index}]"
            obj = self.object(item, path, required, allowed)
            if obj is None:
                continue
            event_id = obj.get("id")
            if self.string(event_id, f"{path}.id"):
                if not EVENT_ID_RE.fullmatch(event_id):
                    self.error(f"{path}.id", "contains characters not allowed by schema v0.1")
                if event_id in ids:
                    self.error(f"{path}.id", "duplicates an earlier event id")
                ids.add(event_id)
            if "timestamp" in obj:
                self.timestamp(obj["timestamp"], f"{path}.timestamp")
            if "amount" in obj:
                self.decimal(obj["amount"], f"{path}.amount")
            for key in ("asset", "source", "destination"):
                if key in obj:
                    self.string(obj[key], f"{path}.{key}")
            if "direction" in obj:
                self.enum(obj["direction"], f"{path}.direction", {"incoming", "outgoing"})
            if "claimed_category" in obj:
                self.enum(
                    obj["claimed_category"],
                    f"{path}.claimed_category",
                    {
                        "customer_revenue",
                        "support",
                        "owner_funding",
                        "internal_transfer",
                        "expense",
                        "refund",
                    },
                )
            if "evidence" in obj:
                self.validate_evidence(obj["evidence"], f"{path}.evidence")
            if "status" in obj:
                self.enum(
                    obj["status"],
                    f"{path}.status",
                    {
                        "chain_verified",
                        "receipt_bound",
                        "operator_attested",
                        "unclassified",
                        "conflicted",
                    },
                )
            for key in ("network", "transaction_hash"):
                if key in obj:
                    self.string(obj[key], f"{path}.{key}")
            for key in ("amount_usd", "unit_price_usd"):
                if key in obj:
                    self.decimal(obj[key], f"{path}.{key}")
            if "price_source" in obj:
                self.uri(obj["price_source"], f"{path}.price_source")
            if "note" in obj:
                self.string(obj["note"], f"{path}.note", nonempty=False)

    def validate_models(self, value: Any) -> None:
        path = "$.metadata.models"
        if not isinstance(value, list):
            self.error(path, "must be an array")
            return
        if not value:
            self.error(path, "must contain at least one model record")
        ids: set[str] = set()
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            obj = self.object(
                item,
                item_path,
                {"model_id"},
                {"model_id", "role", "first_wake", "last_wake"},
            )
            if obj is None:
                continue
            model_id = obj.get("model_id")
            if self.string(model_id, f"{item_path}.model_id"):
                if model_id in ids:
                    self.error(f"{item_path}.model_id", "duplicates an earlier model id")
                ids.add(model_id)
            if "role" in obj:
                self.enum(
                    obj["role"],
                    f"{item_path}.role",
                    {"operator", "auditor", "caretaker", "historical"},
                )
            for key in ("first_wake", "last_wake"):
                if key in obj:
                    self.integer(obj[key], f"{item_path}.{key}")
            if (
                isinstance(obj.get("first_wake"), int)
                and not isinstance(obj.get("first_wake"), bool)
                and isinstance(obj.get("last_wake"), int)
                and not isinstance(obj.get("last_wake"), bool)
                and obj["last_wake"] < obj["first_wake"]
            ):
                self.error(item_path, "last_wake must not precede first_wake")

    def validate_corrections(self, value: Any) -> None:
        path = "$.metadata.corrections"
        if not isinstance(value, list):
            self.error(path, "must be an array")
            return
        ids: set[str] = set()
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            required = {"id", "timestamp", "summary", "targets"}
            obj = self.object(item, item_path, required, required)
            if obj is None:
                continue
            correction_id = obj.get("id")
            if self.string(correction_id, f"{item_path}.id"):
                if correction_id in ids:
                    self.error(f"{item_path}.id", "duplicates an earlier correction id")
                ids.add(correction_id)
            if "timestamp" in obj:
                self.timestamp(obj["timestamp"], f"{item_path}.timestamp")
            if "summary" in obj:
                self.string(obj["summary"], f"{item_path}.summary")
            if "targets" in obj:
                self.string_array(obj["targets"], f"{item_path}.targets", min_items=1, unique=True)

    def validate_metadata(self, value: Any) -> None:
        required = {"models", "wake_count", "last_wake_at", "corrections"}
        obj = self.object(value, "$.metadata", required, required)
        if obj is None:
            return
        if "models" in obj:
            self.validate_models(obj["models"])
        if "wake_count" in obj:
            self.integer(obj["wake_count"], "$.metadata.wake_count")
        if "last_wake_at" in obj:
            self.timestamp(obj["last_wake_at"], "$.metadata.last_wake_at")
        if "corrections" in obj:
            self.validate_corrections(obj["corrections"])

    def validate(self, document: Any) -> list[str]:
        required = {
            "schema_version",
            "core_version",
            "required_core_fields",
            "venture",
            "treasuries",
            "monetary_events",
            "metadata",
        }
        obj = self.object(document, "$", required, required)
        if obj is None:
            return self.errors

        properties = self.schema.get("properties", {})
        expected_schema = properties.get("schema_version", {}).get("const")
        expected_core = properties.get("core_version", {}).get("const")
        expected_fields = properties.get("required_core_fields", {}).get("const")
        if not expected_schema or not expected_core or not isinstance(expected_fields, list):
            self.error("$schema", "schema is missing its fixed version or core field list")
            return self.errors

        if obj.get("schema_version") != expected_schema:
            self.error("$.schema_version", f"must equal {expected_schema!r}")
        if obj.get("core_version") != expected_core:
            self.error("$.core_version", f"must equal {expected_core!r}")
        if obj.get("required_core_fields") != expected_fields:
            self.error(
                "$.required_core_fields",
                "must exactly match the ordered field list fixed by " + str(expected_core),
            )
        if "venture" in obj:
            self.validate_venture(obj["venture"])
        if "treasuries" in obj:
            self.validate_treasuries(obj["treasuries"])
        if "monetary_events" in obj:
            self.validate_events(obj["monetary_events"])
        if "metadata" in obj:
            self.validate_metadata(obj["metadata"])
        return self.errors


def load_json(path: Path, label: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"{label} not found: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"could not read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an Open Agent Books v0.1 JSON file.")
    parser.add_argument("books", type=Path, help="Path to books.json")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="OAB v0.1 schema path")
    args = parser.parse_args(argv)

    try:
        schema = load_json(args.schema, "schema")
        document = load_json(args.books, "books document")
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2
    if not isinstance(schema, dict):
        print(f"FAIL: schema must be a JSON object: {args.schema}")
        return 2

    errors = Validator(schema).validate(document)
    if errors:
        print(f"FAIL: {args.books} has {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS: {args.books} conforms to Open Agent Books v0.1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
