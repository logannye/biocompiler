"""Actual started Python-child cancellation using the installed Core transport.

This fixture proves process lifecycle mechanics, not native operation semantics.
The selected Core binaries are exercised separately by installed smoke/campaigns.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def started_cancellation(directory):
    from biocompiler import core_client
    directory = Path(directory)
    require(directory.is_absolute() and not directory.exists(), 'Cancellation fixture needs a fresh absolute directory')
    directory.mkdir(mode=0o700)
    marker, executable = directory / 'started.json', directory / 'child'
    source = ('#!' + sys.executable + '\nimport json, os, pathlib, signal\n'
        + 'path = pathlib.Path(' + repr(str(marker)) + ')\n'
        + 'with path.open("x") as output:\n'
        + ' output.write(json.dumps({"pid":os.getpid(),"parent":os.getppid(),"group":os.getpgrp()}))\n'
        + 'while True: signal.pause()\n').encode()
    executable.write_bytes(source); executable.chmod(0o700)
    calls, observed = 0, None
    def cancelled():
        nonlocal calls, observed
        calls += 1
        if not marker.exists():
            return False
        # The child closes this small marker before entering its wait. A partly
        # flushed file means keep waiting; no process result is accepted from it.
        raw = marker.read_bytes()
        require(len(raw) <= 1024, 'Cancellation child marker exceeds bound')
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            return False
        require(type(value) is dict and set(value) == {'pid', 'parent', 'group'}
            and all(type(item) is int for item in value.values()) and value['pid'] > 0
            and value['parent'] == os.getpid() and value['group'] == value['pid'],
            'Cancellation marker is not this actual isolated child')
        observed = value
        return True
    started = time.monotonic()
    try:
        core_client._exchange(executable, b'{}', 5.0, cancelled)
    except core_client.CoreCancelled as error:
        require(str(error) == 'Core operation cancelled', 'Only pre-spawn cancellation was exercised')
    else:
        raise AssertionError('Installed transport failed to cancel its actual child')
    require(observed is not None and calls >= 2, 'Cancellation did not observe an actual started process')
    try:
        os.waitpid(observed['pid'], os.WNOHANG)
    except ChildProcessError:
        reaped = True
    else:
        reaped = False
    require(reaped, 'Cancelled child was not reaped by the transport')
    return {'schema_version': 'biocompiler.prebuilt_process_probe.v1', 'native_execution': False,
        'kind': 'installed_transport_python_child_started_cancellation', 'pid': observed['pid'],
        'parent': observed['parent'], 'group': observed['group'], 'reaped': reaped, 'attempts': 1,
        'predicate_calls': calls, 'elapsed_seconds': time.monotonic() - started,
        'fixture_sha256': hashlib.sha256(source).hexdigest(),
        'transport_sha256': hashlib.sha256(Path(core_client.__file__).read_bytes()).hexdigest(),
        'python': sys.version, 'transport_path': core_client.__file__}
