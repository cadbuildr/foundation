"""Utility functions for foundation compatibility."""

from .dag_utils import show_dag, show


def reset_ids():
    """Reset ID counters (no-op in new foundation since IDs are hash-based)."""
    pass


__all__ = ["reset_ids", "show_dag", "show"]
