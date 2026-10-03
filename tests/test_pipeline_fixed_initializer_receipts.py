"""Independent repaired-transport controls; no native compiler execution."""
from copy import deepcopy
import tempfile
import unittest

from tests import test_pipeline_fixed_registration_campaign as fixtures
from tests.test_pipeline_manager_campaign import reframe


def resequence(values):
    """Assign valid physical identities from a mutated well-nested transcript.

    Hashes and cumulative byte/node/work counters are repaired by reframe. This
    deliberately repairs the semantic mutant's enclosing protocol too: an
    invalid hash, old sequence, or impossible callback stack cannot reject it
    in place of the independent initializer proof.
    """
    sequence = event = 0
    commands, invocations = [], []
    for value in values:
        kind = value['kind']
        if kind in ('hello', 'command', 'close', 'continue'):
            value['sequence'] = sequence
            sequence += 1
            if kind == 'continue':
                value['invocation_id'] = invocations.pop()
            else:
                if kind != 'hello':
                    value['parent_invocation'] = invocations[-1] if invocations else None
                commands.append(value['sequence'])
        else:
            value['event_id'] = event
            event += 1
            if kind == 'invoke':
                value['invocation_id'] = value['event_id']
                value['command_sequence'] = commands[-1]
                value['parent_invocation'] = invocations[-1] if invocations else None
                invocations.append(value['invocation_id'])
            else:
                assert kind == 'reply'
                value['sequence'] = commands.pop()
    assert not commands and not invocations


def invocation_range(values, action, ordinal=0):
    start = [i for i, value in enumerate(values) if value.get('action') == action][ordinal]
    identity = values[start]['invocation_id']
    end = next(i for i in range(start+1, len(values))
        if values[i]['kind'] == 'continue' and values[i]['invocation_id'] == identity)
    return start, end+1


def registration_range(values, ordinal=0):
    start = [i for i, value in enumerate(values)
        if value.get('operation') == 'register'][ordinal]
    sequence = values[start]['sequence']
    end = next(i for i in range(start+1, len(values))
        if values[i]['kind'] == 'reply' and values[i]['sequence'] == sequence)
    return start, end+1


def replace_reference(value, old, new):
    if type(value) is dict:
        if value == old:
            value.clear(); value.update(new)
        else:
            for child in value.values():
                replace_reference(child, old, new)
    elif type(value) is list:
        for child in value:
            replace_reference(child, old, new)


class FixedInitializerSemanticReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.FixedInitializerReceiptTests.setUpClass()

    def rejected(self, mutate, diagnostic):
        helper = fixtures.FixedInitializerReceiptTests()
        with tempfile.TemporaryDirectory() as directory:
            receipt, frames, contracts, channel, application, _ = helper.fixture(directory, 3)
            helper.validate(helper.details(receipt, frames, directory, channel, application, 3), contracts)
            row = {'frames': frames}
            receipt['checks'] = [row]
            def change(values):
                mutate(values)
                resequence(values)
            reframe(receipt, row, change)
            # This assertion is deliberately outside the expected failure: the
            # whole malformed semantic witness still has valid exact framing.
            details = helper.details(receipt, row['frames'], directory, channel, application, 3)
            with self.assertRaisesRegex(AssertionError, diagnostic):
                helper.validate(details, contracts)

    def test_publication_is_exactly_once_and_precedes_native_registration(self):
        def missing(values):
            start, end = invocation_range(values, 'manager-created')
            del values[start:end]
        def duplicate(values):
            start, end = invocation_range(values, 'manager-created')
            values[end:end] = deepcopy(values[start:end])
        def late(values):
            start, end = invocation_range(values, 'manager-created')
            moved = values[start:end]; del values[start:end]
            _, destination = invocation_range(values, 'native-provider')
            values[destination:destination] = moved
        for mutate in (missing, duplicate, late):
            with self.subTest(mutation=mutate.__name__):
                self.rejected(mutate, 'omitted, repeated, or reordered publication')

    def test_every_hook_owns_exactly_one_real_registration(self):
        def missing(values):
            start, end = registration_range(values)
            del values[start:end]
        def duplicate(values):
            start, end = registration_range(values)
            values[end:end] = deepcopy(values[start:end])
        for mutate in (missing, duplicate):
            with self.subTest(mutation=mutate.__name__):
                self.rejected(mutate, 'exactly one actual register')

    def test_valid_nested_register_under_wrong_callback_is_rejected(self):
        def mutate(values):
            start, end = registration_range(values)
            moved = values[start:end]; del values[start:end]
            publication, _ = invocation_range(values, 'manager-created')
            values[publication+1:publication+1] = moved
        self.rejected(mutate, 'exactly one actual register')

    def test_extra_valid_manager_command_cannot_hide_inside_publication_or_hook(self):
        def extra(values, action):
            command = deepcopy(next(value for value in values if value.get('operation') == 'register'))
            command.update(operation='target', arguments={})
            reply = deepcopy(next(value for value in values if value['kind'] == 'reply' and value.get('closed') is False))
            target = next(value for value in values if value.get('action') == 'manager-created')['arguments']['target']
            reply['outcome'] = {'status': 'ok', 'value': deepcopy(target)}
            _, end = invocation_range(values, action)
            values[end-1:end-1] = [command, reply]
        for action, diagnostic in (('manager-created', 'Unclaimed or reordered command'),
                                   ('register-fixed', 'exactly one actual register')):
            with self.subTest(action=action):
                self.rejected(lambda values: extra(values, action), diagnostic)

    def test_real_primitive_moved_to_outer_command_cannot_keep_registration_authority(self):
        def mutate(values):
            start, end = invocation_range(values, 'callable')
            moved = values[start:end]; del values[start:end]
            target, _ = registration_range(values)
            values[target:target] = moved
        self.rejected(mutate, 'omitted, repeated, or reordered publication')

    def test_native_provider_tokens_and_physical_handles_cannot_alias(self):
        def token(values):
            providers = [value for value in values if value.get('action') == 'native-provider']
            providers[1]['arguments']['provider_id'] = providers[0]['arguments']['provider_id']
        def physical(values):
            providers = [invocation_range(values, 'native-provider', i) for i in (0, 1)]
            refs = [values[end-1]['outcome']['value'] for _, end in providers]
            replace_reference(values, deepcopy(refs[1]), deepcopy(refs[0]))
        self.rejected(token, 'wrong or repeated closure role')
        self.rejected(physical, 'rebound a host object')

    def test_native_provider_cannot_claim_preexisting_authored_target_handle(self):
        def mutate(values):
            _, end = invocation_range(values, 'native-provider')
            old = deepcopy(values[end-1]['outcome']['value'])
            initializer = next(value for value in values if value.get('operation') == 'initialize-components')
            replace_reference(values, old, deepcopy(initializer['arguments']['target_object']))
        self.rejected(mutate, 'source|authored|rebound')

    def test_obligation_projection_and_physical_source_edges_are_exact(self):
        def projection(values):
            hook = next(value for value in values
                if value.get('action') == 'register-fixed' and value['arguments']['obligation_objects'])
            tree = hook['arguments']['obligation_objects'][0]['tree']
            next(pair for pair in tree[1] if pair[0] == 'description')[1] = ['scalar', 'forged declaration']
        def stale_handle(values):
            commands = [value for value in values if value.get('operation') == 'register'
                and value['arguments']['obligation_objects']]
            commands[1]['arguments']['obligation_objects'][0] = deepcopy(commands[0]['arguments']['obligation_objects'][0])
        def provider_handle(values):
            command = next(value for value in values if value.get('operation') == 'register'
                and value['arguments']['obligation_objects'])
            command['arguments']['obligation_objects'][0] = deepcopy(command['arguments']['producer'])
        for mutate, diagnostic in ((projection, 'binding projection differs'),
                                    (stale_handle, 'rebound a host object'),
                                    (provider_handle, 'rebound a host object')):
            with self.subTest(mutation=mutate.__name__):
                self.rejected(mutate, diagnostic)

    def test_reused_native_obligation_identity_with_new_content_is_rejected(self):
        def mutate(values):
            hooks = [value for value in values if value.get('action') == 'register-fixed'
                and value['arguments']['obligation_objects']]
            hooks[1]['arguments']['obligation_objects'][0]['identity'] = hooks[0]['arguments']['obligation_objects'][0]['identity']
        self.rejected(mutate, 'identity|rebound|repeated')


if __name__ == '__main__':
    unittest.main()
