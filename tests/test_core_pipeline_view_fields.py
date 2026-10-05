"""Native structural views preserve the original raw dataclass namespace."""
from contextlib import ExitStack
from dataclasses import fields
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import core_pipeline_manager as bridge
from biocompiler.compiler.pipeline import (
    CheckSpec, CompletionProfile, ComponentInputContract, PassContract, ScopedObligation,
)
from biocompiler.core_client import CoreProtocolError
from biocompiler.ir.stages import Stage
from biocompiler.verification.evidence import EvidenceKind
from tools import check_pipeline_reference_install as campaign


CLASSES = (ScopedObligation, CheckSpec, ComponentInputContract, PassContract, CompletionProfile)


def original_values():
    obligation = ScopedObligation('exact', 'checked', EvidenceKind.EXACT, 'Exact fixture requirement')
    check = CheckSpec('verify', EvidenceKind.EXACT, ('exact',))
    admission = ComponentInputContract('admission', '1', 'components.v1', (check,),
        ('exact',), (obligation,), ('request',), ('admit',))
    contract = PassContract('pass', '1', Stage.INTENT, Stage.BEHAVIOR, 'intent.v1',
        'behavior.v1', 'checked', '1', ('operation',), (check,), introduces=(obligation,))
    profile = CompletionProfile('checked', Stage.BEHAVIOR, 'behavior.v1', ('exact',))
    return obligation, check, admission, contract, profile


def wire(value):
    if type(value) is CompletionProfile:
        value = {'scope': value.scope, 'stage': value.stage.value,
            'schema': value.schema, 'obligations': list(value.obligations)}
    else:
        value = value.to_dict()
    # Actual native frame JSON sorts object keys. Hydration must not adopt it
    # as the Python constructor's raw attribute insertion order.
    return json.loads(json.dumps(value, sort_keys=True))


def hydrate(value, document):
    if type(value) is ScopedObligation:
        return bridge._obligation(document)
    if type(value) is CheckSpec:
        return bridge._check_view(document)
    if type(value) is CompletionProfile:
        return bridge._profile_view(document)
    return bridge._contract_view(document, admission=type(value) is ComponentInputContract)


class CorePipelineViewFieldTests(unittest.TestCase):
    def test_actual_views_match_generated_constructor_namespace_and_field_values(self):
        for original in original_values():
            with self.subTest(cls=type(original).__name__):
                document = wire(original)
                with ExitStack() as stack:
                    for cls in CLASSES:
                        stack.enter_context(patch.object(cls, '__init__', side_effect=AssertionError('Constructor ran')))
                        stack.enter_context(patch.object(cls, '__post_init__', side_effect=AssertionError('Semantic check ran')))
                    actual = hydrate(original, document)
                self.assertIs(type(actual), type(original))
                self.assertEqual(list(vars(actual)), list(vars(original)))
                self.assertEqual(list(vars(actual)), [field.name for field in fields(original)])
                self.assertEqual(vars(actual), vars(original))
                self.assertEqual(wire(actual), document)
                self.assertNotIn('stage', vars(actual) if type(actual) is ComponentInputContract else {})

    def test_complete_graph_metadata_and_value_comparison_remains_exact(self):
        oracle = campaign.load_original()
        for original in original_values():
            with self.subTest(cls=type(original).__name__):
                actual = hydrate(original, wire(original))
                old = oracle.Graph(oracle.Store(), object)
                new = campaign.ObservationGraph(oracle, SimpleNamespace())
                left = old.snapshot([('value', original)])
                right = new.snapshot([('value', actual)])
                campaign.GraphCorrespondence(old.store.docs, new.store.docs).compare(left, right)
                # Recreate the old JSON-order namespace defect. The unchanged
                # complete graph comparator must still reject it.
                moved = vars(actual).pop(next(iter(vars(actual))))
                setattr_name = fields(actual)[0].name
                object.__setattr__(actual, setattr_name, moved)
                bad = campaign.ObservationGraph(oracle, SimpleNamespace())
                changed = bad.snapshot([('value', actual)])
                with self.assertRaisesRegex(AssertionError, 'raw dataclass structure changed'):
                    campaign.GraphCorrespondence(old.store.docs, bad.store.docs).compare(left, changed)

    def test_raw_hydration_retains_each_supplied_object_and_ignores_input_order(self):
        for cls in CLASSES:
            with self.subTest(cls=cls.__name__):
                names = [field.name for field in fields(cls)]
                values = {name: object() for name in reversed(names)}
                actual = bridge._raw_fields(cls, values)
                self.assertEqual(list(vars(actual)), names)
                for name, value in values.items():
                    self.assertIs(vars(actual)[name], value)

    def test_unknown_classes_and_missing_extra_fields_are_rejected(self):
        class ProfileSubclass(CompletionProfile):
            pass
        with self.assertRaisesRegex(CoreProtocolError, 'Unreviewed native structural view class'):
            bridge._raw_fields(ProfileSubclass, {})
        for cls in CLASSES:
            names = [field.name for field in fields(cls)]
            valid = {name: object() for name in names}
            for changed in ({name: value for name, value in valid.items() if name != names[0]},
                            {**valid, 'extra': object()}, None):
                with self.subTest(cls=cls.__name__), self.assertRaisesRegex(CoreProtocolError, 'field census differs'):
                    bridge._raw_fields(cls, changed)

    def test_existing_native_value_guards_still_reject_malformed_views(self):
        obligation, check, admission, contract, profile = original_values()
        mutants = ((obligation, 'evidence_kind', 'unreviewed'),
            (check, 'discharges', 'not-an-array'), (admission, 'stage', Stage.BEHAVIOR.value),
            (contract, 'requires_source_map', 'not-a-bool'), (profile, 'scope', 5))
        for value, field, changed in mutants:
            with self.subTest(cls=type(value).__name__, field=field):
                document = wire(value)
                document[field] = changed
                with self.assertRaises((CoreProtocolError, ValueError)):
                    hydrate(value, document)


if __name__ == '__main__':
    unittest.main()
