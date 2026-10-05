"""Real SDK record decoder controls with an inert session; no native execution."""
from copy import copy
from types import SimpleNamespace
import unittest

from tools import check_pipeline_fixed_registration_install as gate


class RegistrationHistoricalRecordTests(unittest.TestCase):
    def setUp(self):
        from tests.test_core_pipeline_manager import CorePipelineManagerTests
        self.views = CorePipelineManagerTests()
        self.views.setUp()
        self.addCleanup(self.views.doCleanups)
        self.actual = self.views.manager
        self.names = ('request', 'behavior', 'mechanism')
        self.envelopes = {name: self.views.record(identity=name) for name in self.names}
        # build_result('synthetic') decodes its mechanism candidate before the
        # first native inspection publishes the complete ordered history.
        self.mechanism = self.actual._record(self.envelopes['mechanism'])
        for name in self.names:
            self.actual._record(self.envelopes[name])
        self.before = tuple((name, self.actual._records[name]) for name in self.names)
        # Subsequent native reference definitions reuse the same typed objects.
        for name in self.names:
            self.assertIs(self.actual._record(self.envelopes[name]), dict(self.before)[name])
        self.response = SimpleNamespace(operation='inspect-ordered-references', sequence=288,
            result={'order': {'records': list(self.names)}})
        self.actual.session.last_response = self.response
        self.actual.session.traffic = [object(), object()]
        self.case = {'before_records': self.before, 'completed': 288,
            'events': [{'after': 288}], '_last_inspection': (self.response, 2)}

    def test_mechanism_first_cache_keeps_native_order_and_actual_objects(self):
        self.assertEqual(tuple(self.actual._records), ('mechanism', 'request', 'behavior'))
        self.assertIs(self.actual._records['mechanism'], self.mechanism)
        gate.unchanged_historical_records(self.actual, self.case)
        self.assertEqual(tuple(self.actual._records), ('mechanism', 'request', 'behavior'))
        self.assertEqual(len(self.actual.session.traffic), 2)

    def test_cache_insertion_order_does_not_replace_the_native_order_check(self):
        self.actual._records = dict(self.before)
        gate.unchanged_historical_records(self.actual, self.case)
        for names in (list(reversed(self.names)), list(self.names[:-1]), [*self.names, 'components']):
            self.response.result['order']['records'] = names
            with self.subTest(names=names), self.assertRaisesRegex(AssertionError, 'original record order'):
                gate.unchanged_historical_records(self.actual, self.case)

    def test_added_and_missing_cached_records_are_rejected(self):
        before = dict(self.actual._records)
        for name in self.names:
            self.actual._records = dict(before)
            del self.actual._records[name]
            with self.subTest(missing=name), self.assertRaisesRegex(AssertionError, 'stored or replaced'):
                gate.unchanged_historical_records(self.actual, self.case)
        self.actual._records = {**before, 'components': object()}
        with self.assertRaisesRegex(AssertionError, 'stored or replaced'):
            gate.unchanged_historical_records(self.actual, self.case)

    def test_equal_but_replaced_record_is_rejected(self):
        for name, retained in self.before:
            replacement = copy(retained)
            self.assertIsNot(replacement, retained)
            self.assertEqual(replacement, retained)
            self.actual._records[name] = replacement
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'stored or replaced'):
                gate.unchanged_historical_records(self.actual, self.case)
            self.actual._records[name] = retained

    def test_wrong_retained_record_census_is_rejected(self):
        for records in (self.before[:-1], tuple(reversed(self.before)), self.before + (self.before[-1],)):
            self.case['before_records'] = records
            with self.subTest(records=len(records)), self.assertRaisesRegex(AssertionError, 'stored or replaced'):
                gate.unchanged_historical_records(self.actual, self.case)

    def test_final_inspection_cannot_be_stale_copied_or_detached_from_failed_event(self):
        changes = (
            ('response', lambda: setattr(self.actual.session, 'last_response', copy(self.response))),
            ('traffic', lambda: self.actual.session.traffic.append(object())),
            ('operation', lambda: setattr(self.response, 'operation', 'inspect')),
            ('sequence', lambda: setattr(self.response, 'sequence', 287)),
            ('completed', lambda: self.case.update(completed=287)),
            ('event', lambda: self.case['events'][-1].update(after=287)),
        )
        for name, change in changes:
            self.actual.session.last_response = self.response
            self.actual.session.traffic = [object(), object()]
            self.response.operation, self.response.sequence = 'inspect-ordered-references', 288
            self.case['completed'], self.case['events'][-1]['after'] = 288, 288
            change()
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, 'actual final inspection'):
                gate.unchanged_historical_records(self.actual, self.case)
