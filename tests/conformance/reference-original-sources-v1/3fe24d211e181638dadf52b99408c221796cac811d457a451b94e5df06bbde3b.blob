"""Bounded, independent source proofs for distinct functional control meanings.

These proofs inspect original Intent nodes, never a compiler's coverage labels
or generated behavior. They are conditional language statements, not evidence
of a molecular mechanism. The caller separately checks implementation authority,
product/activity bindings, physical composition and control independence.
"""

from __future__ import annotations

from itertools import product
import math

from biocompiler.errors import BiocompilerError
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.types import DURATION, PRODUCTION_RATE, TypeSpec, decode_binding


class _Unsupported(Exception):
    pass


def _fail(reason):
    raise _Unsupported(reason)


def _typed(value):
    return type(value), value


def _atom(node):
    return node.inputs[0], fingerprint(node.attributes)


class _BooleanSpace:
    """Enumerate at most eight explicit observations, preserving scope and band.

Different bands are independent explicit observations in the language. No
biological relationship between ``present``, ``high`` and ``low`` is assumed.
Contact observations are allowed only in activity guards, never controllers.
"""

    def __init__(self, nodes, control, role):
        self.nodes, self.role = nodes, role
        self.atoms = set()
        refs = control["controlling_node_ids"]
        if len(refs) != 1:
            _fail("requires_one_boolean_condition")
        self.controller = refs[0]
        if nodes[self.controller].kind == "signal":
            predicates = [node.id for node in nodes.values()
                          if node.kind == "qualitative" and node.inputs == (self.controller,)]
            if len(predicates) != 1:
                _fail("ambiguous_signal_predicate")
            self.controller = predicates[0]
        self.add(self.controller, controller=True)
        self.control_atoms = frozenset(self.atoms)
        if not self.control_atoms:
            _fail("vacuous_control_condition")

    def add(self, identity, *, controller=False, state=None, contacts=False):
        pending, seen = [identity], set()
        while pending:
            ref = pending.pop()
            if ref in seen:
                continue
            seen.add(ref)
            node = self.nodes[ref]
            if node.data_type is None or node.data_type.get("kind") != "condition":
                _fail("non_boolean_control" if controller else "non_boolean_guard")
            if node.role not in {None, self.role}:
                _fail("cross_role_control_expression")
            if node.kind == "qualitative":
                signal = self.nodes[node.inputs[0]]
                if signal.kind != "signal" or signal.role != self.role:
                    _fail("unsupported_observation_atom")
                contact = (signal.attributes.get("scope") == "contact"
                           or self.nodes[signal.inputs[0]].attributes.get("scope") == "contact")
                if contact and not contacts:
                    _fail("non_cell_local_control" if controller else "non_cell_local_guard")
                if node.attributes.get("band") not in {"present", "high", "low"}:
                    _fail("unsupported_observation_band")
                self.atoms.add(_atom(node))
            elif node.kind == "signature":
                pending.append(node.inputs[0])
            elif node.kind in {"not", "and", "or"}:
                pending.extend(node.inputs)
            elif not controller and state is not None and node.kind == "state.is":
                if node.inputs != (state,):
                    _fail("other_store_guard")
                options = {_typed(value) for value in self.nodes[state].attributes["values"]}
                if _typed(node.attributes["value"]) not in options:
                    _fail("undeclared_state_predicate")
            else:
                _fail("unsupported_control_expression" if controller else "unsupported_guard_expression")
        if len(self.atoms) > 8:
            _fail("boolean_control_proof_bound")

    def value(self, ref, values, state_value=None):
        node = self.nodes[ref]
        if node.kind == "qualitative":
            return values[_atom(node)]
        if node.kind == "state.is":
            return _typed(state_value) == _typed(node.attributes["value"])
        if node.kind == "signature":
            return self.value(node.inputs[0], values, state_value)
        if node.kind == "not":
            return not self.value(node.inputs[0], values, state_value)
        parts = [self.value(child, values, state_value) for child in node.inputs]
        return all(parts) if node.kind == "and" else any(parts)

    def rows(self):
        atoms = sorted(self.atoms)
        rows = [(dict(zip(atoms, bits))) for bits in product((False, True), repeat=len(atoms))]
        if {self.value(self.controller, row) for row in rows} != {False, True}:
            _fail("vacuous_control_condition")
        return rows


def _primitive(nodes, ref):
    action, seen = nodes[ref], set()
    while action.kind == "action.pulse":
        if action.id in seen:
            _fail("cyclic_action_wrapper")
        seen.add(action.id)
        action = nodes[action.inputs[0]]
    return action


def _uses(nodes, predicate):
    """Every installed use, including reused primitives hidden behind pulses."""
    return [(rule, nodes[ref], primitive)
            for rule in nodes.values() if rule.kind == "rule"
            for ref in rule.inputs[2:]
            for primitive in (_primitive(nodes, ref),) if predicate(primitive)]


def _ongoing(rule, installed, primitive):
    if (installed.kind == "action.pulse" or rule.attributes.get("trigger") != "condition"
            or primitive.attributes.get("ongoing") is not True):
        _fail("persistent_or_event_installation")


def _constant(nodes, ref, bindings, cache=None):
    """Use the source scalar operations and exact independent frozen bindings."""
    cache = {} if cache is None else cache
    if ref in cache:
        return cache[ref]
    node = nodes[ref]
    dtype = TypeSpec.from_dict(node.data_type)
    if dtype.kind != "scalar":
        _fail("non_scalar_constant")
    if node.kind in {"literal", "parameter"}:
        if node.kind == "literal":
            raw = node.attributes["value"]
        elif bindings is not None:
            if node.attributes["name"] not in bindings:
                _fail("unbound_parameter")
            raw = bindings[node.attributes["name"]]
        else:
            raw = node.attributes.get("default")
            if raw is None:
                _fail("unbound_parameter")
        value = decode_binding(raw, dtype).canonical_value
    elif node.kind == "negate":
        child = nodes[node.inputs[0]]
        if not dtype.compatible(TypeSpec.from_dict(child.data_type)):
            _fail("constant_type_mismatch")
        value = -_constant(nodes, child.id, bindings, cache)
    elif node.kind in {"add", "subtract", "multiply", "divide"}:
        left, right = [TypeSpec.from_dict(nodes[child].data_type) for child in node.inputs]
        if node.kind in {"add", "subtract"}:
            if not left.compatible(right):
                _fail("constant_type_mismatch")
            expected = left
        else:
            expected = left * right if node.kind == "multiply" else left / right
        if not dtype.compatible(expected):
            _fail("constant_type_mismatch")
        a, b = [_constant(nodes, child, bindings, cache) for child in node.inputs]
        if node.kind == "divide" and b == 0:
            _fail("undefined_constant")
        value = {"add": lambda: a + b, "subtract": lambda: a - b,
                 "multiply": lambda: a * b, "divide": lambda: a / b}[node.kind]()
    else:
        _fail("non_constant_rate_or_duration")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        _fail("non_finite_constant")
    cache[ref] = value
    return value


def _target_store(nodes, target):
    store = nodes[target]
    if store.kind in {"memory.is_set", "state.is"}:
        store = nodes[store.inputs[0]]
    if store.kind not in {"memory", "state"}:
        _fail("target_not_memory_or_state")
    return store


def _memory_reset(nodes, target, control, bindings):
    store = _target_store(nodes, target)
    if store.kind == "state":
        return _state_reset(nodes, store, control)
    attrs = store.attributes
    if (attrs.get("initial") is not False or attrs.get("setting") != "onset"
            or attrs.get("initial_true_is_onset") is not True or attrs.get("reset_priority") is not True):
        _fail("unsupported_memory_policy")
    refs = dict(zip(attrs["input_names"], store.inputs))
    if "reset_when" not in refs:
        _fail("memory_reset_missing")
    expected_expiry = "latest_setting_onset" if "duration" in refs else "until_reset"
    if attrs.get("expiry") != expected_expiry:
        _fail("unsupported_memory_policy")
    if "duration" in refs:
        if (not TypeSpec.from_dict(nodes[refs["duration"]].data_type).compatible(DURATION)
                or _constant(nodes, refs["duration"], bindings) <= 0):
            _fail("unsupported_memory_duration")
    space = _BooleanSpace(nodes, control, store.role)
    space.add(refs["set_when"])
    space.add(refs["reset_when"])
    can_set = False
    for row in space.rows():
        asserted = space.value(space.controller, row)
        reset = space.value(refs["reset_when"], row)
        if asserted and not reset:
            _fail("assertion_does_not_reset")
        can_set |= not asserted and not reset and space.value(refs["set_when"], row)
    if not can_set:
        _fail("memory_never_set_without_control")


def _state_reset(nodes, store, control):
    attrs = store.attributes
    options = attrs["values"]
    if len(options) > 16:
        _fail("state_reset_proof_bound")
    if attrs.get("observation") != "prior_state" or attrs.get("arbitration") != "unspecified":
        _fail("unsupported_state_policy")
    keys = {_typed(value) for value in options}
    initial = attrs["initial"]
    if len(keys) != len(options) or _typed(initial) not in keys:
        _fail("invalid_state_domain")
    writers = _uses(nodes, lambda action: action.kind == "action.state_set"
                    and action.inputs == (store.id,))
    if not writers:
        _fail("state_reset_writer_missing")
    space = _BooleanSpace(nodes, control, store.role)
    for rule, installed, action in writers:
        if installed.kind == "action.pulse" or rule.attributes.get("trigger") != "condition":
            _fail("persistent_or_event_state_writer")
        if (action.attributes.get("idempotent") is not True
                or action.attributes.get("ongoing") is not False
                or _typed(action.attributes["value"]) not in keys):
            _fail("unsupported_state_assignment")
        space.add(rule.inputs[1], state=store.id)
    rows = space.rows()
    transitions = {}
    for row_index, row in enumerate(rows):
        asserted = space.value(space.controller, row)
        for before in options:
            written = {_typed(action.attributes["value"]): action.attributes["value"]
                       for rule, _, action in writers if space.value(rule.inputs[1], row, before)}
            if len(written) > 1:
                _fail("conflicting_state_writers")
            after = next(iter(written.values())) if written else before
            if asserted and _typed(after) != _typed(initial):
                _fail("assertion_does_not_reset_state")
            transitions[row_index, _typed(before)] = after

    # Inactive executions must settle under the actual shared-prestate,
    # simultaneous-write semantics. A graph edge is a complete stable reaction,
    # not a transient state that immediately resets in the same microstep loop.
    stable = {}
    for row_index, row in enumerate(rows):
        if space.value(space.controller, row):
            continue
        for before in options:
            current, seen = before, set()
            while True:
                key = _typed(current)
                if key in seen:
                    _fail("nonsettling_state_writers")
                seen.add(key)
                after = transitions[row_index, key]
                if _typed(after) == key:
                    stable[row_index, _typed(before)] = after
                    break
                current = after
    reachable, pending = {_typed(initial)}, [initial]
    while pending:
        before = pending.pop()
        for row_index, row in enumerate(rows):
            if space.value(space.controller, row):
                continue
            after = stable[row_index, _typed(before)]
            if _typed(after) not in reachable:
                reachable.add(_typed(after))
                pending.append(after)
    if len(reachable) < 2:
        _fail("state_never_changes_without_control")


def _target_actions(nodes, target):
    node = nodes[target]
    refs = node.inputs[2:] if node.kind == "rule" else (target,)
    if not refs or any(not nodes[ref].kind.startswith("action.") for ref in refs):
        _fail("target_not_installed_ongoing_action")
    return tuple(refs)


def _production_uses(nodes, target):
    """Resolve the complete product effect scope before any functional proof."""
    target_node = nodes[target]
    if target_node.kind == "secretion":
        declarations = [target_node]
    else:
        declarations = []
        for ref in _target_actions(nodes, target):
            action = nodes[ref]
            if action.kind != "action.secrete":
                _fail("target_not_production_action")
            declarations.append(nodes[action.inputs[0]])
    products = {(node.role, node.attributes["product"]) for node in declarations if node.kind == "secretion"}
    if len(products) != 1 or any(node.kind != "secretion" for node in declarations):
        _fail("ambiguous_production_product")
    role, identity = next(iter(products))
    declaration_ids = {node.id for node in nodes.values() if node.kind == "secretion"
                       and (node.role, node.attributes["product"]) == (role, identity)}
    uses = _uses(nodes, lambda action: action.kind == "action.secrete" and action.role == role
                 and action.inputs[0] in declaration_ids)
    if not uses:
        _fail("target_not_installed_ongoing_action")
    if target_node.kind != "secretion" and not all(
            any(action.id == ref for _, _, action in uses) for ref in _target_actions(nodes, target)):
        _fail("target_not_installed_ongoing_action")
    return role, uses


def _production_adjustment(nodes, target, control, bindings):
    role, uses = _production_uses(nodes, target)
    space = _BooleanSpace(nodes, control, role)
    branches = []
    for rule, installed, action in uses:
        _ongoing(rule, installed, action)
        space.add(rule.inputs[1])
        if action.attributes.get("rate") != "expression" or len(action.inputs) != 2:
            _fail("unspecified_production_rate")
        if not TypeSpec.from_dict(nodes[action.inputs[1]].data_type).compatible(PRODUCTION_RATE):
            _fail("production_rate_type_mismatch")
        rate = _constant(nodes, action.inputs[1], bindings)
        if rate < 0:
            _fail("negative_production_rate")
        branches.append((rule.inputs[1], rate))
    groups = {}
    other_atoms = sorted(space.atoms - space.control_atoms)
    for row in space.rows():
        rates = [rate for guard, rate in branches if space.value(guard, row)]
        if len(rates) > 1:
            _fail("overlapping_production_requests")
        key = tuple(row[atom] for atom in other_atoms)
        asserted = space.value(space.controller, row)
        groups.setdefault(key, {False: set(), True: set()})[asserted].add(rates[0] if rates else 0)
    directions = set()
    for values in groups.values():
        if any(len(values[state]) != 1 for state in (False, True)):
            _fail("ambiguous_production_control_state")
        inactive, active = next(iter(values[False])), next(iter(values[True]))
        if inactive != active:
            directions.add(1 if active > inactive else -1)
    if not directions:
        _fail("production_rate_unchanged")
    if len(directions) > 1:
        _fail("nonmonotone_production_adjustment")


def _activity_control(nodes, target, control):
    actions = _target_actions(nodes, target)
    if any(nodes[ref].kind not in {"action.eliminate", "action.engulf", "action.rest"} for ref in actions):
        _fail("target_not_explicit_activity_action")
    roles = {nodes[ref].role for ref in actions}
    if len(roles) != 1:
        _fail("ambiguous_activity_role")
    space = _BooleanSpace(nodes, control, next(iter(roles)))
    by_action = {}
    for action_id in actions:
        uses = _uses(nodes, lambda action: action.id == action_id)
        if not uses:
            _fail("target_not_installed_ongoing_action")
        by_action[action_id] = []
        for rule, installed, primitive in uses:
            _ongoing(rule, installed, primitive)
            space.add(rule.inputs[1], contacts=True)
            by_action[action_id].append(rule.inputs[1])
    witnessed = set()
    for row in space.rows():
        asserted = space.value(space.controller, row)
        for action_id, guards in by_action.items():
            enabled = any(space.value(guard, row) for guard in guards)
            if enabled and not asserted:
                _fail("deassertion_does_not_gate_activity")
            if enabled:
                witnessed.add(action_id)
    if witnessed != set(actions):
        _fail("activity_never_enabled")


def extended_control_targets(nodes, target, kind):
    """Exact effect/store scope for causal and material checks of each proof.

    Production targets expand to every installed primitive secretion action for
    the selected role/product, across all declarations and source rules. Merely
    binding the named branch's component cannot establish aggregate production
    control or aggregate independence. Store read aliases resolve to the store;
    activity rule targets resolve to all of that rule's action specifications.

    Resolution is not a functional proof. Unsupported or malformed target
    resolution returns an empty tuple, which must never discharge an obligation.
    ``prove_extended_control`` supplies the corresponding explicit failure.
    Other control kinds retain their known original target unchanged.
    """
    try:
        if kind == "production_adjustment":
            _, uses = _production_uses(nodes, target)
            return tuple(dict.fromkeys(action.id for _, _, action in uses))
        if kind == "memory_reset":
            return (_target_store(nodes, target).id,)
        if kind == "activity_control":
            return tuple(dict.fromkeys(_target_actions(nodes, target)))
        return (target,) if target in nodes else ()
    except (_Unsupported, BiocompilerError, KeyError, TypeError, ValueError,
            IndexError, AttributeError, RecursionError):
        return ()


def prove_extended_control(nodes, target, control, kind, *, parameter_bindings=None):
    """Return ``None`` only for the requested nonvacuous source theorem.

    ``memory_reset``: assertion dominates setting and clears a reset-priority
    memory, or forces a finite state to its declared initial value. Finite state
    proofs consider every installed writer and typed prestate (at most 16),
    including simultaneous writes. A stable noninitial inactive state must be
    reachable. Temporal/event/other-store dependencies remain unsupported.

    ``production_adjustment``: for the complete role/product aggregate, each
    fixed noncontroller observation has exactly one off and on requested rate.
    Rates are finite nonnegative typed source constants, no requests overlap,
    and changes are monotone in one direction with at least one strict change.
    Zero means no active request, not an assertion of zero biological secretion.

    ``activity_control``: every installed use of each explicit ongoing effector
    action is disabled when the controller is false, and each action has an
    enabled witness when true. The caller must independently require explicit
    biological_activity/activity_control product authority. This is not protein
    removal or control of an independently persistent product.

    All proofs enumerate at most eight explicit qualitative observation atoms;
    the controller is cell-local and both assertion states must be attainable.
    Frozen parameter bindings, when supplied, are complete independent authority
    and never fall back to defaults. Reasons preserve unsupported/failed scope.
    """
    proofs = {"memory_reset": _memory_reset, "production_adjustment": _production_adjustment}
    try:
        if kind == "activity_control":
            _activity_control(nodes, target, control)
        elif kind in proofs:
            proofs[kind](nodes, target, control, parameter_bindings)
        else:
            return "kind_not_implemented"
    except _Unsupported as error:
        return str(error)
    except (BiocompilerError, KeyError, TypeError, ValueError, IndexError,
            AttributeError, OverflowError, RecursionError):
        return "malformed_or_unsupported_control_source"
    return None
