"""Correspondence records linking requirements to transformed representations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLink:
    """Record lineage; the link itself does not demonstrate semantic preservation."""

    requirement_id: str
    source_node_id: str
    target_node_id: str
    pass_name: str
