"""Acceptance must follow locked contracts, grounded providers and shared pools."""

from dataclasses import replace
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import (
    ComponentRecord,
    DependencyRequirement,
    PinnedIdentity,
    ProvidedCapability,
    ResourceReservation,
)
from biocompiler.ir.composition import (
    CompositionInstance,
    CompositionRequest,
    Connection,
    DependencyBinding,
    LifecycleInterval,
    Provider,
    ResourceBinding,
    ResourcePool,
)
from biocompiler.ir.intent import SourceLocation
from biocompiler.registry.components import ComponentRegistry
from biocompiler.semantics.component_contracts import (
    OperatingDomain,
    PortContract,
    ValueDomain,
)
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.types import LEVEL, Level, TypeSpec
from biocompiler.verification.components import CompositionResult, check_composition


MODEL = PinnedIdentity("model", "fixture", "1", "0" * 64)
DOMAIN = OperatingDomain({"temperature": ValueDomain.interval(20, 40)})
TARGET = TargetContext("abstract", "1", PayloadFormat.RNA)


def port(id, direction, **changes):
    result = PortContract(
        id,
        direction,
        "activator",
        LEVEL,
        "1",
        "cell",
        "cell",
        "abstract",
        "atomic_snapshot_stateless.v0.1",
        ValueDomain.interval(0, 1),
        ValueDomain.interval(0, 1),
    )
    return replace(result, **changes)


def component(id, **changes):
    result = ComponentRecord(
        id, "1", "synthetic_model", "fixture", ("RNA",), (), DOMAIN, (MODEL,)
    )
    return replace(result, **changes)


def capability(id="supply", **changes):
    return replace(ProvidedCapability(id, "cell", "cell", "abstract"), **changes)


def requirement(id="need", **changes):
    return replace(
        DependencyRequirement(id, "supply", "cell", "cell", "abstract"), **changes
    )


def supply(id="external", **changes):
    return replace(Provider(id, "external", (capability(),), ("RNA",)), **changes)


def composition(records, *, target=TARGET, **changes):
    registry = ComponentRegistry(
        "fixtures",
        "1",
        tuple({record.id: record for record in records.values()}.values()),
    )
    lock = registry.lock(records)
    instances = tuple(
        CompositionInstance(
            item.node_id,
            item,
            DOMAIN,
            requirement_ids=("intent",),
            source=SourceLocation("fixture.py", 7, "build"),
        )
        for item in lock.components
    )
    request = CompositionRequest(
        target, lock, instances, requirement_ids=("intent",), **changes
    )
    return request, registry


class ComponentLinkerTests(unittest.TestCase):
    def assert_status(self, request, registry, status, code=None):
        result = check_composition(request, registry)
        self.assertEqual(result.outcome.value, status, result.to_json())
        self.assertEqual(result.passed, status == "pass")
        if code is not None:
            self.assertIn(code, {item.code for item in result.diagnostics})
        return result

    def linked_pair(self, producer_changes=None, consumer_changes=None):
        source = component(
            "source", ports=(port("out", "output", **(producer_changes or {})),)
        )
        sink = component(
            "sink", ports=(port("in", "input", **(consumer_changes or {})),)
        )
        return composition(
            {"a": source, "b": sink}, connections=(Connection("a", "out", "b", "in"),)
        )

    def test_compatible_ports_link_and_preserve_requirements(self):
        request, registry = self.linked_pair()
        result = self.assert_status(request, registry, "pass")
        self.assertEqual(result.checked_requirement_ids, ("intent",))
        self.assertIn("not biological efficacy", result.claim_scope)

    def test_same_range_does_not_establish_meaning_role_scope_or_compartment(self):
        for changed in (
            {"meaning": "toxin"},
            {"role": "other"},
            {"scope": "contact"},
            {"compartment": "nucleus"},
            {
                "dtype": TypeSpec("scalar", "DifferentMeaning"),
                "initialization": ValueDomain.interval(
                    0, 1, TypeSpec("scalar", "DifferentMeaning")
                ),
                "domain": ValueDomain.interval(
                    0, 1, TypeSpec("scalar", "DifferentMeaning")
                ),
            },
        ):
            with self.subTest(changed=changed):
                request, registry = self.linked_pair(consumer_changes=changed)
                self.assert_status(request, registry, "fail", "incompatible_ports")

    def test_producer_guarantee_must_fit_consumer_accepted_domain_and_initialization(
        self,
    ):
        for producer, consumer in (
            ({"domain": ValueDomain.interval(0, 2)}, {}),
            ({}, {"initialization": ValueDomain.interval(0, 0)}),
        ):
            request, registry = self.linked_pair(
                producer_changes=producer, consumer_changes=consumer
            )
            self.assert_status(request, registry, "fail", "incompatible_ports")

    def test_unknown_guarantee_or_timing_cannot_pass(self):
        for changed in ({"domain": ValueDomain.unknown()}, {"timing": "unknown"}):
            request, registry = self.linked_pair(producer_changes=changed)
            self.assert_status(request, registry, "unknown", "incompatible_ports")

    def test_missing_or_duplicate_input_wiring_cannot_pass(self):
        request, registry = self.linked_pair()
        self.assert_status(
            replace(request, connections=()),
            registry,
            "unknown",
            "input_connection_count",
        )
        self.assert_status(
            replace(request, connections=request.connections * 2),
            registry,
            "fail",
            "input_connection_count",
        )

    def test_required_operating_domain_is_not_inferred(self):
        request, registry = composition({"a": component("part")})
        for required, status in (
            (OperatingDomain({"temperature": ValueDomain.interval(10, 50)}), "fail"),
            (OperatingDomain(), "unknown"),
        ):
            updated = replace(request.instances[0], required_domain=required)
            self.assert_status(
                replace(request, instances=(updated,)),
                registry,
                status,
                "operating_domain",
            )

    def test_target_modality_and_compartment_are_hard_constraints(self):
        request, registry = self.linked_pair()
        self.assert_status(
            replace(request, target=replace(TARGET, payload_format=PayloadFormat.DNA)),
            registry,
            "fail",
            "unsupported_target",
        )
        self.assert_status(
            replace(request, target=replace(TARGET, compartments=("nucleus",))),
            registry,
            "fail",
            "target_compartment",
        )

    def test_missing_or_ambiguous_provider_stays_unresolved(self):
        request, registry = composition(
            {"a": component("part", dependencies=(requirement(),))}
        )
        self.assert_status(request, registry, "unknown", "missing_provider")
        ambiguous = replace(request, providers=(supply("x"), supply("y")))
        self.assert_status(ambiguous, registry, "unknown", "ambiguous_provider")
        explicit = replace(
            ambiguous, dependency_bindings=(DependencyBinding("a", "need", "y"),)
        )
        result = self.assert_status(explicit, registry, "pass")
        self.assertEqual(result.resolved_dependencies[0].provider_id, "y")

    def test_provider_must_match_capability_meaning_role_scope_and_compartment(self):
        for changes in (
            {"id": "different"},
            {"role": "other"},
            {"scope": "contact"},
            {"compartment": "nucleus"},
        ):
            request, registry = composition(
                {"a": component("part", dependencies=(requirement(),))},
                providers=(supply(capabilities=(replace(capability(), **changes),)),),
                dependency_bindings=(DependencyBinding("a", "need", "external"),),
            )
            self.assert_status(request, registry, "fail", "incompatible_provider")

    def test_host_declarations_must_be_in_target(self):
        request, registry = composition(
            {"a": component("part", dependencies=(requirement(),))},
            providers=(supply(kind="host"),),
        )
        self.assert_status(request, registry, "fail", "host_capability")
        self.assert_status(
            replace(request, target=replace(TARGET, capabilities=("supply",))),
            registry,
            "pass",
        )

    def test_explicit_unresolved_provider_cannot_establish_success(self):
        request, registry = composition(
            {"a": component("part", dependencies=(requirement(),))},
            providers=(supply(kind="unresolved"),),
        )
        self.assert_status(request, registry, "unknown", "ungrounded_provider")

    def test_payload_capabilities_come_from_record_and_keep_placement(self):
        request, registry = composition(
            {
                "a": component("sink", dependencies=(requirement(),)),
                "b": component("source", capabilities=(capability(),)),
            }
        )
        result = self.assert_status(request, registry, "pass")
        self.assertEqual(result.resolved_dependencies[0].provider_kind, "encoded_here")
        request = replace(
            request,
            instances=tuple(
                replace(item, placement="co_payload") if item.id == "b" else item
                for item in request.instances
            ),
        )
        result = self.assert_status(request, registry, "pass")
        self.assertEqual(result.resolved_dependencies[0].provider_kind, "co_payload")

    def test_self_and_two_component_assumption_cycles_never_ground(self):
        cyclic = component(
            "cycle",
            dependencies=(requirement(),),
            capabilities=(capability(),),
            assumptions=("supply",),
            guarantees=("supply",),
        )
        request, registry = composition({"a": cyclic})
        self.assert_status(request, registry, "unknown", "ungrounded_provider")
        other = component(
            "other",
            dependencies=(requirement(capability="a"),),
            capabilities=(capability(),),
        )
        first = component(
            "first", dependencies=(requirement(),), capabilities=(capability("a"),)
        )
        request, registry = composition({"a": first, "b": other})
        self.assert_status(request, registry, "unknown", "ungrounded_provider")
        request = replace(
            request,
            providers=(supply(),),
            dependency_bindings=(DependencyBinding("a", "need", "external"),),
        )
        self.assert_status(request, registry, "pass")

    def test_external_prerequisites_cannot_create_assumptions_from_cycles(self):
        request, registry = composition(
            {"a": component("sink", dependencies=(requirement(),))},
            providers=(
                supply("one", depends_on=("two",)),
                supply("two", capabilities=(), depends_on=("one",)),
            ),
        )
        self.assert_status(request, registry, "unknown", "ungrounded_provider")

    def test_textual_guarantees_do_not_supply_capabilities(self):
        request, registry = composition(
            {
                "a": component("sink", dependencies=(requirement(),)),
                "b": component("source", guarantees=("supply",)),
            }
        )
        self.assert_status(request, registry, "unknown", "missing_provider")

    def test_provider_lifetime_must_cover_its_consumer(self):
        request, registry = composition(
            {
                "a": component("sink", dependencies=(requirement(),)),
                "b": component("source", capabilities=(capability(),)),
            }
        )
        request = replace(
            request,
            instances=tuple(
                replace(item, lifetime=LifecycleInterval(0, 1))
                if item.id == "b"
                else item
                for item in request.instances
            ),
        )
        self.assert_status(request, registry, "fail", "provider_lifecycle")

    def resource_fixture(self, *, amount=4, capacity=7, reusable=False, count=2):
        part = component(
            "part",
            resources=(
                ResourceReservation(
                    "reserve", "supply", amount, "1", reusable=reusable
                ),
            ),
        )
        return composition(
            {str(i): part for i in range(count)},
            providers=(supply(),),
            resource_pools=(
                ResourcePool("shared", "supply", "1", capacity, "external"),
            ),
            resource_bindings=tuple(
                ResourceBinding(str(i), "reserve", "shared") for i in range(count)
            ),
        )

    def test_all_instances_charge_one_shared_capacity(self):
        request, registry = self.resource_fixture()
        self.assert_status(request, registry, "fail", "resource_overallocation")
        request = replace(
            request, resource_pools=(replace(request.resource_pools[0], capacity=8),)
        )
        result = self.assert_status(request, registry, "pass")
        self.assertEqual(result.resource_usage[0].peak_reservation, 8)

    def test_decimal_accounting_does_not_hide_a_small_overallocation(self):
        request, registry = self.resource_fixture(
            amount=0.1, capacity=0.29999999999999993, count=3
        )
        self.assert_status(request, registry, "fail", "resource_overallocation")
        self.assert_status(
            replace(
                request,
                resource_pools=(replace(request.resource_pools[0], capacity=0.3),),
            ),
            registry,
            "pass",
        )

    def test_unknown_amount_capacity_and_missing_binding_do_not_mean_unlimited(self):
        for changes, code in (
            ({"amount": None}, "unknown_reservation"),
            ({"capacity": None}, "unknown_capacity"),
        ):
            request, registry = self.resource_fixture(**changes)
            self.assert_status(request, registry, "unknown", code)
        request, registry = self.resource_fixture()
        self.assert_status(
            replace(request, resource_bindings=()),
            registry,
            "unknown",
            "missing_resource_pool",
        )

    def test_typed_units_and_resource_meaning_must_match(self):
        request, registry = self.resource_fixture(capacity=100)
        for changes in (
            {"unit": "dimensionless"},
            {"dtype": TypeSpec("scalar", "Different")},
            {"resource": "unrelated"},
        ):
            self.assert_status(
                replace(
                    request,
                    resource_pools=(replace(request.resource_pools[0], **changes),),
                ),
                registry,
                "fail",
                "resource_unit_or_type",
            )

    def test_reuse_requires_explicit_lifetimes_and_reusable_contract(self):
        for reusable, expected in ((True, "pass"), (False, "fail")):
            request, registry = self.resource_fixture(reusable=reusable)
            request = replace(
                request,
                instances=tuple(
                    replace(
                        item, lifetime=LifecycleInterval(int(item.id), int(item.id) + 1)
                    )
                    for item in request.instances
                ),
            )
            result = self.assert_status(request, registry, expected)
            self.assertEqual(
                result.resource_usage[0].peak_reservation, 4 if reusable else 8
            )
        request, registry = self.resource_fixture(reusable=True)
        self.assert_status(request, registry, "fail", "resource_overallocation")

    def test_overlapping_lifetimes_and_unknown_scheduling_do_not_allow_reuse(self):
        request, registry = self.resource_fixture(reusable=True)
        request = replace(
            request,
            instances=tuple(
                replace(item, lifetime=LifecycleInterval(0, 2))
                for item in request.instances
            ),
        )
        self.assert_status(request, registry, "fail", "resource_overallocation")
        request = replace(
            request,
            instances=tuple(
                replace(item, lifetime=LifecycleInterval(0, 2, "min"))
                for item in request.instances
            ),
        )
        self.assert_status(request, registry, "unsupported", "unsupported_lifecycle")

    def test_pool_aliases_cannot_multiply_physical_capacity(self):
        request, registry = self.resource_fixture()
        other = replace(request.resource_pools[0], id="alias")
        request = replace(
            request,
            resource_pools=(*request.resource_pools, other),
            resource_bindings=(
                request.resource_bindings[0],
                replace(request.resource_bindings[1], pool_id="alias"),
            ),
        )
        self.assert_status(request, registry, "unsupported", "aliased_resource_pool")

    def test_host_capacity_is_authoritative_and_cannot_be_renamed(self):
        request, registry = self.resource_fixture(capacity=10, count=1)
        request = replace(
            request,
            providers=(supply(kind="host"),),
            target=replace(TARGET, capabilities=("supply",)),
        )
        self.assert_status(request, registry, "unknown", "unknown_host_capacity")
        request = replace(
            request, target=replace(request.target, resources={"supply": Level(5)})
        )
        self.assert_status(request, registry, "fail", "host_capacity_mismatch")
        request = replace(
            request, resource_pools=(replace(request.resource_pools[0], capacity=5),)
        )
        self.assert_status(request, registry, "pass")

    def test_pool_requires_grounded_provider_and_matching_capability(self):
        request, registry = self.resource_fixture(capacity=10)
        self.assert_status(
            replace(request, providers=(supply(kind="unresolved"),)),
            registry,
            "unknown",
            "resource_provider_unresolved",
        )
        self.assert_status(
            replace(request, providers=(supply(capabilities=()),)),
            registry,
            "fail",
            "resource_provider_capability",
        )

    def test_resource_consumption_cannot_establish_its_own_provider(self):
        part = component(
            "part",
            capabilities=(capability(),),
            resources=(ResourceReservation("reserve", "supply", 1, "1"),),
        )
        request, registry = composition(
            {"a": part},
            resource_pools=(ResourcePool("pool", "supply", "1", 10, "a"),),
            resource_bindings=(ResourceBinding("a", "reserve", "pool"),),
        )
        self.assert_status(request, registry, "unknown", "resource_provider_unresolved")

    def test_record_registry_model_and_target_changes_invalidate_result(self):
        request, registry = self.linked_pair()
        result = self.assert_status(request, registry, "pass")
        self.assertTrue(result.is_fresh(request, registry))
        for update in (
            replace(registry, version="2"),
            replace(
                registry,
                components=tuple(
                    replace(item, guarantees=("changed",))
                    for item in registry.components
                ),
            ),
            replace(
                registry,
                components=tuple(
                    replace(
                        item, identities=(replace(MODEL, content_fingerprint="1" * 64),)
                    )
                    for item in registry.components
                ),
            ),
        ):
            self.assert_status(request, update, "fail", "stale_registry_lock")
            self.assertFalse(result.is_fresh(request, update))
        self.assertFalse(
            result.is_fresh(
                replace(request, target=replace(TARGET, context_version="2")), registry
            )
        )

    def test_request_cannot_drop_selected_instances_or_change_component_lock(self):
        request, registry = self.linked_pair()
        self.assert_status(
            replace(request, instances=request.instances[:1]),
            registry,
            "fail",
            "instance_lock_mismatch",
        )
        altered = replace(
            request.instances[0],
            component=replace(
                request.instances[0].component, content_fingerprint="f" * 64
            ),
        )
        self.assert_status(
            replace(request, instances=(altered, request.instances[1])),
            registry,
            "fail",
            "instance_lock_mismatch",
        )

    def test_frozen_inputs_roundtrip_and_canonical_order(self):
        request, registry = self.resource_fixture(capacity=8)
        result = self.assert_status(request, registry, "pass")
        self.assertEqual(
            CompositionRequest.from_json(request.to_json()).fingerprint,
            request.fingerprint,
        )
        self.assertEqual(
            CompositionResult.from_json(result.to_json()).fingerprint,
            result.fingerprint,
        )
        self.assertEqual(
            replace(request, instances=tuple(reversed(request.instances))).fingerprint,
            request.fingerprint,
        )
        mutable = list(request.instances)
        frozen = replace(request, instances=mutable)
        mutable.clear()
        self.assertEqual(frozen.fingerprint, request.fingerprint)
        with self.assertRaises(TypeError):
            result.dependencies["registry"] = "f" * 64

    def test_malformed_shapes_raise_serialization_errors(self):
        for value in (None, "invalid", {}, 1):
            raw = supply().to_dict()
            raw["capabilities"] = value
            with self.subTest(value=value), self.assertRaises(SerializationError):
                Provider.from_dict(raw)
        for value in (True, float("nan"), float("inf"), -1, 10**1000):
            with (
                self.subTest(value=type(value).__name__),
                self.assertRaises(SerializationError),
            ):
                ResourcePool("pool", "resource", "1", value, "supply")


if __name__ == "__main__":
    unittest.main()
