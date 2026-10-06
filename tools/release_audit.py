"""Versioned inert complete-release audit with explicit source and API authority.

No GitHub access, native execution, packaging, test discovery or receipt producer
runs here. The caller supplies independently authenticated exact API records and
archive bytes. A source/run plan is inert data; no per-run Python is generated.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import tarfile
import zipfile

TOOL_ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from release_audit_artifacts import ArtifactStore, sha, decode, read_json
# Load the committed tool closure before adding the audited source checkout to
# sys.path. A later source release can itself contain an older audit tool version.
import release_audit_identity
import release_audit_native
import release_audit_plan
import release_audit_policy
import release_audit_units

BOOTSTRAP_STEP_NAME = 'Seed the exact hosted macOS ARM64 Python runtime'

def require(value, message):
    if not value:
        raise AssertionError(message)

def same(left, right):
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)

def inert(event, args):
    if event.startswith('subprocess.') or event.startswith('socket.') or event in ('os.system', 'os.exec', 'os.posix_spawn'):
        raise RuntimeError('Final artifact audit forbids subprocess/network: ' + event)

def validate_legacy_comparison(record, *, name, plan, identity):
    expected_schema = plan['legacy_comparison_schemas'][name]['schema_version']
    require(record['schema_version'] == expected_schema, 'Legacy hosted comparator schema differs: ' + name)
    require(record['status'] == 'success' and record['revision'] == identity['revision']
            and record['source_revision'] == identity['head_revision'] and record['run_id'] == identity['run_id'],
            'Legacy hosted comparator receipt is stale or unsuccessful: ' + name)

def bootstrap_step_conditions(physical_jobs):
    """Evaluate only the reviewed bootstrap condition in its exact physical slots."""
    fixed = {'ocaml-build', 'ocaml-native-tests', 'ocaml-core'}
    selected = {'architecture-sdk', 'installed-campaigns',
                'realization-conformance', 'policy-prebuilt-installed'}
    expected_counts = {'ocaml-build': 2, 'ocaml-native-tests': 2, 'ocaml-core': 2,
                       'architecture-sdk': 4, 'installed-campaigns': 20,
                       'realization-conformance': 4, 'policy-prebuilt-installed': 4}
    seed_name = BOOTSTRAP_STEP_NAME
    counts = Counter(); result = {}
    for spec in physical_jobs:
        seeds = [row for row in spec['steps'] if row['name'] == seed_name]
        if spec['job'] not in fixed | selected:
            require(not seeds, 'Bootstrap declared outside reviewed runtime slots')
            continue
        counts[spec['job']] += 1
        matrix = spec['matrix']
        keys = {'runner', 'platform'} | ({'python-version'} if spec['job'] in selected else set())
        if spec['job'] == 'installed-campaigns':
            keys.add('group')
        if spec['job'] == 'policy-prebuilt-installed':
            keys.add('wheel-tag')
        require(type(matrix) is dict and set(matrix) == keys, 'Bootstrap matrix fields differ')
        runners = {'linux-x86_64': 'ubuntu-24.04', 'macos-arm64': 'macos-14'}
        require(matrix['platform'] in runners and matrix['runner'] == spec['runner']
                == runners[matrix['platform']], 'Bootstrap runner/platform differs')
        minor = matrix.get('python-version', '3.11')
        require(minor in {'3.11', '3.14'}, 'Bootstrap selected Python profile differs')
        components = [matrix['runner'], matrix['platform']]
        if spec['job'] in selected:
            components.append(minor)
        if spec['job'] == 'installed-campaigns':
            require(matrix['group'] in {'protocol', 'manager', 'fixed', 'workflow', 'synthetic'},
                    'Bootstrap installed campaign group differs')
            components.append(matrix['group'])
        if spec['job'] == 'policy-prebuilt-installed':
            wheels = {'linux-x86_64': 'manylinux_2_39_x86_64', 'macos-arm64': 'macosx_14_0_arm64'}
            require(matrix['wheel-tag'] == wheels[matrix['platform']], 'Bootstrap wheel platform differs')
            components.append(matrix['wheel-tag'])
        require(spec['name'] == spec['job'] + ' (' + ', '.join(components) + ')'
                and spec['name'] not in result, 'Bootstrap physical slot identity differs')
        selected_version = ("fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.11']" if spec['job'] in fixed
                            else 'fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version]')
        condition = ("${{ runner.environment == 'github-hosted' && runner.os == 'macOS' "
                     "&& runner.arch == 'ARM64' && " + selected_version + " == '3.11.15' }}")
        expected = {'if': condition, 'name': seed_name, 'uses': None, 'yaml_ordinal': 2}
        require(same(seeds, [expected]) and len(spec['steps']) >= 3
                and same(spec['steps'][:3], [
                    {'if': None, 'name': None, 'uses': 'actions/checkout@v4', 'yaml_ordinal': 1},
                    expected,
                    {'if': None, 'name': None, 'uses': 'actions/setup-python@v5', 'yaml_ordinal': 3}]),
                'Bootstrap condition or checkout/setup ordering differs')
        # The whole workflow pins these minor-to-patch mappings. Runner labels
        # are independently required from API jobs below; source/runtime checks
        # separately bind every native and installed platform in the final audit.
        patch = {'3.11': '3.11.15', '3.14': '3.14.6'}[minor]
        result[spec['name']] = (condition, matrix['platform'] == 'macos-arm64' and patch == '3.11.15')
    require(counts == expected_counts and len(result) == 38
            and sum(value for _, value in result.values()) == 11,
            'Complete bootstrap runtime census differs')
    return result

def validate_jobs(document, run, plan):
    jobs = document['jobs']; expected = {row['name']: row for row in plan['physical_jobs']}
    bootstrap = bootstrap_step_conditions(plan['physical_jobs'])
    require(document['total_count'] == len(jobs) == len(expected) == 74 and len({row['id'] for row in jobs}) == 74, 'Incomplete physical job census')
    require(Counter(row['name'] for row in jobs) == Counter(expected.keys()), 'Physical matrix job census differs')
    allowed_skips = []
    for job in jobs:
        spec = expected[job['name']]
        require(job['run_id'] == run['id'] and job['run_attempt'] == 1 and job['head_sha'] == run['head_sha'] and job['status'] == 'completed' and job['conclusion'] == 'success', 'Incomplete, foreign or failed job: ' + job['name'])
        require(job['labels'] == [spec['runner']], 'Unexpected hosted runner label')
        steps = job['steps']; by_number = {row['number']: row for row in steps}
        require(steps and len(by_number) == len(steps) and all(type(n) is int and n > 0 for n in by_number), 'Malformed API step census')
        observed_seeds = [step['number'] for step in steps if step['name'] == BOOTSTRAP_STEP_NAME]
        require(observed_seeds == ([3] if job['name'] in bootstrap else []),
                'Observed bootstrap step census differs: ' + job['name'])
        for declared in spec['steps']:
            number = declared['yaml_ordinal'] + 1
            require(number in by_number, 'Authored workflow step omitted from API: ' + job['name'])
            actual = by_number[number]
            if declared['name'] is not None:
                require(actual['name'] == declared['name'], 'Authored step number/name differs: ' + job['name'])
            if declared['if'] == 'failure()':
                require(actual['conclusion'] == 'skipped', 'Failure-only upload executed in an otherwise successful accepted job')
            if job['name'] in bootstrap and declared['yaml_ordinal'] == 2:
                _, applies = bootstrap[job['name']]
                require(actual['conclusion'] == ('success' if applies else 'skipped'),
                        'Bootstrap step differs from evaluated runtime condition: ' + job['name'])
        for index, step in enumerate(steps):
            require(step['status'] == 'completed', 'Incomplete hosted step')
            if step['conclusion'] == 'success':
                continue
            matching = [row for row in spec['steps'] if row['yaml_ordinal'] + 1 == step['number']]
            if job['name'] in bootstrap and step['number'] == 3:
                condition, applies = bootstrap[job['name']]
                require(not applies and step['conclusion'] == 'skipped' and len(matching) == 1
                        and matching[0]['if'] == condition and matching[0]['name'] == step['name']
                        and all(row['conclusion'] == 'success' for row in steps[:index]),
                        'Inapplicable bootstrap step was not skipped exactly')
                allowed_skips.append({'job': job['name'], 'step': step['name'], 'number': step['number'],
                                      'condition': condition, 'value': False})
                continue
            require(spec['job'] == 'integration-examples' and len(matching) == 1 and matching[0]['if'] == 'failure()' and matching[0]['uses'] == 'actions/upload-artifact@v4' and matching[0]['name'] == step['name'] == 'Retain reference build failure evidence' and step['number'] == 33 and step['conclusion'] == 'skipped' and all(row['conclusion'] == 'success' for row in steps[:index]), 'Failed/skipped validation step: ' + job['name'] + '/' + step['name'])
            allowed_skips.append({'job': job['name'], 'step': step['name'], 'number': step['number'], 'condition': 'failure()', 'value': False})
    return allowed_skips

def audit_source_tar(path, *, source_archive_files, tested_revision):
    with zipfile.ZipFile(path) as companion:
        entry = companion.getinfo('biocompiler/source.tar')
        require(0 < entry.file_size <= 256 * 1024**2, 'Source tar exceeds reviewed bound')
        with companion.open(entry) as stream:
            with tarfile.open(fileobj=stream, mode='r|') as archive:
                found = {}; directories = set()
                for member in archive:
                    require(member.name not in found and member.name not in directories and not member.name.startswith('/') and '..' not in Path(member.name).parts and not member.issym() and not member.islnk(), 'Unsafe or repeated source tar member')
                    if member.isdir():
                        require(member.mode == 0o775, 'Source tar directory mode differs from git archive recipe')
                        directories.add(member.name.rstrip('/')); continue
                    require(member.isfile() and member.name in source_archive_files, 'Unreviewed source tar file')
                    expected = source_archive_files[member.name]
                    require(member.size == expected['size'] and member.mode == expected['mode'], 'Source archive file mode/size differs')
                    source = archive.extractfile(member); require(source is not None, 'Source file missing')
                    found[member.name] = hashlib.file_digest(source, 'sha256').hexdigest()
                require(archive.pax_headers == {'comment': tested_revision}, 'Source archive is not stamped with tested C')
    require(found == {name: row['sha256'] for name, row in source_archive_files.items()}, 'Source tar does not contain exact current C-tree source files')
    expected_directories = {parent.as_posix() for name in source_archive_files for parent in Path(name).parents if parent.as_posix() != '.'}
    require(directories == expected_directories, 'Source tar directory census differs')
    return {'files': len(found), 'directories': len(directories), 'tested_revision': tested_revision}

def audit_policy_and_prebuilt(store, output, plan, identity):
    import check_architecture_routing_reproducibility as architecture
    import check_policy_material_prebuilt as prebuilt
    import check_prebuilt_core_release as release_check
    import check_prebuilt_matrix as original_matrix
    from release_audit_policy import audit_source, audit_operational, audit_implementation, audit_material, audit_consumer
    platforms = ('linux-x86_64', 'macos-arm64'); minors = ('3.11', '3.14')
    core_root = output / 'core'; directories = {}
    for target in platforms:
        store.extract('core-' + target, core_root / target)
        for minor in minors:
            store.extract('architecture-sdk-' + target + '-py' + minor, core_root / target, allow_identical_existing=True)
        directories['prebuilt-' + target] = store.extract('prebuilt-' + target, output / 'payloads' / ('prebuilt-' + target))
    for name in ['policy-prebuilt-sdk', 'prebuilt-wheelhouse']:
        directories[name] = store.extract(name, output / 'payloads' / name)
    comparison = 'architecture-core-reproducibility'
    observed = architecture.compare(core_root, revision=identity['revision'], source_revision=identity['head_revision'], run_id=identity['run_id'])
    require(same(observed, store.json(comparison, 'receipt.json')), 'Architecture comparison differs')
    fixture_root = ROOT / 'core/test/data'
    def paths(layer):
        return [core_root / target / ('policy-' + layer + '-' + minor + '.json') for target in platforms for minor in minors]
    source = audit_source(paths('core'), fixture=fixture_root / 'policy_documents_v01.json', native_artifacts=core_root, audited_identity=identity)
    hosted = store.json(comparison, 'policy-receipt.json')
    require(len(source['variants']) == len(hosted['variants']) == 4, 'Source comparison variants differ')
    for local, saved in zip(source['variants'], hosted['variants']):
        relative = Path(local['receipt_path']).relative_to(core_root).as_posix()
        require(Path(saved['receipt_path']).is_absolute() and saved['receipt_path'].endswith('/artifacts/core/' + relative), 'Hosted source receipt provenance differs')
        local['receipt_path'] = saved['receipt_path']
    require(same(source, hosted), 'Source comparison differs')
    for layer, checker, fixture in [('operational', audit_operational, 'policy_operational_v01.json'), ('implementation', audit_implementation, 'policy_implementation_request_v01.json'), ('material', audit_material, 'policy_material_request_v01.json')]:
        rebuilt = checker(paths(layer), core_root, fixture_root / fixture, audited_identity=identity)
        require(same(rebuilt, store.json(comparison, 'policy-' + layer + '-receipt.json')), 'Policy comparison differs: ' + layer)
    rebuilt = audit_consumer(paths('consumer'), paths('material'), core_root, fixture_root / 'policy_material_request_v01.json', audited_identity=identity)
    require(same(rebuilt, store.json(comparison, 'policy-consumer-receipt.json')), 'Verify-only consumer comparison differs')
    sdk_root = directories['policy-prebuilt-sdk']; candidate_path = sdk_root / 'candidate.json'
    sdk = sdk_root / ('biocompiler-' + prebuilt.build.VERSION + '-py3-none-any.whl')
    candidate, sdk_entries, sdk_stamp = prebuilt.candidate_authority(candidate_path, sdk, identity)
    native_data = {}; source_archives = {}
    for target in platforms:
        directory = directories['prebuilt-' + target]
        data = prebuilt.platform_authority(directory, directory / 'material-authority.json', candidate, identity)
        require(data['target'] == target, 'Wrong native wheel target')
        native_data[target] = data
        for role in ('biocompiler-core', 'biocompiler-verify'):
            require(data['entries']['biocompiler_core/bin/' + role][0] == (core_root / target / role).read_bytes(), 'Wheel and published executable bytes differ')
        source_archives[target] = audit_source_tar(directory / candidate['material_companions'][target]['filename'], source_archive_files=plan['source_archive_files'], tested_revision=identity['revision'])
    slots = []; producers = []; consumers = []
    for target in platforms:
        for minor in minors:
            name = 'policy-prebuilt-' + target + '-py' + minor
            directory = store.extract(name, output / 'payloads' / name)
            slot, _ = prebuilt.verify_slot(directory, identity, candidate_path, sdk, sdk_entries, sdk_stamp, native_data, fixture_root / 'policy_material_request_v01.json')
            require(slot == (*prebuilt.build.TARGETS[target][:2], minor), 'Wrong supplied-wheel installed slot')
            slots.append((slot, directory, target)); producers.append(directory / 'evidence/material.json'); consumers.append(directory / 'evidence/consumer.json')
    material = audit_material(producers, core_root, fixture_root / 'policy_material_request_v01.json', audited_identity=identity)
    offline = audit_consumer(consumers, producers, core_root, fixture_root / 'policy_material_request_v01.json', audited_identity=identity)
    owned = {'schema_version': prebuilt.SCHEMA, 'status': 'pass', **identity, 'source_pins': prebuilt.source_pins(), 'fixture': prebuilt.pin(fixture_root / 'policy_material_request_v01.json'),
             'slots': [{'slot': list(slot), 'receipt': prebuilt.pin(directory / 'prebuilt.json'), 'run_attempt': '1', 'upstream_attempts': {'sdk': sdk_stamp['producer_run_attempt'], 'native': native_data[target]['stamp']['producer_run_attempt']}} for slot, directory, target in sorted(slots)],
             'material': material, 'consumer': offline, 'claim': 'supplied_prebuilt_material_profile_only', 'default_cutover': 'unassessed'}
    require(same(owned, store.json('policy-prebuilt-comparison', 'prebuilt-comparison.json')), 'Supplied-wheel complete comparison differs')
    # Original full release has its own independently generated SDK/candidate.
    original_root = directories['prebuilt-wheelhouse']; original_candidate_path = original_root / 'candidate.json'
    original_candidate = read_json(original_candidate_path); original_sdk = original_root / sdk.name
    source_files = release_check.source_package(ROOT)
    release_check.validate_sdk(release_check.read_wheel(original_sdk), source_files=source_files, release=candidate['release'])
    expected_candidate = {**candidate, 'sdk': prebuilt.pin(original_sdk)}
    require(same(original_candidate, expected_candidate), 'Original SDK candidate differs from independently verified byte closure')
    expected = {'source_revision': identity['head_revision'], 'tested_revision': identity['revision'], 'run_id': identity['run_id']}
    results = {}
    for variant, (target, minor) in original_matrix.SLOTS.items():
        name = 'realization-' + variant
        receipt = store.json(name, 'installed-release.json')
        results[variant] = original_matrix.validate_partitioned_slot(receipt, expected, target, minor, original_candidate, lambda relative, name=name: store.read(name, relative))
    original = store.json('prebuilt-release-validation', 'receipt.json')
    needs = original['needs']
    require(set(needs) == original_matrix.REQUIRED_RELEASE_NEEDS and all(row['result'] == 'success' for row in needs.values()), 'Original release prerequisite census differs')
    rebuilt_original = {'schema_version': 'biocompiler.prebuilt_release_validation.v1', 'status': 'pass', **expected, 'candidate_sha256': sha(original_candidate_path), 'slots': results, 'needs': needs, 'scope': 'internal release artifacts; publishing and default semantic cutover are separate'}
    require(same(rebuilt_original, original), 'Original four-runtime/17-campaign prebuilt comparison differs')
    return {'architecture_policy_comparisons': 6, 'policy_prebuilt_slots': 4, 'original_installed_assemblies': 4, 'original_campaigns_per_assembly': 17, 'original_group_receipts': 20, 'source_archives': source_archives,
            'legacy_semantic_scope': 'Complete installed ownership, group/campaign receipt byte pins, lifecycle/campaign command recipes, logs and assembly census independently checked. The large legacy domain-level semantic comparisons and reference reconstruction remain hosted-gate evidence; not locally replayed by this inert audit.'}

def check_artifacts(store, output, plan, identity, ci, args, skips, metadata):
    source, tree = identity['head_revision'], plan['tree']
    ci_identity = {key: identity[key] for key in ['revision', 'run_id', 'run_attempt']}
    from release_audit_native import audit_bundle, audit_suites, audit_groups
    from release_audit_units import audit_unit_evidence
    unit_artifacts = {}
    for row in plan['unit_artifacts']:
        name = row['artifact']
        expected_file = Path(row['workspace_path']).name
        require(store.names(name) == {expected_file}, 'Unit ZIP exact JSON member census differs')
        unit_artifacts[name] = {'files': {expected_file: store.read(name, expected_file)},
                                'provenance': {'run_id': int(identity['run_id']), 'run_attempt': int(identity['run_attempt']), 'head_revision': source,
                                               'revision': identity['revision'], 'artifact_id': metadata[name]['id'],
                                               'zip_sha256': metadata[name]['digest'].removeprefix('sha256:')}}
    unit = audit_unit_evidence(unit_artifacts,
        authority={'head_revision': source, 'revision': identity['revision'], 'head_tree': tree, 'tree': tree,
                   'run_id': int(identity['run_id']), 'run_attempt': int(identity['run_attempt'])},
        expected_source_inventory=plan['source_inventory'], shard_protocol_source=(ROOT / 'tools/test_shards.py').read_bytes(),
        weights_source=(ROOT / 'tools/test_shard_weights.json').read_bytes())
    ordinary = []
    for row in plan['ordinary_receipts']:
        receipt = store.json(row['artifact'], row['receipt_file'])
        require((receipt['job'], receipt['variant']) == (row['job'], row['variant']), 'Ordinary receipt mapping differs')
        ordinary.append(receipt)
    accounting = [store.json('unit-accounting-py' + minor, 'accounting-py' + minor + '.json') for minor in ['3.11', '3.14']]
    aggregate = store.json('validation-receipt', 'receipt.json')
    ci_identity = {key: identity[key] for key in ['revision', 'run_id', 'run_attempt']}
    rebuilt = ci.validate(aggregate['prerequisites'], ordinary, accounting, ci_identity)
    require(rebuilt['status'] == 'pass' and same(rebuilt, aggregate), 'Full 59-receipt final aggregate differs')
    native_results = {}
    for target, runtime in plan['platforms'].items():
        directory = store.extract('native-bundle-' + target, output / 'bundles' / target)
        require(store.names('native-bundle-' + target) == {'native.zip'}, 'Outer native bundle census differs')
        with zipfile.ZipFile(directory / 'native.zip') as archive:
            bundle = audit_bundle(archive, identity=ci_identity, runtime=runtime, expected_members=plan['native_members'], fixture_pins=plan['fixture_pins'], dune_sha256=plan['dune_sha256'])
        suite_name = 'core-native-tests-' + target
        suites = audit_suites(lambda name: store.read(suite_name, name), store.names(suite_name), identity=ci_identity, plan=plan['native_plan'], environment_paths=plan['native_environment_paths'])
        group_name = 'native-checks-' + target
        groups = audit_groups(lambda name: store.read(group_name, name), store.names(group_name), identity=ci_identity, source_revision=source, runtime=runtime, plan=plan['direct_groups'], plan_sha256=plan['direct_group_plan_sha256'])
        core_manifest = store.json('core-' + target, 'binaries.json')
        require(core_manifest == {'revision': identity['revision'], 'system': runtime[0], 'machine': runtime[1], 'sha256': {role: bundle['files']['core/_build/default/bin/' + ('core' if role.endswith('-core') else 'verify') + '/main.exe']['sha256'] for role in ['biocompiler-core', 'biocompiler-verify']}}, 'Native bundle roles differ from published binaries')
        native_results[target] = {'executables': 151, 'fixtures': 23, 'suites': suites, 'groups': groups}
    material = audit_policy_and_prebuilt(store, output, plan, identity)
    # These receipts are retained verbatim, bound by complete successful physical
    # comparator jobs. They are not mislabeled as local semantic re-execution.
    legacy = {}
    require(store.names('realization-core-reproducibility') == set(plan['legacy_comparison_receipts']), 'Legacy comparator receipt census differs')
    for name in plan['legacy_comparison_receipts']:
        raw = store.read('realization-core-reproducibility', name)
        record = decode(raw)
        validate_legacy_comparison(record, name=name, plan=plan, identity=identity)
        legacy[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'schema_version': record['schema_version'], 'claim': 'hosted semantic result, not locally reconstructed'}
    return {'unit': unit, 'native': native_results, 'material_and_prebuilt': material,
            'legacy_hosted_comparison_receipts': legacy, 'conditional_step_skips': skips}


def pin(path):
    return {'sha256': sha(path), 'bytes': Path(path).stat().st_size}


def read_pinned(path, expected):
    require(type(expected) is str and len(expected) == 64 and set(expected) <= set('0123456789abcdef'),
            'Caller must supply an independently reviewed SHA-256')
    value = read_json(path)
    require(sha(path) == expected, 'Input differs from independently supplied digest: ' + str(path))
    return value


def git_catalog(root, revision, tree=None):
    root = Path(root).resolve()
    observed = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD', 'HEAD^{tree}'], text=True).splitlines()
    require(len(observed) == 2 and observed[0] == revision and (tree is None or observed[1] == tree),
            'Checkout does not match independently supplied revision/tree')
    require(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain=v1'], text=True) == '',
            'Audit/tool checkout must be clean')
    tracked = [p for p in subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0') if p]
    rows = subprocess.check_output(['git', '-C', str(root), 'ls-tree', '-r', revision, '--',
                                   'core', 'src', 'protocol', 'tools', 'pyproject.toml'], text=True).splitlines()
    return {'revision': observed[0], 'tree': observed[1], 'tracked': tracked, 'source_rows': rows}


def read_packet(path, expected_digest):
    packet = read_pinned(path, expected_digest)
    require(type(packet) is dict and set(packet) == {'schema', 'files'}
            and packet['schema'] == 'biocompiler.release_api_packet.v1' and type(packet['files']) is dict,
            'Malformed authenticated API packet')
    data, pins = {}, {}
    for name, row in packet['files'].items():
        require(type(name) is str and type(row) is dict and set(row) == {'path', 'sha256'}, 'Malformed API file pin')
        require(type(row['path']) is str, 'API packet path must be text')
        relative = Path(row['path'])
        require(relative.parts and not relative.is_absolute()
                and '..' not in relative.parts, 'Unsafe API packet path')
        target = path.parent / relative
        data[name] = read_pinned(target, row['sha256']); pins[name] = {'path': str(target), **pin(target)}
    return data, pins


def identity_from_authority(expected, packet, success):
    from release_audit_identity import check_main_identity, check_pr_identity
    if expected.get('schema') == 'biocompiler.pull_request_identity.v1':
        required = {'run', 'commit', 'head_commit', 'main_ref', 'merge_ref', 'pr', 'suite'}
        checker = check_pr_identity
        base = expected['base_revision']
    else:
        require(expected.get('schema') == 'biocompiler.actual_main_identity.v1', 'Unsupported identity authority')
        required = {'run', 'commit', 'main_ref', 'pr', 'suite'}
        checker = check_main_identity
        base = expected['premerge_main']
    require(set(packet) == required, 'API packet has omitted or unreviewed identity inputs')
    proof = checker(expected=expected, require_success=success, **packet)
    identity = {'head_revision': proof['source_revision'], 'revision': proof['tested_revision'],
                'run_id': str(proof['run_id']), 'run_attempt': str(proof['run_attempt'])}
    return identity, proof['tree'], base, proof


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'check'))
    for name in ('source-root', 'authority', 'packet', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('authority-sha256', 'packet-sha256', 'tool-revision'):
        parser.add_argument('--' + name, required=True)
    for name in ('plan', 'jobs', 'artifacts', 'archive-paths'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--plan-sha256')
    return parser.parse_args(argv)


def main(argv=None):
    global ROOT
    from release_audit_plan import build_plan
    args = parse_args(argv)
    require(not sys.flags.optimize, 'Audit assertions must remain enabled')
    require(type(args.tool_revision) is str and len(args.tool_revision) == 40
            and set(args.tool_revision) <= set('0123456789abcdef'), 'Expected tool revision must be a full Git SHA')
    tool = git_catalog(TOOL_ROOT, args.tool_revision)
    tool_files = sorted(TOOLS.glob('release_audit*.py')) + [TOOL_ROOT / 'protocol/release-audit-v1.json']
    tool_pins = {str(path.relative_to(TOOL_ROOT)): pin(path) for path in tool_files}
    expected = read_pinned(args.authority, args.authority_sha256)
    packet, api_pins = read_packet(args.packet, args.packet_sha256)
    identity, tree, base, identity_proof = identity_from_authority(expected, packet, args.command == 'check')
    ROOT = args.source_root.resolve()
    source = git_catalog(ROOT, identity['head_revision'], tree)
    require(args.output.is_absolute() and not args.output.exists(), 'Output must be a fresh explicit absolute path')
    profile_path = TOOL_ROOT / 'protocol/release-audit-v1.json'
    profile = read_json(profile_path)
    # All Git reads finish before the inert guard. Original source-root helpers
    # are then imported from that authenticated checkout, not the tool checkout.
    sys.path[:0] = [str(ROOT / 'tools'), str(ROOT), str(ROOT / 'src')]
    sys.addaudithook(inert)
    rebuilt = build_plan(ROOT, identity=identity, tree=tree, base=base, profile=profile,
                         profile_sha256=sha(profile_path), tracked=source['tracked'], source_rows=source['source_rows'])
    rebuilt['toolchain'] = {'revision': tool['revision'], 'tree': tool['tree'], 'files': tool_pins}
    rebuilt['authority_sha256'] = args.authority_sha256
    if args.command == 'prepare':
        require(all(getattr(args, name) is None for name in ('plan', 'jobs', 'artifacts', 'archive_paths', 'plan_sha256')),
                'Preparation may not consume final artifact inputs')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rebuilt, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'status': 'prepared_not_accepted', 'plan': str(args.output), **pin(args.output),
                          'identity': identity, 'tree': tree}))
        return 0
    require(all(getattr(args, name) is not None for name in ('plan', 'jobs', 'artifacts', 'archive_paths', 'plan_sha256')),
            'Final check requires complete explicit input paths and expected plan digest')
    plan = read_pinned(args.plan, args.plan_sha256)
    require(same(plan, rebuilt), 'Supplied plan differs from independent full-source/profile rederivation')
    run = packet['run']; jobs = read_json(args.jobs); meta_doc = read_json(args.artifacts)
    skips = validate_jobs(jobs, run, plan)
    rows = meta_doc['artifacts']; metadata = {row['name']: row for row in rows}
    require(meta_doc['total_count'] == len(rows) == len(metadata) and len({row['id'] for row in rows}) == len(rows),
            'Artifact pagination or uniqueness differs')
    require(set(metadata) <= set(plan['permitted_artifact_names'])
            and set(plan['required_metadata_names']) <= set(metadata), 'Artifact producer/name census differs')
    for row in rows:
        require(not row['expired'] and row['workflow_run']['id'] == run['id']
                and row['workflow_run']['head_sha'] == identity['head_revision']
                and row['created_at'] >= run['run_started_at'], 'Foreign/stale artifact metadata')
    store = ArtifactStore(metadata=metadata, paths=read_json(args.archive_paths), required=plan['download_artifact_names'],
                          run=run['id'], head=identity['head_revision'], started_at=run['run_started_at'])
    args.output.mkdir(parents=True)
    import ci_validation as ci
    try:
        result = check_artifacts(store, args.output, plan, identity, ci, args, skips, metadata)
        proof = {'schema': 'biocompiler.release_inert_audit.v1', 'status': 'pass_for_stated_scope',
                 **identity, 'tree': tree, 'identity_check': identity_proof, 'toolchain': rebuilt['toolchain'],
                 'physical_jobs': 74, 'ordinary_receipts': 59, **result, 'archives': store.proof,
                 'extracted_bytes': store.extracted, 'plan_sha256': args.plan_sha256,
                 'authority_sha256': args.authority_sha256, 'packet_sha256': args.packet_sha256,
                 'api_input_pins': api_pins,
                 'input_pins': {str(p): pin(p) for p in (args.jobs, args.artifacts, args.archive_paths)},
                 'limitations': profile['limitations'],
                 'remaining': (['Owner release acceptance including explicitly hosted legacy semantic comparisons',
                                'Exact-head normal merge', 'Fresh complete actual-main validation']
                               if run['event'] == 'pull_request' else ['Owner release acceptance including explicitly hosted legacy semantic comparisons']),
                 'local_native_execution': 'not_performed'}
        output = args.output / 'proof.json'
        output.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'status': proof['status'], 'proof': str(output), **pin(output)}))
    finally:
        store.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
