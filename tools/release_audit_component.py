"""Inert component-release adapters with independently authenticated authority.

Every adapter preserves its pinned original function body except explicit source
catalog/identity inputs and delegation to these same inert adapters. Tests reverse
those changes to the original AST and check imported dependency identity. No Git,
native execution, environment spoofing or producer is invoked. The caller must
bind audited_identity and audited_sources to its independently prepared plan.
"""
from __future__ import annotations

import re
from release_audit_policy import audit_material


def _source_rows(catalog):
    """Encode the externally authenticated Git catalog, rejecting open shapes."""
    if type(catalog) is not dict or not catalog:
        raise AssertionError("A complete authenticated component source catalog is required")
    rows = []
    for name, value in sorted(catalog.items()):
        if (type(name) is not str or not name or name.startswith("/") or "\\" in name
                or any(part in ("", ".", "..") for part in name.split("/"))
                or any(char in name for char in ("\0", "\t", "\n", "\r"))
                or type(value) is not dict or set(value) != {"sha256", "size", "git_blob", "mode"}
                or value["mode"] not in ("100644", "100755")
                or type(value["size"]) is not int or not 0 <= value["size"] <= 128 * 1024 * 1024
                or type(value["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
                or type(value["git_blob"]) is not str or re.fullmatch(r"[0-9a-f]{40}", value["git_blob"]) is None):
            raise AssertionError("Malformed authenticated component source record")
        rows.append((value["mode"] + " blob " + value["git_blob"] + "\t" + name).encode("utf-8"))
    return rows



def audit_sources(root, *, audited_sources):
    from check_policy_development import Path, SOURCE_ROOTS, git, hashlib, os, pin, require, stat
    'Check actual bytes against HEAD blobs, including a full source-file census.'
    rows = _source_rows(audited_sources)
    result = {}
    for row in filter(None, rows):
        header, name = row.split(b'\t', 1)
        mode, kind, blob = header.decode().split()
        relative = name.decode('utf-8')
        require(mode in {'100644', '100755'} and kind == 'blob', 'Unsupported tracked source kind')
        path = root / relative
        require(relative not in result and (not Path(relative).is_absolute()) and ('..' not in Path(relative).parts), 'Unsafe or duplicated tracked source')
        metadata = pin(root, relative, allow_empty=True)
        raw = path.read_bytes()
        actual_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\x00' + raw).hexdigest()
        require(actual_blob == blob and bool(path.stat().st_mode & stat.S_IXUSR) == (mode == '100755'), 'Source differs from checked revision: ' + relative)
        result[relative] = {**metadata, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'git_blob': blob, 'mode': mode}
    require(result, 'Empty tracked source census')
    present = set()
    for relative in SOURCE_ROOTS:
        base = root / relative
        if base.is_file():
            present.add(relative)
            continue
        require(base.is_dir() and (not base.is_symlink()), 'Missing source root: ' + relative)
        for parent, directories, files in os.walk(base, followlinks=False):
            directories[:] = [name for name in directories if name != '__pycache__' and Path(parent, name) != root / 'core/_build']
            require(all((not Path(parent, name).is_symlink() for name in directories)), 'Symlinked source directory')
            for name in files:
                path = Path(parent, name)
                present.add(path.relative_to(root).as_posix())
    require(present == set(result), 'Tracked source census changed or new source files appeared')
    require(result == audited_sources, 'Current source metadata differs from authenticated catalog')
    return result


def audit_fixture(root, fixture_path, provenance_path, *, identity, native_sha256, expected_platform=None, audited_sources):
    from check_policy_component_fixture import BINARIES, MAX_FIXTURE, MAX_LOG, MAX_PROVENANCE, PLATFORMS, Path, SCHEMA, check_identity, check_packet, core, development, logical_command, pin, re, read, require
    'Check externally bound emitted data without invoking any native program.'
    root, fixture_path, provenance_path = (Path(root), Path(fixture_path), Path(provenance_path))
    require(fixture_path.name == 'originals.json' and provenance_path.name == 'provenance.json' and (fixture_path.parent == provenance_path.parent), 'Component fixture pair paths differ')
    before = {name: pin(fixture_path.parent / name, maximum, empty=name.endswith('.log')) for name, maximum in (('originals.json', MAX_FIXTURE), ('provenance.json', MAX_PROVENANCE), ('stdout.log', MAX_LOG), ('stderr.log', MAX_LOG))}
    value = read(provenance_path, MAX_PROVENANCE)
    require(type(value) is dict and set(value) == {'schema_version', 'status', 'acceptance', 'identity', 'platform', 'sources', 'binaries', 'fixture', 'command'} and (value['schema_version'] == SCHEMA) and (value['status'] == 'source_declarations_only') and (value['acceptance'] is False), 'Component fixture provenance is incomplete or changes authority scope')
    check_identity(value['identity'], identity)
    require(type(value['platform']) is dict and set(value['platform']) == {'system', 'machine'}, 'Component fixture platform fields differ')
    actual_platform = (value['platform']['system'], value['platform']['machine'])
    require(actual_platform in PLATFORMS and (expected_platform is None or actual_platform == tuple(expected_platform)), 'Component fixture platform differs')
    require(core.canonical_digest(value['sources']) == core.canonical_digest(audit_sources(root, audited_sources=audited_sources)), 'Component fixture build sources changed')
    binaries = value['binaries']
    require(type(binaries) is dict and set(binaries) == set(BINARIES) and (type(native_sha256) is dict) and (set(native_sha256) == {'core', 'verify'}), 'Component fixture binary inventory differs')
    for role, record in binaries.items():
        require(type(record) is dict and set(record) == {'sha256', 'size'} and (type(record['size']) is int) and (0 < record['size'] <= 128 * 1024 * 1024) and (type(record['sha256']) is str) and re.fullmatch('[0-9a-f]{64}', record['sha256']), 'Invalid component fixture executable pin')
        if role != 'originals':
            require(record['sha256'] == native_sha256[role], 'Component fixture differs from externally pinned native role')
    expected_command = {'argv': logical_command(), 'cwd': 'checkout', 'returncode': 0, 'logs': {name: before[name] for name in ('stdout.log', 'stderr.log')}}
    require(core.canonical_digest(value['fixture']) == core.canonical_digest(before['originals.json']) and core.canonical_digest(value['command']) == core.canonical_digest(expected_command), 'Component fixture command, complete logs or output changed')
    check_packet(root, fixture_path)
    require(before == {name: pin(fixture_path.parent / name, MAX_FIXTURE if name == 'originals.json' else MAX_PROVENANCE if name == 'provenance.json' else MAX_LOG, empty=name.endswith('.log')) for name in before}, 'Component fixture evidence changed during validation')
    return value


def audit_installed(receipt, evidence_root, fixture, fixture_path, identity_value, binaries, *, expected_sources, fixture_provenance, expected_slot=None):
    from check_policy_component_material import CASE_NAMES, INSTALLED_SCHEMA, INSTALLED_SCOPE, MAX_EVIDENCE, Path, SLOTS, __file__, _require, _retained, _sha, archive_receipt, author_request, bounded_pin, canonical_digest, check_installed_origins, check_observations, checked_fixture, fixture_authority_pins, installed_source_modules, re, read_json, validate_fixture_provenance
    root = Path(__file__).resolve().parents[1]
    evidence_root = Path(evidence_root)
    authority = fixture_authority_pins(fixture_path, fixture_provenance)
    fields = {'schema_version', 'status', 'revision', 'head_revision', 'run_id', 'run_attempt', 'system', 'machine', 'python_version', 'scope', 'fixture_sha256', 'fixture_provenance_sha256', 'binary_sha256', 'package', 'installed_modules', 'parent_imports', 'source_snapshot_sha256', 'authoring', 'shared_driver_fingerprint', 'observations', 'observations_fingerprint', 'publications', 'python_semantic_authority'}
    _require(type(receipt) is dict and set(receipt) == fields and (receipt['schema_version'] == INSTALLED_SCHEMA) and (receipt['status'] == 'pass'), 'Not a complete installed component campaign receipt')
    _require(type(receipt['python_version']) is str and re.fullmatch('3\\.(11|14)\\.[0-9]+', receipt['python_version']) is not None, 'Invalid installed component runtime')
    slot = (receipt['system'], receipt['machine'], '.'.join(receipt['python_version'].split('.')[:2]))
    _require(slot in SLOTS and (expected_slot is None or slot == expected_slot), 'Wrong or unexpected installed component slot')
    _require(all((receipt[key] == identity_value[key] for key in ('revision', 'head_revision', 'run_id'))) and type(receipt['run_attempt']) is str and (re.fullmatch('[1-9][0-9]*', receipt['run_attempt']) is not None) and (int(receipt['run_attempt']) <= int(identity_value['run_attempt'])), 'Stale installed component source/run/attempt')
    _require(set(binaries) == {'biocompiler-core', 'biocompiler-verify'} and all((_sha(value) for value in binaries.values())) and (receipt['binary_sha256'] == binaries) and (receipt['fixture_sha256'] == bounded_pin(fixture_path, 4000000)['sha256']) and (receipt['fixture_provenance_sha256'] == bounded_pin(fixture_provenance, MAX_EVIDENCE)['sha256']) and (receipt['source_snapshot_sha256'] == canonical_digest(expected_sources)), 'Installed component external identity differs')
    _require(receipt['scope'] == INSTALLED_SCOPE and receipt['python_semantic_authority'] == 'forbidden', 'Installed component scope promoted')
    audit_fixture(root, fixture_path, fixture_provenance, identity=identity_value, native_sha256={role: binaries['biocompiler-' + role] for role in ('core', 'verify')}, expected_platform=slot[:2], audited_sources=expected_sources)
    _require(fixture == checked_fixture(root, fixture_path), 'Component original fixture was replaced')
    _require(not Path(receipt['package']).resolve().is_relative_to(root.resolve()), 'Installed package belongs to checkout')
    _require(receipt['installed_modules'] == installed_source_modules(root), 'Installed component module inventory differs')
    check_installed_origins(receipt['parent_imports'], receipt['package'], receipt['installed_modules'])
    authoring = [{'case': case['id'], **author_request(case['request'], case['id'] == 'B')[1]} for case in fixture['cases']]
    _require(receipt['authoring'] == authoring, 'Complete original Python authoring evidence changed')
    drivers = [case['request']['component_library']['components'][1] for case in fixture['cases']]
    _require(drivers[0] == drivers[1] and receipt['shared_driver_fingerprint'] == canonical_digest(drivers[0]), 'Reusable original driver changed')
    rows = receipt['observations']
    _require(type(rows) is list and all((type(row) is dict and set(row) == {'case', 'name', 'path', 'sha256', 'bytes'} for row in rows)) and ([(row['case'], row['name']) for row in rows] == [(case, name) for case in ('A', 'B') for name in CASE_NAMES]), 'Incomplete installed observation files')
    observations = []
    folder = None
    paths = []
    for row in rows:
        path = _retained(row['path'], evidence_root, {key: row[key] for key in ('sha256', 'bytes')}, MAX_EVIDENCE)
        _require(path.name == row['case'] + '-' + row['name'] + '.json', 'Renamed component observation')
        folder = folder or path.parent
        _require(path.parent == folder, 'Component observations split across unrelated directories')
        observations.append({'case': row['case'], 'name': row['name'], 'result': read_json(path, MAX_EVIDENCE)})
        paths.append(path)
    _require(receipt['observations_fingerprint'] == canonical_digest(observations), 'Complete installed observations changed')
    inputs = check_observations(observations, fixture)
    pubs = receipt['publications']
    _require(type(pubs) is list and all((type(row) is dict and set(row) == {'case', 'path', 'sha256', 'bytes'} for row in pubs)) and ([row['case'] for row in pubs] == ['A', 'B']), 'Missing or reordered paired component ZIPs')
    for row in pubs:
        path = _retained(row['path'], evidence_root, {key: row[key] for key in ('sha256', 'bytes')}, MAX_EVIDENCE)
        _require(path.parent == folder and path.name == row['case'] + '-program.zip', 'Foreign component paired ZIP path')
        archive_receipt(inputs[row['case']]['exported'], path)
        paths.append(path)
    _require(folder is not None and set(folder.iterdir()) == set(paths), 'Missing or extra component evidence file')
    for row in (*rows, *pubs):
        _retained(row['path'], evidence_root, {key: row[key] for key in ('sha256', 'bytes')}, MAX_EVIDENCE)
    _require(fixture_authority_pins(fixture_path, fixture_provenance) == authority, 'Original component authority changed while validating evidence')
    return inputs


def audit_component(paths, native_root, fixture_path, fixture_provenances, *, audited_identity, audited_sources):
    from check_policy_component_material import INSTALLED_SCHEMA, INSTALLED_SCOPE, MAX_EVIDENCE, MAX_RECEIPT, Path, SLOTS, __file__, _require, bounded_pin, checked_fixture, fixture_authority_pins, native_manifests, read_json, source_identity, source_snapshot, validate_installed
    root = Path(__file__).resolve().parents[1]
    hosted, sources = (dict(audited_identity), audit_sources(root, audited_sources=audited_sources))
    binaries = native_manifests(Path(native_root), hosted['revision'])
    fixture = checked_fixture(root, fixture_path)
    _require(len(paths) == 4 and set(fixture_provenances) == {('Linux', 'x86_64'), ('Darwin', 'arm64')}, 'All four component slots and both fixture authorities are required')
    found, baseline, attempts = (set(), None, [])
    authorities = []
    retained = [(Path(fixture_path), 4000000, bounded_pin(fixture_path, 4000000))]
    for path in paths:
        path = Path(path)
        receipt_pin = bounded_pin(path, MAX_RECEIPT)
        retained.append((path, MAX_RECEIPT, receipt_pin))
        receipt = read_json(path, MAX_RECEIPT)
        platform_key = (receipt.get('system'), receipt.get('machine'))
        _require(platform_key in fixture_provenances, 'Unexpected component platform')
        slot = (*platform_key, '.'.join(receipt.get('python_version', '').split('.')[:2]))
        _require(slot not in found, 'Duplicate component slot')
        found.add(slot)
        local_fixture = Path(fixture_provenances[platform_key]).parent / 'originals.json'
        _require(bounded_pin(local_fixture, 4000000) == bounded_pin(fixture_path, 4000000) and checked_fixture(root, local_fixture) == fixture, 'Platform original component packets differ')
        authorities.append((local_fixture, Path(fixture_provenances[platform_key]), fixture_authority_pins(local_fixture, fixture_provenances[platform_key])))
        audit_installed(receipt, path.parent, fixture, local_fixture, hosted, binaries[platform_key[0].lower()]['sha256'], expected_sources=sources, fixture_provenance=fixture_provenances[platform_key], expected_slot=slot)
        retained.extend(((path.parent / row['path'], MAX_EVIDENCE, {key: row[key] for key in ('sha256', 'bytes')}) for row in (*receipt['observations'], *receipt['publications'])))
        fingerprint = receipt['observations_fingerprint']
        _require(baseline is None or baseline == fingerprint, 'Complete component outputs differ across installed slots')
        baseline = fingerprint
        attempts.append({'slot': list(slot), 'run_attempt': receipt['run_attempt'], 'receipt': receipt_pin})
    _require(all((bounded_pin(path, maximum) == expected for path, maximum, expected in retained)) and all((fixture_authority_pins(original, provenance) == expected for original, provenance, expected in authorities)) and (native_manifests(Path(native_root), hosted['revision']) == binaries), 'Retained component comparison evidence or native authority changed')
    _require(found == SLOTS and dict(audited_identity) == hosted and (audit_sources(root, audited_sources=audited_sources) == sources), 'Incomplete component slots or changed comparison authority')
    return {'schema_version': INSTALLED_SCHEMA, 'status': 'pass', **hosted, 'slots': sorted(found), 'attempts': attempts, 'fixture_sha256': bounded_pin(fixture_path, 4000000)['sha256'], 'observations_fingerprint': baseline, 'scope': INSTALLED_SCOPE, 'empirical': 'unassessed', 'python_semantic_authority': 'forbidden'}


def audit_component_producer(receipt, receipt_path, fixture, fixture_path, identity, binaries, provenance, *, expected_slot, audited_sources):
    from check_policy_material_consumer import INPUT_FILES, Path, __file__, component_support, deepcopy
    component = component_support()
    checkout = Path(__file__).resolve().parents[1]
    cases = audit_installed(receipt, Path(receipt_path).parent, fixture, fixture_path, identity, binaries, expected_sources=audit_sources(checkout, audited_sources=audited_sources), fixture_provenance=provenance, expected_slot=expected_slot)
    if type(cases) is not dict or list(cases) != ['A', 'B'] or any((type(row) is not dict or set(row) != set(INPUT_FILES) for row in cases.values())):
        raise AssertionError('Component producer omitted complete separate A/B original/proposal/expectation inputs')
    return {label + '.' + name: deepcopy(cases[label][name]) for label in ('A', 'B') for name in INPUT_FILES}


def audit_consumer(paths, producer_paths, native_root, fixture_path, *, profile='material', fixture_provenances=None, audited_identity, audited_sources):
    from check_policy_material_consumer import PRODUCER_ABSENCE, Path, __file__, check_manifest, check_worker, component_support, deepcopy, digest, file_digest, profile_spec, read_json, slot, support, validate_component_producer, validate_producer
    core, material = support()
    route = profile_spec(profile)
    identity = dict(audited_identity)
    if profile == 'component':
        comparison_sources = deepcopy(audit_sources(Path(__file__).resolve().parents[1], audited_sources=audited_sources))
        if type(fixture_provenances) is not dict or set(fixture_provenances) != {('Linux', 'x86_64'), ('Darwin', 'arm64')}:
            raise AssertionError('Both independently supplied platform fixture provenances are required')
        retained = [(Path(path), file_digest(path)) for path in (*paths, *producer_paths, fixture_path, Path(__file__))]
        original_authorities = [(Path(provenance).parent / 'originals.json', provenance, component_support().fixture_authority_pins(Path(provenance).parent / 'originals.json', provenance)) for provenance in fixture_provenances.values()]
        audit_component(producer_paths, native_root, fixture_path, fixture_provenances, audited_identity=audited_identity, audited_sources=audited_sources)
    else:
        audit_material(producer_paths, native_root, fixture_path, audited_identity=audited_identity)
    binaries = core.native_manifests(native_root, identity['revision'])
    fixture = component_support().checked_fixture(Path(__file__).resolve().parents[1], fixture_path) if profile == 'component' else material.checked_fixture(fixture_path)
    producers = {slot(value): (path, value) for path in producer_paths for value in [read_json(path)]}
    expected = {(system, machine, minor) for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')) for minor in ('3.11', '3.14')}
    if len(paths) != 4 or set(producers) != expected:
        raise AssertionError('All four consumer and original producer slots are required exactly once')
    if profile == 'component':
        producer_evidence = [(Path(path).parent / row['path'], {key: row[key] for key in ('sha256', 'bytes')}) for path, producer in producers.values() for row in (*producer['observations'], *producer['publications'])]
    found, baseline = (set(), None)
    checkout = Path(__file__).resolve().parents[1]
    for path in paths:
        receipt = read_json(path)
        fields = {'schema_version', 'status', 'revision', 'head_revision', 'run_id', 'run_attempt', 'system', 'machine', 'python_version', 'fixture_sha256', 'producer_receipt_sha256', 'verify_sha256', 'installed_package', 'installed_modules', 'worker'}
        if profile == 'component':
            fields |= {'core_sha256', 'fixture_provenance_sha256'}
        if type(receipt) is not dict or set(receipt) != fields:
            raise AssertionError('Malformed consumer campaign receipt')
        current = slot(receipt)
        if current not in expected or current in found:
            raise AssertionError('Missing, duplicate or unexpected consumer platform slot')
        found.add(current)
        producer_path, producer = producers[current]
        verify_sha = binaries[receipt['system'].lower()]['sha256']['biocompiler-verify']
        if receipt['schema_version'] != route['schema'] or receipt['status'] != 'pass' or any((receipt[key] != identity[key] for key in ('revision', 'head_revision', 'run_id'))) or (type(receipt['run_attempt']) is not str) or (not receipt['run_attempt'].isdecimal()) or (not 0 < int(receipt['run_attempt']) <= int(identity['run_attempt'])) or (receipt['fixture_sha256'] != file_digest(fixture_path)) or (receipt['producer_receipt_sha256'] != file_digest(producer_path)) or (receipt['verify_sha256'] != verify_sha):
            raise AssertionError('Consumer receipt lacks exact current source/run/original expectation/binary identity')
        if profile == 'component':
            native_pins = binaries[receipt['system'].lower()]['sha256']
            provenance = fixture_provenances[current[:2]]
            platform_fixture = Path(provenance).parent / 'originals.json'
            if file_digest(platform_fixture) != file_digest(fixture_path) or read_json(platform_fixture) != fixture:
                raise AssertionError('Component platform original packets differ from the complete common authority')
            if receipt['core_sha256'] != native_pins['biocompiler-core'] or receipt['fixture_provenance_sha256'] != file_digest(provenance):
                raise AssertionError('Component consumer lacks exact native Core or original fixture provenance')
            inputs = audit_component_producer(producer, producer_path, fixture, platform_fixture, identity, {name: native_pins[name] for name in ('biocompiler-core', 'biocompiler-verify')}, provenance, expected_slot=current, audited_sources=audited_sources)
        else:
            inputs = validate_producer(producer, fixture, fixture_path, identity, verify_sha, expected_slot=current)
        manifest = receipt['worker']['stage_manifest']
        package = Path(receipt['installed_package'])
        if not package.is_absolute() or '..' in package.parts or set(receipt['installed_modules']) != set(route['modules']):
            raise AssertionError('Consumer lost installed transport package origins')
        check_manifest(manifest, profile=profile)
        for name, evidence in receipt['installed_modules'].items():
            source = checkout / 'src/biocompiler' / name
            expected_pin = file_digest(source)
            if evidence != {'origin': str(package / name), 'sha256': expected_pin} or manifest['files']['transport/biocompiler/' + name] != {'sha256': expected_pin, 'bytes': source.stat().st_size}:
                raise AssertionError('Consumer transport source/origin pin changed')
        folder = 'linux-x86_64' if receipt['system'] == 'Linux' else 'macos-arm64'
        if manifest['files']['bin/biocompiler-verify'] != {'sha256': verify_sha, 'bytes': (native_root / folder / 'biocompiler-verify').stat().st_size}:
            raise AssertionError('Consumer staged binary inventory differs from published native bytes')
        if manifest['files']['consumer.py'] != {'sha256': file_digest(Path(__file__)), 'bytes': Path(__file__).stat().st_size} or manifest['verify_sha256'] != verify_sha or manifest['inputs'] != {name: digest(value) for name, value in inputs.items()}:
            raise AssertionError('Consumer worker or separate original-input pins changed')
        check_worker(receipt['worker'], inputs, manifest, profile=profile)
        required_mechanism = 'linux_libseccomp' if receipt['system'] == 'Linux' else 'macos_sandbox_exec'
        if receipt['worker']['network']['mechanism'] != required_mechanism:
            raise AssertionError('Consumer network enforcement belongs to another OS')
        fingerprint = receipt['worker']['observations_fingerprint']
        if baseline is not None and baseline != fingerprint:
            raise AssertionError('Complete fresh consumer outputs differ across four slots')
        baseline = fingerprint
    if profile == 'component' and (dict(audited_identity) != identity or audit_sources(checkout, audited_sources=audited_sources) != comparison_sources or any((file_digest(path) != expected_pin for path, expected_pin in retained)) or any((component_support().bounded_pin(path) != expected_pin for path, expected_pin in producer_evidence)) or any((component_support().fixture_authority_pins(original, provenance) != expected_pin for original, provenance, expected_pin in original_authorities)) or (core.native_manifests(native_root, identity['revision']) != binaries)):
        raise AssertionError('Component consumer comparison evidence/source/run/native authority changed')
    return {'schema_version': route['schema'], 'status': 'pass', **identity, 'slots': sorted(found), 'fixture_sha256': file_digest(fixture_path), 'observations_fingerprint': baseline, 'producer_absence': PRODUCER_ABSENCE, 'network': 'os_denied_worker_and_descendants', 'claim_scope': 'fresh_verify_only_bounded_conditional_component_material_reproduction' if profile == 'component' else 'fresh_verify_only_bounded_conditional_material_reproduction', 'empirical': 'unassessed'}


def audit_authorities(pairs, identity, native_data, *, audited_sources):
    from check_policy_material_prebuilt import ROOT, build, pin, read_json, require
    'Authenticate each independent emitter packet against supplied native bytes.'
    import check_policy_component_fixture as fixture_tool
    result = {}
    for fixture, provenance in pairs:
        value = read_json(provenance)
        platform_value = value.get('platform', {})
        key = (platform_value.get('system'), platform_value.get('machine'))
        targets = [name for name, row in build.TARGETS.items() if row[:2] == key and name in native_data]
        require(len(targets) == 1 and key not in result, 'Duplicate or unexpected component fixture platform')
        native = native_data[targets[0]]
        hashes = {role: build.sha(native['entries']['biocompiler_core/bin/biocompiler-' + role][0]) for role in ('core', 'verify')}
        checked = audit_fixture(ROOT, fixture, provenance, identity=identity, native_sha256=hashes, expected_platform=key, audited_sources=audited_sources)
        result[key] = {'fixture': fixture, 'provenance': provenance, 'sources': checked['sources'], 'pins': {'fixture': pin(fixture), 'provenance': pin(provenance)}}
    require(set(result) == {build.TARGETS[name][:2] for name in native_data}, 'Missing component fixture platform')
    require(len({row['pins']['fixture']['sha256'] for row in result.values()}) == 1, 'Complete original component packets differ across platforms')
    return result


def audit_component_inputs(receipt, evidence, authority, identity, hashes, slot, *, audited_sources):
    from check_policy_material_prebuilt import ROOT
    import check_policy_component_material as component
    if authority["sources"] != audit_sources(ROOT, audited_sources=audited_sources):
        raise AssertionError("Prebuilt component authority differs from authenticated source catalog")
    return audit_installed(receipt, evidence, component.checked_fixture(ROOT, authority['fixture']), authority['fixture'], identity, hashes, expected_sources=authority['sources'], fixture_provenance=authority['provenance'], expected_slot=slot)


def audit_prebuilt_slot(directory, identity, candidate_path, sdk, sdk_entries, sdk_stamp, native_data, fixture, component_authority=None, *, audited_sources):
    from check_policy_material_prebuilt import CASES, COMPONENT_CASES, COMPONENT_CLAIM, COMPONENT_EVIDENCE, COMPONENT_SCHEMA, EVIDENCE, MAX_JSON, PROBE_SCHEMA, Path, ROOT, SCHEMA, authority_receipt, build, canonical, check_commands, check_component_controls, check_ownership, check_rejection, component_inputs, consumer, mutation_files, pin, prior_attempt, re, read_json, require, same, source_pins
    value = read_json(directory / 'prebuilt.json')
    required = {'schema_version', 'status', *identity, 'system', 'machine', 'python_version', 'output_root', 'checkout_root', 'fixture', 'source_pins', 'artifacts', 'evidence', 'commands', 'cases', 'claim', 'python_semantic_authority', 'network', 'default_cutover'}
    if component_authority is not None:
        required |= {'component_originals', 'component_cases'}
    require(type(value) is dict and set(value) == required and (value['schema_version'] == (COMPONENT_SCHEMA if component_authority is not None else SCHEMA)) and (value['status'] == 'pass') and prior_attempt(value, identity), 'Stale, failed or incomplete prebuilt slot')
    slot = consumer.slot(value)
    require(slot in {(row[0], row[1], minor) for row in build.TARGETS.values() for minor in ('3.11', '3.14')}, 'Unexpected runtime slot')
    target = next((name for name, row in build.TARGETS.items() if row[:2] == slot[:2]))
    native = native_data[target]
    require(same(value['artifacts'], authority_receipt(candidate_path, sdk, sdk_stamp, native)) and same(value['source_pins'], source_pins()) and same(value['fixture'], pin(fixture)) and (value['cases'] == list(CASES)) and (value['claim'] == (COMPONENT_CLAIM if component_authority is not None else 'supplied_prebuilt_material_profile_only')) and (value['python_semantic_authority'] == 'forbidden') and (value['network'] == 'consumer_required_os_denial') and (value['default_cutover'] == 'unassessed'), 'Prebuilt slot authority or scope differs')
    evidence_names = EVIDENCE + (COMPONENT_EVIDENCE if component_authority is not None else ())
    expected_evidence = {'evidence/' + name + '.json' for name in evidence_names}
    require(set(value['evidence']) == expected_evidence and all((same(pin(directory / name, MAX_JSON), row) for name, row in value['evidence'].items())) and same(value['commands'], pin(directory / 'commands.json', MAX_JSON)), 'Complete retained slot evidence differs')
    data = {name: read_json(directory / 'evidence' / (name + '.json')) for name in evidence_names}
    origin = Path(value['output_root'])
    require(origin.is_absolute() and (not origin.is_relative_to(ROOT)), 'Original run was not outside checkout')
    candidate = read_json(candidate_path)
    check_ownership(data['ownership-before'], sdk_entries, native, candidate, origin / 'env')
    require(same(data['ownership-before'], data['ownership-after']) and data['ownership-before']['runtime'] == {key: value[key] for key in ('system', 'machine', 'python_version')}, 'Ownership lifecycle or runtime identity differs')
    check_rejection(data['missing'], 'missing')
    controls = data['controls']
    require(type(controls) is list and [row.get('case') for row in controls] == list(CASES), 'Installed mutation census differs')
    for row in controls:
        require(set(row) == {'case', 'changes', 'rejection', 'restored'} and row['restored'] == consumer.digest(data['ownership-before']), 'Mutation restoration identity differs')
        check_rejection(row['rejection'], row['case'])
        require(same(read_json(directory / 'evidence' / (row['case'] + '.json')), row['rejection']) and same(read_json(directory / 'evidence' / (row['case'] + '-restored.json')), data['ownership-before']), 'Original installed control/restoration output differs from retained receipt')
        paths = mutation_files(row['case'], data['ownership-before']['ownership'])
        require([entry['path'] for entry in row['changes']] == [str(path) for path in paths] and all((set(entry) == {'path', 'before', 'after'} and entry['before'] != entry['after'] and all((type(pin_value) is dict and set(pin_value) == {'sha256', 'size'} and re.fullmatch('[0-9a-f]{64}', pin_value['sha256']) and (type(pin_value['size']) is int) and (pin_value['size'] > 0) for pin_value in (entry['before'], entry['after']))) for entry in row['changes'])), 'Installed mutation byte evidence differs')
    ownership = data['ownership-before']['ownership']
    material = data['material']
    offline = data['consumer']
    require(all((row['run_attempt'] == value['run_attempt'] for row in (material, offline))) and material['package'] == ownership['sdk_root'] and (offline['installed_package'] == ownership['sdk_root']), 'Delegated campaign did not use the same current-attempt owned SDK')
    expected_binary = {'biocompiler-' + role: ownership['files']['bin/biocompiler-' + role]['sha256'] for role in ('core', 'verify')}
    require(material['binary_sha256'] == expected_binary and offline['verify_sha256'] == expected_binary['biocompiler-verify'], 'Delegated campaign did not use supplied final wheel executables')
    from check_policy_material import checked_fixture
    inputs = consumer.validate_producer(material, checked_fixture(fixture), fixture, identity, expected_binary['biocompiler-verify'], expected_slot=slot)
    resolver = data['resolver']
    require(set(resolver) == {'schema_version', 'status', 'environment', 'ownership', 'results'} and resolver['schema_version'] == PROBE_SCHEMA and (resolver['status'] == 'pass') and (resolver['ownership'] == ownership) and (resolver['environment'] == data['ownership-before']['environment']) and (canonical(resolver['results']) == canonical({role: {'checked': inputs['checked'], 'exported': inputs['exported']} for role in ('core', 'verify')})), 'Fresh installed resolver results differ')
    if component_authority is not None:
        authority = component_authority[slot[:2]]
        require(same(value['component_originals'], authority['pins']) and value['component_cases'] == list(COMPONENT_CASES), 'Component original authority or mandatory controls differ')
        producer = data['component-material']
        offline_component = data['component-consumer']
        require(all((row['run_attempt'] == value['run_attempt'] and row['python_version'] == value['python_version'] for row in (producer, offline_component))) and producer['package'] == ownership['sdk_root'] and (offline_component['installed_package'] == ownership['sdk_root']) and (offline_component['core_sha256'] == expected_binary['biocompiler-core']) and (offline_component['verify_sha256'] == expected_binary['biocompiler-verify']), 'Component campaign did not use the same current-attempt owned SDK and supplied executables')
        component_values = audit_component_inputs(producer, directory / 'evidence', authority, identity, expected_binary, slot, audited_sources=audited_sources)
        check_component_controls(directory, data, component_values, sdk_entries)
    check_commands(directory, read_json(directory / 'commands.json'), origin, ownership, fixture, value, component_authority=component_authority[slot[:2]] if component_authority is not None else None)
    return (slot, data)
