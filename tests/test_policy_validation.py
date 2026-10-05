"""Authoring checks reject malformed authority without interpreting policies."""
from dataclasses import replace
import unittest

from biocompiler.policy import model as m
from biocompiler.policy.inspection import diff, inspect, render_html
from biocompiler.policy.logic import FALSE, TRUE, UNKNOWN, all_of, count, exists, forall, literal, rising
from biocompiler.policy.serialization import document_digest
from biocompiler.policy.validation import check


SECOND = m.Unit("second", "time", "duration")
TIME = m.TypeSpec("quantity", SECOND)
ROLE = m.Ref("worker", "Role")
POLICY = m.Arbitration("concurrent", "reject", "identical_only", "forbidden", "none")


def fixture():
    capability = m.SemanticDefinition("capability", "1", "capability", "Requested abstract fixture capability.")
    observation = m.SemanticDefinition("observation", "1", "observation", "Fixture Boolean observation.", result=m.TRUTH)
    operation = m.SemanticDefinition("operation", "1", "operation", "Abstract request with no physical outcome claim.")
    lifecycle = m.SemanticDefinition("lifecycle", "1", "lifecycle", "Declared feedback and cancellation contract.")
    relation = m.SemanticDefinition("relation", "1", "spatial", "Declared relation to the selected subject.")
    transport = m.SemanticDefinition("transport", "1", "transport", "Explicit fixture message transport.")
    definitions = m.SemanticBundle("semantics", "1", (capability, observation, operation, lifecycle, relation, transport))
    role = m.Role("worker", (capability.ref,))
    clock = m.Clock("clock", "availability", m.Quantity("1", SECOND))
    sample = m.Observation("sample", ROLE, ROLE, m.TRUTH, observation.ref,
                           m.Ref("clock", "Clock"), "cell", "sampled", "frame", m.Quantity("2", SECOND))
    effect = m.Effect("effect", operation.ref, ROLE, ROLE,
                      m.EffectLifecycle("continuous", "request_stop", "request_stop", "acknowledged", "feedback", "feedback", lifecycle.ref))
    rule = m.Rule("rule", ROLE, sample.updated, sample.expression, "defer", (m.Ref("effect", "Effect"),), arbitration=POLICY)
    source = m.SourceSpan("rule", "policy_fixture.py", 19, 4)
    return m.PolicyProgram("fixture", definitions, (role, clock, sample, effect, rule), (source,))


def update(program, identity, **kwargs):
    return replace(program, declarations=tuple(replace(item, **kwargs) if item.id == identity else item for item in program.declarations))


def add(program, *declarations):
    return replace(program, declarations=program.declarations + declarations)


def codes(program):
    return {item.code for item in check(program).diagnostics}


class PolicyValidationTests(unittest.TestCase):
    def test_complete_is_structural_only_and_report_is_detached(self):
        program = fixture()
        result = check(program)
        self.assertEqual(result.status, "complete")
        self.assertEqual(result.errors, ())
        self.assertEqual(result.semantic_status, "unassessed")
        self.assertEqual(result.target_status, "unassessed")
        self.assertIn("effect_authorization_feedback_and_cancellation", result.deferred_obligations)
        self.assertIn("effects:lifecycle", result.required_features)
        data = result.to_dict()
        data["required_features"].clear()
        self.assertTrue(result.required_features)
        self.assertFalse(hasattr(result, "passed"))

    def test_unknown_guard_and_contradictory_requirements_are_not_executed(self):
        program = update(fixture(), "rule", when=UNKNOWN)
        program = add(program,
                      m.Requirement("required", "progress", "Require a response", m.Scope("executor", ROLE), condition=TRUE, response=TRUE),
                      m.Requirement("forbidden", "safety", "Prohibit the same response", m.Scope("executor", ROLE), condition=TRUE, response=FALSE))
        result = check(program)
        self.assertEqual(result.status, "complete")
        self.assertIn("safety_and_progress_satisfaction", result.deferred_obligations)
        self.assertEqual(result.semantic_status, "unassessed")

    def test_shape_checks_reject_wrong_tags_types_and_enum_values(self):
        program = fixture()
        for changed in (replace(program, declarations=("not a declaration",)),
                        update(program, "sample", access="secret"),
                        update(program, "rule", when=m.Expr("execute_python", m.TRUTH)),
                        update(program, "rule", when=m.Expr("literal", m.TypeSpec("predicate"), value=True))):
            with self.subTest(changed=changed):
                self.assertEqual(check(changed).status, "invalid")
                self.assertIn("document_shape", codes(changed))
        self.assertIn("document_type", codes({"schema_version": m.PROFILE}))

    def test_exact_definition_body_cannot_be_replaced_by_matching_labels(self):
        program = fixture()
        defs = list(program.semantics.definitions)
        defs[0] = replace(defs[0], meaning="Different capability, same identity and version.")
        changed = replace(program, semantics=replace(program.semantics, definitions=tuple(defs)))
        self.assertIn("definition_identity", codes(changed))
        missing = replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions[1:]))
        self.assertIn("missing_definition", codes(missing))

    def test_duplicate_and_mistyped_references_remain_visible(self):
        program = fixture()
        self.assertIn("duplicate_declaration", codes(add(program, program.declarations[0])))
        self.assertIn("reference_identity", codes(update(program, "rule", effects=(m.Ref("worker", "Effect"),))))
        self.assertIn("missing_reference", codes(update(program, "rule", effects=(m.Ref("absent", "Effect"),))))

    def test_imported_identifiers_match_builder_grammar_without_restricting_scientific_units(self):
        program = fixture()
        for identity in ("white space", "λ", "1starts_with_digit", "trailing\n"):
            with self.subTest(identity=identity):
                self.assertIn("invalid_identifier", codes(replace(program, id=identity)))
                self.assertIn("invalid_identifier", codes(add(program, m.Subject(identity, "cell", "stable"))))
                definition = m.SemanticDefinition(identity, "1", "model", "Free-form scientific meaning is preserved.")
                changed = replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions + (definition,)))
                self.assertIn("invalid_identifier", codes(changed))
        self.assertEqual(check(replace(program, id="namespace.policy:variant-1/name")).status, "complete")
        unit = m.Unit("µg", "mass", "payload mass")
        scientific = m.Parameter("mass", m.TypeSpec("quantity", unit), m.Quantity("1", unit))
        self.assertEqual(check(add(program, scientific)).status, "complete")

    def test_diagnostics_bind_original_source_and_related_identity(self):
        program = update(fixture(), "rule", effects=(m.Ref("missing", "Effect"),))
        diagnostic = next(item for item in check(program).errors if item.code == "missing_reference")
        self.assertEqual(diagnostic.declaration_id, "rule")
        self.assertEqual(diagnostic.source, program.source_map[0])
        self.assertEqual(diagnostic.path, "/declarations/4/effects/0")
        self.assertEqual(diagnostic.related, ("missing",))

    def test_observation_access_cannot_be_promoted_by_a_rule(self):
        external = update(fixture(), "sample", access="external_evaluator")
        self.assertIn("observation_access", codes(external))
        # Evaluator-only observations are legal evidence for requirements.
        requirements_only = replace(external, declarations=tuple(item for item in external.declarations if not isinstance(item, m.Rule)), source_map=())
        sample = next(item for item in requirements_only.declarations if isinstance(item, m.Observation))
        requirements_only = add(requirements_only, m.Requirement("observability", "observability", "Observe an endpoint", m.Scope("program"), condition=sample.expression))
        self.assertEqual(check(requirements_only).status, "complete")

    def test_cross_executor_reads_effects_and_emissions_reject(self):
        program = add(fixture(), m.Role("other", (fixture().semantics.definitions[0].ref,)))
        self.assertIn("executor_ownership", codes(update(program, "rule", executor=m.Ref("other", "Role"))))
        channel = m.Channel("channel", ROLE, (m.Ref("other", "Role"),), m.TRUTH,
                            program.semantics.definitions[-1].ref, m.Scope("program"), "fifo", "forbidden", "deduplicate", "required", "bounded", 2)
        message = m.Message("message", m.Ref("channel", "Channel"), ROLE, ROLE, ROLE, TRUE)
        program = add(program, channel, message)
        self.assertEqual(check(update(program, "rule", emissions=(m.Ref("message", "Message"),))).status, "complete")
        bad = add(program, m.Rule("other_rule", m.Ref("other", "Role"), rising(TRUE), TRUE, "defer", (), emissions=(m.Ref("message", "Message"),)))
        self.assertIn("executor_ownership", codes(bad))

    def test_message_notifications_require_the_declared_phase_interface(self):
        program = add(fixture(), m.Role("recipient", ()), m.Role("outsider", ()))
        recipient = m.Ref("recipient", "Role")
        channel = m.Channel("channel", ROLE, (recipient,), m.TRUTH,
                            program.semantics.definitions[-1].ref, m.Scope("program"), "fifo", "permitted", "deduplicate", "required", "bounded", 2)
        message = m.Message("message", m.Ref("channel", "Channel"), ROLE, ROLE, ROLE, TRUE)
        rule = m.Rule("receive", recipient, message.event("received"), TRUE, "defer", ())
        program = add(program, channel, message, rule)
        self.assertEqual(check(program).status, "complete")
        self.assertIn("executor_ownership", codes(update(program, "receive", executor=m.Ref("outsider", "Role"))))
        self.assertIn("executor_ownership", codes(update(program, "receive", on=message.event("sent"))))
        self.assertEqual(check(update(update(program, "receive", executor=ROLE), "receive", on=message.event("acknowledged"))).status, "complete")

    def test_effect_subject_needs_explicit_relation(self):
        program = add(fixture(), m.Subject("target", "cell", "stable"), m.Subject("observed", "cell", "stable"))
        sample = replace(program.declarations[2], subject=m.Ref("observed", "Subject"))
        program = update(update(program, "sample", subject=sample.subject), "rule", on=sample.updated, when=sample.expression)
        changed = update(program, "effect", subject=m.Ref("target", "Subject"))
        self.assertIn("effect_relationship", codes(changed))
        fixed = update(changed, "effect", relationship=program.semantics.definitions[-2].ref)
        self.assertEqual(check(fixed).status, "complete")
        same_subject = update(changed, "effect", subject=sample.subject)
        self.assertEqual(check(same_subject).status, "complete")

    def test_expression_arity_event_truth_and_units_are_distinct(self):
        program = fixture()
        self.assertIn("expression_arity", codes(update(program, "rule", when=m.Expr("not", m.TRUTH, (TRUE, FALSE)))))
        self.assertIn("expression_input_type", codes(update(program, "rule", when=m.Expr("all", m.TRUTH, (rising(TRUE),)))))
        self.assertIn("guard_type", codes(update(program, "rule", when=rising(TRUE))))
        rate = m.Unit("rate", "amount/time", "production_rate", reference="per_executor")
        concentration = m.Unit("concentration", "amount/time", "concentration", reference="bulk")
        compare = m.Expr("ge", m.TRUTH, (literal(m.Quantity("1", rate)), literal(m.Quantity("1", concentration))))
        self.assertIn("incompatible_operands", codes(update(program, "rule", when=compare)))

    def test_wrong_leaf_scope_and_nested_mixed_subjects_reject(self):
        program = fixture()
        sample = program.declarations[2]
        self.assertIn("expression_scope", codes(update(program, "rule", when=replace(sample.expression, scope=m.Ref("other", "Role")))))
        first = m.Subject("first", "cell", "stable")
        second = m.Subject("second", "cell", "stable")
        one = replace(sample, id="one", subject=m.Ref("first", "Subject"))
        two = replace(sample, id="two", subject=m.Ref("second", "Subject"))
        program = add(program, first, second, one, two)
        self.assertIn("mixed_subject_scope", codes(update(program, "rule", when=all_of(all_of(one.expression), two.expression))))

    def test_custom_operation_is_an_explicit_subject_relationship_boundary(self):
        program = fixture()
        first = m.Subject("first", "cell", "stable")
        second = m.Subject("second", "cell", "stable")
        one = replace(program.declarations[2], id="one", subject=m.Ref("first", "Subject"))
        two = replace(program.declarations[2], id="two", subject=m.Ref("second", "Subject"))
        definition = m.SemanticDefinition("relationship", "1", "operation", "Explicit two-subject supplied relation.",
                                           (m.Parameter("left", m.TRUTH), m.Parameter("right", m.TRUTH)), m.TRUTH)
        program = add(replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions + (definition,))), first, second, one, two)
        call = m.Expr("call", m.TRUTH, (one.expression, two.expression), contract=definition.ref)
        self.assertEqual(check(update(program, "rule", when=all_of(call))).status, "complete")

    def test_quantifiers_bind_a_declared_member_in_the_matching_domain(self):
        program = fixture()
        domain = m.Ref("population", "Subject")
        binding = m.Ref("member", "Subject")
        member = m.Subject("member", "cell", "bound", ROLE, domain=domain)
        observation = replace(program.declarations[2], id="member_observation", subject=binding)
        program = add(program, m.Subject("population", "population", "aggregate"), member, observation)
        for quantified in (exists(domain, observation.expression, binding=binding),
                           forall(domain, observation.expression, binding=binding),
                           count(domain, observation.expression, binding=binding).compare("ge", 1)):
            with self.subTest(operation=quantified.op):
                self.assertEqual(check(update(program, "rule", when=quantified)).status, "complete")
        quantified = exists(domain, observation.expression, binding=binding)
        self.assertIn("quantifier_binding", codes(update(program, "rule", when=replace(quantified, binding=None))))
        other = m.Ref("region", "Subject")
        program = add(program, m.Subject("region", "region", "aggregate"))
        self.assertIn("quantifier_binding", codes(update(program, "rule", when=replace(quantified, scope=other))))
        with self.assertRaises(TypeError):
            exists(domain, observation.expression)

    def test_quantifiers_cannot_use_free_targets_or_let_bound_subjects_escape(self):
        program = fixture()
        domain = m.Ref("population", "Subject")
        binding = m.Ref("member", "Subject")
        bound = m.Subject("member", "cell", "bound", ROLE, domain=domain)
        member = replace(program.declarations[2], id="member_observation", subject=binding)
        external = replace(program.declarations[2], id="external_observation", subject=m.Ref("external", "Subject"))
        program = add(program, m.Subject("population", "population", "aggregate"), bound, member,
                      m.Subject("external", "cell", "stable"), external)
        unused = exists(domain, external.expression, binding=binding)
        self.assertIn("unused_quantifier_binding", codes(update(program, "rule", when=unused)))
        self.assertIn("quantifier_free_subject", codes(update(program, "rule", when=unused)))
        self.assertIn("unbound_subject", codes(update(program, "rule", when=member.expression)))
        self.assertIn("bound_subject_escape", codes(update(program, "effect", subject=binding)))
        self.assertIn("subject_domain", codes(update(program, "member", domain=None)))

    def test_nested_quantifiers_keep_separate_lexical_bindings(self):
        program = fixture()
        domain = m.Ref("population", "Subject")
        first, second = m.Ref("first", "Subject"), m.Ref("second", "Subject")
        one = replace(program.declarations[2], id="one", subject=first)
        two = replace(program.declarations[2], id="two", subject=second)
        program = add(program, m.Subject("population", "population", "aggregate"),
                      m.Subject("first", "cell", "bound", ROLE, domain=domain),
                      m.Subject("second", "cell", "bound", ROLE, domain=domain), one, two)
        nested = exists(domain, all_of(one.expression, exists(domain, two.expression, binding=second)), binding=first)
        self.assertEqual(check(update(program, "rule", when=nested)).status, "complete")
        shadowed = exists(domain, exists(domain, one.expression, binding=first), binding=first)
        self.assertIn("quantifier_shadowing", codes(update(program, "rule", when=shadowed)))
        escaped = exists(domain, two.expression, binding=first)
        self.assertIn("unbound_subject", codes(update(program, "rule", when=escaped)))

    def test_time_declarations_require_clock_duration_and_coverage(self):
        program = fixture()
        held = m.Expr("holds", m.TRUTH, (TRUE,), duration=m.Quantity("2", SECOND), clock=m.Ref("clock", "Clock"), coverage="continuous")
        self.assertEqual(check(update(program, "rule", when=held)).status, "complete")
        for field, value, code in (("clock", None, "missing_clock"), ("duration", None, "missing_duration"),
                                   ("coverage", None, "missing_coverage"), ("duration", m.Quantity("0", SECOND), "duration_bound")):
            with self.subTest(field=field):
                self.assertIn(code, codes(update(program, "rule", when=replace(held, **{field: value}))))

    def test_temporal_and_reference_fields_are_closed_per_operation(self):
        program = fixture()
        held = m.Expr("holds", m.TRUTH, (TRUE,), duration=m.Quantity("2", SECOND), clock=m.Ref("clock", "Clock"), coverage="event")
        self.assertIn("temporal_coverage", codes(update(program, "rule", when=held)))
        timestamp = m.Unit("timepoint", "time", "timestamp")
        self.assertIn("duration_dimension", codes(update(program, "clock", resolution=m.Quantity("1", timestamp))))
        until = m.Expr("until", m.TRUTH, (TRUE, FALSE), clock=m.Ref("clock", "Clock"), duration=m.Quantity("2", SECOND))
        self.assertIn("unexpected_expression_field", codes(update(program, "rule", when=until)))
        parameter = m.Parameter("parameter", m.TRUTH, True)
        scoped = m.Expr("parameter", m.TRUTH, ref=m.Ref("parameter", "Parameter"), scope=ROLE)
        self.assertIn("expression_scope", codes(update(add(program, parameter), "rule", when=scoped)))

    def test_draft_holes_are_incomplete_not_runtime_unknown(self):
        program = fixture()
        draft = m.PolicyDraft(program.id, program.semantics, program.declarations,
                              (m.Hole("which_endpoint", "Observation", "Which endpoint is accessible?"),), program.source_map)
        result = check(draft)
        self.assertEqual(result.status, "incomplete")
        self.assertEqual(result.errors, ())
        self.assertEqual(result.diagnostics[0].category, "authoring_incomplete")
        broken = replace(draft, declarations=tuple(item for item in draft.declarations if not isinstance(item, m.Role)))
        self.assertEqual(check(broken).status, "invalid")

    def test_state_scope_lifetime_capacity_and_assignment(self):
        program = fixture()
        state = m.StateStore("store", m.INTEGER, m.Scope("executor", ROLE), 0, 1, "reject", "executor", None, "not_applicable")
        program = add(program, state)
        self.assertEqual(check(program).status, "complete")
        self.assertIn("state_capacity", codes(update(program, "store", capacity=0)))
        self.assertIn("state_lifetime", codes(update(program, "store", lifetime="duration")))
        self.assertIn("assignment_type", codes(update(program, "rule", assignments=(m.Assignment(m.Ref("store", "StateStore"), TRUE),))))
        program = add(program, m.Subject("population", "population", "aggregate"))
        self.assertIn("population_coordination", codes(update(program, "store", scope=m.Scope("population", m.Ref("population", "Subject")))))

    def test_encounter_state_and_machine_scope_retain_executor_ownership(self):
        program = fixture()
        contract = m.SemanticDefinition("encounter", "1", "encounter", "Declared encounter identity.")
        program = replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions + (contract,)))
        target = m.Subject("target", "cell", "encounter", ROLE, m.Ref("encounter", "Encounter"))
        encounter = m.Encounter("encounter", ROLE, m.Ref("target", "Subject"), contract.ref, "contact_loss")
        state = m.StateStore("store", m.TRUTH, m.Scope("encounter", m.Ref("encounter", "Encounter")), False, 1, "reject", "encounter", None, "not_applicable")
        other = m.Ref("other", "Role")
        rule = m.Rule("other_rule", other, rising(TRUE), state.expression, "defer", ())
        program = add(program, target, encounter, state, m.Role("other", ()))
        self.assertEqual(check(program).status, "complete")
        self.assertIn("executor_ownership", codes(add(program, rule)))
        write = replace(rule, when=TRUE, assignments=(m.Assignment(m.Ref("store", "StateStore"), TRUE),))
        self.assertIn("executor_ownership", codes(add(program, write)))
        machine = m.Machine("machine", other, state.scope, ("ready",), "ready", (), "encounter", POLICY)
        self.assertIn("executor_ownership", codes(add(program, machine)))
        self.assertIn("subject_encounter", codes(update(program, "target", executor=other)))
        persistent = update(program, "store", lifetime="persistent")
        result = check(persistent)
        self.assertEqual(result.status, "complete")
        self.assertEqual(next(item for item in result.diagnostics if item.code == "persistent_encounter_identity").severity, "warning")
        self.assertIn("persistent_encounter_identity_lifetime", result.deferred_obligations)
        self.assertEqual(result.semantic_status, "unassessed")

    def test_spatial_and_resource_references_reject_wrong_declared_kinds(self):
        program = fixture()
        self.assertIn("reference_kind", codes(update(program, "sample", spatial_scope=ROLE)))
        self.assertIn("definition_category", codes(update(program, "effect", resources=(program.semantics.definitions[0].ref,))))

    def test_machine_membership_is_checked_without_proving_reachability(self):
        program = fixture()
        machine = m.Machine("machine", ROLE, m.Scope("executor", ROLE), ("ready", "active", "failed", "succeeded"), "ready", ("failed", "succeeded"), "executor", POLICY)
        transition = m.Transition("start", m.Ref("machine", "Machine"), "ready", "active", rising(TRUE), TRUE, "defer")
        cycle = replace(transition, id="cycle", source="active", destination="ready")
        program = add(program, machine, transition, cycle)
        self.assertEqual(check(program).status, "complete")
        self.assertIn("machine_reachability_termination_and_progress", check(program).deferred_obligations)
        self.assertIn("machine_membership", codes(update(program, "machine", initial="absent")))
        self.assertIn("transition_membership", codes(update(program, "start", destination="absent")))
        self.assertIn("unknown_target", codes(update(program, "start", unknown="transition")))

    def test_same_output_writers_require_arbitration_even_for_disjoint_guards(self):
        program = update(fixture(), "rule", arbitration=None, when=TRUE)
        rule = next(item for item in program.declarations if isinstance(item, m.Rule))
        program = add(program, replace(rule, id="other_rule", when=FALSE))
        self.assertIn("missing_arbitration", codes(program))
        program = update(update(program, "rule", arbitration=POLICY), "other_rule", arbitration=POLICY)
        self.assertEqual(check(program).status, "complete")

    def test_rules_and_machine_transitions_share_conflict_arbitration(self):
        program = update(fixture(), "rule", arbitration=None)
        machine = m.Machine("machine", ROLE, m.Scope("executor", ROLE), ("ready", "done"), "ready", ("done",), "executor", POLICY)
        transition = m.Transition("start", m.Ref("machine", "Machine"), "ready", "done", rising(TRUE), TRUE, "defer", effects=(m.Ref("effect", "Effect"),))
        program = add(program, machine, transition)
        self.assertIn("missing_arbitration", codes(program))
        program = update(program, "rule", arbitration=POLICY)
        self.assertEqual(check(program).status, "complete")
        self.assertIn("inconsistent_arbitration", codes(update(program, "machine", arbitration=replace(POLICY, mode="exclusive"))))
        ordered = replace(POLICY, mode="priority", order=("rule", "start"))
        program = update(update(program, "rule", arbitration=ordered), "machine", arbitration=ordered)
        self.assertEqual(check(program).status, "complete")
        partial = replace(ordered, order=("rule",))
        self.assertIn("arbitration_order_coverage", codes(update(update(program, "rule", arbitration=partial), "machine", arbitration=partial)))

    def test_priority_and_declared_order_cover_every_required_participant(self):
        program = fixture()
        empty = replace(POLICY, mode="priority", order=())
        self.assertIn("arbitration_order", codes(update(program, "rule", arbitration=empty)))
        machine = m.Machine("machine", ROLE, m.Scope("executor", ROLE), ("ready", "done"), "ready", (), "executor", replace(POLICY, tie="declared_order", order=("start",)))
        start = m.Transition("start", m.Ref("machine", "Machine"), "ready", "done", rising(TRUE), TRUE, "defer")
        back = replace(start, id="back", source="done", destination="ready")
        program = add(program, machine, start, back)
        self.assertIn("arbitration_order_coverage", codes(program))
        self.assertEqual(check(update(program, "machine", arbitration=replace(machine.arbitration, order=("start", "back")))).status, "complete")

    def test_parameters_and_fixed_capacity_references_preserve_numeric_bounds(self):
        program = fixture()
        bad = m.Parameter("text", m.TEXT, "a", lower=m.Quantity("1", SECOND), upper=m.Quantity("2", SECOND))
        self.assertIn("parameter_bound_type", codes(add(program, bad)))
        value = m.Parameter("time", TIME, m.Quantity("3", SECOND), lower=m.Quantity("1", SECOND), upper=m.Quantity("2", SECOND))
        self.assertIn("parameter_bound_value", codes(add(program, value)))
        self.assertEqual(check(add(program, replace(value, value=m.Quantity("1.5", SECOND)))).status, "complete")
        capacity = m.Parameter("capacity", m.INTEGER, -3)
        state = m.StateStore("store", m.TRUTH, m.Scope("executor", ROLE), False, m.Ref("capacity", "Parameter"), "reject", "executor", None, "not_applicable")
        self.assertIn("state_capacity", codes(add(program, capacity, state)))
        count_unit = m.Unit("count", "count", "count")
        capacity = replace(capacity, value=2, lower=m.Quantity("1", count_unit), upper=m.Quantity("3", count_unit))
        self.assertEqual(check(add(program, capacity, state)).status, "complete")
        broken = replace(capacity, lower=m.Quantity("1", replace(count_unit, scale="not-a-number")))
        self.assertEqual(check(add(program, broken, state)).status, "invalid")

    def test_timed_requirements_retain_trigger_clock_and_progress_response(self):
        program = fixture()
        effect = program.declarations[3]
        requirement = m.Requirement("progress", "progress", "Correlated response from the explicit request event.", m.Scope("executor", ROLE), condition=TRUE,
                                    response=effect.completed, deadline=m.Quantity("2", SECOND), trigger=effect.event("requested"), clock=m.Ref("clock", "Clock"))
        self.assertEqual(check(add(program, requirement)).status, "complete")
        self.assertIn("requirement_deadline_anchor", codes(add(program, replace(requirement, trigger=None))))
        self.assertIn("requirement_deadline_anchor", codes(add(program, replace(requirement, clock=None))))
        self.assertIn("requirement_trigger", codes(add(program, replace(requirement, trigger=TRUE))))
        self.assertIn("reference_kind", codes(add(program, replace(requirement, clock=ROLE))))
        self.assertIn("progress_response", codes(add(program, replace(requirement, response=None))))
        self.assertIn("progress_enabling", codes(add(program, replace(requirement, condition=None, trigger=None, deadline=None))))

    def test_definition_call_arguments_and_local_parameter_references(self):
        program = fixture()
        parameter = m.Parameter("value", m.TRUTH)
        local = m.Expr("parameter", m.TRUTH, ref=m.Ref("value", "Parameter"))
        definition = m.SemanticDefinition("predicate", "1", "operation", "Opaque declared operation.",
                                           (parameter,), m.TRUTH, (m.ContractClause("precondition", "Declared local parameter", local),))
        program = replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions + (definition,)))
        call = m.Expr("call", m.TRUTH, (TRUE,), contract=definition.ref)
        self.assertEqual(check(update(program, "rule", when=call)).status, "complete")
        self.assertIn("call_argument_type", codes(update(program, "rule", when=replace(call, args=(literal(1),)))))
        self.assertIn("call_arity", codes(update(program, "rule", when=replace(call, args=()))))

    def test_definition_parameters_are_lexical_even_with_colliding_declaration_ids(self):
        program = fixture()
        local = m.Expr("parameter", m.TRUTH, ref=m.Ref("private", "Parameter"))
        definition = m.SemanticDefinition("rule", "1", "operation", "Formal parameter remains local to this definition.",
                                           (m.Parameter("private", m.TRUTH),), m.TRUTH,
                                           (m.ContractClause("precondition", "Declared local parameter", local),))
        program = replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions + (definition,)))
        self.assertEqual(check(program).status, "complete")
        self.assertIn("missing_reference", codes(update(program, "rule", when=local)))
        program = add(program, m.Parameter("private", m.INTEGER, 1))
        self.assertIn("reference_value_type", codes(update(program, "rule", when=local)))
        global_expression = m.Expr("parameter", m.INTEGER, ref=m.Ref("private", "Parameter"))
        self.assertEqual(check(update(program, "rule", when=global_expression.compare("ge", 0))).status, "complete")

    def test_inspection_is_detached_and_html_escapes_authored_text(self):
        program = fixture()
        definition = replace(program.semantics.definitions[-1], meaning="<script>alert('x')</script>")
        program = replace(program, semantics=replace(program.semantics, definitions=program.semantics.definitions[:-1] + (definition,)))
        inspected = inspect(program)
        inspected["declarations"].clear()
        self.assertEqual(len(program.declarations), 5)
        html = render_html(program)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("unassessed", html)
        self.assertEqual(program._repr_html_(), html)

    def test_diff_reports_context_order_provenance_and_no_semantic_equality(self):
        program = fixture()
        changed = update(program, "sample", freshness=m.Quantity("9", SECOND))
        result = diff(program, changed)
        self.assertEqual(result["declaration_changes"][0]["id"], "sample")
        self.assertFalse(result["identical_declaration_content"])
        self.assertEqual(result["semantic_status"], "unassessed")
        source_changed = replace(program, source_map=(replace(program.source_map[0], line=25),))
        self.assertEqual(document_digest(program), document_digest(source_changed))
        result = diff(program, source_changed)
        self.assertTrue(result["identical_declaration_content"])
        self.assertFalse(result["identical_document"])
        self.assertTrue(result["provenance_changes"])
        reordered = replace(program, declarations=tuple(reversed(program.declarations)))
        self.assertTrue(diff(program, reordered)["declaration_order_changed"])
        self.assertEqual(diff(program, reordered)["declaration_changes"], [])

    def test_diff_does_not_collapse_duplicate_declarations(self):
        program = fixture()
        result = diff(program, add(program, program.declarations[0]))
        self.assertEqual(result["ambiguous_declaration_ids"], ["worker"])
        self.assertTrue(result["changes"])


if __name__ == "__main__":
    unittest.main()
