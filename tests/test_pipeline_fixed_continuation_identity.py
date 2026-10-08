"""Per-call identity controls; no original campaigns or native execution."""
from collections import defaultdict
from copy import deepcopy
import inspect
import unittest

from tools import capture_pipeline_fixed_continuation_semantics as observations
from tools import check_pipeline_fixed_continuation_install as campaign


class PipelineFixedContinuationIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()
        cls.value = observations.read_frozen(cls.corpus, campaign)

    def rehash(self, value):
        value['inventory_fingerprint'] = campaign.sha(campaign.canonical({key: item
            for key, item in value.items() if key != 'inventory_fingerprint'}))
        return value

    def test_every_occurrence_has_original_context_and_independent_graph(self):
        graphs = observations.validate(self.value, self.corpus, campaign)
        self.assertEqual(list(graphs), [row['id'] for row in self.corpus.cases])
        self.assertEqual(len(graphs), 39)
        self.assertEqual(self.value['coverage']['contexts'], 17)
        self.assertEqual(self.value['coverage']['original_methods'], 13)

    def test_driver_identity_uses_identical_source_text_across_python_minors(self):
        bodies = {name: inspect.getsource(getattr(campaign, name)) for name in (
            'load_body_modules', 'run_original_bodies', 'public_graph', 'observed_public_graph')}
        expected = campaign.sha(campaign.canonical({'methods': campaign.METHODS, 'bodies': bodies}))
        self.assertEqual(observations.driver_identity(campaign), expected)

    def test_equal_serialized_authorities_retain_distinct_source_identity(self):
        by_authority = defaultdict(set)
        for row in self.value['occurrences']:
            by_authority[row['authority']].add(row['graph'])
        variants = [pins for pins in by_authority.values() if len(pins) > 1]
        self.assertTrue(variants, 'Deserialized calls borrowed an authored source identity graph')
        selected = next(case for case in self.corpus.build['cases'] if case['id'] == 'selected_temporal')
        graphs = [self.value['graphs'][pin] for pin in by_authority[selected['authority_sha256']]]
        aliases = set()
        for graph in graphs:
            roots = dict(graph['source_origins'])
            aliases.add(roots['constant:BOOLEAN'] == roots['request:domain.inputs[0].observable.dtype'])
        self.assertEqual(aliases, {True, False})

    def test_six_frozen_authored_graphs_remain_exact(self):
        for case in self.corpus.build['cases']:
            original = campaign.public_graph(case)
            found = [row for row in self.value['occurrences'] if row['authority'] == case['authority_sha256']]
            self.assertTrue(any(self.value['graphs'][row['graph']] == original for row in found), case['id'])

    def test_equal_authority_does_not_allow_borrowing_another_occurrence_graph(self):
        pair = next((left, right) for left in self.value['occurrences'] for right in self.value['occurrences']
            if left['authority'] == right['authority'] and left['graph'] != right['graph'])
        left, right = (self.value['graphs'][row['graph']] for row in pair)
        with self.assertRaisesRegex(AssertionError, 'physical identities differ'):
            campaign.equal_public_graph(left, right)

    def test_missing_reordered_and_reassigned_occurrences_are_rejected(self):
        for change in ('missing', 'reordered', 'context', 'index', 'authority'):
            with self.subTest(change=change):
                value = deepcopy(self.value)
                rows = value['occurrences']
                if change == 'missing':
                    rows.pop()
                elif change == 'reordered':
                    rows[0], rows[1] = rows[1], rows[0]
                elif change == 'context':
                    rows[0]['context'] += ':forged'
                elif change == 'index':
                    rows[0]['call_index'] += 1
                else:
                    rows[0]['authority'] = '0' * 64
                with self.assertRaisesRegex(AssertionError, 'census|occurrence identity/order'):
                    observations.validate(self.rehash(value), self.corpus, campaign)

    def test_graph_bytes_and_observer_cannot_change_under_rehashed_inventory(self):
        for change in ('graph', 'observer', 'driver'):
            with self.subTest(change=change):
                value = deepcopy(self.value)
                if change == 'graph':
                    pin = value['occurrences'][0]['graph']
                    value['graphs'][pin]['source_origins'][0][0] += ':forged'
                elif change == 'observer':
                    value['source_files'][observations.SOURCE] = '0' * 64
                else:
                    value['driver_body_sha256'] = '0' * 64
                with self.assertRaisesRegex(AssertionError, 'graph content|observer source|driver changed'):
                    observations.validate(self.rehash(value), self.corpus, campaign)


if __name__ == '__main__':
    unittest.main()
