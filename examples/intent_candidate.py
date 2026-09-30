"""Compile authored product choices into artificial RNA research candidates.

All part strings are nonfunctional software fixtures. The original human target,
conditional rule, deployment contract and prohibitions remain in the request.
"""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import biocompiler as bc

if __package__:
    from .human_acceptance import make_human_acceptance
else:
    from human_acceptance import make_human_acceptance


def fixture_library():
    definitions = (
        ("front_short", "five_prime_utr", "GG"),
        ("front_long", "five_prime_utr", "GGGG"),
        ("back", "three_prime_utr", "CC"),
        ("tail", "poly_a", "AAAA"),
        ("coding_a", "cds", "AUGGCUUAA"),
        ("coding_b", "cds", "AUGUUUUAA"),
    )
    parts = tuple(
        bc.MolecularPart(
            identity,
            bc.SequenceFragment(
                identity,
                sequence,
                hashlib.sha256(sequence.encode("ascii")).hexdigest(),
                "software-fixture:intent_candidate:" + identity,
            ),
            kind,
        )
        for identity, kind, sequence in definitions
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
    return bc.MolecularLibrary(
        "artificial_product_cassettes",
        "1",
        parts,
        (
            bc.ProductBinding("declared_product", "coding_a", "MA*"),
            bc.ProductBinding("alternative_product", "coding_b", "MF*"),
        ),
        (
            bc.RNAArchitecture("compact", "1", "front_short", "back", "tail", features),
            bc.RNAArchitecture("extended", "1", "front_long", "back", "tail", features),
        ),
    )


def make_candidate_request(*, product="declared_product", constraints=None):
    source = make_human_acceptance()
    if product != "declared_product":
        behavior = source.behavior_request
        document = behavior.build_request.intent.to_dict()
        for node in document["nodes"]:
            if node["kind"] == "secretion":
                node["attributes"]["product"] = product
        build = replace(
            behavior.build_request, intent=bc.IntentProgram.from_dict(document)
        )
        behavior = replace(
            behavior,
            build_request=build,
            contract=replace(behavior.contract, product=product),
        )
        source = replace(
            source,
            deployment_request=replace(
                source.deployment_request, behavior_request=behavior
            ),
            acceptance=replace(
                source.acceptance, behavior_fingerprint=behavior.fingerprint
            ),
        )
    return bc.CandidateRequest(
        source, fixture_library(), constraints or bc.CandidateConstraints()
    )


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    expectations = {
        "product_a": (make_candidate_request(), "GGAUGGCUUAACCAAAA"),
        "product_b": (
            make_candidate_request(product="alternative_product"),
            "GGAUGUUUUAACCAAAA",
        ),
        "extended": (
            make_candidate_request(
                constraints=bc.CandidateConstraints(
                    allowed_architecture_ids=("extended",)
                )
            ),
            "GGGGAUGGCUUAACCAAAA",
        ),
    }
    identities = []
    for label, (request, expected) in expectations.items():
        compilation = bc.compile(request)
        record = compilation.record
        assert record.molecule.sequence == expected
        assert record.request.target == request.source.target
        assert record.requirements.unresolved
        assert record.to_dict()["therapeutic_implementation"] == "partial"
        assert bc.verify_candidate_build(record, expected_request=request) == record
        identities.append(record.fingerprint)
        (output / (label + ".request.json")).write_text(
            request.to_json() + "\n", encoding="utf-8"
        )
        (output / (label + ".build.json")).write_text(
            record.to_json() + "\n", encoding="utf-8"
        )
        (output / (label + ".fasta")).write_text(
            bc.export_candidate_fasta(record, expected_request=request),
            encoding="ascii",
        )
    assert len(set(identities)) == 3
    exhausted_request = make_candidate_request(
        constraints=bc.CandidateConstraints(max_length=1)
    )
    exhausted = bc.compile_candidate(exhausted_request).record
    assert exhausted.status == "no_candidate_found" and exhausted.molecule is None
    assert (
        bc.verify_candidate_build(exhausted, expected_request=exhausted_request)
        == exhausted
    )
    (output / "exhausted.build.json").write_text(
        exhausted.to_json() + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "builds": identities,
                "bounded_search": exhausted.status,
                "scope": "product_cassette_structure",
                "therapeutic_implementation": "partial",
                "human_therapeutic_admission": "not_admitted",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
