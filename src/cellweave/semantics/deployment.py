"""Frozen delivery assumptions, distinct from recognition and biological evidence."""

from dataclasses import dataclass, fields as record_fields
from typing import ClassVar

from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.ir.serialization import JsonArtifact, fields, name, require
from cellweave.semantics.component_contracts import ValueDomain
from cellweave.semantics.context import PayloadFormat
from cellweave.semantics.human_target import TargetClaim
from cellweave.semantics.realization import _duration, _interval
from cellweave.semantics.types import DURATION, Interval, ScalarLiteral, decode_binding


def _window(data):
    return decode_binding(data, Interval[DURATION])


def _optional_window(data):
    return None if data is None else _window(data)


def _collection(values, cls):
    require(isinstance(values, (tuple, list)), "Records must be an array.")
    require(
        all(isinstance(item, cls) for item in values), "Invalid deployment records."
    )
    require(
        len({item.id for item in values}) == len(values),
        "Duplicate deployment record IDs.",
    )
    return tuple(sorted(values, key=lambda item: item.id))


def _decode_collection(values, cls):
    require(isinstance(values, (tuple, list)), "Records must be an array.")
    return tuple(cls.from_dict(item) for item in values)


class _DeploymentRecord(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _fixed: ClassVar[dict] = {}

    def to_dict(self):
        def encode(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {
            "schema_version": self.schema_version,
            **self._fixed,
            **{
                field.name: encode(getattr(self, field.name))
                for field in record_fields(self)
            },
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {field.name for field in record_fields(cls)}
            | {"schema_version"}
            | set(cls._fixed),
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported deployment schema.",
        )
        for key, value in cls._fixed.items():
            require(
                type(data[key]) is type(value) and data[key] == value,
                f"Unsupported {key}.",
            )
        try:
            return cls(
                **{
                    field.name: cls._decoders.get(field.name, lambda value: value)(
                        data[field.name]
                    )
                    for field in record_fields(cls)
                }
            )
        except SerializationError:
            raise
        except (
            TypeError,
            ValueError,
            KeyError,
            AttributeError,
            IndexError,
            OverflowError,
            RecursionError,
        ) as error:
            raise SerializationError(f"Invalid {cls.__name__}: {error}") from error

    def _utf8(self):
        try:
            self.to_json(indent=None).encode("utf-8")
        except UnicodeError as error:
            raise SerializationError(
                "Deployment strings must be valid UTF-8."
            ) from error


@dataclass(frozen=True)
class DeliveryPlatformSpec(_DeploymentRecord):
    identity: PinnedIdentity
    payload_format: PayloadFormat
    administration_context: TargetClaim
    recipient_targeting: TargetClaim
    support: TargetClaim
    schema_version: ClassVar[str] = "cellweave.delivery_platform_spec.v0.1"
    _decoders: ClassVar[dict] = {
        "identity": PinnedIdentity.from_dict,
        "payload_format": PayloadFormat,
        **dict.fromkeys(
            ("administration_context", "recipient_targeting", "support"),
            TargetClaim.from_dict,
        ),
    }

    def __post_init__(self):
        require(
            isinstance(self.identity, PinnedIdentity)
            and self.identity.kind in {"source", "reference"},
            "Delivery requires an independently retainable source/reference specification identity.",
        )
        require(
            isinstance(self.payload_format, PayloadFormat),
            "Delivery modality must be explicit DNA or RNA.",
        )
        for key in ("administration_context", "recipient_targeting", "support"):
            require(
                isinstance(getattr(self, key), TargetClaim),
                f"{key} requires an explicit TargetClaim.",
            )
        self._utf8()


@dataclass(frozen=True)
class ExposureAssumption(_DeploymentRecord):
    id: str
    observable: str
    compartment: str
    domain: ValueDomain
    support: TargetClaim
    schema_version: ClassVar[str] = "cellweave.exposure_assumption.v0.1"
    _decoders: ClassVar[dict] = {
        "domain": ValueDomain.from_dict,
        "support": TargetClaim.from_dict,
    }

    def __post_init__(self):
        for key in ("id", "observable", "compartment"):
            name(getattr(self, key), key)
        require(
            isinstance(self.domain, ValueDomain)
            and self.domain.dtype.kind == "scalar"
            and self.domain.kind in {"scalar_interval", "unknown"},
            "Exposure requires a scalar domain or explicitly unknown bounds.",
        )
        require(
            self.domain.kind == "unknown" or self.domain.lower >= 0,
            "Exposure cannot have negative bounds.",
        )
        require(
            isinstance(self.support, TargetClaim), "Exposure support must be explicit."
        )
        self._utf8()


@dataclass(frozen=True)
class ExpressionTiming(_DeploymentRecord):
    """Expression competence relative to deployment, not secretion activation."""

    onset: Interval | None
    duration: Interval | None
    behavior_start: ScalarLiteral
    unknown_reason: str | None
    support: TargetClaim
    schema_version: ClassVar[str] = "cellweave.expression_timing.v0.1"
    _decoders: ClassVar[dict] = {
        "onset": _optional_window,
        "duration": _optional_window,
        "behavior_start": lambda value: decode_binding(value, DURATION),
        "support": TargetClaim.from_dict,
    }
    _fixed: ClassVar[dict] = {
        "clock": "start_of_declared_exposure",
        "availability": "closed_window_from_onset_through_onset_plus_duration",
    }

    def __post_init__(self):
        for key in ("onset", "duration"):
            value = getattr(self, key)
            if value is not None:
                value = _interval(value, DURATION, key)
                require(
                    value.lower.canonical_value > 0
                    if key == "duration"
                    else value.lower.canonical_value >= 0,
                    "Expression onset must be nonnegative and duration positive.",
                )
                object.__setattr__(self, key, value)
        if self.onset is None or self.duration is None:
            name(self.unknown_reason, "Unknown timing reason")
        else:
            require(
                self.unknown_reason is None,
                "Known timing cannot carry an unknown reason.",
            )
        object.__setattr__(
            self, "behavior_start", _duration(self.behavior_start, "behavior start")
        )
        require(
            isinstance(self.support, TargetClaim), "Timing requires explicit support."
        )
        self._utf8()


@dataclass(frozen=True)
class CoPayloadRequirement(_DeploymentRecord):
    id: str
    payload_identity: PinnedIdentity
    capability: str
    destination: str
    required_overlap: Interval
    support: TargetClaim
    schema_version: ClassVar[str] = "cellweave.co_payload_requirement.v0.1"
    _fixed: ClassVar[dict] = {
        "recipient_scope": "same_selected_recipient_cell",
        "required": True,
    }
    _decoders: ClassVar[dict] = {
        "payload_identity": PinnedIdentity.from_dict,
        "required_overlap": _window,
        "support": TargetClaim.from_dict,
    }

    def __post_init__(self):
        for key in ("id", "capability", "destination"):
            name(getattr(self, key), key)
        require(
            isinstance(self.payload_identity, PinnedIdentity)
            and self.payload_identity.kind == "reference",
            "Co-payload requirements need a pinned payload reference.",
        )
        overlap = _interval(self.required_overlap, DURATION, "required overlap")
        require(
            0 <= overlap.lower.canonical_value < overlap.upper.canonical_value,
            "Same-cell overlap must have nonnegative start and positive extent.",
        )
        object.__setattr__(self, "required_overlap", overlap)
        require(
            isinstance(self.support, TargetClaim),
            "Co-payload support must be explicit.",
        )
        self._utf8()


@dataclass(frozen=True)
class DeploymentContract(_DeploymentRecord):
    id: str
    target_fingerprint: str
    recipient_role: str
    platform: DeliveryPlatformSpec
    intended_population: TargetClaim
    excluded_population: TargetClaim
    intracellular_destination: str
    exposure_window: Interval
    exposures: tuple[ExposureAssumption, ...]
    timing: ExpressionTiming
    unintended_recipients: TargetClaim
    co_payloads: tuple[CoPayloadRequirement, ...]
    schema_version: ClassVar[str] = "cellweave.deployment_contract.v0.1"
    _fixed: ClassVar[dict] = {
        "time_origin": "start_of_declared_exposure",
        "delivery_targeting_is_disease_recognition": False,
    }
    _decoders: ClassVar[dict] = {
        "platform": DeliveryPlatformSpec.from_dict,
        **dict.fromkeys(
            ("intended_population", "excluded_population", "unintended_recipients"),
            TargetClaim.from_dict,
        ),
        "exposure_window": _window,
        "exposures": lambda data: _decode_collection(data, ExposureAssumption),
        "timing": ExpressionTiming.from_dict,
        "co_payloads": lambda data: _decode_collection(data, CoPayloadRequirement),
    }

    def __post_init__(self):
        for key in ("id", "recipient_role", "intracellular_destination"):
            name(getattr(self, key), key)
        require(
            isinstance(self.target_fingerprint, str)
            and len(self.target_fingerprint) == 64
            and set(self.target_fingerprint) <= set("0123456789abcdef"),
            "Deployment must pin the entire human target identity.",
        )
        require(
            isinstance(self.platform, DeliveryPlatformSpec),
            "Expected DeliveryPlatformSpec.",
        )
        require(isinstance(self.timing, ExpressionTiming), "Expected ExpressionTiming.")
        for key in (
            "intended_population",
            "excluded_population",
            "unintended_recipients",
        ):
            require(
                isinstance(getattr(self, key), TargetClaim), f"{key} must be explicit."
            )
        window = _interval(self.exposure_window, DURATION, "exposure window")
        require(
            window.lower.canonical_value == 0 and window.upper.canonical_value > 0,
            "Exposure window must begin at zero and have positive extent.",
        )
        object.__setattr__(self, "exposure_window", window)
        object.__setattr__(
            self, "exposures", _collection(self.exposures, ExposureAssumption)
        )
        require(
            bool(self.exposures),
            "At least one explicit exposure assumption is required; omission is not unlimited exposure.",
        )
        require(
            len({(item.observable, item.compartment) for item in self.exposures})
            == len(self.exposures),
            "Exposure endpoints must be unique; aliases cannot hide conflicting bounds.",
        )
        object.__setattr__(
            self, "co_payloads", _collection(self.co_payloads, CoPayloadRequirement)
        )
        self._utf8()

    @property
    def claims(self):
        return (
            ("platform.administration_context", self.platform.administration_context),
            ("platform.recipient_targeting", self.platform.recipient_targeting),
            ("platform.support", self.platform.support),
            ("intended_population", self.intended_population),
            ("excluded_population", self.excluded_population),
            ("timing", self.timing.support),
            ("unintended_recipients", self.unintended_recipients),
            *((f"exposures.{item.id}", item.support) for item in self.exposures),
            *((f"co_payloads.{item.id}", item.support) for item in self.co_payloads),
        )

    @property
    def unresolved_evidence(self):
        return tuple(path for path, _ in self.claims)
