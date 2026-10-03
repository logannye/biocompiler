"""Supplied expression windows and source-side RNA deployment requirements.

Time is seconds from the explicitly shared start of declared exposure. A window
describes availability to execute the supplied component contract, not RNA
concentration, tissue delivery probability, effector clearance or clinical
duration. Bounds are independent closed intervals; no correlation is inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from typing import ClassVar

from biocompiler.ir.molecule_records import _MoleculeRecord, _text
from biocompiler.ir.payload_contracts import _assumptions
from biocompiler.ir.serialization import require


MAX_DEPLOYMENT_SECONDS = 31_536_000
DEPLOYMENT_CLOCK = "declared_exposure_start"


def _time(value, label):
    require(type(value) in (int, float) and math.isfinite(value)
            and 0 <= value <= MAX_DEPLOYMENT_SECONDS,
            f"Invalid {label}; require finite nonnegative seconds within the deployment bound.")


def _assume(record):
    values = _assumptions(record.assumptions)
    require(bool(values), "Deployment timing requires explicit supplied assumptions.")
    object.__setattr__(record, "assumptions", values)
    require(record.clock == DEPLOYMENT_CLOCK, "Unsupported RNA deployment clock.")


@dataclass(frozen=True)
class RNAAvailabilityContract(_MoleculeRecord):
    """Availability of one local material placement under supplied assumptions.

    Every possible onset/duration pair must satisfy a requested window. Thus the
    guaranteed interval is [onset_max, onset_min + duration_min], which can be
    empty. The latest possible end is onset_max + duration_max. Empty guaranteed
    overlap is a selection diagnostic, not malformed component authority.
    """

    id: str
    placement_id: str
    onset_min_seconds: float
    onset_max_seconds: float
    duration_min_seconds: float
    duration_max_seconds: float
    assumptions: tuple[str, ...]
    clock: str = DEPLOYMENT_CLOCK
    schema_version: ClassVar[str] = "biocompiler.rna_availability_contract.v0.1"

    def __post_init__(self):
        _text(self.id, "RNA availability identity")
        _text(self.placement_id, "RNA availability placement")
        for key in ("onset_min_seconds", "onset_max_seconds",
                    "duration_min_seconds", "duration_max_seconds"):
            _time(getattr(self, key), key)
        require(self.onset_min_seconds <= self.onset_max_seconds,
                "RNA availability onset bounds are reversed.")
        require(0 < self.duration_min_seconds <= self.duration_max_seconds,
                "RNA availability duration must have positive ordered bounds.")
        require(Fraction(str(self.onset_max_seconds)) + Fraction(str(self.duration_max_seconds))
                <= MAX_DEPLOYMENT_SECONDS,
                "RNA availability exceeds the deployment time bound.")
        _assume(self)
        self._check_resources()


@dataclass(frozen=True)
class RNADeploymentRequirement(_MoleculeRecord):
    """A required common execution window for a role's complete delivery group.

    Every selected member placement in that group/role must satisfy the window
    and destination, including helpers and complex-member placements. An optional
    latest unavailability bound limits expression-contract availability only.
    It does not assert removal of previously produced effectors or RNA clearance.
    """

    id: str
    delivery_group_id: str
    recipient_role: str
    compartment: str
    required_from_seconds: float
    required_until_seconds: float
    assumptions: tuple[str, ...]
    unavailable_after_seconds: float | None = None
    require_same_recipient: bool = True
    clock: str = DEPLOYMENT_CLOCK
    schema_version: ClassVar[str] = "biocompiler.rna_deployment_requirement.v0.1"

    def __post_init__(self):
        for key in ("id", "delivery_group_id", "recipient_role", "compartment"):
            _text(getattr(self, key), key)
        _time(self.required_from_seconds, "required window start")
        _time(self.required_until_seconds, "required window end")
        require(self.required_from_seconds < self.required_until_seconds,
                "Deployment requires a nonempty execution window.")
        if self.unavailable_after_seconds is not None:
            _time(self.unavailable_after_seconds, "latest expression unavailability")
            require(self.unavailable_after_seconds >= self.required_until_seconds,
                    "Expression unavailability precedes its required window.")
        require(type(self.require_same_recipient) is bool,
                "Same-recipient deployment requirement must be Boolean.")
        _assume(self)
        self._check_resources()
