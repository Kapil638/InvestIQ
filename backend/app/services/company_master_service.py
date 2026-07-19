"""In-memory NSE (and future BSE) company master search."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.utils.logging import get_logger

logger = get_logger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "company_master.json"

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


@dataclass(frozen=True, slots=True)
class CompanyMasterEntry:
    symbol: str
    company_name: str
    series: str
    isin: str
    exchange: str
    source: str
    searchable_text: str


def normalize_query(text: str) -> str:
    """Normalize user query for case/punctuation/Ltd-insensitive matching."""
    lowered = text.lower().strip()
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    words = [word for word in lowered.split() if word and word not in STOP_WORDS]
    return "".join(words)


def normalize_name_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^\w\s]", " ", lowered)
    words = [word for word in lowered.split() if word and word not in STOP_WORDS]
    return "".join(words)


def _match_rank(query_norm: str, entry: CompanyMasterEntry) -> int:
    symbol_norm = normalize_query(entry.symbol)
    name_norm = normalize_name_text(entry.searchable_text)

    if not query_norm:
        return 0

    if symbol_norm == query_norm:
        return 400
    if symbol_norm.startswith(query_norm):
        return 300
    if name_norm.startswith(query_norm):
        return 200
    if query_norm in name_norm:
        return 100
    return 0


class CompanyMasterService:
    """Lazy-loaded, in-memory company master index."""

    def __init__(self, data_path: Path | None = None) -> None:
        self._data_path = data_path or DATA_PATH
        self._lock = threading.Lock()
        self._loaded = False
        self._entries: tuple[CompanyMasterEntry, ...] = ()
        self._symbol_index: dict[tuple[str, str], CompanyMasterEntry] = {}
        self._symbol_by_bare: dict[str, list[CompanyMasterEntry]] = {}
        self._load_count = 0

    @property
    def load_count(self) -> int:
        return self._load_count

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._entries = tuple(self._read_entries())
            self._build_indexes()
            self._loaded = True
            self._load_count += 1
            logger.info("Loaded %s company master entries from %s", len(self._entries), self._data_path)

    def search(self, query: str, *, limit: int = 15) -> list[CompanyMasterEntry]:
        self.ensure_loaded()
        query_norm = normalize_query(query)
        if len(query_norm) < 2:
            return []

        scored: list[tuple[int, int, str, CompanyMasterEntry]] = []
        for entry in self._entries:
            rank = _match_rank(query_norm, entry)
            if rank <= 0:
                continue
            scored.append((rank, len(entry.symbol), entry.company_name.lower(), entry))

        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [entry for _, _, _, entry in scored[:limit]]

    def lookup_by_symbol(self, symbol: str, exchange: str | None = None) -> CompanyMasterEntry | None:
        """Exact lookup by bare ticker; prefers NSE when exchange is omitted."""
        self.ensure_loaded()
        bare = symbol.split(".")[0].strip().upper()
        if not bare:
            return None

        if exchange:
            return self._symbol_index.get((bare, exchange.strip().upper()))

        entries = self._symbol_by_bare.get(bare, [])
        if not entries:
            return None
        for entry in entries:
            if entry.exchange.upper() == "NSE":
                return entry
        return entries[0]

    def _build_indexes(self) -> None:
        symbol_index: dict[tuple[str, str], CompanyMasterEntry] = {}
        symbol_by_bare: dict[str, list[CompanyMasterEntry]] = {}
        for entry in self._entries:
            key = (entry.symbol.upper(), entry.exchange.upper())
            symbol_index[key] = entry
            symbol_by_bare.setdefault(entry.symbol.upper(), []).append(entry)
        self._symbol_index = symbol_index
        self._symbol_by_bare = symbol_by_bare

    def _read_entries(self) -> list[CompanyMasterEntry]:
        if not self._data_path.exists():
            logger.warning("Company master JSON not found at %s", self._data_path)
            return []

        raw = json.loads(self._data_path.read_text(encoding="utf-8"))
        companies: list[Any]
        if isinstance(raw, dict):
            companies = raw.get("companies", [])
        elif isinstance(raw, list):
            companies = raw
        else:
            companies = []

        entries: list[CompanyMasterEntry] = []
        for item in companies:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip().upper()
            company_name = str(item.get("company_name", "")).strip()
            if not symbol or not company_name:
                continue
            entries.append(
                CompanyMasterEntry(
                    symbol=symbol,
                    company_name=company_name,
                    series=str(item.get("series", "")).strip(),
                    isin=str(item.get("isin", "")).strip(),
                    exchange=str(item.get("exchange", "NSE")).strip() or "NSE",
                    source=str(item.get("source", "NSE")).strip() or "NSE",
                    searchable_text=str(item.get("searchable_text", "")).strip()
                    or normalize_searchable_text(symbol, company_name),
                )
            )
        return entries

    def reset_for_tests(self) -> None:
        with self._lock:
            self._loaded = False
            self._entries = ()
            self._symbol_index = {}
            self._symbol_by_bare = {}
            self._load_count = 0


def normalize_searchable_text(symbol: str, company_name: str) -> str:
    combined = f"{symbol} {company_name}".lower()
    combined = re.sub(r"[^\w\s]", " ", combined)
    words = [word for word in combined.split() if word and word not in STOP_WORDS]
    return " ".join(words)


_master_service: CompanyMasterService | None = None
_master_lock = threading.Lock()


def get_company_master_service() -> CompanyMasterService:
    global _master_service
    if _master_service is None:
        with _master_lock:
            if _master_service is None:
                _master_service = CompanyMasterService()
    return _master_service


def reset_company_master_service_for_tests() -> None:
    global _master_service
    with _master_lock:
        if _master_service is not None:
            _master_service.reset_for_tests()
        _master_service = None
