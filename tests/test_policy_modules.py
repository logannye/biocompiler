"""Pure authoring checks; expected source originates in independent examples."""
from dataclasses import replace
import unittest

from biocompiler.policy import model as m
from biocompiler.policy.examples import build_example
from biocompiler.policy.logic import TRUE
from biocompiler.policy.modules import (
    InputPort, ModuleBinding, ModuleError, ModuleLimits, ModuleOutput,
    ModuleTemplate, OutputPort, compose_modules, instantiate,
)
from biocompiler.policy.serialization import dumps
from biocompiler.policy.validation import check


def fixture(*, export=False, reset=False):
    original = build_example("encounter_sentinel")
    context = tuple(d for d in original.declarations if isinstance(
        d, (m.Role, m.Clock, m.Subject, m.Encounter, m.Observation)))
    body = tuple(d for d in original.declarations if isinstance(d, (m.Effect, m.StateStore, m.Rule)))
    state = next(d for d in body if isinstance(d, m.StateStore))
    if reset:
        state = replace(state, reset=TRUE)
        body = tuple(state if isinstance(d, m.StateStore) else d for d in body)
    body = tuple(replace(d, arbitration=replace(d.arbitration, order=(d.id,)))
                 if isinstance(d, m.Rule) else d for d in body)
    requirements = tuple(d for d in original.declarations if isinstance(d, m.Requirement))
    local_ids = {d.id for d in body + requirements}
    ports = tuple(InputPort("input" + str(i), d, "read" if isinstance(d, m.Observation) else "context")
                  for i, d in enumerate(context))
    template = ModuleTemplate(
        "sentinel", "1", original.semantics, ports,
        (OutputPort("seen", state),) if export else (), body,
        private=tuple(m.Ref(d.id, type(d).__name__) for d in body
                      if isinstance(d, (m.Effect, m.StateStore)) and (not export or d.id != state.id)),
        guarantees=requirements,
        source_map=tuple(s for s in original.source_map if s.declaration_id in local_ids),
    )
    bindings = tuple(ModuleBinding(p.name, m.Ref(p.declaration.id, type(p.declaration).__name__)) for p in ports)
    return original, context, template, bindings


def writer_fixture(*, access="write"):
    original, context, source, bindings = fixture(export=True)
    state = next(d for d in source.declarations if isinstance(d, m.StateStore))
    rule = next(d for d in source.declarations if isinstance(d, m.Rule))
    rule = replace(rule, effects=(), when=TRUE)
    template = ModuleTemplate(
        "writer", "1", original.semantics,
        source.inputs + (InputPort("state", state, access),), (), (rule,),
    )
    return original, context, state, template, bindings


class PolicyModuleTests(unittest.TestCase):
    def test_two_instances_hygienically_preserve_original_source(self):
        original, context, template, bindings = fixture()
        left, right = (instantiate(template, name, bindings=bindings) for name in ("left", "right"))
        result = compose_modules("two", semantics=original.semantics, declarations=context, instances=(left, right))
        self.assertEqual(check(result).status, "complete")
        self.assertEqual(check(result).semantic_status, "unassessed")
        self.assertEqual(result.semantics, original.semantics)
        self.assertEqual(len(result.declarations), len(context) + 2 * (len(template.declarations) + len(template.guarantees)))
        by_id = {d.id: d for d in result.declarations}
        for name in ("left", "right"):
            rule = by_id[name + "/sentinel/respond"]
            self.assertEqual(rule.effects, (m.Ref(name + "/effect", "Effect"),))
            self.assertEqual(rule.assignments[0].state, m.Ref(name + "/sentinel/seen", "StateStore"))
            self.assertEqual(rule.arbitration.order, (name + "/sentinel/respond",))
            self.assertEqual(by_id[name + "/effect"].lifecycle, next(d for d in original.declarations if isinstance(d, m.Effect)).lifecycle)
            self.assertEqual(by_id[name + "/sentinel/seen"].scope, m.Scope("encounter", m.Ref("encounter", "Encounter")))
            for requirement in template.guarantees:
                expanded = by_id[name + "/" + requirement.id]
                self.assertEqual((expanded.kind, expanded.description, expanded.deadline, expanded.horizon),
                                 (requirement.kind, requirement.description, requirement.deadline, requirement.horizon))
        self.assertEqual({s.declaration_id for s in result.source_map},
                         {name + "/" + s.declaration_id for name in ("left", "right") for s in template.source_map})
        self.assertEqual(dumps(result), dumps(compose_modules("two", semantics=original.semantics, declarations=context, instances=(left, right))))

    def test_footprint_is_recomputed_from_body(self):
        _, _, template, _ = fixture()
        footprint = template.footprint()
        self.assertIn(m.Ref("sentinel/seen", "StateStore"), footprint.reads)
        self.assertEqual(footprint.writes, (m.Ref("sentinel/seen", "StateStore"),))
        self.assertEqual(footprint.requests, (m.Ref("effect", "Effect"),))

    def test_exported_output_reconnects_through_full_declared_interface(self):
        original, context, producer, bindings = fixture(export=True)
        state = next(d for d in producer.declarations if isinstance(d, m.StateStore))
        rule = next(d for d in producer.declarations if isinstance(d, m.Rule))
        consumer = ModuleTemplate("reader", "1", original.semantics,
                                  producer.inputs + (InputPort("state", state),), (),
                                  (replace(rule, effects=(), assignments=()),))
        left = instantiate(producer, "left", bindings=bindings)
        right = instantiate(consumer, "right", bindings=bindings + (ModuleBinding("state", left.output("seen")),))
        result = compose_modules("linked", semantics=original.semantics, declarations=context, instances=(right, left))
        rule = next(d for d in result.declarations if d.id == "right/sentinel/respond")
        self.assertEqual(rule.when.args[1].args[0].ref, m.Ref("left/sentinel/seen", "StateStore"))

    def test_private_state_and_effect_require_explicit_ownership(self):
        _, _, template, _ = fixture()
        with self.assertRaisesRegex(ModuleError, "explicit private ownership"):
            replace(template, private=())
        with self.assertRaisesRegex(ModuleError, "cannot be duplicated or exported"):
            replace(template, outputs=(OutputPort("effect", template.declarations[0], "request"),))

    def test_hidden_external_reference_is_rejected(self):
        _, _, template, _ = fixture()
        rule = next(d for d in template.declarations if isinstance(d, m.Rule))
        with self.assertRaisesRegex(ModuleError, "hidden external"):
            replace(template, declarations=tuple(replace(d, effects=(m.Ref("ambient", "Effect"),)) if d == rule else d for d in template.declarations))

    def test_unauthorized_input_effect_request_is_rejected(self):
        original, _, template, _ = fixture()
        effect = next(d for d in template.declarations if isinstance(d, m.Effect))
        with self.assertRaisesRegex(ModuleError, "does not authorize request"):
            ModuleTemplate("bad", "1", original.semantics,
                           template.inputs + (InputPort("effect", effect, "read"),), (),
                           tuple(d for d in template.declarations if d != effect),
                           private=tuple(r for r in template.private if r.id != effect.id))

    def test_unauthorized_input_state_write_is_rejected(self):
        with self.assertRaisesRegex(ModuleError, "does not authorize write"):
            writer_fixture(access="read")

    def test_shared_writes_are_rejected(self):
        original, context, state, template, bindings = writer_fixture()
        bindings += (ModuleBinding("state", m.Ref(state.id, "StateStore")),)
        instances = tuple(instantiate(template, name, bindings=bindings) for name in ("left", "right"))
        with self.assertRaisesRegex(ModuleError, "Conflicting shared writes"):
            compose_modules("conflict", semantics=original.semantics, declarations=context + (state,), instances=instances)

    def test_explicit_reset_is_a_write_owned_by_context(self):
        original, context, state, template, bindings = writer_fixture()
        state = replace(state, reset=TRUE)
        template = replace(template, inputs=template.inputs[:-1] + (InputPort("state", state, "write"),))
        instance = instantiate(template, "writer", bindings=bindings + (ModuleBinding("state", m.Ref(state.id, "StateStore")),))
        with self.assertRaisesRegex(ModuleError, "Conflicting shared writes"):
            compose_modules("reset_conflict", semantics=original.semantics, declarations=context + (state,), instances=(instance,))

    def test_raw_context_cannot_read_private_or_exported_instance_state(self):
        for export in (False, True):
            original, context, template, bindings = fixture(export=export)
            instance = instantiate(template, "left", bindings=bindings)
            intruder = m.Requirement("intruder", "safety", "No implicit module access", m.Scope("executor", m.Ref("executor", "Role")),
                                     condition=m.Expr("state", m.TRUTH, ref=m.Ref("left/sentinel/seen", "StateStore"), scope=m.Ref("encounter", "Encounter")))
            with self.assertRaisesRegex(ModuleError, "Raw context references"):
                compose_modules("bad", semantics=original.semantics, declarations=context + (intruder,), instances=(instance,))

    def test_raw_binding_cannot_name_private_instance_state(self):
        original, context, producer, bindings = fixture()
        _, _, _, writer, write_bindings = writer_fixture()
        instances = (instantiate(producer, "left", bindings=bindings),
                     instantiate(writer, "right", bindings=write_bindings + (ModuleBinding("state", m.Ref("left/sentinel/seen", "StateStore")),)))
        with self.assertRaisesRegex(ModuleError, "Raw bindings"):
            compose_modules("bad", semantics=original.semantics, declarations=context, instances=instances)

    def test_raw_context_arbitration_cannot_interfere_with_module_rule(self):
        original, context, template, bindings = fixture()
        rule = next(d for d in template.declarations if isinstance(d, m.Rule))
        intruder = replace(rule, id="intruder", when=TRUE, effects=(), assignments=(),
                           arbitration=replace(rule.arbitration, order=("left/" + rule.id,)))
        with self.assertRaisesRegex(ModuleError, "Raw context arbitration"):
            compose_modules("bad", semantics=original.semantics, declarations=context + (intruder,),
                            instances=(instantiate(template, "left", bindings=bindings),))

    def test_output_signature_cannot_expose_private_dependency(self):
        _, _, template, _ = fixture()
        effect = next(d for d in template.declarations if isinstance(d, m.Effect))
        # A reset predicate carries private state through the public signature.
        state = next(d for d in template.declarations if isinstance(d, m.StateStore))
        state = replace(state, reset=m.Expr("state", m.TRUTH, ref=m.Ref("hidden", "StateStore"), scope=state.scope.subject))
        hidden = replace(state, id="hidden", reset=None)
        body = tuple(state if isinstance(d, m.StateStore) else d for d in template.declarations) + (hidden,)
        with self.assertRaisesRegex(ModuleError, "private or undeclared local dependency"):
            replace(template, declarations=body, outputs=(OutputPort("seen", state),),
                    private=(m.Ref(effect.id, "Effect"), m.Ref(hidden.id, "StateStore")))

    def test_cyclic_module_output_connections_are_rejected(self):
        original, context, source, bindings = fixture(export=True)
        state = next(d for d in source.declarations if isinstance(d, m.StateStore))
        rule = next(d for d in source.declarations if isinstance(d, m.Rule))
        formal = replace(state, id="input_state")
        reader = m.Expr("state", m.TRUTH, ref=m.Ref(formal.id, "StateStore"), scope=formal.scope.subject)
        template = ModuleTemplate("relay", "1", original.semantics,
                                  source.inputs + (InputPort("state", formal),), (OutputPort("seen", state),),
                                  (state, replace(rule, when=reader, effects=())))
        instances = tuple(instantiate(template, name, bindings=bindings + (ModuleBinding("state", ModuleOutput(other, "seen")),))
                          for name, other in (("left", "right"), ("right", "left")))
        with self.assertRaisesRegex(ModuleError, "Cyclic module output"):
            compose_modules("cycle", semantics=original.semantics, declarations=context, instances=instances)

    def test_distinct_write_formals_cannot_alias_one_shared_state(self):
        original, context, state, template, bindings = writer_fixture()
        other = replace(state, id="other_state")
        rule = template.declarations[0]
        template = replace(template, inputs=template.inputs + (InputPort("other", other, "write"),),
                           declarations=(replace(rule, assignments=rule.assignments + (m.Assignment(m.Ref(other.id, "StateStore"), TRUE),)),))
        instance = instantiate(template, "writer", bindings=bindings +
                               (ModuleBinding("state", m.Ref(state.id, "StateStore")), ModuleBinding("other", m.Ref(state.id, "StateStore"))))
        with self.assertRaisesRegex(ModuleError, "write inputs alias"):
            compose_modules("alias", semantics=original.semantics, declarations=context + (state,), instances=(instance,))

    def test_output_access_cannot_be_escalated(self):
        original, context, producer, bindings = fixture(export=True)
        _, _, _, writer, write_bindings = writer_fixture()
        left = instantiate(producer, "left", bindings=bindings)
        right = instantiate(writer, "right", bindings=write_bindings + (ModuleBinding("state", left.output("seen")),))
        with self.assertRaisesRegex(ModuleError, "does not authorize"):
            compose_modules("bad", semantics=original.semantics, declarations=context, instances=(left, right))

    def test_output_connection_must_name_declared_port(self):
        original, context, producer, bindings = fixture()
        _, _, _, writer, write_bindings = writer_fixture()
        instances = (instantiate(producer, "left", bindings=bindings),
                     instantiate(writer, "right", bindings=write_bindings + (ModuleBinding("state", ModuleOutput("left", "seen")),)))
        with self.assertRaisesRegex(ModuleError, "undeclared port"):
            compose_modules("bad", semantics=original.semantics, declarations=context, instances=instances)

    def test_complete_signature_rejects_scope_and_contract_changes(self):
        original, context, template, bindings = fixture()
        for change in (lambda d: replace(d, coherence="different"), lambda d: replace(d, coverage="sampled")):
            changed = tuple(change(d) if isinstance(d, m.Observation) and d.id == "disease" else d for d in context)
            with self.assertRaisesRegex(ModuleError, "Input signature differs"):
                compose_modules("bad", semantics=original.semantics, declarations=changed,
                                instances=(instantiate(template, "left", bindings=bindings),))

    def test_complete_signature_rejects_nominal_scope_and_unit_changes(self):
        original, context, state, template, bindings = writer_fixture()
        changed = replace(state, scope=m.Scope("executor", m.Ref("executor", "Role")))
        self.assertEqual(check(m.PolicyProgram("source", original.semantics, context + (changed,))).status, "complete")
        with self.assertRaisesRegex(ModuleError, "Input signature differs"):
            compose_modules("scope", semantics=original.semantics, declarations=context + (changed,),
                            instances=(instantiate(template, "left", bindings=bindings + (ModuleBinding("state", m.Ref(state.id, "StateStore")),)),))
        unit = m.Unit("count", "count", "target_count", reference="target")
        parameter = m.Parameter("amount", m.TypeSpec("quantity", unit), m.Quantity("1", unit))
        semantics = m.SemanticBundle("empty", "1")
        template = ModuleTemplate("quantity", "1", semantics, (InputPort("amount", parameter),), (), ())
        other_unit = replace(unit, reference="executor")
        other = replace(parameter, value_type=m.TypeSpec("quantity", other_unit), value=m.Quantity("1", other_unit))
        with self.assertRaisesRegex(ModuleError, "Input signature differs"):
            compose_modules("units", semantics=semantics, declarations=(other,),
                            instances=(instantiate(template, "left", bindings=(ModuleBinding("amount", m.Ref("amount", "Parameter")),)),))

    def test_complete_signature_rejects_lifecycle_change(self):
        original, context, source, bindings = fixture()
        effect = next(d for d in source.declarations if isinstance(d, m.Effect))
        template = ModuleTemplate("effect_reader", "1", original.semantics,
                                  source.inputs + (InputPort("effect", effect),), (), ())
        changed = replace(effect, lifecycle=replace(effect.lifecycle, timeout=replace(effect.lifecycle.timeout, amount="11")))
        self.assertEqual(check(m.PolicyProgram("source", original.semantics, context + (changed,))).status, "complete")
        with self.assertRaisesRegex(ModuleError, "Input signature differs"):
            compose_modules("lifecycle", semantics=original.semantics, declarations=context + (changed,),
                            instances=(instantiate(template, "left", bindings=bindings + (ModuleBinding("effect", m.Ref(effect.id, "Effect")),)),))

    def test_original_template_is_revalidated_and_definition_conflicts_fail(self):
        original, context, template, bindings = fixture()
        instance = instantiate(template, "left", bindings=bindings)
        altered = replace(original.semantics.definitions[0], meaning="Different explicit supplied contract")
        altered_semantics = replace(original.semantics, definitions=(altered,) + original.semantics.definitions[1:])
        with self.assertRaisesRegex(ModuleError, "Conflicting pinned semantic definitions"):
            compose_modules("changed", semantics=altered_semantics, declarations=context, instances=(instance,))
        object.__setattr__(template, "private", ())
        with self.assertRaisesRegex(ModuleError, "explicit private ownership"):
            compose_modules("forged", semantics=original.semantics, declarations=context, instances=(instance,))

    def test_exact_assumption_bodies_are_required_and_preserved(self):
        original, context, template, bindings = fixture()
        premise = m.Requirement("premise", "assumption", "Supplied explicit premise", m.Scope("executor", m.Ref("executor", "Role")), condition=TRUE)
        template = replace(template, assumptions=(premise,))
        with self.assertRaisesRegex(ModuleError, "Missing or undeclared"):
            instantiate(template, "left", bindings=bindings)
        with self.assertRaisesRegex(ModuleError, "content differs"):
            instantiate(template, "left", bindings=bindings, assumptions=(replace(premise, description="Changed premise"),))
        instance = instantiate(template, "left", bindings=bindings, assumptions=(premise,))
        result = compose_modules("premised", semantics=original.semantics, declarations=context, instances=(instance,))
        self.assertIn(replace(premise, id="left/premise"), result.declarations)
        self.assertEqual(check(result).semantic_status, "unassessed")
        with self.assertRaisesRegex(ModuleError, "must already"):
            replace(template, assumptions=template.guarantees, guarantees=())

    def test_forged_instance_is_revalidated_at_composition(self):
        original, context, template, bindings = fixture()
        instance = instantiate(template, "left", bindings=bindings)
        object.__setattr__(instance, "bindings", ())
        with self.assertRaisesRegex(ModuleError, "Every module input"):
            compose_modules("bad", semantics=original.semantics, declarations=context, instances=(instance,))

    def test_forged_target_records_produce_module_diagnostic(self):
        original, context, template, bindings = fixture()
        for target in (m.Ref("executor", "Role"), ModuleOutput("left", "seen")):
            instance = instantiate(template, "left", bindings=bindings)
            binding = ModuleBinding(bindings[0].port, target)
            object.__setattr__(target, "id" if isinstance(target, m.Ref) else "instance", 1)
            object.__setattr__(instance, "bindings", (binding,) + bindings[1:])
            with self.assertRaises(ModuleError):
                compose_modules("bad", semantics=original.semantics, declarations=context, instances=(instance,))

    def test_duplicate_namespaces_and_shadowing_are_rejected(self):
        original, context, template, bindings = fixture()
        instance = instantiate(template, "left", bindings=bindings)
        with self.assertRaisesRegex(ModuleError, "Duplicate instance"):
            compose_modules("bad", semantics=original.semantics, declarations=context, instances=(instance, instance))
        with self.assertRaisesRegex(ModuleError, "shadow"):
            compose_modules("bad", semantics=original.semantics, declarations=context + (m.Parameter("left/reserved", m.INTEGER, 1),), instances=(instance,))

    def test_no_instance_declaration_limit_is_enforced(self):
        with self.assertRaisesRegex(ModuleError, "declaration bound"):
            compose_modules("bounded", semantics=m.SemanticBundle("empty", "1"),
                            declarations=(m.Role("a", ()), m.Role("b", ())), instances=(),
                            limits=ModuleLimits(max_declarations=1))

    def test_work_byte_depth_and_cyclic_data_bounds_fail_closed(self):
        original, context, template, bindings = fixture()
        instance = instantiate(template, "left", bindings=bindings)
        for limits in (ModuleLimits(max_work=20), ModuleLimits(max_bytes=20), ModuleLimits(max_depth=2)):
            with self.assertRaises(ModuleError):
                compose_modules("bounded", semantics=original.semantics, declarations=context, instances=(instance,), limits=limits)
        expression = m.Expr("not", m.TRUTH, (TRUE,))
        object.__setattr__(expression, "args", (expression,))
        rule = next(d for d in template.declarations if isinstance(d, m.Rule))
        object.__setattr__(rule, "when", expression)
        with self.assertRaisesRegex(ModuleError, "Cyclic"):
            compose_modules("cycle", semantics=original.semantics, declarations=context, instances=(instance,))

    def test_free_text_and_nominal_unit_references_are_not_rewritten(self):
        original, context, template, bindings = fixture()
        unit = m.Unit("local", "count", "target_count", reference="sentinel/seen")
        parameter = m.Parameter("nominal", m.TypeSpec("quantity", unit), m.Quantity("1", unit))
        requirement = replace(template.guarantees[0], description="sentinel/seen effect executor", assumptions=("Free text remains explicit",))
        template = replace(template, declarations=template.declarations + (parameter,), guarantees=(requirement,) + template.guarantees[1:])
        result = compose_modules("text", semantics=original.semantics, declarations=context,
                                 instances=(instantiate(template, "left", bindings=bindings),))
        self.assertIn(replace(parameter, id="left/nominal"), result.declarations)
        self.assertEqual(next(d for d in result.declarations if d.id == "left/permission").assumptions, requirement.assumptions)

    def test_definition_formals_remain_lexical_and_pins_unchanged(self):
        original, context, template, bindings = fixture()
        formal = m.Parameter("sentinel/seen", m.TRUTH, selection="design")
        definition = m.SemanticDefinition("lexical", "1", "operation", "Lexical formal",
                                          parameters=(formal,), result=m.TRUTH,
                                          clauses=(m.ContractClause("precondition", "Lexical read", m.Expr("parameter", m.TRUTH, ref=m.Ref(formal.id, "Parameter"))),))
        semantics = replace(original.semantics, definitions=original.semantics.definitions + (definition,))
        template = replace(template, semantics=semantics)
        result = compose_modules("lexical", semantics=original.semantics, declarations=context,
                                 instances=(instantiate(template, "left", bindings=bindings),))
        self.assertEqual(result.semantics.definitions[-1], definition)
        self.assertEqual(result.semantics.definitions[-1].ref, definition.ref)
        captured = replace(definition, clauses=(m.ContractClause("precondition", "Hidden capture", m.Expr("state", m.TRUTH, ref=m.Ref("sentinel/seen", "StateStore"))),))
        with self.assertRaisesRegex(ModuleError, "cannot capture"):
            replace(template, semantics=replace(semantics, definitions=semantics.definitions[:-1] + (captured,)))


if __name__ == "__main__":
    unittest.main()
