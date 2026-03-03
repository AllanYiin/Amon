"""TaskGraph schemas shared by multiple runtime versions."""

from .v3.validate import detect_graph_version, parse_graph

__all__ = ["detect_graph_version", "parse_graph"]
