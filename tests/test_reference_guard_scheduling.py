"""Exact guarded I/O call sites under finite schedules; no native execution."""
from copy import deepcopy
import sys
import time
from types import SimpleNamespace, FunctionType
import unittest
from unittest.mock import patch

from biocompiler import core_pipeline_callback_session as transport
from tools import reference_execution_guard as guard
from tools import check_pipeline_reference_install as campaign


class Schedule:
    def __init__(self, chunks, idle, stderr):
        self.chunks, self.idle, self.stderr_chunks = list(chunks), idle, list(stderr)
        self.written, self.iterations, self.sent = bytearray(), 0, False
        self.stdin = SimpleNamespace(fd=101, fileobj=object(), data='stdin')
        self.stdout = SimpleNamespace(fd=102, fileobj=object(), data='stdout')
        self.stderr = SimpleNamespace(fd=103, fileobj=object(), data='stderr')

    def register(self, *args): pass
    def unregister(self, pipe): pass

    def select(self, timeout):
        if timeout == 0:
            return [(self.stderr, 0)] if self.stderr_chunks else []
        self.iterations += 1
        if self.iterations > 12: raise AssertionError('Finite selector bound exceeded')
        if not self.sent:
            self.sent = True
            return [(self.stdin, 0), (self.stdout, 0)]
        if self.idle:
            self.idle -= 1
            return []
        if not self.chunks: raise AssertionError('Finite response schedule exhausted')
        return [(self.stdout, 0)]

    def read(self, fd, maximum):
        assert maximum == 65536
        if fd == 103: return self.stderr_chunks.pop(0)
        assert fd == 102
        return self.chunks.pop(0)

    def write(self, fd, raw):
        assert fd == 101
        self.written.extend(raw)
        return len(raw)


class ReferenceGuardSchedulingTests(unittest.TestCase):
    BODY = b'{"sequence":0}'
    REPLY = b'{"kind":"reply","sequence":0,"status":"return"}'
    PACKET = f'{len(REPLY):08x}\n'.encode() + REPLY

    def exchange(self, chunks=None, *, idle=0, stderr=(), extra_checks=False, foreign=False):
        schedule = Schedule(chunks or [self.PACKET], idle, stderr)
        session = object.__new__(transport.CorePipelineCallbackSession)
        session._selector = schedule
        session._process = SimpleNamespace(stdin=object(), poll=lambda: None)
        session._eof, session._stderr, session._commands = set(), bytearray(), []
        session._limits = dict(transport._DEFAULTS)
        session._input_bytes = session._output_bytes = session._frame_count = session._node_count = 0
        session._sent, session._traffic, session._next_event = {}, [], 0
        with patch.object(transport.subprocess, 'Popen', side_effect=AssertionError('No subprocess allowed')), \
                patch.object(transport.os, 'read', schedule.read), patch.object(transport.os, 'write', schedule.write):
            with guard.execution() as execution:
                # Scope the actual transport without pretending this finite
                # fixture is a complete manager/native acceptance receipt.
                frame = sys._getframe()
                execution.active[id(frame)] = frame
                try:
                    if extra_checks:
                        transport._require(True, 'outside reviewed scheduling sites')
                        session._check_time(time.monotonic() + 1)
                    function = transport.CorePipelineCallbackSession._exchange
                    if foreign == 'caller':
                        function = FunctionType(function.__code__, dict(function.__globals__), function.__name__)
                    original_require = transport._require
                    require_function = (FunctionType(original_require.__code__, dict(original_require.__globals__),
                        original_require.__name__) if foreign == 'callee' else original_require)
                    with patch.object(transport, '_require', require_function):
                        result = function(session, self.BODY, time.monotonic() + 1)
                finally:
                    execution.active.pop(id(frame), None)
            evidence = execution.evidence()
        self.assertEqual(result, self.REPLY)
        self.assertFalse(schedule.chunks or schedule.stderr_chunks)
        complete = {'traffic': [(row.direction, row.index, row.frame) for row in session.traffic],
            'written': bytes(schedule.written), 'result': result, 'stderr': bytes(session._stderr),
            'eof': session._eof, 'input_bytes': session._input_bytes, 'output_bytes': session._output_bytes,
            'frame_count': session._frame_count, 'node_count': session._node_count}
        return evidence, complete

    def project(self, evidence):
        return campaign.guarded_projection(evidence, {})

    def test_identical_complete_frames_with_chunk_and_readiness_variance(self):
        baseline, complete = self.exchange()
        unchanged = deepcopy(baseline)
        expected = {'exchange-deadline': (1, 3, 5), 'exchange-read': (1, 3, 3),
                    'exchange-aggregate': (1, 3, 3), 'exchange-trailing': (1, 2, 2)}
        variants = [baseline]
        for idle in (0, 2):
            changed, actual = self.exchange([self.PACKET[:4], self.PACKET[4:15], self.PACKET[15:]], idle=idle)
            self.assertEqual(actual, complete)
            self.assertNotEqual(changed['calls'], baseline['calls'])
            self.assertEqual(self.project(changed), self.project(baseline))
            variants.append(changed)
        for name, counts in expected.items():
            self.assertEqual(tuple(next(row['count'] for row in value['scheduling']['counts']
                if row['site'] == name) for value in variants), counts)
        self.assertEqual(baseline, unchanged)

    def test_quiet_stderr_chunking_has_only_its_proven_read_site(self):
        baseline, complete = self.exchange(stderr=(b'notes',))
        changed, actual = self.exchange(stderr=(b'no', b'tes'))
        self.assertEqual(actual, complete)
        self.assertEqual(self.project(changed), self.project(baseline))
        counts = lambda value: {row['site']: row['count'] for row in value['scheduling']['counts']}
        self.assertEqual(counts(baseline)['quiet-read'], 1)
        self.assertEqual(counts(changed)['quiet-read'], 2)
        self.assertTrue(all(site['caller']['qualname'] != 'CorePipelineCallbackSession._finish'
                            for site in baseline['scheduling']['sites']))

    def test_non_scheduling_require_and_deadline_calls_remain_exact(self):
        baseline, complete = self.exchange()
        extra, actual = self.exchange(extra_checks=True)
        self.assertEqual(actual, complete)
        self.assertEqual(extra['scheduling'], baseline['scheduling'])
        self.assertNotEqual(self.project(extra), self.project(baseline))
        for name in ('_require', 'CorePipelineCallbackSession._check_time'):
            altered = deepcopy(baseline)
            row = next(row for row in altered['calls'] if row['frame']['module'] == guard.SCHEDULING_MODULE
                       and row['frame']['qualname'] == name)
            row['count'] += 1
            self.assertNotEqual(self.project(altered), self.project(baseline))

    def test_unknown_stale_or_altered_callsite_authority_is_rejected(self):
        baseline, _ = self.exchange()
        mutations = (
            lambda value: value.update(schema='biocompiler.reference_execution_guard.v1'),
            lambda value: value['scheduling']['sites'].pop(),
            lambda value: value['scheduling']['sites'][0]['source'].update(sha256='0' * 64),
            lambda value: value['scheduling']['sites'][0]['caller'].update(code_sha256='0' * 64),
            lambda value: value['scheduling']['sites'][0]['callee'].update(code_sha256='0' * 64),
            lambda value: value['scheduling']['sites'][0]['caller'].update(qualname='CorePipelineCallbackSession._continuation'),
            lambda value: value['scheduling']['sites'][0]['callee'].update(category='public-prefix'),
            lambda value: value['scheduling']['sites'][0].update(position=[320, 320, 0, 1]),
            lambda value: value['scheduling']['sites'][0].update(instruction=0),
            lambda value: value['scheduling']['counts'][0].update(site='semantic-check'),
        )
        for mutate in mutations:
            altered = deepcopy(baseline); mutate(altered)
            with self.subTest(mutation=repr(mutate)), self.assertRaises(AssertionError): self.project(altered)

    def test_scheduling_counts_are_positive_unique_and_bounded_by_raw_census(self):
        baseline, _ = self.exchange()
        for count in (True, 0, -1, '1', 10**9):
            altered = deepcopy(baseline); altered['scheduling']['counts'][0]['count'] = count
            with self.subTest(count=count), self.assertRaises(AssertionError): self.project(altered)
        altered = deepcopy(baseline); altered['scheduling']['counts'].append(altered['scheduling']['counts'][0])
        with self.assertRaises(AssertionError): self.project(altered)
        altered = deepcopy(baseline)
        altered['calls'] = [row for row in altered['calls']
            if row['frame']['qualname'] != 'CorePipelineCallbackSession._exchange']
        with self.assertRaisesRegex(AssertionError, 'source-bound caller'): self.project(altered)
        altered = deepcopy(baseline)
        row = next(row for row in altered['calls'] if row['frame']['module'] == guard.SCHEDULING_MODULE
                   and row['frame']['qualname'] == '_require')
        row['count'] = 1
        with self.assertRaisesRegex(AssertionError, 'exceeds'): self.project(altered)
        # A fabricated but individually bounded occurrence changes the exact
        # residual and therefore still fails the cross-execution equality.
        altered = deepcopy(baseline)
        altered['scheduling']['counts'][0]['count'] += 1
        self.assertNotEqual(self.project(altered), self.project(baseline))

    def test_code_identity_and_unrelated_guard_fields_remain_exact(self):
        baseline, _ = self.exchange()
        for field in ('commands', 'routes', 'delegation'):
            altered = deepcopy(baseline); altered[field].append({'changed': True})
            self.assertNotEqual(self.project(altered), self.project(baseline))
        altered = deepcopy(baseline); altered['inspection']['count'] += 1
        self.assertNotEqual(self.project(altered), self.project(baseline))
        altered = deepcopy(baseline); altered['calls'][0]['frame']['code_sha256'] = '0' * 64
        with self.assertRaises(AssertionError):
            guard.validate(altered, [], SimpleNamespace(raw=lambda key: b''))
        for foreign in ('caller', 'callee'):
            with self.subTest(foreign=foreign), self.assertRaisesRegex(AssertionError, 'foreign globals'):
                self.exchange(foreign=foreign)


if __name__ == '__main__':
    unittest.main()
