"""Search and prefilter ledgers have independent, finite record allowances."""
from dataclasses import replace
import unittest

from biocompiler.compiler.payload_architecture import compile_payload_architecture
from biocompiler.errors import SerializationError
from biocompiler.ir.architecture_build import (
    ArchitectureAlternative, MAX_ARCHITECTURE_ALTERNATIVES, PayloadArchitectureBuild,
)
from examples.payload_architectures import make_architecture_request


class ArchitectureSearchBoundsTests(unittest.TestCase):
    def test_prefilter_diagnostics_do_not_overflow_the_full_search_budget(self):
        request = make_architecture_request("A", variants=("one_rna",))
        refinement = request.library.refinements[0]
        # Incomplete ownership rejects all subsets before construction; this
        # exercises the real enumeration/receipt path without expensive builds.
        partial = replace(refinement, owned_node_ids=(refinement.owned_node_ids[0],))
        choices = tuple(replace(partial, id="choice." + str(index)) for index in range(13))
        mapping = dict(partial.source_bindings)
        mapping[next(iter(mapping))] = "absent_source"
        rejected = replace(partial, id="prefilter_rejected", source_bindings=mapping)
        request = replace(request,
            library=replace(request.library, refinements=(*choices, rejected)),
            constraints=replace(request.constraints, max_combinations=4096))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertGreater(len(build.alternatives), 1)
        self.assertLess(len(build.alternatives), 4097)
        prefilter = next(item for item in build.alternatives if item.refinement_ids == (rejected.id,))
        self.assertIn("absent_source_correspondence", {gap.code for gap in prefilter.gaps})
        self.assertEqual(build.diagnostics[-1].code, "architecture_record_budget_exhausted")
        self.assertIn("candidate subsets", build.diagnostics[-1].message)
        self.assertTrue(build.diagnostics[-1].candidate_ids)
        self.assertEqual(PayloadArchitectureBuild.from_json(build.to_json()).to_dict(), build.to_dict())
        # Dense candidate explanations still obey the existing global byte/item
        # safety limits. A small structural record isolates the array-count limit.
        entry = ArchitectureAlternative((), ())
        lightweight = replace(build, alternatives=(entry,) * MAX_ARCHITECTURE_ALTERNATIVES)
        decoded = PayloadArchitectureBuild.from_dict(lightweight.to_dict())
        self.assertEqual(len(decoded.alternatives), MAX_ARCHITECTURE_ALTERNATIVES)
        with self.assertRaisesRegex(SerializationError, "Invalid alternatives"):
            replace(build, alternatives=(entry,) * (MAX_ARCHITECTURE_ALTERNATIVES + 1))
        document = lightweight.to_dict()
        document["alternatives"] = [entry.to_dict()] * (MAX_ARCHITECTURE_ALTERNATIVES + 1)
        with self.assertRaises(SerializationError):
            PayloadArchitectureBuild.from_dict(document)


if __name__ == "__main__":
    unittest.main()
