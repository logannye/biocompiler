"""Freshness distinguishes retained reference identity from source-file provenance."""

from dataclasses import replace
import unittest

from cellweave.ir.intent import SourceLocation
from cellweave.verification.construct import check_construct
from cellweave.verification.evidence import CheckOutcome
from test_construct_checker import candidate_for, fixture


class ConstructProvenanceAuditTests(unittest.TestCase):
    def test_archival_source_relocation_requires_new_authority_and_fresh_evidence(self):
        request, candidate, registry, manifests = fixture()
        original = check_construct(request, candidate, registry, manifests)
        relocated_source = SourceLocation("relocated/reference_build.py", 12)
        placement = replace(request.placements[0], source=relocated_source)

        # Changing only the proposed layout cannot rewrite selected provenance,
        # even when the producer updates the candidate's request identity.
        unilateral = replace(request, placements=(placement,))
        rejected = check_construct(
            unilateral, candidate_for(unilateral), registry, manifests
        )
        self.assertEqual(rejected.outcome, CheckOutcome.FAIL)
        self.assertIn(
            "source_correspondence", {item.code for item in rejected.diagnostics}
        )

        # A caller can freeze a new structural request with the relocated source.
        # Source paths currently participate in archival/layout identity.
        # Unchanged reference pins do not make the earlier receipt reusable.
        composition = replace(
            request.composition,
            instances=(
                replace(request.composition.instances[0], source=relocated_source),
            ),
        )
        relocated = replace(
            request,
            composition=composition,
            placements=(placement,),
            source_request_fingerprint=composition.fingerprint,
        )
        changed = candidate_for(relocated)
        self.assertEqual(
            check_construct(relocated, changed, registry, manifests).outcome,
            CheckOutcome.PASS,
        )
        self.assertEqual(candidate.registry_lock, changed.registry_lock)
        self.assertEqual(
            candidate.placements[0].reference, changed.placements[0].reference
        )
        self.assertNotEqual(candidate.layout_fingerprint, changed.layout_fingerprint)
        self.assertNotEqual(candidate.fingerprint, changed.fingerprint)
        stale = original.freshness(relocated, changed, registry, manifests)
        self.assertEqual(
            set(stale.changed_dependencies),
            {"request", "candidate", "layout", "composition"},
        )


if __name__ == "__main__":
    unittest.main()
