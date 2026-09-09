"""Tests for the frozen per-slot CSV logging schema (E15, F9.2)."""

from common.contracts.log_schema import SLOT_LOG_COLUMNS, validate_slot_row


def test_slot_log_columns_has_21_fields():
    assert len(SLOT_LOG_COLUMNS) == 21


def test_slot_log_columns_has_no_duplicates():
    assert len(set(SLOT_LOG_COLUMNS)) == len(SLOT_LOG_COLUMNS)


def _sample_row() -> dict:
    return {col: 0 for col in SLOT_LOG_COLUMNS}


def test_validate_slot_row_accepts_exact_column_set():
    assert validate_slot_row(_sample_row()) is True


def test_validate_slot_row_rejects_missing_column():
    row = _sample_row()
    del row["shield_fired"]
    assert validate_slot_row(row) is False


def test_validate_slot_row_rejects_extra_column():
    row = _sample_row()
    row["unexpected_field"] = 1
    assert validate_slot_row(row) is False
