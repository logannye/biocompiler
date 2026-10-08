"""Propose a software RNA layout from explicitly frozen fragment placements."""

from biocompiler.ir.molecular_design import (
    MolecularDesignConstruct,
    MolecularDesignRequest,
)
from biocompiler.ir.serialization import require
from biocompiler.verification.admission import require_software_use

GENERATOR_VERSION = "biocompiler.molecular_design_generator.v0.1"


def generate_molecular_design_construct(
    request: MolecularDesignRequest,
) -> MolecularDesignConstruct:
    """Copy authored layout authority; this unchecked proposal certifies nothing.

    The checked pipeline admits the independently pinned fragment root before
    generation. This function does not choose biological components or invent
    missing regulatory regions, source sequences or chemistry.
    """
    require(
        isinstance(request, MolecularDesignRequest),
        "Expected a molecular design request.",
    )
    require_software_use(request.target, boundary="selection")
    return MolecularDesignConstruct(
        request_fingerprint=request.fingerprint,
        molecule_id=request.molecule_id,
        placements=request.placements,
        features=request.features,
        unknown_features=request.unknown_features,
    )
