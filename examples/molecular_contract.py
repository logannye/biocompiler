"""Connect a requested FAP response to an exact CDS while retaining evidence gaps.

The readout bands and one-second deadlines below are software examples of
requested obligations, not measured biological parameters or recommendations.
Run: PYTHONPATH=src python examples/molecular_contract.py [--output DIRECTORY]
"""

import argparse
from dataclasses import replace
from pathlib import Path

import cellweave as cw
from cellweave.compiler.molecular import run_molecular_pipeline
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.semantics.types import BOOLEAN, DURATION
from cellweave.synthesis.construct import prepare_reference_construct

if __package__:
    from .reference_construct import reference_request
else:
    from reference_construct import reference_request


def requested_fap_contract():
    construct_request, manifest, registry = reference_request("RNA")
    target = cw.TargetContext(
        "requested_murine_T_cell_FAP_context", "1", cw.PayloadFormat.RNA
    )
    construct_request = prepare_reference_construct(
        manifest,
        construct_request.references[0].selection,
        replace(construct_request.composition, target=target),
        registry,
    )
    manifests = {manifest.reference_set_id: manifest}
    molecular_build = run_molecular_pipeline(construct_request, registry, manifests)
    therapy = cw.Therapy("requested_fap_contact_response")
    cells = therapy.engineer("responder", cell_type="murine_T_cell")
    signal = cells.contact.marker("FAP")
    action = cells.eliminate(cells.contact)
    rule = cells.when(signal.present(), name="requested_FAP_response").do(action)
    build_request = cw.BuildRequest.freeze(
        therapy.freeze(), target=target, artifact_scope="complete_payload"
    )
    behavior = cw.lower_to_behavior(build_request)
    response = cw.ResponseRequirement(
        "requested_target_response",
        rule.node_id,
        action.node_id,
        cw.Observable(
            "requested_normalized_contact_readout",
            cw.Level,
            cells.role,
            scope="contact",
        ),
        cw.Interval(0.9, 1),
        cw.Interval(0, 0.1),
        cw.Duration(1),
        cw.Duration(1),
    )
    requested_behavior = cw.BehaviorContract(
        "requested_FAP_response", behavior.fingerprint, (response,)
    )
    observed = cw.InputDomain(
        signal.node_id,
        "present",
        cw.Observable("requested_FAP_presence", BOOLEAN, cells.role, scope="contact"),
        (False, True),
    )
    domain = cw.OperatingDomain(
        "requested_contact_domain",
        "1",
        cells.role,
        (observed,),
        cw.Duration(4),
        max_contacts=1,
    )
    realization = cw.RealizationRequest.freeze(
        build_request, behavior, requested_behavior, domain
    )
    source = next(s for s in manifest.sources if s["id"] == "retained-html-excerpts")
    citation = cw.MolecularEvidence(
        "disclosed_cds",
        "sequence_identity",
        PinnedIdentity(
            "source", source["id"], source["publication_version"], source["sha256"]
        ),
        target.fingerprint,
        "associated_reference",
        "The selected patent-disclosed CDS is a study-associated reference; exact experimental composite/material identity and dynamics remain unestablished.",
    )
    contract = cw.MolecularImplementationContract.freeze(
        "requested_FAP_to_CDS_correspondence",
        realization,
        construct_request,
        molecular_build.candidate,
        input_bindings=(
            cw.MolecularInputBinding(
                signal.node_id, "present", "fap_cds", observed.observable
            ),
        ),
        response_bindings=(
            cw.MolecularResponseBinding(
                response.id,
                rule.node_id,
                action.node_id,
                "fap_cds",
                response.observable,
            ),
        ),
        assumptions=(
            "The named murine T-cell context is a requested context, not validated applicability.",
            "Response bands and deadlines are illustrative design obligations, not calibration data.",
            "No synthetic logic/delay model is assigned to the selected CAR CDS.",
            "The larger experimental P2A/RISR-RIAD context and complete transcript remain unreconciled.",
        ),
        parameters=(
            cw.MolecularParameter("activation_delay", DURATION),
            cw.MolecularParameter("recovery_delay", DURATION),
        ),
        evidence=(citation,),
    )
    inputs = (
        contract,
        realization,
        construct_request,
        molecular_build.construct,
        molecular_build.candidate,
        registry,
        manifests,
    )
    result = cw.check_molecular_implementation(*inputs)
    return inputs, result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    inputs, result = requested_fap_contract()
    contract, realization = inputs[:2]
    assert result.linkage_outcome is cw.CheckOutcome.PASS
    assert result.outcome is cw.CheckOutcome.UNKNOWN
    assert not result.passed
    assert result.freshness(*inputs).fresh
    print(f"Exact source/observation/CDS linkage: {result.linkage_outcome.value}")
    print(f"Molecular behavior: {result.outcome.value}")
    print("Unestablished: " + ", ".join(contract.unestablished_claims))
    try:
        cw.compile(realization)
    except cw.CompilationUnavailableError as error:
        assert "complete_payload_not_promoted" in {d.code for d in error.diagnostics}
        print(
            "Complete-payload compilation: unavailable; no promoted full-molecule reference"
        )
    else:
        raise AssertionError(
            "An unresolved molecular contract cannot complete a payload."
        )
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "molecular-contract.json").write_text(
            contract.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "molecular-behavior-result.json").write_text(
            result.to_json() + "\n", encoding="utf-8"
        )
        (args.output / "realization-request.json").write_text(
            realization.to_json() + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
