"""Explicit requested molecular behavior, separate from established sequence facts.

This first profile freezes correspondence and missing evidence. It provides no
calibrated biological adapter, and no record in this module grants acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.components import ComponentLock
from biocompiler.ir.molecular import _Record, _array, _decode_array, _enum, _hash
from biocompiler.ir.serialization import name, names, require
from biocompiler.semantics.realization import Observable
from biocompiler.semantics.types import (
    Interval,
    ScalarLiteral,
    TypeSpec,
    decode_binding,
)

MOLECULAR_CONTRACT_PROFILE = "biocompiler.molecular_correspondence.v0.1"
UNESTABLISHED_CLAIMS = (
    "molecular_observation_mapping",
    "context_applicability",
    "parameter_calibration",
    "model_validation",
    "uncertainty_characterization",
    "therapeutic_outcomes",
    "exact_experimental_material",
    "auxiliary_coding_processing_context",
)


def _utf8(record):
    try:
        record.to_json(indent=None).encode("utf-8")
    except UnicodeError as error:
        raise SerializationError(
            "Molecular contract strings must be valid UTF-8."
        ) from error


def _optional_name(value, label):
    if value is not None:
        name(value, label)


def _identity(value, kinds, label):
    require(isinstance(value, PinnedIdentity) and value.kind in kinds, label)


def _scalar(value):
    if value is None:
        return None
    dtype = TypeSpec.from_dict(value["type"])
    require(dtype.kind == "scalar", "Parameters require scalar quantities.")
    return decode_binding(value, dtype)


def _interval(value):
    if value is None:
        return None
    dtype = TypeSpec.from_dict(value["type"])
    require(dtype.kind == "interval", "Uncertainty requires a typed interval.")
    return decode_binding(value, dtype)


@dataclass(frozen=True)
class MolecularParameter(_Record):
    """A typed declared parameter; fitted values do not validate a model."""

    id: str
    dtype: TypeSpec
    category: str = "unestablished"
    value: ScalarLiteral | None = None
    source: PinnedIdentity | None = None
    method: str = "No calibrated value has been established."
    uncertainty: Interval | None = None
    schema_version: ClassVar[str] = "biocompiler.molecular_parameter.v0.1"
    _decoders: ClassVar[dict] = {
        "dtype": TypeSpec.from_dict,
        "value": _scalar,
        "source": lambda value: (
            PinnedIdentity.from_dict(value) if value is not None else None
        ),
        "uncertainty": _interval,
    }

    def __post_init__(self):
        name(self.id, "Parameter id")
        name(self.method, "Parameter method")
        require(
            isinstance(self.dtype, TypeSpec) and self.dtype.kind == "scalar",
            "A parameter requires a scalar type and units.",
        )
        _enum(
            self.category,
            {"unestablished", "assumed", "fitted", "measured"},
            "parameter category",
        )
        if self.category == "unestablished":
            require(
                self.value is None and self.uncertainty is None and self.source is None,
                "Unestablished parameters cannot supply values or evidence.",
            )
        else:
            require(
                isinstance(self.value, ScalarLiteral),
                "Established parameter declarations require a typed value.",
            )
            decode_binding(self.value.to_dict(), self.dtype)
            _identity(
                self.source,
                {"source", "evidence"},
                "Parameter declarations require pinned provenance.",
            )
        if self.uncertainty is not None:
            require(
                isinstance(self.uncertainty, Interval),
                "Uncertainty requires a typed interval.",
            )
            interval = decode_binding(self.uncertainty.to_dict(), Interval[self.dtype])
            require(
                interval.lower.canonical_value
                <= self.value.canonical_value
                <= interval.upper.canonical_value,
                "Declared value must lie in its uncertainty interval.",
            )

        _utf8(self)


@dataclass(frozen=True)
class MolecularEvidence(_Record):
    """A cited claim, never automatically accepted model or therapeutic evidence."""

    id: str
    category: str
    source: PinnedIdentity
    context_fingerprint: str
    material_relationship: str
    claim: str
    schema_version: ClassVar[str] = "biocompiler.molecular_evidence.v0.1"
    _decoders: ClassVar[dict] = {"source": PinnedIdentity.from_dict}

    def __post_init__(self):
        name(self.id, "Evidence id")
        name(self.claim, "Evidence claim")
        _enum(
            self.category,
            {
                "sequence_identity",
                "material_identity",
                "parameter_fitting",
                "model_validation",
                "uncertainty",
                "therapeutic_outcome",
            },
            "evidence category",
        )
        _identity(
            self.source,
            {"source", "evidence"},
            "Evidence requires a pinned source or evidence record.",
        )
        _hash(self.context_fingerprint, "Evidence context")
        _enum(
            self.material_relationship,
            {"associated_reference", "exact_material", "unestablished"},
            "evidence/material relationship",
        )

        _utf8(self)


@dataclass(frozen=True)
class MolecularInputBinding(_Record):
    signal_id: str
    field: str
    instance_id: str
    observable: Observable
    adapter_input: str | None = None
    schema_version: ClassVar[str] = "biocompiler.molecular_input_binding.v0.1"
    _decoders: ClassVar[dict] = {"observable": Observable.from_dict}

    def __post_init__(self):
        name(self.signal_id, "Signal id")
        name(self.instance_id, "Component instance")
        _enum(self.field, {"value", "present", "high", "low"}, "input field")
        require(isinstance(self.observable, Observable), "Expected an observable.")
        _optional_name(self.adapter_input, "Adapter input")
        _utf8(self)


@dataclass(frozen=True)
class MolecularResponseBinding(_Record):
    requirement_id: str
    rule_id: str
    specification_id: str
    instance_id: str
    observable: Observable
    adapter_output: str | None = None
    schema_version: ClassVar[str] = "biocompiler.molecular_response_binding.v0.1"
    _decoders: ClassVar[dict] = {"observable": Observable.from_dict}

    def __post_init__(self):
        for key in ("requirement_id", "rule_id", "specification_id", "instance_id"):
            name(getattr(self, key), key)
        require(isinstance(self.observable, Observable), "Expected an observable.")
        _optional_name(self.adapter_output, "Adapter output")
        _utf8(self)


@dataclass(frozen=True)
class MolecularImplementationContract(_Record):
    """Requested correspondence to independently selected exact molecular inputs.

    Source node identities are explicit and checked against the current frozen
    realization request. An adapter identity is only a proposal until a provider
    with separately versioned semantics and validation is implemented.
    """

    id: str
    version: str
    realization_request_fingerprint: str
    construct_request_fingerprint: str
    molecular_fingerprint: str
    target_fingerprint: str
    domain_fingerprint: str
    selected_components: tuple[ComponentLock, ...]
    input_bindings: tuple[MolecularInputBinding, ...]
    response_bindings: tuple[MolecularResponseBinding, ...]
    assumptions: tuple[str, ...] = ()
    parameters: tuple[MolecularParameter, ...] = ()
    evidence: tuple[MolecularEvidence, ...] = ()
    model_profile: str = MOLECULAR_CONTRACT_PROFILE
    adapter: PinnedIdentity | None = None
    unestablished_claims: tuple[str, ...] = UNESTABLISHED_CLAIMS
    schema_version: ClassVar[str] = "biocompiler.molecular_implementation_contract.v0.1"
    _decoders: ClassVar[dict] = {
        "selected_components": lambda value: _decode_array(value, ComponentLock),
        "input_bindings": lambda value: _decode_array(value, MolecularInputBinding),
        "response_bindings": lambda value: _decode_array(
            value, MolecularResponseBinding
        ),
        "parameters": lambda value: _decode_array(value, MolecularParameter),
        "evidence": lambda value: _decode_array(value, MolecularEvidence),
        "adapter": lambda value: (
            PinnedIdentity.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        for key in ("id", "version", "model_profile"):
            name(getattr(self, key), key)
        for key in (
            "realization_request_fingerprint",
            "construct_request_fingerprint",
            "molecular_fingerprint",
            "target_fingerprint",
            "domain_fingerprint",
        ):
            _hash(getattr(self, key), key)
        for key, cls in (
            ("selected_components", ComponentLock),
            ("input_bindings", MolecularInputBinding),
            ("response_bindings", MolecularResponseBinding),
            ("parameters", MolecularParameter),
            ("evidence", MolecularEvidence),
        ):
            object.__setattr__(self, key, _array(getattr(self, key), cls, key))
        require(
            bool(self.selected_components)
            and bool(self.input_bindings)
            and bool(self.response_bindings),
            "Molecular contracts require selected components and input/response correspondence.",
        )
        for key, identities in (
            ("components", [item.node_id for item in self.selected_components]),
            (
                "input bindings",
                [(item.signal_id, item.field) for item in self.input_bindings],
            ),
            (
                "response bindings",
                [item.requirement_id for item in self.response_bindings],
            ),
            ("parameters", [item.id for item in self.parameters]),
            ("evidence", [item.id for item in self.evidence]),
        ):
            require(
                len(set(identities)) == len(identities), f"Duplicate molecular {key}."
            )
        for key in ("assumptions", "unestablished_claims"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            set(UNESTABLISHED_CLAIMS) <= set(self.unestablished_claims),
            "The correspondence profile cannot discharge biological claims.",
        )
        if self.adapter is not None:
            _identity(
                self.adapter,
                {"model"},
                "Adapter proposals require a pinned model identity.",
            )
        else:
            require(
                all(item.adapter_input is None for item in self.input_bindings)
                and all(item.adapter_output is None for item in self.response_bindings),
                "Named adapter ports require an explicit adapter identity.",
            )

        _utf8(self)

    @classmethod
    def freeze(
        cls,
        id,
        realization_request,
        construct_request,
        molecular,
        *,
        input_bindings,
        response_bindings,
        assumptions=(),
        parameters=(),
        evidence=(),
        model_profile=MOLECULAR_CONTRACT_PROFILE,
        adapter=None,
        unestablished_claims=UNESTABLISHED_CLAIMS,
        version="1",
    ):
        """Freeze caller-selected correspondence; acceptance still needs a check."""
        from biocompiler.compiler.request import RealizationRequest
        from biocompiler.ir.construct import ConstructRequest
        from biocompiler.ir.molecular import MolecularArtifact

        require(
            isinstance(realization_request, RealizationRequest),
            "Expected realization authority.",
        )
        require(
            isinstance(construct_request, ConstructRequest),
            "Expected construct authority.",
        )
        require(
            isinstance(molecular, MolecularArtifact), "Expected molecular candidate."
        )
        return cls(
            id,
            version,
            realization_request.fingerprint,
            construct_request.fingerprint,
            molecular.fingerprint,
            realization_request.target.fingerprint,
            realization_request.domain.fingerprint,
            construct_request.composition.registry_lock.components,
            input_bindings,
            response_bindings,
            assumptions,
            parameters,
            evidence,
            model_profile,
            adapter,
            unestablished_claims,
        )
