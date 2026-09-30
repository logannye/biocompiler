"""Deterministic whole-CDS layout generation from independently pinned references.

Preparation freezes the requested assembly before a candidate is generated. Neither
operation grants acceptance: the current references, composition and candidate must
still pass the independent construct checker. No nucleotide spelling is emitted.
"""

from __future__ import annotations

from biocompiler.ir.composition import CompositionRequest
from biocompiler.ir.construct import (
    ComponentPlacement,
    ConstructCandidate,
    ConstructMolecule,
    ConstructReference,
    ConstructRequest,
    SequenceRange,
)
from biocompiler.ir.serialization import name, require
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from biocompiler.registry.references import ReferenceManifest

CONSTRUCT_GENERATOR_VERSION = "biocompiler.reference_construct_generator.v0.1"


def prepare_reference_construct(
    manifest: ReferenceManifest,
    selection: ReferenceSelection,
    composition: CompositionRequest,
    registry: ComponentRegistry,
    *,
    molecule_id: str = "reference_cds",
    source_request_fingerprint: str | None = None,
) -> ConstructRequest:
    """Freeze one selected whole DNA/RNA CDS and its structural source authority.

    ``selection`` is a caller-trusted identity supplied independently of the
    manifest. The manifest should be loaded with ``load_reference_manifest`` so
    retained local source and review files are checked. This function does not
    accept a prior success receipt and does not infer molecular behavior.
    """
    require(isinstance(composition, CompositionRequest), "Expected a composition.")
    require(isinstance(registry, ComponentRegistry), "Expected a component registry.")
    name(molecule_id, "Molecule ID")
    require(
        source_request_fingerprint in (None, composition.fingerprint),
        "Reference constructs use the current composition as source authority.",
    )
    require(
        len(composition.instances) == 1,
        "The reference construct profile supports one component on one molecule.",
    )
    require(
        not any(
            (
                composition.connections,
                composition.providers,
                composition.dependency_bindings,
                composition.resource_pools,
                composition.resource_bindings,
            )
        ),
        "The reference construct profile does not support additional dependencies or resources.",
    )
    instance = composition.instances[0]
    require(
        instance.placement == "encoded_here",
        "The reference construct profile does not support co-payload assembly.",
    )
    require(
        set(instance.requirement_ids) == set(composition.requirement_ids),
        "The selected reference component must retain every source requirement.",
    )
    expected = adapt_reference_component(manifest, selection)
    records = registry.resolve(composition.registry_lock)
    require(
        set(records) == {instance.id}
        and records[instance.id] == expected
        and composition.registry_lock.components == (instance.component,),
        "The selected component must exactly match the independently pinned CDS reference.",
    )
    record = manifest.record(selection.reference.id)
    require(
        composition.target.payload_format.value == record.alphabet,
        "Reference alphabet must match the frozen target modality.",
    )
    require(
        not instance.required_domain.constraints,
        "The CDS reference supplies no molecular operating-domain contract.",
    )
    molecule = ConstructMolecule(
        id=molecule_id,
        alphabet=record.alphabet,
        artifact_class=record.artifact_class,
        length=record.length,
        component_order=(instance.id,),
        topology="unspecified",
        completeness=record.completeness,
        unknown_features=record.unknown_features,
        compartment="unspecified",
    )
    placement = ComponentPlacement(
        instance_id=instance.id,
        molecule_id=molecule_id,
        component=instance.component,
        reference=selection.reference,
        source_range=SequenceRange(0, record.length),
        molecule_range=SequenceRange(0, record.length),
        orientation="forward",
        reading_frame=0,
        requirement_ids=instance.requirement_ids,
        source=instance.source,
    )
    return ConstructRequest(
        composition=composition,
        references=(ConstructReference(instance.id, selection),),
        molecules=(molecule,),
        placements=(placement,),
        assumptions=expected.assumptions,
        source_request_fingerprint=composition.fingerprint,
    )


def generate_construct(request: ConstructRequest) -> ConstructCandidate:
    """Copy the frozen supported layout into a candidate, without certifying it.

    Request parsing admits a richer inventory for inspection. Generation remains
    deliberately limited to one whole reference CDS; unsupported layouts cannot
    become supported merely by entering the generic schema.
    """
    require(isinstance(request, ConstructRequest), "Expected a construct request.")
    require(
        len(request.molecules)
        == len(request.placements)
        == len(request.references)
        == 1
        and len(request.composition.instances) == 1,
        "The reference construct profile supports one component on one molecule.",
    )
    require(
        not any(
            (
                request.features,
                request.junctions,
                request.regulatory_relations,
                request.dependencies,
                request.composition.connections,
                request.composition.providers,
                request.composition.dependency_bindings,
                request.composition.resource_pools,
                request.composition.resource_bindings,
            )
        ),
        "Subfeatures, junctions, regulatory layouts and co-payloads require a separate assembly profile.",
    )
    molecule, placement = request.molecules[0], request.placements[0]
    require(
        placement.source_range == SequenceRange(0, molecule.length)
        and placement.molecule_range == SequenceRange(0, molecule.length)
        and placement.orientation == "forward"
        and placement.reading_frame == 0
        and molecule.component_order == (placement.instance_id,)
        and molecule.topology == "unspecified"
        and molecule.completeness == "CDS-reference-only"
        and molecule.compartment == "unspecified",
        "The reference construct profile requires one complete forward CDS in frame zero with unknown delivered context.",
    )
    require(
        request.composition.instances[0].placement == "encoded_here"
        and request.source_request_fingerprint
        in (None, request.composition.fingerprint),
        "Reference constructs must retain their encoded component source authority.",
    )
    return ConstructCandidate(
        request_fingerprint=request.fingerprint,
        composition_fingerprint=request.composition.fingerprint,
        registry_lock=request.composition.registry_lock,
        molecules=request.molecules,
        placements=request.placements,
        features=request.features,
        junctions=request.junctions,
        regulatory_relations=request.regulatory_relations,
        dependencies=request.dependencies,
        assumptions=request.assumptions,
        evidence_policy=request.evidence_policy,
    )
