"""Archive molecular declarations, experimental amounts and separate run metadata."""

from collections.abc import Mapping
from dataclasses import dataclass
import math
from typing import ClassVar

from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_molecules import CircuitMoleculeSet, MAX_ROLES
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.molecule_records import (
    DeclarationProvenance,
    _MoleculeRecord,
    _decode_records,
    _records,
    _text,
    _bounded_tree,
)
from biocompiler.ir.serialization import fingerprint, require


MAX_AMOUNTS = 128


@dataclass(frozen=True)
class ExperimentalAmount(_MoleculeRecord):
    """One physical subject/preparation amount, possibly serving several roles.

    Roles are not independent doses. Quantities and units are declared and never
    converted, summed, inferred from role multiplicity or treated as observations
    establishing circuit function.
    """

    id: str
    subject_id: str
    subject_fingerprint: str
    preparation_id: str
    role_instance_ids: tuple[str, ...]
    quantity: int | float | None
    unit: str
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.molecular_experimental_amount.v0.1"
    _decoders: ClassVar[dict] = {"provenance": DeclarationProvenance.from_dict}

    def __post_init__(self):
        for key in ("id", "subject_id", "preparation_id", "unit"):
            _text(getattr(self, key), key)
        _hash(self.subject_fingerprint, "Amount subject record")
        require(
            isinstance(self.role_instance_ids, (tuple, list))
            and len(self.role_instance_ids) <= MAX_ROLES,
            "Invalid amount role inventory.",
        )
        for identity in self.role_instance_ids:
            _text(identity, "Amount role identity")
        require(
            len(set(self.role_instance_ids)) == len(self.role_instance_ids),
            "Duplicate amount role identity.",
        )
        object.__setattr__(
            self, "role_instance_ids", tuple(sorted(self.role_instance_ids))
        )
        require(
            self.quantity is None or type(self.quantity) in (int, float),
            "Amount requires a numeric declaration or explicit unknown.",
        )
        if type(self.quantity) is int:
            require(
                self.quantity.bit_length() <= 1024, "Amount integer limit exceeded."
            )
        if self.quantity is not None:
            require(
                self.quantity >= 0
                and (type(self.quantity) is int or math.isfinite(self.quantity)),
                "Amount must be finite and nonnegative.",
            )
        require(
            isinstance(self.provenance, DeclarationProvenance),
            "Amount requires explicit provenance.",
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitMoleculeRecord(_MoleculeRecord):
    bundle: CircuitMoleculeSet
    experimental_amounts: tuple[ExperimentalAmount, ...]
    run_metadata: Mapping
    schema_version: ClassVar[str] = "biocompiler.circuit_molecule_record.v0.1"
    _decoders: ClassVar[dict] = {
        "bundle": CircuitMoleculeSet.from_dict,
        "experimental_amounts": _decode_records(ExperimentalAmount, MAX_AMOUNTS),
    }

    def __post_init__(self):
        require(
            isinstance(self.bundle, CircuitMoleculeSet),
            "Expected complete molecular set declaration.",
        )
        object.__setattr__(
            self, "bundle", CircuitMoleculeSet.from_dict(self.bundle.to_dict())
        )
        object.__setattr__(
            self,
            "experimental_amounts",
            _records(
                self.experimental_amounts,
                ExperimentalAmount,
                MAX_AMOUNTS,
                "experimental amounts",
            ),
        )
        subjects = {
            item.id: item for item in (*self.bundle.molecules, *self.bundle.complexes)
        }
        roles = {item.id: item for item in self.bundle.role_instances}
        preparations = set()
        nominal_subjects = self.bundle._nominal_subject_identities()
        for amount in self.experimental_amounts:
            subject = subjects.get(amount.subject_id)
            require(
                subject is not None
                and subject.fingerprint == amount.subject_fingerprint,
                "Missing or stale experimental-amount subject.",
            )
            key = (
                amount.preparation_id,
                nominal_subjects[amount.subject_id],
            )
            require(
                key not in preparations,
                "A physical species/preparation amount must be declared once, with all shared roles; record aliases cannot duplicate it.",
            )
            preparations.add(key)
            for identity in amount.role_instance_ids:
                role = roles.get(identity)
                require(
                    role is not None
                    and role.subject_id == amount.subject_id
                    and role.subject_fingerprint == amount.subject_fingerprint,
                    "Amount role must refer to the same physical subject declaration.",
                )
        require(
            isinstance(self.run_metadata, Mapping) and len(self.run_metadata) <= 128,
            "Run metadata requires a bounded JSON object.",
        )
        _bounded_tree(self.run_metadata)
        object.__setattr__(self, "run_metadata", freeze_json(dict(self.run_metadata)))
        self._check_resources()

    @property
    def nominal_bundle_identity(self):
        return self.bundle.declared_nominal_bundle_identity

    @property
    def experimental_specification_identity(self):
        return fingerprint(
            {
                "profile": "declared_molecular_experiment.v0.1",
                "bundle": self.bundle.to_dict(),
                "amounts": [item.to_dict() for item in self.experimental_amounts],
            }
        )

    @property
    def artifact_fingerprint(self):
        return self.fingerprint
