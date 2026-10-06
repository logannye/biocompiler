"""Inert native artifact/accounting checks with explicit external identity.

No executable is extracted or executed here. Native suite outcomes remain hosted
observations whose exact identities, inventories, arguments and logs are checked.
"""
from pathlib import PurePosixPath
import hashlib
import json
import math
import stat


def require(value, message):
    if not value:
        raise AssertionError(message)


def decode(raw):
    def unique(items):
        value = {}
        for key, item in items:
            require(key not in value, 'Duplicate JSON key')
            value[key] = item
        return value
    def invalid(value):
        raise AssertionError('Nonfinite JSON value: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def digest(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def duration(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'Invalid duration')


def audit_bundle(archive, *, identity, runtime, expected_members, fixture_pins, dune_sha256,
                 expected_executables=151, expected_fixtures=23):
    require(type(expected_executables) is int and type(expected_fixtures) is int
            and (expected_executables, expected_fixtures) in {(151, 23), (158, 23)},
            'Unsupported native executable/fixture scope')
    names = archive.namelist()
    require(len(names) == len(set(names)) == expected_executables + expected_fixtures + 1
            and len(expected_members) == len(set(expected_members))
            and set(names) == set(expected_members) | {'manifest.json'}, 'Native bundle exact member census differs')
    require(sum(entry.file_size for entry in archive.infolist()) <= 2 * 1024**3, 'Nested native bundle exceeds prepared expansion bound')
    require(archive.getinfo('manifest.json').file_size < 1024 * 1024, 'Native manifest exceeds bound')
    document = decode(archive.read('manifest.json'))
    require(set(document) == {'schema', 'revision', 'run_id', 'run_attempt', 'system', 'machine', 'dune_sha256', 'files'}, 'Native manifest fields differ')
    require(document['schema'] == 'biocompiler.ci_native_bundle.v1' and all(document[k] == v for k, v in identity.items()), 'Native manifest identity differs')
    require((document['system'], document['machine']) == tuple(runtime), 'Native manifest platform differs')
    require(document['dune_sha256'] == dune_sha256 and set(document['files']) == set(expected_members), 'Native Dune/member authority differs')
    for name in expected_members:
        entry = archive.getinfo(name)
        require(not entry.is_dir() and not stat.S_ISLNK(entry.external_attr >> 16) and not entry.flag_bits & 1 and 0 < entry.file_size <= 128 * 1024**2, 'Unsafe native member')
        h = hashlib.sha256(); size = 0
        with archive.open(entry) as stream:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk); h.update(chunk)
        observed = {'sha256': h.hexdigest(), 'size': size}
        require(observed == document['files'][name], 'Native member bytes differ: ' + name)
        if name in fixture_pins:
            require(observed == fixture_pins[name], 'Native fixture differs from original source: ' + name)
    require(set(fixture_pins) <= set(expected_members) and len(fixture_pins) == expected_fixtures
            and len(expected_members) - len(fixture_pins) == expected_executables,
            'Native executable/fixture split differs')
    return document


def audit_suites(read, names, *, identity, plan, environment_paths, expected_count=149):
    require(type(expected_count) is int and expected_count in {149, 156}, 'Unsupported native suite scope')
    document = decode(read('native-suites/receipt.json'))
    require(set(document) == {'revision', 'run_id', 'run_attempt', 'tests', 'expected'} and all(document[k] == v for k, v in identity.items()), 'Native suite receipt identity/fields differ')
    expected = [row['name'] for row in plan]
    require(len(expected) == len(set(expected)) == expected_count and document['expected'] == expected
            and len(document['tests']) == expected_count, 'Native suite census differs')
    required_logs = {'native-suites/' + name + '.log' for name in expected}
    require({name for name in names if name.startswith('native-suites/')} == required_logs | {'native-suites/receipt.json'}, 'Native suite log census differs')
    roots = set()
    for original, observed in zip(plan, document['tests']):
        require(set(observed) == {'name', 'argv', 'returncode', 'duration_seconds', 'log'} and observed['name'] == original['name'], 'Native suite row fields/order differ')
        require(type(observed['returncode']) is int and observed['returncode'] == 0, 'Native suite failed')
        duration(observed['duration_seconds'])
        argv = observed['argv']; suffix = '/core/_build/default/test/' + original['name'] + '.exe'
        require(type(argv) is list and argv and type(argv[0]) is str and PurePosixPath(argv[0]).is_absolute() and argv[0].endswith(suffix), 'Native suite executable path differs')
        root = argv[0][:-len(suffix)]; require(root and root != '/', 'Invalid hosted checkout root'); roots.add(root)
        wanted = [root + suffix] + [root + '/' + environment_paths[name] for name in original['environment']]
        wanted += [root + '/core/_build/default/test/' + path for path in original.get('dependencies', [])]
        require(argv == wanted, 'Native suite original fixture arguments differ: ' + original['name'])
        require(observed['log'] == digest(read('native-suites/' + original['name'] + '.log')), 'Native suite log pin differs')
    require(len(roots) == 1, 'Mixed native suite checkout roots')
    return {'tests': len(expected), 'hosted_checkout_root': next(iter(roots)), 'receipt': digest(read('native-suites/receipt.json'))}


def audit_groups(read, names, *, identity, source_revision, runtime, plan, plan_sha256):
    document = decode(read('command-groups/receipt.json'))
    require(set(document) == {'schema', 'revision', 'run_id', 'run_attempt', 'source_revision', 'system', 'machine', 'plan_sha256', 'workers', 'groups'}, 'Direct-core receipt fields differ')
    require(document['schema'] == 'biocompiler.ci_core_groups_receipt.v1' and all(document[k] == v for k, v in identity.items()) and document['source_revision'] == source_revision, 'Direct-core identity differs')
    require((document['system'], document['machine']) == tuple(runtime) and document['plan_sha256'] == plan_sha256 and type(document['workers']) is int and document['workers'] == 2, 'Direct-core platform/plan/concurrency differs')
    require(len(plan) == len(document['groups']) == 67, 'Direct-core group census differs')
    require({name for name in names if name.startswith('command-groups/')} == {'command-groups/receipt.json'} | {'command-groups/' + row['id'] + '.log' for row in plan}, 'Direct-core log census differs')
    for original, observed in zip(plan, document['groups']):
        require(set(observed) == {'id', 'name', 'run_sha256', 'status', 'returncode', 'duration_seconds', 'log'}, 'Direct-core row fields differ')
        require(observed['id'] == original['id'] and observed['name'] == original['name'] and observed['run_sha256'] == hashlib.sha256(original['run'].encode()).hexdigest(), 'Direct-core original command/order differs')
        require(observed['status'] == 'pass' and type(observed['returncode']) is int and observed['returncode'] == 0, 'Direct-core group failed')
        duration(observed['duration_seconds'])
        filename = original['id'] + '.log'
        require(observed['log'] == {'path': filename, **digest(read('command-groups/' + filename))}, 'Direct-core log bytes differ')
    return {'groups': len(plan), 'receipt': digest(read('command-groups/receipt.json'))}
