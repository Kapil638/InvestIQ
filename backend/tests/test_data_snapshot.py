"""Tests for data snapshot hashing."""

from app.services.data_snapshot import compute_data_snapshot_hash


def test_data_snapshot_hash_includes_ticker() -> None:
    hash_infy = compute_data_snapshot_hash("INFY", None, None)
    hash_tcs = compute_data_snapshot_hash("TCS", None, None)
    assert hash_infy != hash_tcs


def test_data_snapshot_hash_normalizes_ticker_case() -> None:
    assert compute_data_snapshot_hash("infy", None, None) == compute_data_snapshot_hash(
        "INFY", None, None
    )
