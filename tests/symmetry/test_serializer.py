"""Tests for pgm_map_studio.symmetry.serializer."""

import json
import pytest
from pathlib import Path

from pgm_map_studio.symmetry.datatypes import SymmetryResult, GlobalSymmetryEntry
from pgm_map_studio.symmetry import serializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result_with(entries, status='unconfirmed', center=None):
    return SymmetryResult(
        status=status,
        modes=entries,
        center=center or {'cx': 0.0, 'cz': 0.0},
    )


def _detected_entry(sym_type, confidence=0.95):
    return GlobalSymmetryEntry(type=sym_type, detected=True, confidence=confidence)


def _undetected_entry(sym_type, confidence=0.10):
    return GlobalSymmetryEntry(type=sym_type, detected=False, confidence=confidence)


# ---------------------------------------------------------------------------
# Required keys present
# ---------------------------------------------------------------------------

def test_required_keys_present():
    result = _result_with([_detected_entry('rot_180')])
    d = serializer.to_dict(result)
    assert 'status' in d
    assert 'modes' in d
    assert 'center' in d
    assert 'center_cell' in d
    assert 'primary' in d


def test_center_cell_serialized():
    result = _result_with([], center={'cx': 2.5, 'cz': 0.0})
    d = serializer.to_dict(result)
    assert d['center_cell'] == '1x2'


def test_intra_team_symmetry_absent():
    result = _result_with([_detected_entry('rot_180')])
    d = serializer.to_dict(result)
    assert 'intra_team_symmetry' not in d


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_unconfirmed_by_default():
    result = _result_with([])
    d = serializer.to_dict(result)
    assert d['status'] == 'unconfirmed'


def test_status_confirmed():
    result = _result_with([], status='confirmed')
    d = serializer.to_dict(result)
    assert d['status'] == 'confirmed'


# ---------------------------------------------------------------------------
# modes entries
# ---------------------------------------------------------------------------

def test_modes_entries():
    entries = [
        _detected_entry('rot_180', 1.0),
        _undetected_entry('mirror_x', 0.31),
    ]
    result = _result_with(entries)
    d = serializer.to_dict(result)
    assert len(d['modes']) == 2


def test_modes_entry_fields():
    entries = [_detected_entry('rot_180', 0.92)]
    result = _result_with(entries)
    d = serializer.to_dict(result)
    e = d['modes'][0]
    assert e['type'] == 'rot_180'
    assert e['detected'] is True
    assert e['confidence'] == pytest.approx(0.92)
    assert 'description' not in e


# ---------------------------------------------------------------------------
# center
# ---------------------------------------------------------------------------

def test_center_fields():
    result = _result_with([], center={'center_x': 1.5, 'center_z': -2.5})
    d = serializer.to_dict(result)
    assert d['center']['center_x'] == 1.5
    assert d['center']['center_z'] == -2.5


# ---------------------------------------------------------------------------
# primary
# ---------------------------------------------------------------------------

def test_primary_when_detected():
    result = _result_with([_detected_entry('rot_180', 1.0)])
    d = serializer.to_dict(result)
    assert d['primary'] is not None
    assert d['primary']['type'] == 'rot_180'
    assert d['primary']['confidence'] == pytest.approx(1.0)


def test_primary_is_null_when_none_detected():
    result = _result_with([
        _undetected_entry('rot_180', 0.10),
        _undetected_entry('mirror_x', 0.15),
    ])
    d = serializer.to_dict(result)
    assert d['primary'] is None


def test_primary_highest_confidence_wins():
    result = _result_with([
        _detected_entry('mirror_x', 0.70),
        _detected_entry('rot_180', 0.90),
    ])
    d = serializer.to_dict(result)
    assert d['primary']['type'] == 'rot_180'


def test_primary_tiebreak_by_symmetry_order():
    # rot_90 (order 4) > rot_180 (order 2) at same confidence
    result = _result_with([
        _detected_entry('rot_90', 0.90),
        _detected_entry('rot_180', 0.90),
    ])
    d = serializer.to_dict(result)
    assert d['primary']['type'] == 'rot_90'


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def test_json_is_valid():
    result = _result_with([_detected_entry('rot_180', 1.0)])
    json_str = serializer.to_json(result)
    parsed = json.loads(json_str)
    assert isinstance(parsed, dict)


def test_save_creates_file(tmp_path):
    result = _result_with([_detected_entry('rot_180', 1.0)])
    out = tmp_path / "symmetry.json"
    serializer.save(result, out)
    assert out.exists()
    d = json.loads(out.read_text())
    assert d['status'] == 'unconfirmed'
