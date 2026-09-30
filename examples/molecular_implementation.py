"""Checked precursor architecture with artificial, nonfunctional test sequences.

This example demonstrates research design records, never a therapeutic recipe.
The product, signal segment, processing boundary, chemistry and host support are
explicit software fixtures; no physical processing or secretion is established.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import biocompiler as bc
from biocompiler.ir.implementation import DEPENDENCY_COMPARTMENTS

if __package__:
    from .human_acceptance import make_human_acceptance
else:
    from human_acceptance import make_human_acceptance


def fixture_source():
    source = make_human_acceptance()
    behavior = source.behavior_request
    old_target = behavior.target
    claims = list(old_target.human_target.host_dependencies)
    for capability, compartment in DEPENDENCY_COMPARTMENTS.items():
        if any(
            item.capability == capability and item.compartment == compartment
            for item in claims
        ):
            continue
        claims.append(
            bc.HumanHostDependency(
                "precursor." + capability,
                capability,
                compartment,
                bc.TargetClaim(
                    "Declared precursor fixture host dependency: " + capability,
                    "assumed",
                    (),
                    "Software-only declaration; no applicable biological evidence.",
                ),
            )
        )
    target = replace(
        old_target,
        context_version="precursor-fixture-1",
        compartments=tuple(
            sorted(set(old_target.compartments) | set(DEPENDENCY_COMPARTMENTS.values()))
        ),
        capabilities=tuple(
            sorted(set(old_target.capabilities) | set(DEPENDENCY_COMPARTMENTS))
        ),
        human_target=replace(old_target.human_target, host_dependencies=tuple(claims)),
    )
    behavior = replace(
        behavior, build_request=replace(behavior.build_request, target=target)
    )
    deployment = replace(
        source.deployment_request,
        behavior_request=behavior,
        deployment=replace(
            source.deployment_request.deployment, target_fingerprint=target.fingerprint
        ),
    )
    return replace(
        source,
        deployment_request=deployment,
        acceptance=replace(
            source.acceptance, behavior_fingerprint=behavior.fingerprint
        ),
    )


def fixture_library(source):
    report = bc.analyze_implementation_requirements(source)
    product = report.products[0]
    target = source.target

    def sequence(identity, bases):
        return bc.SequenceAuthority(
            identity,
            bases,
            hashlib.sha256(bases.encode("ascii")).hexdigest(),
            "software-fixture:molecular_implementation:" + identity,
            provenance="software_fixture",
        )

    dependencies = tuple(
        bc.DependencyRequirement(
            "needs." + capability, capability, product.role_id, "cell", compartment
        )
        for capability, compartment in DEPENDENCY_COMPARTMENTS.items()
    )
    providers = tuple(
        bc.Provider(
            "host." + item.id,
            "host",
            (
                bc.ProvidedCapability(
                    item.capability, item.role, item.scope, item.compartment
                ),
            ),
            (target.fingerprint,),
            evidence_refs=("software-fixture:unestablished-host-support",),
        )
        for item in dependencies
    )
    bindings = tuple(
        bc.ImplementationDependencyBinding(item.id, provider.id)
        for item, provider in zip(dependencies, providers)
    )
    features = tuple(
        bc.PayloadFeature(key, "known", "software-fixture:chemistry", value)
        for key, value in (
            ("cap", "cap1"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "capped"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    architectures = []
    for identity, prefix, peptide in (
        ("compact", "AUGGCU", "MA"),
        ("extended", "AUGGCUGCU", "MAA"),
    ):
        segments = (
            bc.CodingSegment(
                "signal",
                "signal_peptide",
                sequence(identity + ".signal", prefix),
                peptide,
            ),
            bc.CodingSegment(
                "product", "mature_product", sequence("product", "UUU"), "F"
            ),
            bc.CodingSegment("stop", "terminal_stop", sequence("stop", "UAA"), "*"),
        )
        architectures.append(
            bc.SecretedRNAArchitecture(
                identity,
                "1",
                product.product,
                target.fingerprint,
                sequence("front", "GG"),
                sequence("back", "CC"),
                segments,
                tuple(
                    bc.CodingJunction(left.id, right.id)
                    for left, right in zip(segments, segments[1:])
                ),
                peptide + "F*",
                "F",
                len(peptide),
                dependencies,
                bindings,
                features,
                sequence("tail", "AAAA"),
            )
        )
    return bc.ImplementationLibrary(
        "artificial_precursor_architectures", "1", tuple(architectures), providers
    )


def make_implementation_request(*, constraints=None):
    source = fixture_source()
    return bc.ImplementationRequest(
        source, fixture_library(source), constraints or bc.ImplementationConstraints()
    )


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    baseline = make_implementation_request()
    report = bc.analyze_implementation_requirements(baseline.source)
    bc.verify_implementation_requirements(report, expected_source=baseline.source)
    (output / "source.json").write_text(
        baseline.source.to_json() + "\n", encoding="utf-8"
    )
    (output / "requirements.json").write_text(report.to_json() + "\n", encoding="utf-8")
    cases = {
        "compact": (baseline, "GGAUGGCUUUUUAACCAAAA"),
        "extended": (
            replace(
                baseline,
                constraints=bc.ImplementationConstraints(
                    allowed_architecture_ids=("extended",)
                ),
            ),
            "GGAUGGCUGCUUUUUAACCAAAA",
        ),
        "strict": (
            replace(
                baseline,
                constraints=bc.ImplementationConstraints(
                    require_implementation_complete=True
                ),
            ),
            None,
        ),
        "exhausted": (
            replace(baseline, constraints=bc.ImplementationConstraints(max_length=1)),
            None,
        ),
        "missing_host": (
            replace(baseline, library=replace(baseline.library, providers=())),
            None,
        ),
    }
    results = []
    for label, (request, expected) in cases.items():
        compilation = bc.compile(request)
        record = compilation.record
        assert (record.molecule.sequence if record.molecule else None) == expected
        assert record.request.source == request.source
        assert (
            bc.verify_implementation_build(record, expected_request=request) == record
        )
        assert record.therapeutic_implementation == "partial"
        assert record.human_therapeutic_admission == "not_admitted"
        (output / (label + ".request.json")).write_text(
            request.to_json() + "\n", encoding="utf-8"
        )
        (output / (label + ".build.json")).write_text(
            record.to_json() + "\n", encoding="utf-8"
        )
        if expected is not None:
            assert record.construct.mature_protein == "F"
            assert record.plan.unresolved_obligation_ids
            (output / (label + ".fasta")).write_text(
                bc.export_implementation_fasta(record, expected_request=request),
                encoding="ascii",
            )
        results.append(
            dict(
                case=label,
                status=record.status,
                build_fingerprint=record.fingerprint,
                length_nt=len(expected) if expected is not None else None,
            )
        )
    print(
        json.dumps(
            dict(
                scope="secreted_precursor_structure",
                physical_function="unestablished",
                human_therapeutic_admission="not_admitted",
                cases=results,
            ),
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("generated/molecular-implementation")
    )
    run(parser.parse_args().output)


if __name__ == "__main__":
    main()
