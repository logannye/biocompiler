"""Check final payload correspondence to independent required-region authority.

An empty diagnostic result means correspondence to supplied declarations only.
It is not a regulatory-function check, an independent source review, a source
fidelity assessment or human therapeutic admission. The complete human circuit
request remains part of the bundle and is never replaced by this narrower gate.
"""

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import CircuitMoleculeSet
from biocompiler.ir.circuit_payloads import (
    MAX_PAYLOAD_CONTRACTS,
    PAYLOAD_MODALITY_CAPABILITIES,
    PayloadStructureContract,
)
from biocompiler.ir.molecule_records import _records


def check_payload_structures(contracts, *, bundle):
    """Return contradictions and unsupported obligations without upgrading proof.

    Exactly one contract must name each distinct covalent ``requested_payload``
    component. Nucleotide complexes expand to their declared constituent records;
    roles and stoichiometry do not duplicate a component contract. Declared
    membership establishes no binding, complementarity or co-delivery. Required
    features are checked in their nominated frame with no inferred region order,
    non-overlap rule or universal biological list.
    """
    diagnostics, unsupported = [], []
    if contracts is None:
        contracts = ()
    try:
        contracts = _records(
            contracts,
            PayloadStructureContract,
            MAX_PAYLOAD_CONTRACTS,
            "payload structure contracts",
            key="member_id",
        )
    except SerializationError:
        return ("payload_contract_inventory_invalid",), ()
    if not contracts:
        unsupported.append("payload_authority_missing")
    if not isinstance(bundle, CircuitMoleculeSet):
        return ("payload_bundle_invalid",), tuple(unsupported)
    try:
        bundle = CircuitMoleculeSet.from_dict(bundle.to_dict())
    except SerializationError:
        return ("payload_bundle_invalid",), tuple(unsupported)
    subjects = {
        role.subject_id
        for role in bundle.role_instances
        if role.purpose == "requested_payload"
    }
    molecules = {molecule.id: molecule for molecule in bundle.molecules}
    complexes = {complex_.id: complex_ for complex_ in bundle.complexes}
    requested = set()
    for identity in sorted(subjects):
        if identity in molecules:
            requested.add(identity)
            continue
        complex_ = complexes[identity]
        if complex_.kind not in {"dna_duplex", "rna_complex"}:
            unsupported.append(f"payload_complex_modality_unsupported:{identity}")
            continue
        for component in complex_.constituents:
            requested.add(component.molecule_id)
            if component.stoichiometry is None:
                unsupported.append(
                    f"payload_complex_stoichiometry_unknown:{identity}/{component.molecule_id}"
                )
    by_member = {contract.member_id: contract for contract in contracts}
    for identity in sorted(requested - by_member.keys()):
        unsupported.append(f"payload_authority_missing:{identity}")
    for identity in sorted(by_member.keys() - requested):
        diagnostics.append(f"payload_contract_extra:{identity}")
    for identity in sorted(requested):
        molecule = molecules[identity]
        alphabet = PAYLOAD_MODALITY_CAPABILITIES.get(
            (molecule.form, molecule.space.topology)
        )
        if alphabet is None:
            unsupported.append(f"payload_modality_unsupported:{identity}")
        elif molecule.space.alphabet != alphabet:
            diagnostics.append(f"payload_modality_alphabet:{identity}")
        if molecule.sequence_extent != "complete":
            unsupported.append(f"payload_extent_incomplete:{identity}")
        if not molecule.chemistry.declared_nominal_complete:
            unsupported.append(f"payload_chemistry_incomplete:{identity}")
        contract = by_member.get(identity)
        if contract is None:
            continue
        if contract.form != molecule.form:
            diagnostics.append(f"payload_form_mismatch:{identity}")
        if contract.topology != molecule.space.topology:
            diagnostics.append(f"payload_topology_mismatch:{identity}")
        if contract.provenance.status != "declared":
            unsupported.append(f"payload_authority_undeclared:{identity}")
        features = {feature.id: feature for feature in molecule.features}
        for required in contract.regions:
            label = identity + "/" + required.feature_id
            feature = features.get(required.feature_id)
            if feature is None:
                diagnostics.append(f"payload_region_missing:{label}")
                continue
            if feature.kind != required.kind:
                diagnostics.append(f"payload_region_kind_mismatch:{label}")
            if feature.provenance.status != "declared":
                unsupported.append(f"payload_boundary_authority_undeclared:{label}")
            if feature.path is None:
                unsupported.append(f"payload_region_coordinates_unknown:{label}")
            elif feature.path.length == 0:
                diagnostics.append(f"payload_region_empty:{label}")
            else:
                try:
                    feature.path.validate_for(molecule.space)
                except SerializationError:
                    diagnostics.append(f"payload_region_coordinates_invalid:{label}")
    return tuple(sorted(set(diagnostics))), tuple(sorted(set(unsupported)))
