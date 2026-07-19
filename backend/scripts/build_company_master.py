#!/usr/bin/env python3
"""Build company_master.json from NSE EQUITY_L CSV."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

STOP_WORDS = frozenset(
    {
        "ltd",
        "limited",
        "pvt",
        "private",
        "inc",
        "corp",
        "corporation",
        "company",
        "co",
        "the",
        "and",
    }
)


def _normalize_column(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).upper()


def normalize_searchable_text(symbol: str, company_name: str) -> str:
    """Lowercase, strip punctuation, drop Ltd/Limited-style tokens."""
    combined = f"{symbol} {company_name}".lower()
    combined = re.sub(r"[^\w\s]", " ", combined)
    words = [word for word in combined.split() if word and word not in STOP_WORDS]
    return " ".join(words)


def build_entries(csv_path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen_symbols: set[str] = set()

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"No header row found in {csv_path}")

        columns = {_normalize_column(name): name for name in reader.fieldnames}

        def col(*candidates: str) -> str:
            for candidate in candidates:
                key = columns.get(candidate)
                if key:
                    return key
            raise KeyError(f"Missing expected column(s): {candidates}")

        symbol_key = col("SYMBOL")
        name_key = col("NAME OF COMPANY")
        series_key = col("SERIES")
        isin_key = col("ISIN NUMBER")

        for row in reader:
            symbol = (row.get(symbol_key) or "").strip().upper()
            company_name = (row.get(name_key) or "").strip()
            if not symbol or not company_name:
                continue
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)

            entries.append(
                {
                    "symbol": symbol,
                    "company_name": company_name,
                    "series": (row.get(series_key) or "").strip(),
                    "isin": (row.get(isin_key) or "").strip(),
                    "exchange": "NSE",
                    "source": "NSE",
                    "searchable_text": normalize_searchable_text(symbol, company_name),
                }
            )

    entries.sort(key=lambda item: item["symbol"])
    return entries


def main() -> int:
    base = Path(__file__).resolve().parent.parent / "app" / "data"
    csv_path = base / "company_master.csv"
    json_path = base / "company_master.json"

    if not csv_path.exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    entries = build_entries(csv_path)
    payload = {
        "version": 1,
        "generated_from": csv_path.name,
        "count": len(entries),
        "companies": entries,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} companies to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
