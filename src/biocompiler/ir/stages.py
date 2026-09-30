"""Compiler abstraction boundaries, including supported and planned stages."""

from enum import StrEnum


class Stage(StrEnum):
    INTENT = "typed intent and contracts"
    BEHAVIOR = "behavioral IR"
    MECHANISM = "molecular mechanism IR"
    COMPONENTS = "selected component IR"
    CONSTRUCT = "construct IR"
    MOLECULAR = "sequence and molecular specification"


STAGE_ORDER: tuple[Stage, ...] = tuple(Stage)
