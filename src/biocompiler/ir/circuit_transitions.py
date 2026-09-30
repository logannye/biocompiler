"""Explicit chemistry and annotation transitions; no biochemical fate is inferred."""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.molecule_chemistry import MoleculeChemistry
from biocompiler.ir.molecule_records import (
    DeclarationProvenance,
    MAX_TEXT_BYTES,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.serialization import require


MAX_DISPOSITIONS = 4096
MAX_COMPONENT_DESTINATIONS = 256
MAX_FEATURE_OUTPUTS = 256
CHEMISTRY_FACETS = frozenset(
    {"cap", "start_end", "finish_end", "terminal_tail", "modification_inventory"}
)


def _component(value):
    prefix = "modification:"
    _text(value, "Chemistry component", MAX_TEXT_BYTES + len(prefix))
    require(
        value in CHEMISTRY_FACETS or value.startswith(prefix),
        "Unknown chemistry component selector.",
    )
    if value.startswith(prefix):
        _text(value[len(prefix) :], "Modification occurrence selector")


def _provenance(value):
    require(
        isinstance(value, DeclarationProvenance),
        "Expected explicit transition provenance.",
    )


@dataclass(frozen=True)
class ChemistryDisposition(_MoleculeRecord):
    """Disposition of one source facet or ``modification:<occurrence_id>``.

    Replacement records may converge on one declared product facet. They do not
    claim retention; mapped copies require separate coordinate/identity checks.
    """

    source_id: str
    component: str
    decision: str
    destination_components: tuple[str, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.chemistry_disposition.v0.1"
    _decoders: ClassVar[dict] = {"provenance": DeclarationProvenance.from_dict}

    def __post_init__(self):
        _text(self.source_id, "Chemistry source identity")
        _component(self.component)
        _choice(
            self.decision,
            {"mapped_copy", "declared_replacement", "not_carried", "unknown"},
            "chemistry disposition",
        )
        require(
            isinstance(self.destination_components, (tuple, list))
            and len(self.destination_components) <= MAX_COMPONENT_DESTINATIONS,
            "Invalid destination chemistry inventory.",
        )
        for component in self.destination_components:
            _component(component)
        require(
            len(set(self.destination_components)) == len(self.destination_components),
            "Duplicate destination chemistry components.",
        )
        object.__setattr__(
            self, "destination_components", tuple(sorted(self.destination_components))
        )
        require(
            not self.destination_components
            if self.decision == "not_carried"
            else bool(self.destination_components)
            if self.decision in {"mapped_copy", "declared_replacement"}
            else True,
            "Chemistry disposition and destination component count disagree.",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class ChemistryTransition(_MoleculeRecord):
    """Either exact whole-value inheritance or explicit product chemistry."""

    mode: str
    output: MoleculeChemistry | None
    dispositions: tuple[ChemistryDisposition, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.chemistry_transition.v0.1"
    _decoders: ClassVar[dict] = {
        "output": _optional(MoleculeChemistry),
        "dispositions": _decode_records(ChemistryDisposition, MAX_DISPOSITIONS),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _choice(
            self.mode,
            {"exact_inheritance", "explicit_output"},
            "chemistry transition mode",
        )
        require(
            isinstance(self.dispositions, (tuple, list))
            and len(self.dispositions) <= MAX_DISPOSITIONS,
            "Invalid chemistry disposition inventory.",
        )
        require(
            all(isinstance(item, ChemistryDisposition) for item in self.dispositions),
            "Expected chemistry dispositions.",
        )
        keys = [(item.source_id, item.component) for item in self.dispositions]
        require(len(set(keys)) == len(keys), "Duplicate source chemistry dispositions.")
        object.__setattr__(
            self,
            "dispositions",
            tuple(
                sorted(
                    self.dispositions, key=lambda item: (item.source_id, item.component)
                )
            ),
        )
        if self.mode == "exact_inheritance":
            require(
                self.output is None and not self.dispositions,
                "Exact inheritance cannot override chemistry or carry replacement dispositions.",
            )
        else:
            require(
                isinstance(self.output, MoleculeChemistry),
                "Explicit output requires a complete chemistry declaration.",
            )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class FeatureDisposition(_MoleculeRecord):
    """Explicit fate of an annotation, without asserting its biological effect."""

    source_id: str
    feature_id: str
    decision: str
    outputs: tuple[MoleculeFeature, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.feature_disposition.v0.1"
    _decoders: ClassVar[dict] = {
        "outputs": _decode_records(MoleculeFeature, MAX_FEATURE_OUTPUTS),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.source_id, "Feature source identity")
        _text(self.feature_id, "Source feature identity")
        _choice(
            self.decision,
            {
                "exact",
                "partial",
                "split",
                "not_carried",
                "outside_selection",
                "unknown",
            },
            "feature disposition",
        )
        object.__setattr__(
            self,
            "outputs",
            _records(
                self.outputs, MoleculeFeature, MAX_FEATURE_OUTPUTS, "mapped features"
            ),
        )
        expected = len(self.outputs)
        require(
            expected == 1
            if self.decision in {"exact", "partial"}
            else expected >= 2
            if self.decision == "split"
            else expected == 0
            if self.decision in {"not_carried", "outside_selection"}
            else True,
            "Feature disposition and output count disagree.",
        )
        _provenance(self.provenance)
        self._check_resources()


@dataclass(frozen=True)
class FeatureTransition(_MoleculeRecord):
    """Exhaustive source annotation dispositions and independently added ones."""

    dispositions: tuple[FeatureDisposition, ...]
    added: tuple[MoleculeFeature, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.feature_transition.v0.1"
    _decoders: ClassVar[dict] = {
        "dispositions": _decode_records(FeatureDisposition, MAX_DISPOSITIONS),
        "added": _decode_records(MoleculeFeature, MAX_FEATURE_OUTPUTS),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(self.dispositions, (tuple, list))
            and len(self.dispositions) <= MAX_DISPOSITIONS,
            "Invalid feature disposition inventory.",
        )
        require(
            all(isinstance(item, FeatureDisposition) for item in self.dispositions),
            "Expected typed feature dispositions.",
        )
        keys = [(item.source_id, item.feature_id) for item in self.dispositions]
        require(len(set(keys)) == len(keys), "Duplicate source feature dispositions.")
        object.__setattr__(
            self,
            "dispositions",
            tuple(
                sorted(
                    self.dispositions,
                    key=lambda item: (item.source_id, item.feature_id),
                )
            ),
        )
        object.__setattr__(
            self,
            "added",
            _records(
                self.added, MoleculeFeature, MAX_FEATURE_OUTPUTS, "added features"
            ),
        )
        outputs = [
            feature.id for item in self.dispositions for feature in item.outputs
        ] + [feature.id for feature in self.added]
        require(
            len(outputs) <= MAX_FEATURE_OUTPUTS, "Total output feature limit exceeded."
        )
        require(
            len(set(outputs)) == len(outputs), "Duplicate output feature identities."
        )
        _provenance(self.provenance)
        self._check_resources()
