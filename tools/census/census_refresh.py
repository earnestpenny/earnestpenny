#!/usr/bin/env python3
"""Refresh supported public-chain balances in the Census registry.

The script is deliberately read-only toward chains. It performs JSON-RPC calls,
updates only balance-check fields in census.json, and never handles a private key.
"""

from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable
from urllib import error, request


SOLANA_RPC = "https://api.mainnet-beta.solana.com"
BASE_RPC = "https://mainnet.base.org"
MONAD_RPC = "https://rpc.monad.xyz"
ARBITRUM_RPC = "https://arb1.arbitrum.io/rpc"
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
BASE_USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
MONAD_USDC_CONTRACT = "0x754704Bc059F8C67012fEd69BC8A327a5aafb603"
ARBITRUM_USDC_CONTRACT = "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
DEFAULT_CENSUS = Path(__file__).resolve().parents[2] / "census" / "census.json"
EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
USER_AGENT = "CensusBalanceRefresher/0.1 (+https://github.com/)"


class RpcError(RuntimeError):
    """A public RPC endpoint did not return a usable result."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def decimal_string(value: Decimal) -> str:
    shown = format(value, "f")
    if "." in shown:
        shown = shown.rstrip("0").rstrip(".")
    return shown or "0"


def _rpc(endpoint: str, method: str, params: list[Any], timeout: float, retries: int = 1) -> Any:
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        separators=(",", ":"),
    ).encode("utf-8")
    last_error = "unknown RPC failure"
    for attempt in range(retries + 1):
        req = request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
            body = json.loads(raw.decode("utf-8"))
            if not isinstance(body, dict):
                raise RpcError("RPC response was not an object")
            if body.get("error") is not None:
                problem = body["error"]
                if isinstance(problem, dict):
                    problem = problem.get("message", problem.get("code", "RPC error"))
                raise RpcError(str(problem))
            if "result" not in body:
                raise RpcError("RPC response omitted result")
            return body["result"]
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError, RpcError) as exc:
            last_error = str(getattr(exc, "reason", exc))
            if attempt < retries:
                time.sleep(0.25)
    raise RpcError(last_error)


def fetch_solana_balances(address: str, rpc_url: str = SOLANA_RPC, timeout: float = 6.0) -> dict[str, str]:
    if not isinstance(address, str) or not address.strip():
        raise ValueError("empty Solana address")
    native = _rpc(rpc_url, "getBalance", [address, {"commitment": "confirmed"}], timeout)
    if not isinstance(native, dict) or isinstance(native.get("value"), bool) or not isinstance(native.get("value"), int):
        raise RpcError("getBalance returned an invalid value")

    token_accounts = _rpc(
        rpc_url,
        "getTokenAccountsByOwner",
        [
            address,
            {"mint": SOLANA_USDC_MINT},
            {"encoding": "jsonParsed", "commitment": "confirmed"},
        ],
        timeout,
    )
    if not isinstance(token_accounts, dict) or not isinstance(token_accounts.get("value"), list):
        raise RpcError("getTokenAccountsByOwner returned an invalid value")
    usdc = Decimal(0)
    for account in token_accounts["value"]:
        try:
            token_amount = account["account"]["data"]["parsed"]["info"]["tokenAmount"]
            raw_amount = token_amount["amount"]
            decimals = token_amount["decimals"]
            if not isinstance(raw_amount, str) or not raw_amount.isdigit():
                raise ValueError("invalid token amount")
            if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
                raise ValueError("invalid token decimals")
            usdc += Decimal(int(raw_amount)).scaleb(-decimals)
        except (KeyError, TypeError, ValueError) as exc:
            raise RpcError("USDC token account had an invalid parsed balance") from exc
    return {
        "SOL": decimal_string(Decimal(native["value"]).scaleb(-9)),
        "USDC": decimal_string(usdc),
    }


def fetch_evm_balances(
    address: str,
    rpc_url: str,
    native_asset: str,
    usdc_contract: str,
    timeout: float = 6.0,
    *,
    rpc_call: Callable[..., Any] = _rpc,
) -> dict[str, str]:
    if not isinstance(address, str) or EVM_ADDRESS.fullmatch(address) is None:
        raise ValueError("EVM address must be a 20-byte 0x-prefixed hex string")
    if not isinstance(native_asset, str) or not native_asset.strip():
        raise ValueError("native asset symbol is missing")
    if not isinstance(usdc_contract, str) or EVM_ADDRESS.fullmatch(usdc_contract) is None:
        raise ValueError("USDC contract must be a 20-byte 0x-prefixed hex string")
    native = rpc_call(rpc_url, "eth_getBalance", [address, "latest"], timeout)
    if not isinstance(native, str) or not native.startswith("0x"):
        raise RpcError("eth_getBalance returned an invalid quantity")
    calldata = "0x70a08231" + address[2:].lower().rjust(64, "0")
    token = rpc_call(
        rpc_url,
        "eth_call",
        [{"to": usdc_contract, "data": calldata}, "latest"],
        timeout,
    )
    if not isinstance(token, str) or not token.startswith("0x"):
        raise RpcError("USDC balanceOf returned invalid data")
    try:
        wei = int(native, 16)
        usdc_units = int(token, 16)
    except ValueError as exc:
        raise RpcError("EVM RPC returned malformed hexadecimal data") from exc
    return {
        native_asset: decimal_string(Decimal(wei).scaleb(-18)),
        "USDC": decimal_string(Decimal(usdc_units).scaleb(-6)),
    }


def fetch_base_balances(address: str, rpc_url: str = BASE_RPC, timeout: float = 6.0) -> dict[str, str]:
    return fetch_evm_balances(address, rpc_url, "ETH", BASE_USDC_CONTRACT, timeout)


def fetch_monad_balances(address: str, rpc_url: str = MONAD_RPC, timeout: float = 6.0) -> dict[str, str]:
    return fetch_evm_balances(address, rpc_url, "MON", MONAD_USDC_CONTRACT, timeout)


def fetch_arbitrum_balances(
    address: str,
    rpc_url: str = ARBITRUM_RPC,
    timeout: float = 6.0,
) -> dict[str, str]:
    return fetch_evm_balances(address, rpc_url, "ETH", ARBITRUM_USDC_CONTRACT, timeout)


def fetch_address(
    tagged: dict[str, Any],
    *,
    solana_rpc: str = SOLANA_RPC,
    base_rpc: str = BASE_RPC,
    monad_rpc: str = MONAD_RPC,
    arbitrum_rpc: str = ARBITRUM_RPC,
    timeout: float = 6.0,
) -> dict[str, str]:
    chain = str(tagged.get("chain", tagged.get("network", ""))).strip().lower().replace("_", "-")
    address = tagged.get("address")
    if chain in {"solana", "solana-mainnet"}:
        return fetch_solana_balances(address, solana_rpc, timeout)
    if chain in {"base", "base-mainnet"}:
        return fetch_base_balances(address, base_rpc, timeout)
    if chain in {"monad", "monad-mainnet"}:
        return fetch_monad_balances(address, monad_rpc, timeout)
    if chain in {"arbitrum", "arbitrum-one", "arbitrum-mainnet"}:
        return fetch_arbitrum_balances(address, arbitrum_rpc, timeout)
    raise ValueError(f"unsupported chain tag: {chain or 'missing'}")


def _ventures(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("ventures", "rows", "census"):
            if key in data:
                rows = data[key]
                if not isinstance(rows, list):
                    raise ValueError(f"{key} must be an array")
                return rows
    raise ValueError("census root must be an array or contain ventures, rows, or census")


def refresh_registry(
    data: Any,
    *,
    solana_rpc: str = SOLANA_RPC,
    base_rpc: str = BASE_RPC,
    monad_rpc: str = MONAD_RPC,
    arbitrum_rpc: str = ARBITRUM_RPC,
    timeout: float = 6.0,
    fetcher: Callable[..., dict[str, str]] = fetch_address,
) -> tuple[int, int]:
    checked = 0
    unchecked = 0
    stamp = utc_now()
    for venture in _ventures(data):
        if not isinstance(venture, dict):
            continue
        addresses = venture.get("treasury_addresses", venture.get("treasuries", []))
        if not isinstance(addresses, list):
            raise ValueError(f"{venture.get('name', 'unnamed venture')}: treasury addresses must be an array")
        for tagged in addresses:
            if not isinstance(tagged, dict):
                unchecked += 1
                continue
            try:
                balances = fetcher(
                    tagged,
                    solana_rpc=solana_rpc,
                    base_rpc=base_rpc,
                    monad_rpc=monad_rpc,
                    arbitrum_rpc=arbitrum_rpc,
                    timeout=timeout,
                )
                tagged["verified_balance"] = balances
                tagged["checked_at"] = stamp
                tagged["verification_status"] = "checked"
                tagged["error"] = None
                checked += 1
            except (OSError, ValueError, RpcError) as exc:
                tagged["verified_balance"] = None
                tagged["checked_at"] = None
                tagged["verification_status"] = "unchecked"
                tagged["error"] = str(exc)[:240]
                unchecked += 1
    return checked, unchecked


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def self_test() -> None:
    fixture = {
        "ventures": [
            {
                "name": "fixture",
                "treasury_addresses": [
                    {"chain": "solana-mainnet", "address": "sol"},
                    {"chain": "base-mainnet", "address": "0x" + "1" * 40},
                    {"chain": "monad-mainnet", "address": "0x" + "2" * 40},
                    {"chain": "arbitrum-one", "address": "0x" + "3" * 40},
                    {"chain": "bitcoin", "address": "btc"},
                ],
            }
        ]
    }

    def fake_fetch(tagged: dict[str, Any], **_: Any) -> dict[str, str]:
        chain = tagged["chain"]
        if chain == "solana-mainnet":
            return {"SOL": "1", "USDC": "2.5"}
        if chain == "base-mainnet":
            return {"ETH": "0.1", "USDC": "3"}
        if chain == "monad-mainnet":
            return {"MON": "0", "USDC": "0.0174"}
        if chain == "arbitrum-one":
            return {"ETH": "0", "USDC": "0.0174"}
        raise ValueError("unsupported chain tag: bitcoin")

    checked, unchecked = refresh_registry(fixture, fetcher=fake_fetch)
    addresses = fixture["ventures"][0]["treasury_addresses"]
    assert (checked, unchecked) == (4, 1)
    assert addresses[0]["verified_balance"]["USDC"] == "2.5"
    assert addresses[1]["verification_status"] == "checked"
    assert addresses[2]["verified_balance"] == {"MON": "0", "USDC": "0.0174"}
    assert addresses[3]["verified_balance"] == {"ETH": "0", "USDC": "0.0174"}
    assert addresses[4]["verification_status"] == "unchecked" and addresses[4]["error"]

    calls: list[tuple[str, str, list[Any], float]] = []

    def fake_rpc(endpoint: str, method: str, params: list[Any], timeout: float) -> str:
        calls.append((endpoint, method, params, timeout))
        if method == "eth_getBalance":
            return hex(10**18)
        if method == "eth_call":
            return hex(17400)
        raise AssertionError(f"unexpected method {method}")

    evm = fetch_evm_balances(
        "0x" + "4" * 40,
        "https://rpc.example",
        "MON",
        MONAD_USDC_CONTRACT,
        rpc_call=fake_rpc,
    )
    assert evm == {"MON": "1", "USDC": "0.0174"}
    assert [call[1] for call in calls] == ["eth_getBalance", "eth_call"]
    assert calls[1][2][0]["to"] == MONAD_USDC_CONTRACT
    print("PASS: census refresher self-test checked 4 addresses, 2 EVM methods, and 1 unsupported address")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh supported public-chain balances in census.json.")
    parser.add_argument("--input", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--output", type=Path, help="Defaults to replacing --input atomically.")
    parser.add_argument("--solana-rpc", default=SOLANA_RPC)
    parser.add_argument("--base-rpc", default=BASE_RPC)
    parser.add_argument("--monad-rpc", default=MONAD_RPC)
    parser.add_argument("--arbitrum-rpc", default=ARBITRUM_RPC)
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    if not 0 < args.timeout <= 30:
        print("FAIL: timeout must be greater than 0 and no more than 30 seconds", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        checked, unchecked = refresh_registry(
            data,
            solana_rpc=args.solana_rpc,
            base_rpc=args.base_rpc,
            monad_rpc=args.monad_rpc,
            arbitrum_rpc=args.arbitrum_rpc,
            timeout=args.timeout,
        )
        output = args.output or args.input
        write_json_atomic(output, data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    label = "PASS" if unchecked == 0 else "FAIL"
    print(f"{label}: checked {checked} address(es), left {unchecked} unchecked; wrote {output}")
    return 0 if unchecked == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
