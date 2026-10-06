"""Versioned receipt checks with independently verified explicit hosted identity.

All five comparison bodies preserve their original source obligations. Only the
identity input and consumer-to-material delegation differ; no environment or
source_identity is spoofed. The fixed profile pins original function bytes and
regression controls reverse these adaptations to the source functions exactly.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Sequence

def audit_source(paths: Sequence[Path], *, fixture: Path | None=None, native_artifacts: Path | None=None, audited_identity) -> dict[str, Any]:
    from check_policy_core import EXPECTED_NAMES, ImportBoundary, Path, __file__, canonical_digest, digest_file, load_cases, mutations, native_manifests, read_json, semantic_digest
    'Compare complete hosted variants while retaining machine provenance.'
    if len(paths) != 4 or len({path.resolve() for path in paths}) != 4:
        raise AssertionError('Comparison requires four distinct hosted receipts')
    workflow_identity = dict(audited_identity)
    if workflow_identity['run_id'] == 'local':
        raise AssertionError('Hosted comparison requires a current GitHub run identity')
    if native_artifacts is None:
        raise AssertionError('Hosted comparison requires --native-artifacts with published binary bytes')
    published = native_manifests(native_artifacts, workflow_identity['revision'])
    platform_pins: dict[str, dict[str, str]] = {}
    fixture = fixture or Path(__file__).resolve().parents[1] / 'core/test/data/policy_documents_v01.json'
    corpus = load_cases(fixture)
    input_rows = {(row['name'], row['kind']): row for row in corpus}
    expected_controls = {(name, role): (status, code, canonical_digest(document)) for name, document, status, code in mutations(corpus) for role in ('core', 'verify')}
    expected_variants = {(system, minor) for system in ('linux', 'darwin') for minor in (11, 14)}
    receipt_fields = {'schema_version', 'status', 'selected_inputs', 'source_identity', 'machine', 'python', 'python_version', 'sys_platform', 'interpreter', 'platform', 'installed_package', 'executables', 'console', 'fixture', 'frontend_scope', 'semantic_execution', 'lowering', 'sequence_artifact', 'empirical_acceptance', 'cases', 'negative_controls', 'cli', 'parent_imports', 'parent_execution_guard', 'counts'}
    assessment_fields = {'schema_version', 'status', 'document_digest', 'program_digest', 'artifact_digest', 'declarations', 'requirements', 'required_features', 'dependencies', 'assumptions', 'unresolved_obligations', 'diagnostics', 'semantic_status', 'target_status', 'lowering', 'artifact'}
    expected_counts = {'assessments': 48, 'fresh_replays': 48, 'forged_replays': 48, 'negative_controls': 20, 'installed_cli': 6}
    scopes = {'frontend_scope': 'independent_native_policy_source_contracts', 'semantic_execution': 'unsupported', 'lowering': 'unsupported', 'sequence_artifact': 'withheld', 'empirical_acceptance': 'not_established'}
    seen: set[tuple[str, int]] = set()
    variants: list[dict[str, Any]] = []
    authority: dict[str, Any] | None = None

    def fingerprint(value: object) -> bool:
        return type(value) is str and len(value) == 64 and all((char in '0123456789abcdef' for char in value))

    def absolute(value: object) -> bool:
        return type(value) is str and Path(value).is_absolute()

    def origins(value: object, package: str, required: set[str]) -> None:
        if type(value) is not dict or not required <= value.keys():
            raise AssertionError('Hosted receipt omits required installed transport origins')
        for name, filename in value.items():
            if not ImportBoundary.guarded(name) or not ImportBoundary.allowed(name) or (not absolute(filename)) or (not Path(filename).is_relative_to(package)):
                raise AssertionError('Hosted receipt has a forbidden or foreign module origin')
    for path in paths:
        value = read_json(path)
        if type(value) is not dict or set(value) != receipt_fields or value.get('schema_version') != 'biocompiler.policy_native_campaign.v0.1' or (value.get('status') != 'passed') or (value.get('counts') != expected_counts) or any((value.get(key) != expected for key, expected in scopes.items())):
            raise AssertionError('Hosted native policy receipt is incomplete or changes its claim scope')
        if value.get('source_identity') != workflow_identity:
            raise AssertionError('Hosted receipt belongs to a different tested revision, head or workflow run')
        version = value.get('python_version')
        if type(version) is not list or len(version) != 3 or (not all((type(part) is int for part in version))) or (version[0] != 3):
            raise AssertionError('Hosted receipt lacks an exact Python version')
        variant = (value.get('sys_platform'), version[1])
        if variant not in expected_variants or variant in seen:
            raise AssertionError('Duplicate or unsupported hosted platform/Python variant')
        seen.add(variant)
        if value.get('machine') != {'linux': 'x86_64', 'darwin': 'arm64'}[variant[0]]:
            raise AssertionError('Hosted receipt has the wrong native machine architecture')
        if not absolute(value.get('interpreter')) or not absolute(value.get('installed_package')) or type(value.get('platform')) is not str or (not value['platform']) or (type(value.get('python')) is not str) or (not value['python']):
            raise AssertionError('Hosted receipt lacks interpreter/platform/install provenance')
        expected_platforms = ('Linux-',) if variant[0] == 'linux' else ('Darwin-', 'macOS-')
        if not value['platform'].startswith(expected_platforms) or not value['python'].startswith(f'3.{version[1]}.'):
            raise AssertionError('Hosted platform/interpreter provenance contradicts its variant')
        package = value['installed_package']
        selected_inputs = value.get('selected_inputs')
        if type(selected_inputs) is not dict or set(selected_inputs) != {'core', 'verify', 'fixture'} or (not all((absolute(item) for item in selected_inputs.values()))):
            raise AssertionError('Hosted selected input provenance is incomplete')
        executables = value.get('executables')
        if type(executables) is not dict or set(executables) != {'core', 'verify'}:
            raise AssertionError('Hosted receipt lacks both native executable identities')
        for role in ('core', 'verify'):
            item = executables[role]
            if type(item) is not dict or set(item) != {'path', 'sha256'} or (not absolute(item['path'])) or (not fingerprint(item['sha256'])):
                raise AssertionError('Hosted executable identity is incomplete')
        pins = {role: executables[role]['sha256'] for role in ('core', 'verify')}
        required_pins = {role: published[variant[0]]['sha256']['biocompiler-' + role] for role in ('core', 'verify')}
        if pins != required_pins or (variant[0] in platform_pins and platform_pins[variant[0]] != pins):
            raise AssertionError('Hosted executable pins differ from published bytes or the same-platform Python pair')
        platform_pins[variant[0]] = pins
        for field in ('console', 'fixture'):
            item = value.get(field)
            if type(item) is not dict or set(item) != {'path', 'sha256'} or (not absolute(item['path'])) or (not fingerprint(item['sha256'])):
                raise AssertionError('Hosted input/console provenance is incomplete')
        if value['fixture']['sha256'] != digest_file(fixture):
            raise AssertionError('Hosted receipt identifies a different frozen input corpus')
        if value.get('parent_execution_guard') is not True:
            raise AssertionError('Parent execution guard was not established')
        origins(value.get('parent_imports'), package, {'biocompiler', 'biocompiler.core_policy', 'biocompiler.core_client'})
        rows = value.get('cases')
        expected_cases = {(name, kind, role) for name in EXPECTED_NAMES for kind in ('program', 'request', 'submission') for role in ('core', 'verify')}
        identities: set[tuple[str, str, str]] = set()
        if type(rows) is not list or len(rows) != 48:
            raise AssertionError('Hosted source assessment census is incomplete')
        for row in rows:
            if type(row) is not dict or set(row) != {'name', 'kind', 'role', 'artifact_digest', 'document_digest', 'program_digest', 'assessment_fingerprint', 'assessment', 'fresh_replay', 'forged_replay'}:
                raise AssertionError('Unexpected hosted assessment row fields')
            identity = (row.get('name'), row.get('kind'), row.get('role'))
            if identity not in expected_cases or identity in identities:
                raise AssertionError('Duplicate or unknown hosted policy case')
            identities.add(identity)
            if row.get('fresh_replay') != 'passed' or row.get('forged_replay') != 'rejected':
                raise AssertionError('Hosted case lacks fresh and rejection replay evidence')
            for key in ('artifact_digest', 'document_digest', 'program_digest', 'assessment_fingerprint'):
                if not fingerprint(row.get(key)):
                    raise AssertionError('Hosted source identity is malformed')
            source = input_rows[row['name'], row['kind']]
            document = source['document']
            if row['artifact_digest'] != source['artifact_digest'] or row['document_digest'] != source['fingerprint']:
                raise AssertionError('Hosted case is not bound to the required frozen input')
            if source['kind'] == 'submission':
                document = document['request']
            program = document['program'] if document['$type'] == 'BuildRequest' else document
            if row['program_digest'] != semantic_digest(program):
                raise AssertionError('Hosted program identity differs from frozen input')
            assessment = row.get('assessment')
            if type(assessment) is not dict or set(assessment) != assessment_fields or canonical_digest(assessment) != row['assessment_fingerprint'] or (assessment.get('schema_version') != 'biocompiler.policy_assessment.v0.1') or (assessment.get('status') != 'valid') or (assessment.get('diagnostics') != []) or any((assessment.get(key) != row[key] for key in ('artifact_digest', 'document_digest', 'program_digest'))) or any((assessment.get(key) != expected for key, expected in {'semantic_status': 'unresolved', 'target_status': 'unassessed', 'lowering': 'unsupported', 'artifact': 'withheld'}.items())):
                raise AssertionError('Hosted assessment differs from its immutable identity or claim scope')
            prefix = {'program': '/document', 'request': '/document/program', 'submission': '/document/request/program'}[source['kind']]
            ledger = [{'id': declaration['id'], 'kind': declaration['$type'], 'path': prefix + '/declarations/' + str(index), 'value': declaration, 'sources': [span for span in program['source_map'] if span['declaration_id'] == declaration['id']]} for index, declaration in enumerate(program['declarations'])]
            if assessment.get('declarations') != ledger or assessment.get('requirements') != [entry for entry in ledger if entry['kind'] == 'Requirement']:
                raise AssertionError('Hosted receipt changed ordered source identity or correspondence')
        controls = value.get('negative_controls')
        if type(controls) is not list or len(controls) != 20 or len({(row['name'], row['role']) for row in controls}) != 20:
            raise AssertionError('Hosted negative-control census is incomplete')
        for row in controls:
            if type(row) is not dict or set(row) != {'name', 'role', 'expected', 'required_diagnostic', 'diagnostics', 'input_digest'}:
                raise AssertionError('Unexpected hosted negative-control fields')
            expected = expected_controls.get((row.get('name'), row.get('role')))
            if expected != (row.get('expected'), row.get('required_diagnostic'), row.get('input_digest')):
                raise AssertionError('Hosted mutation is not bound to the required negative input')
            if row.get('role') not in ('core', 'verify') or row.get('expected') not in ('invalid', 'rejected') or row.get('required_diagnostic') not in row.get('diagnostics', []) or (not fingerprint(row.get('input_digest'))):
                raise AssertionError('Hosted negative control lacks independent rejection evidence')
        cli = value.get('cli')
        expected_cli = {(role, kind) for role in ('core', 'verify') for kind in ('program', 'request', 'submission')}
        if type(cli) is not list or len(cli) != 6 or {(row['role'], row['kind']) for row in cli} != expected_cli:
            raise AssertionError('Hosted installed console census is incomplete')
        for row in cli:
            if type(row) is not dict or set(row) != {'role', 'kind', 'status', 'guard'}:
                raise AssertionError('Unexpected hosted console evidence fields')
            guard = row.get('guard', {})
            if type(guard) is not dict or set(guard) != {'status', 'origins', 'guard_active', 'execution_guard_active', 'python', 'executable'} or row.get('status') != 'passed' or (guard.get('status') != 'ok') or (guard.get('guard_active') is not True) or (guard.get('execution_guard_active') is not True) or (guard.get('python') != version[:2]) or (guard.get('executable') != value['interpreter']):
                raise AssertionError('Installed console guard/interpreter evidence differs')
            origins(guard.get('origins'), package, {'biocompiler.entrypoint', 'biocompiler.policy.cli', 'biocompiler.core_policy', 'biocompiler.core_client'})
        projection = {'counts': value['counts'], 'scopes': scopes, 'fixture_sha256': value['fixture']['sha256'], 'cases': rows, 'negative_controls': controls, 'cli': [{key: row[key] for key in ('role', 'kind', 'status')} for row in cli]}
        if authority is None:
            authority = projection
        elif projection != authority:
            raise AssertionError('Hosted variants disagree on immutable source assessments or diagnostic controls')
        variants.append({'sys_platform': variant[0], 'machine': value['machine'], 'python_version': version, 'receipt_path': str(path.resolve()), 'receipt_sha256': digest_file(path), 'executables': executables, 'console': value['console'], 'interpreter': value['interpreter'], 'platform': value['platform'], 'installed_package': package})
    if seen != expected_variants:
        raise AssertionError('Missing required hosted platform/Python variant')
    return {'schema_version': 'biocompiler.policy_native_comparison.v0.1', 'status': 'passed', 'counts': expected_counts, 'variants': variants, 'source_identity': workflow_identity, 'published_binaries': published, 'source_result_identity': canonical_digest(authority), **scopes, 'claim_scope': 'Exact source-assessment agreement for the retained hosted variants only.'}

def audit_operational(paths: list[Path], native_root: Path, fixture_path: Path, *, audited_identity) -> dict:
    from check_policy_operational import CLI_CASES, SCHEMA, canonical_digest, check_cli_guard, check_import_origins, check_observations, checked_fixture, digest_file, native_manifests, read_json
    identity = dict(audited_identity)
    binaries = native_manifests(native_root, identity['revision'])
    fixture_hash = digest_file(fixture_path)
    fixture = checked_fixture(fixture_path)
    receipts = [read_json(path) for path in paths]
    expected = {(system, machine, python) for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')) for python in ('3.11', '3.14')}
    found = set()
    baseline = None
    for receipt in receipts:
        if type(receipt) is not dict or set(receipt) != {'schema_version', 'revision', 'head_revision', 'run_id', 'run_attempt', 'system', 'machine', 'python_version', 'fixture_sha256', 'binary_sha256', 'package', 'parent_imports', 'cli_guards', 'observations', 'observations_fingerprint', 'python_semantic_authority'} or type(receipt['python_version']) is not str or (type(receipt['run_attempt']) is not str) or (not receipt['run_attempt'].isdecimal()):
            raise AssertionError('Malformed operational campaign receipt')
        slot = (receipt['system'], receipt['machine'], '.'.join(receipt['python_version'].split('.')[:2]))
        if slot not in expected or slot in found:
            raise AssertionError('Missing, duplicated or unexpected operational campaign slot')
        found.add(slot)
        if receipt['schema_version'] != SCHEMA or receipt['fixture_sha256'] != fixture_hash or any((receipt[key] != identity[key] for key in ('revision', 'head_revision', 'run_id'))) or (not 0 < int(receipt['run_attempt']) <= int(identity['run_attempt'])) or (receipt['binary_sha256'] != binaries[receipt['system'].lower()]['sha256']) or (receipt['python_semantic_authority'] != 'forbidden'):
            raise AssertionError('Operational receipt lacks exact current run/source/binary authority')
        observations = receipt['observations']
        if canonical_digest(observations) != receipt['observations_fingerprint']:
            raise AssertionError('Operational receipt observations changed or incomplete')
        check_import_origins(receipt['parent_imports'], receipt['package'], {'biocompiler.core_client', 'biocompiler.core_policy', 'biocompiler.core_policy_operational'})
        if type(receipt['cli_guards']) is not dict or set(receipt['cli_guards']) != set(CLI_CASES):
            raise AssertionError('Missing complete installed CLI guard receipts')
        for guard in receipt['cli_guards'].values():
            check_cli_guard(guard, receipt['package'], receipt['python_version'])
        check_observations(observations, fixture)
        if baseline is not None and canonical_digest(baseline) != canonical_digest(observations):
            raise AssertionError('Complete operational results differ across installed platform/Python slots')
        baseline = observations
    if found != expected:
        raise AssertionError('All four operational campaign slots are required')
    return {'schema_version': SCHEMA, **identity, 'status': 'pass', 'slots': sorted(found), 'fixture_sha256': fixture_hash, 'observations_fingerprint': canonical_digest(baseline), 'claim_scope': 'bounded_abstract_source_execution_only'}

def audit_implementation(paths: list[Path], native_root: Path, fixture_path: Path, *, audited_identity) -> dict:
    from check_policy_implementation import CLI_CASES, SCHEMA, canonical_digest, check_cli_guard, check_import_origins, check_observations, checked_fixture, digest_file, native_manifests, read_json
    identity = dict(audited_identity)
    binaries = native_manifests(native_root, identity['revision'])
    fixture, fixture_hash = (checked_fixture(fixture_path), digest_file(fixture_path))
    expected = {(system, machine, python) for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')) for python in ('3.11', '3.14')}
    found, baseline = (set(), None)
    for path in paths:
        receipt = read_json(path)
        if type(receipt) is not dict or set(receipt) != {'schema_version', 'status', 'revision', 'head_revision', 'run_id', 'run_attempt', 'system', 'machine', 'python_version', 'fixture_sha256', 'binary_sha256', 'package', 'parent_imports', 'cli_guards', 'observations', 'observations_fingerprint', 'python_semantic_authority'} or any((type(receipt[key]) is not str for key in ('system', 'machine', 'python_version', 'run_attempt'))) or (not receipt['run_attempt'].isdecimal()):
            raise AssertionError('Malformed implementation campaign receipt')
        slot = (receipt['system'], receipt['machine'], '.'.join(receipt['python_version'].split('.')[:2]))
        if slot not in expected or slot in found:
            raise AssertionError('Missing, duplicated or unexpected implementation campaign slot')
        found.add(slot)
        if receipt['schema_version'] != SCHEMA or receipt['status'] != 'pass' or receipt['fixture_sha256'] != fixture_hash or any((receipt[key] != identity[key] for key in ('revision', 'head_revision', 'run_id'))) or (not 0 < int(receipt['run_attempt']) <= int(identity['run_attempt'])) or (receipt['binary_sha256'] != binaries[receipt['system'].lower()]['sha256']) or (receipt['python_semantic_authority'] != 'forbidden'):
            raise AssertionError('Implementation receipt lacks exact current run/source/binary authority')
        check_import_origins(receipt['parent_imports'], receipt['package'], {'biocompiler.core_client', 'biocompiler.core_policy', 'biocompiler.core_policy_operational', 'biocompiler.core_policy_implementation'})
        if type(receipt['cli_guards']) is not dict or set(receipt['cli_guards']) != set(CLI_CASES):
            raise AssertionError('Missing complete implementation CLI guard receipts')
        for guard in receipt['cli_guards'].values():
            check_cli_guard(guard, receipt['package'], receipt['python_version'])
        observations = receipt['observations']
        if canonical_digest(observations) != receipt['observations_fingerprint']:
            raise AssertionError('Implementation campaign observations changed or incomplete')
        check_observations(observations, fixture)
        digest = canonical_digest(observations)
        if baseline is not None and baseline != digest:
            raise AssertionError('Complete implementation results differ across installed platform/Python slots')
        baseline = digest
    if found != expected:
        raise AssertionError('All four implementation campaign slots are required')
    return {'schema_version': SCHEMA, **identity, 'status': 'pass', 'slots': sorted(found), 'fixture_sha256': fixture_hash, 'observations_fingerprint': baseline, 'claim_scope': 'bounded_implementation_preservation_only', 'material': 'unassessed', 'export': 'withheld'}

def audit_material(paths: list[Path], native_root: Path, fixture_path: Path, *, audited_identity) -> dict:
    from check_policy_material import CLI_CASES, SCHEMA, authoring_witness, canonical_digest, check_cli_guard, check_import_origins, check_observations, checked_fixture, digest_file, native_manifests, read_json
    if len(paths) != 4:
        raise AssertionError('All four material campaign slots are required exactly once')
    identity = dict(audited_identity)
    binaries = native_manifests(native_root, identity['revision'])
    fixture, fixture_hash = (checked_fixture(fixture_path), digest_file(fixture_path))
    _, authoring = authoring_witness(fixture['request'])
    expected = {(system, machine, python) for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')) for python in ('3.11', '3.14')}
    found, baseline, baseline_observations = (set(), None, None)
    for path in paths:
        receipt = read_json(path)
        if type(receipt) is not dict or set(receipt) != {'schema_version', 'status', 'revision', 'head_revision', 'run_id', 'run_attempt', 'system', 'machine', 'python_version', 'fixture_sha256', 'binary_sha256', 'package', 'authoring', 'parent_imports', 'cli_guards', 'observations', 'observations_fingerprint', 'python_semantic_authority'} or any((type(receipt[key]) is not str for key in ('system', 'machine', 'python_version', 'run_attempt'))) or (not receipt['run_attempt'].isdecimal()):
            raise AssertionError('Malformed material campaign receipt')
        slot = (receipt['system'], receipt['machine'], '.'.join(receipt['python_version'].split('.')[:2]))
        if slot not in expected or slot in found:
            raise AssertionError('Missing, duplicate or unexpected material campaign slot')
        found.add(slot)
        if receipt['schema_version'] != SCHEMA or receipt['status'] != 'pass' or receipt['fixture_sha256'] != fixture_hash or any((receipt[key] != identity[key] for key in ('revision', 'head_revision', 'run_id'))) or (not 0 < int(receipt['run_attempt']) <= int(identity['run_attempt'])) or (receipt['binary_sha256'] != binaries[receipt['system'].lower()]['sha256']) or (receipt['python_semantic_authority'] != 'forbidden') or (canonical_digest(receipt['authoring']) != canonical_digest(authoring)):
            raise AssertionError('Material receipt lacks exact current run/source/binary authority')
        check_import_origins(receipt['parent_imports'], receipt['package'], {'biocompiler.core_client', 'biocompiler.core_policy', 'biocompiler.core_policy_operational', 'biocompiler.core_policy_implementation', 'biocompiler.core_policy_material', 'biocompiler.policy.material'})
        if type(receipt['cli_guards']) is not dict or set(receipt['cli_guards']) != set(CLI_CASES):
            raise AssertionError('Missing complete material CLI guard receipts')
        for name, guard in receipt['cli_guards'].items():
            check_cli_guard(guard, receipt['package'], receipt['python_version'], case=name)
        observations = receipt['observations']
        if canonical_digest(observations) != receipt['observations_fingerprint']:
            raise AssertionError('Material campaign observations changed or incomplete')
        digest = canonical_digest(observations)
        if baseline is not None and baseline != digest:
            raise AssertionError('Complete material results and publication bytes differ across four installed slots')
        if baseline is None:
            baseline_observations = observations
        baseline = digest
    if found != expected:
        raise AssertionError('All four material campaign slots are required')
    check_observations(baseline_observations, fixture)
    return {'schema_version': SCHEMA, **identity, 'status': 'pass', 'slots': sorted(found), 'fixture_sha256': fixture_hash, 'observations_fingerprint': baseline, 'claim_scope': 'bounded_conditional_policy_to_exact_mrna', 'empirical': 'unassessed', 'artifact': 'fresh_native_pair_checked', 'export': 'fresh_original_input_check_only'}

def audit_consumer(paths, producer_paths, native_root, fixture_path, *, audited_identity):
    from check_policy_material_consumer import MODULE_FILES, PRODUCER_ABSENCE, Path, SCHEMA, __file__, check_manifest, check_worker, digest, file_digest, read_json, slot, support, validate_producer
    core, material = support()
    identity = dict(audited_identity)
    audit_material(producer_paths, native_root, fixture_path, audited_identity=audited_identity)
    binaries = core.native_manifests(native_root, identity['revision'])
    fixture = material.checked_fixture(fixture_path)
    producers = {slot(value): (path, value) for path in producer_paths for value in [read_json(path)]}
    expected = {(system, machine, minor) for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')) for minor in ('3.11', '3.14')}
    if len(paths) != 4 or set(producers) != expected:
        raise AssertionError('All four consumer and original producer slots are required exactly once')
    found, baseline = (set(), None)
    checkout = Path(__file__).resolve().parents[1]
    for path in paths:
        receipt = read_json(path)
        fields = {'schema_version', 'status', 'revision', 'head_revision', 'run_id', 'run_attempt', 'system', 'machine', 'python_version', 'fixture_sha256', 'producer_receipt_sha256', 'verify_sha256', 'installed_package', 'installed_modules', 'worker'}
        if type(receipt) is not dict or set(receipt) != fields:
            raise AssertionError('Malformed consumer campaign receipt')
        current = slot(receipt)
        if current not in expected or current in found:
            raise AssertionError('Missing, duplicate or unexpected consumer platform slot')
        found.add(current)
        producer_path, producer = producers[current]
        verify_sha = binaries[receipt['system'].lower()]['sha256']['biocompiler-verify']
        if receipt['schema_version'] != SCHEMA or receipt['status'] != 'pass' or any((receipt[key] != identity[key] for key in ('revision', 'head_revision', 'run_id'))) or (type(receipt['run_attempt']) is not str) or (not receipt['run_attempt'].isdecimal()) or (not 0 < int(receipt['run_attempt']) <= int(identity['run_attempt'])) or (receipt['fixture_sha256'] != file_digest(fixture_path)) or (receipt['producer_receipt_sha256'] != file_digest(producer_path)) or (receipt['verify_sha256'] != verify_sha):
            raise AssertionError('Consumer receipt lacks exact current source/run/original expectation/binary identity')
        inputs = validate_producer(producer, fixture, fixture_path, identity, verify_sha, expected_slot=current)
        manifest = receipt['worker']['stage_manifest']
        package = Path(receipt['installed_package'])
        if not package.is_absolute() or '..' in package.parts or set(receipt['installed_modules']) != set(MODULE_FILES):
            raise AssertionError('Consumer lost installed transport package origins')
        check_manifest(manifest)
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
        check_worker(receipt['worker'], inputs, manifest)
        required_mechanism = 'linux_libseccomp' if receipt['system'] == 'Linux' else 'macos_sandbox_exec'
        if receipt['worker']['network']['mechanism'] != required_mechanism:
            raise AssertionError('Consumer network enforcement belongs to another OS')
        fingerprint = receipt['worker']['observations_fingerprint']
        if baseline is not None and baseline != fingerprint:
            raise AssertionError('Complete fresh consumer outputs differ across four slots')
        baseline = fingerprint
    return {'schema_version': SCHEMA, 'status': 'pass', **identity, 'slots': sorted(found), 'fixture_sha256': file_digest(fixture_path), 'observations_fingerprint': baseline, 'producer_absence': PRODUCER_ABSENCE, 'network': 'os_denied_worker_and_descendants', 'claim_scope': 'fresh_verify_only_bounded_conditional_material_reproduction', 'empirical': 'unassessed'}
