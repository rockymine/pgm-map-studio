"""Symmetry detection from island polygon data.

Public API:
    detect(islands_path, exclude_islands=None) → SymmetryResult
    detect_from_data(islands_data, exclude_islands=None) → SymmetryResult
    SymmetryResult
"""

from .datatypes import SymmetryResult
from .detection import detect, detect_from_data

__all__ = ['SymmetryResult', 'detect', 'detect_from_data']
