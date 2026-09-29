"""Frozen inputs, independent binding authority and acyclic request identities."""

import copy
from contextlib import redirect_stderr
from dataclasses import FrozenInstanceError, replace
import io
import json
from pathlib import Path
import tempfile
import unittest

from cellweave import Duration, Level, Therapy
from cellweave.compiler.behavior import lower_to_behavior, verify_lowering
from cellweave.compiler.request import (
    BindingMetadata,
    BuildRequest,
    ElaborationProvenance,
    RealizationRequest,
)
from cellweave.compiler.workflow import BuildProfile, compile, plan
from cellweave.cli import main
from cellweave.errors import (
    CompilationUnavailableError,
    LoweringVerificationError,
    SerializationError,
    TypeMismatchError,
    UnsupportedBehaviorError,
)
from cellweave.ir.behavior import BehaviorProgram
from cellweave.ir.intent import IntentProgram, SourceLocation
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.semantics.realization import (
    BehaviorContract,
    InputDomain,
    Observable,
    OperatingDomain,
    ResponseRequirement,
)
from cellweave.semantics.types import BOOLEAN, Interval


def inputs(*, unbound=False):
    therapy = Therapy("frozen_inputs")
    cells = therapy.engineer("observer", cell_type="abstract_cell")
    if unbound:
        therapy.parameter("amount", type=Level)
    else:
        therapy.parameter("amount", default=1)
    cells.when(cells.external.signal("ready").present()).do(cells.secrete("output"))
    return therapy.freeze()


def realization():
    source = inputs()
    target = TargetContext("host", "1", PayloadFormat.RNA)
    request = BuildRequest.freeze(
        source, target=target, artifact_scope="synthetic_realization"
    )
    behavior = lower_to_behavior(request)
    role = behavior.find(kind="role")[0].id
    rule = behavior.find(kind="rule")[0]
    response = ResponseRequirement(
        "output",
        rule.id,
        rule.inputs[2],
        Observable("output", Level, role),
        Interval(1, 2),
        Interval(0, 0.2),
        Duration(1),
        Duration(1),
    )
    contract = BehaviorContract("contract", behavior.fingerprint, (response,))
    domain = OperatingDomain(
        "domain",
        "1",
        role,
        (
            InputDomain(
                behavior.find(kind="signal")[0].id,
                "present",
                Observable("input", BOOLEAN, role),
                (False, True),
            ),
        ),
        Duration(4),
    )
    return RealizationRequest.freeze(request, behavior, contract, domain)


class BuildRequestTests(unittest.TestCase):
    def test_defaults_overrides_and_frozen_graph_are_separate_authority(self):
        source = inputs()
        request = BuildRequest.freeze(source)
        override = BuildRequest.freeze(source, parameters={"amount": 9})
        self.assertIs(request.intent, source)
        self.assertEqual(request.resolved_defaults["amount"]["canonical_value"], 1)
        self.assertEqual(dict(request.explicit_overrides), {})
        self.assertEqual(dict(override.resolved_defaults), {})
        self.assertEqual(override.explicit_overrides["amount"]["canonical_value"], 9)
        behavior = lower_to_behavior(override)
        self.assertTrue(verify_lowering(override, behavior).passed)
        with self.assertRaises(LoweringVerificationError):
            verify_lowering(request, behavior)

    def test_mutation_of_node_and_manifest_fails_against_request(self):
        request = BuildRequest.freeze(inputs())
        data = lower_to_behavior(request).to_dict()
        parameter = next(node for node in data["nodes"] if node["kind"] == "parameter")
        parameter["attributes"]["default"].update(value=9, canonical_value=9)
        data["parameter_bindings"]["amount"].update(value=9, canonical_value=9)
        changed = BehaviorProgram.from_dict(data)
        with self.assertRaisesRegex(
            LoweringVerificationError, "authoritative_bindings"
        ):
            verify_lowering(request, changed)

    def test_caller_and_export_mutations_cannot_change_request(self):
        constraints = {"provider": {"allowed": ["synthetic"]}}
        external = {"seed": 7, "selected": ["a"]}
        parameters = {"amount": 2}
        provenance = ElaborationProvenance(external_inputs=external)
        request = BuildRequest.freeze(
            inputs(),
            parameters=parameters,
            implementation_constraints=constraints,
            provenance=provenance,
        )
        before = request.to_json()
        constraints["provider"]["allowed"].append("other")
        external["selected"].append("b")
        parameters["amount"] = 9
        exported = request.to_dict()
        exported["resolved_bindings"]["amount"]["value"] = 7
        self.assertEqual(before, request.to_json())
        with self.assertRaises(TypeError):
            request.resolved_bindings["amount"]["value"] = 9
        with self.assertRaises(FrozenInstanceError):
            request.intent = inputs()

    def test_canonical_roundtrip_and_mapping_order(self):
        source = inputs()
        first = BuildRequest.freeze(source, preferences={"b": 2, "a": 1})
        second = BuildRequest.freeze(source, preferences={"a": 1, "b": 2})
        restored = BuildRequest.from_json(first.to_json())
        self.assertEqual(first, restored)
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.fingerprint, restored.fingerprint)
        self.assertEqual(first.artifact_fingerprint, restored.artifact_fingerprint)

    def test_relocation_changes_archival_but_not_semantic_identity(self):
        source = inputs()
        moved = IntentProgram(
            source.name,
            tuple(
                replace(node, source=SourceLocation("/new/workspace/design.py", 33))
                for node in source.nodes
            ),
            source.roots,
        )
        first = BuildRequest.freeze(
            source,
            provenance=ElaborationProvenance(
                source_identities={"design": "sha256:123"},
                locations={"design": "/old/design.py"},
                recorded_at="yesterday",
            ),
        )
        second = BuildRequest.freeze(
            moved,
            provenance=ElaborationProvenance(
                source_identities={"design": "sha256:123"},
                locations={"design": "/new/design.py"},
                recorded_at="today",
            ),
        )
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.artifact_fingerprint, second.artifact_fingerprint)
        self.assertEqual(
            lower_to_behavior(first).fingerprint, lower_to_behavior(second).fingerprint
        )

    def test_semantic_inputs_affect_identity(self):
        base = BuildRequest.freeze(inputs())
        alternatives = [
            replace(base, preferences={"rank": "first"}),
            replace(base, implementation_constraints={"implementation": "pinned"}),
            replace(
                base, provenance=ElaborationProvenance(external_inputs={"seed": 1})
            ),
            replace(
                base,
                provenance=ElaborationProvenance(
                    dependency_identities={"package": "version1"}
                ),
            ),
            replace(
                base,
                provenance=ElaborationProvenance(
                    source_identities={"design": "sha256:new"}
                ),
            ),
            replace(base, target=TargetContext("host", "1", PayloadFormat.DNA)),
        ]
        for other in alternatives:
            with self.subTest(other=other):
                self.assertNotEqual(base.fingerprint, other.fingerprint)

    def test_serialized_authority_rejects_derived_binding_tampering(self):
        original = BuildRequest.freeze(inputs()).to_dict()
        for field in ("resolved_defaults", "resolved_bindings"):
            data = copy.deepcopy(original)
            data[field]["amount"].update(value=9, canonical_value=9)
            with self.subTest(field=field), self.assertRaises(SerializationError):
                BuildRequest.from_dict(data)

    def test_strict_schema_profile_and_json(self):
        original = BuildRequest.freeze(inputs()).to_dict()
        mutations = (
            lambda d: d.update(extra=1),
            lambda d: d.update(schema_version="future"),
            lambda d: d.update(behavior_profile="future"),
            lambda d: d.update(artifact_scope="implicit_payload"),
            lambda d: d.update(artifact_scope="exact_cds"),
            lambda d: d.update(parameter_metadata={}),
        )
        for mutate in mutations:
            data = copy.deepcopy(original)
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(SerializationError):
                BuildRequest.from_dict(data)
        for text in ('{"a":1,"a":2}', '{"a":NaN}', "[]"):
            with self.subTest(text=text), self.assertRaises(SerializationError):
                BuildRequest.from_json(text)

    def test_unknown_missing_and_wrong_type_bindings_have_diagnostics(self):
        source = inputs(unbound=True)
        parameter = source.find(kind="parameter")[0]
        with self.assertRaisesRegex(TypeMismatchError, "Unknown parameter.*Declared"):
            BuildRequest.freeze(source, parameters={"misspelled": 1})
        with self.assertRaises(UnsupportedBehaviorError) as missing:
            BuildRequest.freeze(source)
        self.assertEqual(missing.exception.node_id, parameter.id)
        self.assertEqual(missing.exception.source, parameter.source)
        with self.assertRaises(TypeMismatchError) as wrong_type:
            BuildRequest.freeze(source, parameters={"amount": Duration(3)})
        self.assertIn(parameter.id, str(wrong_type.exception))
        self.assertIn(parameter.source.file, str(wrong_type.exception))

    def test_frozen_requests_reject_late_overrides(self):
        request = BuildRequest.freeze(inputs())
        with self.assertRaisesRegex(TypeMismatchError, "cannot accept later"):
            lower_to_behavior(request, parameters={"amount": 9})
        with self.assertRaises(TypeMismatchError):
            verify_lowering(request, lower_to_behavior(request), parameters={})

    def test_design_categories_and_units_remain_distinct_from_observations(self):
        source = inputs()
        for category in ("user_selected", "compiler_selected", "measured", "uncertain"):
            metadata = BindingMetadata(
                category, {"reference": "calibration-v1"}, Interval(0, 2).to_dict()
            )
            request = BuildRequest.freeze(
                source, parameter_metadata={"amount": metadata}
            )
            restored = BuildRequest.from_json(request.to_json())
            self.assertEqual(restored.parameter_metadata["amount"], metadata)
            self.assertEqual(restored.resolved_bindings["amount"]["unit"], "1")
            self.assertEqual(
                restored.runtime_observations,
                tuple(node.id for node in source.find(kind="signal")),
            )
        with self.assertRaises(SerializationError):
            BindingMetadata("runtime_observation")
        with self.assertRaises(SerializationError):
            BuildRequest.freeze(
                source,
                parameter_metadata={
                    "amount": BindingMetadata(
                        "uncertain", allowed_variation=Interval(2, 3).to_dict()
                    )
                },
            )

    def test_profiles_and_partial_plans_have_explicit_freezing_boundary(self):
        profile = BuildProfile(
            TargetContext("host", "1", PayloadFormat.RNA), {"amount": 2}
        )
        request = profile.freeze_request(inputs())
        self.assertEqual(request.resolved_bindings["amount"]["canonical_value"], 2)
        design = plan(inputs(), profile=profile)
        self.assertEqual(
            design.freeze_request().fingerprint,
            profile.freeze_request(design.program).fingerprint,
        )
        self.assertFalse(design.ready)
        with self.assertRaises(CompilationUnavailableError):
            compile(request)
        partial = plan(inputs(unbound=True), profile=BuildProfile(profile.target))
        with self.assertRaises(UnsupportedBehaviorError):
            partial.freeze_request()

    def test_invalid_serialized_overrides_raise_serialization_errors(self):
        original = BuildRequest.freeze(inputs(), parameters={"amount": 2}).to_dict()
        for value in (None, [], {}, True, False, 2, "untyped"):
            data = copy.deepcopy(original)
            data["explicit_overrides"]["amount"] = value
            with self.subTest(value=value), self.assertRaises(SerializationError):
                BuildRequest.from_dict(data)
        data = copy.deepcopy(original)
        data["explicit_overrides"]["undeclared"] = data["explicit_overrides"]["amount"]
        with self.assertRaisesRegex(SerializationError, "Unknown parameter bindings"):
            BuildRequest.from_dict(data)

    def test_provenance_rejects_unknown_schema_fields_but_captures_external_values(
        self,
    ):
        provenance = ElaborationProvenance(
            source_identities={"design": "sha256:design"},
            dependency_identities={"library": "version:1"},
            external_inputs={"seed": 7, "optional": None, "flags": [True, False]},
            locations={"design": "/workspace/design.py"},
        )
        self.assertEqual(
            ElaborationProvenance.from_json(provenance.to_json()), provenance
        )
        for field in (
            "source_identities",
            "dependency_identities",
            "external_inputs",
            "locations",
        ):
            for value in (None, [], True, 3):
                data = provenance.to_dict()
                data[field] = value
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(SerializationError),
                ):
                    ElaborationProvenance.from_dict(data)
        for artifact in (provenance, BindingMetadata(), BuildRequest.freeze(inputs())):
            data = artifact.to_dict()
            data["undeclared"] = "value"
            with (
                self.subTest(artifact=type(artifact)),
                self.assertRaises(SerializationError),
            ):
                type(artifact).from_dict(data)

    def test_standalone_metadata_requires_a_typed_interval_for_variation(self):
        for value in ({}, {"minimum": 0, "maximum": 2}, Level(1).to_dict()):
            data = BindingMetadata().to_dict()
            data["allowed_variation"] = value
            with self.subTest(value=value), self.assertRaises(SerializationError):
                BindingMetadata.from_dict(data)
        valid = BindingMetadata(allowed_variation=Interval(0, 2).to_dict())
        self.assertEqual(BindingMetadata.from_json(valid.to_json()), valid)

    def test_runtime_observation_inventory_is_immutable_and_excludes_design_values(
        self,
    ):
        request = BuildRequest.freeze(inputs())
        inventory = request.runtime_observations
        self.assertIsInstance(inventory, tuple)
        self.assertTrue(inventory)
        self.assertEqual(
            inventory,
            tuple(node.id for node in request.intent.nodes if node.kind == "signal"),
        )
        self.assertFalse(
            set(inventory) & {node.id for node in request.intent.find(kind="parameter")}
        )
        self.assertEqual(
            BuildRequest.from_json(request.to_json()).runtime_observations, inventory
        )


class RealizationRequestTests(unittest.TestCase):
    def test_second_phase_roundtrip_preserves_upstream_identity(self):
        request = realization()
        restored = RealizationRequest.from_json(request.to_json())
        self.assertEqual(request, restored)
        self.assertEqual(request.fingerprint, restored.fingerprint)
        self.assertEqual(
            request.upstream_request_fingerprint, request.build_request.fingerprint
        )
        before = request.build_request.to_json()
        changed = replace(request, domain=replace(request.domain, version="2"))
        self.assertNotEqual(changed.fingerprint, request.fingerprint)
        self.assertEqual(before, changed.build_request.to_json())
        self.assertNotIn("contract", request.build_request.to_dict())

    def test_second_phase_cannot_bind_different_behavior_or_authority(self):
        request = realization()
        with self.assertRaises(SerializationError):
            replace(
                request,
                contract=replace(request.contract, behavior_fingerprint="a" * 64),
            )
        altered = BuildRequest.freeze(
            request.build_request.intent,
            target=request.target,
            parameters={"amount": 9},
        )
        with self.assertRaises(LoweringVerificationError):
            replace(request, build_request=altered)
        with self.assertRaises(SerializationError):
            replace(
                request,
                domain=replace(
                    request.domain,
                    role="unknown",
                    inputs=tuple(
                        replace(
                            item, observable=replace(item.observable, role="unknown")
                        )
                        for item in request.domain.inputs
                    ),
                ),
            )

    def test_second_phase_deserialization_revalidates_correspondence(self):
        request = realization()
        data = request.to_dict()
        data["contract"]["behavior_fingerprint"] = "a" * 64
        with self.assertRaises(SerializationError):
            RealizationRequest.from_dict(data)
        data = request.to_dict()
        data["schema_version"] = "future"
        with self.assertRaises(SerializationError):
            RealizationRequest.from_dict(data)

    def test_nested_verification_errors_remain_serialization_errors_on_import(self):
        request = realization()
        for mutation in ("source", "unsupported", "policy"):
            data = request.to_dict()
            if mutation == "source":
                data["build_request"]["intent"]["name"] = "different_authority"
            else:
                rule = next(
                    node
                    for node in data["build_request"]["intent"]["nodes"]
                    if node["kind"] == "rule"
                )
                if mutation == "unsupported":
                    rule["kind"] = "unsupported_operation"
                else:
                    rule["attributes"]["trigger"] = []
            with self.subTest(mutation=mutation), self.assertRaises(SerializationError):
                RealizationRequest.from_dict(data)

    def test_recursive_field_type_mutations_never_leak_python_exceptions(self):
        def paths(value, path=()):
            if isinstance(value, dict):
                for key, item in value.items():
                    yield path + (key,)
                    yield from paths(item, path + (key,))
            elif isinstance(value, list):
                for key, item in enumerate(value):
                    yield path + (key,)
                    yield from paths(item, path + (key,))

        artifacts = (
            BuildRequest.freeze(inputs(), parameters={"amount": 2}),
            realization(),
        )
        for artifact in artifacts:
            original = artifact.to_dict()
            for path in paths(original):
                for value in (None, [], {}, True, 0):
                    data = copy.deepcopy(original)
                    parent = data
                    for key in path[:-1]:
                        parent = parent[key]
                    parent[path[-1]] = value
                    with self.subTest(
                        artifact=type(artifact).__name__, path=path, value=value
                    ):
                        try:
                            restored = type(artifact).from_dict(data)
                        except SerializationError:
                            continue
                        # Some fields permit these values (e.g. empty preferences,
                        # nullable source locations). Accepted variants stay valid.
                        self.assertEqual(
                            type(artifact).from_json(restored.to_json()).fingerprint,
                            restored.fingerprint,
                        )

    def test_cli_reports_bad_requests_without_tracebacks(self):
        first = BuildRequest.freeze(inputs(), parameters={"amount": 2}).to_dict()
        first["explicit_overrides"]["amount"] = False
        second = realization().to_dict()
        second["build_request"]["intent"]["name"] = "different_authority"
        third = realization().to_dict()
        rule = next(
            node
            for node in third["build_request"]["intent"]["nodes"]
            if node["kind"] == "rule"
        )
        rule["attributes"]["trigger"] = []
        with tempfile.TemporaryDirectory(prefix="cellweave-request-test-") as directory:
            path = Path(directory) / "request.json"
            for document in (first, second, third):
                path.write_text(json.dumps(document), encoding="utf-8")
                error = io.StringIO()
                with (
                    self.subTest(document=document["schema_version"]),
                    redirect_stderr(error),
                ):
                    self.assertEqual(main(["inspect", str(path)]), 2)
                self.assertIn("cellweave:", error.getvalue())
                self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
