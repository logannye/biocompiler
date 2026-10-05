"""Reference graphs preserve identities, occurrences and unresolved matches."""
from dataclasses import replace
import json
import unittest

import biocompiler.policy as p
from biocompiler.policy import examples


def document():
    definition = p.SemanticDefinition('shared', '1', 'capability', 'Supplied interface only.')
    role = p.Role('shared', (definition.ref,))
    subject = p.Subject('target', 'cell', 'stable', executor=p.Ref('shared', 'Role'))
    return p.PolicyProgram('graph', p.SemanticBundle('definitions', '1', (definition,)), (role, subject))


class PolicyInspectionGraphTests(unittest.TestCase):
    def test_namespace_separation_and_every_reference_field_path(self):
        value = p.graph(document())
        nodes = {node['key']: node for node in value['nodes']}
        edges = {edge['path']: edge for edge in value['edges']}
        declaration = edges['/declarations/1/executor']
        definition = edges['/declarations/0/requires/0']
        self.assertNotEqual(declaration['target'], definition['target'])
        self.assertEqual(nodes[declaration['target']]['namespace'], 'declaration')
        self.assertEqual(nodes[definition['target']]['namespace'], 'definition')
        self.assertEqual(nodes[declaration['target']]['id'], nodes[definition['target']]['id'])
        self.assertEqual(definition['reference']['digest'], document().semantics.definitions[0].ref.digest)
        self.assertEqual(value['unmatched_reference_count'], 0)
        self.assertEqual(value['semantic_status'], 'unassessed')
        self.assertEqual(value['target_status'], 'unassessed')
        self.assertEqual(json.loads(json.dumps(value)), value)

    def test_missing_wrong_kind_and_stale_definition_pins_remain_visible(self):
        original = document()
        bad_role = replace(original.declarations[0], requires=(replace(original.semantics.definitions[0].ref, digest='0' * 64),))
        wrong = replace(original.declarations[1], executor=p.Ref('shared', 'Subject'))
        missing = replace(original.declarations[1], id='other', executor=p.Ref('absent', 'Role'))
        value = p.graph(replace(original, declarations=(bad_role, wrong, missing)))
        self.assertEqual([edge['match'] for edge in value['edges']], ['missing', 'kind_mismatch', 'missing'])
        self.assertEqual(value['unmatched_reference_count'], 3)
        self.assertEqual(len([node for node in value['nodes'] if node['origin'] == 'reference']), 3)
        duplicate_definitions = replace(original, semantics=replace(original.semantics,
            definitions=original.semantics.definitions * 2))
        duplicated = p.graph(duplicate_definitions)
        edge = next(edge for edge in duplicated['edges'] if edge['namespace'] == 'definition')
        self.assertEqual(edge['match'], 'ambiguous')
        target = next(node for node in duplicated['nodes'] if node['key'] == edge['target'])
        self.assertEqual(len(target['candidates']), 2)

    def test_duplicates_keep_occurrences_and_share_bounded_ambiguity_inventory(self):
        role = p.Role('duplicate', ())
        subjects = tuple(p.Subject(f'target{index}', 'cell', 'stable', executor=p.Ref('duplicate', 'Role')) for index in range(20))
        value = p.graph(p.PolicyProgram('ambiguous', p.SemanticBundle('defs', '1'), (role, role, *subjects)))
        candidates = [node for node in value['nodes'] if node['origin'] == 'declared' and node['id'] == 'duplicate']
        placeholders = [node for node in value['nodes'] if node['origin'] == 'reference']
        self.assertEqual(len(candidates), 2)
        self.assertNotEqual(candidates[0]['key'], candidates[1]['key'])
        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0]['candidates'], [node['key'] for node in candidates])
        self.assertEqual(len(value['edges']), 20)
        self.assertEqual({edge['target'] for edge in value['edges']}, {placeholders[0]['key']})
        self.assertEqual({edge['match'] for edge in value['edges']}, {'ambiguous'})

    def test_build_request_keeps_root_and_program_reference_sources_separate(self):
        request = examples.build_request()
        value = p.graph(request)
        edges = {edge['path']: edge for edge in value['edges']}
        binding = edges['/deployment/bindings/0/role']
        self.assertEqual(binding['source'], 'document:')
        self.assertTrue(binding['target'].startswith('declaration:/program/declarations/'))
        self.assertTrue(edges['/program/declarations/0/requires/0']['source'].startswith('declaration:'))
        for name in examples.NAMES:
            with self.subTest(name=name):
                self.assertEqual(p.graph(examples.build_request(name))['unmatched_reference_count'], 0)

    def test_inspection_and_html_expose_detached_inert_reference_graph(self):
        original = document()
        digest = p.document_digest(original)
        value = p.graph(original)
        self.assertEqual(p.inspect(original)['graph'], value)
        value['nodes'][1]['id'] = 'caller mutation'
        value['edges'].clear()
        self.assertEqual(p.document_digest(original), digest)
        self.assertEqual(p.graph(original)['reference_count'], 2)
        malicious = replace(original, declarations=(replace(original.declarations[0], id='<script>bad</script>'),
            replace(original.declarations[1], executor=p.Ref('<script>bad</script>', 'Role'))))
        html = malicious._repr_html_()
        self.assertIn('Declaration reference graph', html)
        self.assertIn('/declarations/1/executor', html)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<svg', html)

    def test_graph_uses_codec_bounds_and_rejects_malformed_declarations(self):
        with self.assertRaises(p.PolicySerializationError):
            p.graph(replace(document(), id='x' * (3 * 1024 * 1024)))
        malformed = replace(document(), declarations=(p.Ref('wrong', 'Role'),))
        with self.assertRaises(p.PolicySerializationError):
            p.graph(malformed)
        self.assertIsNone(p.inspect(malformed)['graph'])


if __name__ == '__main__':
    unittest.main()
