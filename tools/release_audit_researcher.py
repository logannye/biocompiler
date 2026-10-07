"""Additive inert auditing for the staged and researcher installed profiles.

The sole source-body adapter preserves current ``verify_slot`` checks and only
replaces component source authority with the independently authenticated catalog.
All other delegation is to pinned, retained-byte validators. No hosted runner,
Git helper, package producer, native process or network operation is invoked.
The caller must authenticate identity, sources, original ZIPs and supplied wheel
bytes before using this module; successful audit does not establish empirical
function or release acceptance.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

from release_audit_component import _source_rows, audit_component_inputs, audit_sources


def _require(value, message):
    if not value:
        raise AssertionError(message)


def audit_installed_profiles(directories, staged_path, researcher_path, identity,
                             binary_authorities, *, audited_sources):
    """Independently reconstruct both four-slot comparisons from retained bytes."""
    import check_policy_staged_material_installed as staged
    import check_researcher_alpha_installed as researcher

    directories = [Path(path) for path in directories]
    _require(len(directories) == 4 and len(set(directories)) == 4,
             "Four distinct installed evidence directories are required")
    _require(staged.ROOT == researcher.ROOT, "Installed validators use different source roots")
    sources = audit_sources(staged.ROOT, audited_sources=audited_sources)
    staged_originals = staged.input_pins()
    researcher_originals = researcher.input_pins()
    result = {
        "staged_originals": staged_originals,
        "staged_material": staged.compare_installed(
            [path / "evidence/staged-material.json" for path in directories],
            staged_path, identity, binary_authorities, expected_sources=sources),
        "researcher_originals": researcher_originals,
        "researcher_project": researcher.compare_installed(
            [path / "evidence/researcher-alpha.json" for path in directories],
            researcher_path, identity, binary_authorities, expected_sources=sources),
    }
    _require(audit_sources(staged.ROOT, audited_sources=audited_sources) == sources
             and staged.input_pins() == staged_originals
             and researcher.input_pins() == researcher_originals,
             "Installed original/source authority changed during audit")
    return result


def _starter_sources(root, catalog):
    """Validate a distinct, externally authenticated starter source catalog."""
    import researcher_alpha_starter as starter

    root = Path(root)
    _source_rows(catalog)  # Strict, closed Git/byte metadata shape.
    _require(set(catalog) == set(starter.SOURCE_FILES), "Incomplete starter source catalog")
    result = {}
    for name in starter.SOURCE_FILES:
        path = root / name
        _require(all(not parent.is_symlink() for parent in (path, *path.parents)),
                 "Redirected starter source path")
        raw = starter.read(path)
        actual = {**starter.pin(raw),
                  "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                  "mode": "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"}
        _require(actual == catalog[name], "Starter source differs from authenticated catalog: " + name)
        result[name] = starter.pin(raw)
    return result


def audit_starter(directory, args, comparison, natives, *, source_root, audited_sources):
    """Reconstruct the pure copy plan and check the exact inert handoff contents.

    ``comparison`` and ``natives`` are independently reconstructed results from
    this audit, not claims imported from the starter's own manifest. The source
    catalog is separate from the development snapshot because it includes the
    four distributed documents. This never calls the hosted assembler.
    """
    import researcher_alpha_starter as starter

    directory, source_root = Path(directory), Path(source_root)
    sources = _starter_sources(source_root, audited_sources)
    files, expected = starter.plan(args, comparison, natives, root=source_root)
    _require(all(expected["files"][name] == value for name, value in sources.items()),
             "Starter source bytes changed during reconstruction")
    _require(directory.is_dir() and not directory.is_symlink(), "Missing or redirected starter")
    expected_names = set(files) | {"manifest.json"}
    expected_directories = {parent.as_posix() for name in expected_names
                            for parent in Path(name).parents if parent != Path(".")}
    # Check directories too: redirected or extra empty trees must not be hidden
    # behind an otherwise correct file-only census. Stop at the declared bound.
    found_files, found_directories = set(), set()
    pending = [directory]
    while pending:
        parent = pending.pop()
        for path in parent.iterdir():
            name = path.relative_to(directory).as_posix()
            _require(not path.is_symlink(), "Redirected retained starter member")
            if path.is_dir():
                _require(name in expected_directories and name not in found_directories,
                         "Unexpected retained starter directory")
                found_directories.add(name)
                pending.append(path)
            else:
                _require(path.is_file() and name in expected_names and name not in found_files,
                         "Unexpected retained starter member")
                found_files.add(name)
    _require(found_files == expected_names and found_directories == expected_directories,
             "Incomplete retained starter census")
    manifest_raw = (json.dumps(expected, sort_keys=True, indent=2) + "\n").encode()
    _require(starter.read(directory / "manifest.json") == manifest_raw,
             "Retained starter manifest differs from reconstructed plan")
    for name, source in files.items():
        original = starter.read(source)
        _require(starter.pin(original) == expected["files"][name]
                 and starter.read(directory / name) == original,
                 "Retained starter copy differs from authenticated input: " + name)
    _require(_starter_sources(source_root, audited_sources) == sources
             and all(starter.pin(starter.read(source)) == expected["files"][name]
                     for name, source in files.items()),
             "Starter authority changed during audit")
    return expected

# Exact reviewed original function bodies, additionally bound by whole source
# files in the prepared plan. Legacy profile pins remain unchanged.
SOURCE_FUNCTION_PINS = {'tools/check_policy_material_prebuilt.py:check_commands': '8bc3d1888b75cc2327ebbaad880cee2ca4e158b5e9e9bcd3a4814031bf795e6a',
 'tools/check_policy_material_prebuilt.py:researcher_identity': '7945ffab5bae34e17446919fdf9fe67993d35bf5da342cbaf2d1d81a14ba1733',
 'tools/check_policy_material_prebuilt.py:staged_identity': 'e23dffcc5792f030c9c234e4900f4444ef12ce255de4d014268c2fec2167bd0a',
 'tools/check_policy_material_prebuilt.py:verify_slot': 'ee5a4902928d87709a580498e42b02171596b7693a1f16a6b6e2ce24284e3ca3',
 'tools/check_policy_staged_material_installed.py:check_observations': '1b8eb7f1e3e92895bc0e7f4d624975d563cb7e68ab0bd292eac2db7aac55e9fe',
 'tools/check_policy_staged_material_installed.py:compare_installed': 'c960ee089fd8bc4677ec005d4ee62125985e790b470c6cf14a6091b98751c7ab',
 'tools/check_policy_staged_material_installed.py:input_pins': 'bbbe9efc28de280c066f52396c23496e170f67789e1553d8ef990bd07f62d2e4',
 'tools/check_policy_staged_material_installed.py:validate_installed': '47d7352dc47c3a9707d6a9ce6d95dc80dcd6ef63ab6ef060eef11c055a689f57',
 'tools/check_researcher_alpha.py:check_census': '9727fcc6a5e5fc9e034dbde642c08f1fba5433856ec081484370a2f2364779eb',
 'tools/check_researcher_alpha.py:check_observations': '450e61fc1d35cda8e2238ea630f66eced8ef65274dfc6221d1770a73c8b62d29',
 'tools/check_researcher_alpha.py:checked_assets': '2998b69b3e45fa30eefdf29c6e4ba19078c213cde05313e430009e08c12989d6',
 'tools/check_researcher_alpha_installed.py:check_mutant': '8bb0bbabecae72cf64d7123409c253cd1a7c4ea19196f3e6c6e5012722478abf',
 'tools/check_researcher_alpha_installed.py:check_origins': '3dc89c5a164a98b47a013faf51960d836c9fba6a6d9a07def3cee963151f2d3d',
 'tools/check_researcher_alpha_installed.py:compare_installed': '64c3d318928e9a156ebee6a1b400f978ebbb969bf8870c940daf5c7e2883ee30',
 'tools/check_researcher_alpha_installed.py:expected_project': '3225e4fbd9efdc247d5ccd5bc2218f8c4841c0ae2cb045389b35b770488dfb26',
 'tools/check_researcher_alpha_installed.py:input_pins': '4c14086054db4ba0e955ed9008ce32b41b4948c1ae445ffd43ad186d635fb8a8',
 'tools/check_researcher_alpha_installed.py:validate_installed': 'a6c16485bad318cb51df7d428962814d9e024cbf947ce23090ae499501d9c724',
 'tools/researcher_alpha_starter.py:plan': '3525f292b77adc23de8c500281d0394e8ed214efa746ab3a0aa2df13acab25ef'}


def audit_prebuilt_slot(directory, identity, candidate_path, sdk, sdk_entries, sdk_stamp, native_data, fixture, component_authority=None, *, staged_path=None, researcher_path=None, audited_sources):
    from check_policy_material_prebuilt import CASES, COMPONENT_CASES, COMPONENT_CLAIM, COMPONENT_EVIDENCE, COMPONENT_SCHEMA, EVIDENCE, MAX_JSON, PROBE_SCHEMA, Path, RESEARCHER_CLAIM, RESEARCHER_EVIDENCE, RESEARCHER_SCHEMA, ROOT, SCHEMA, STAGED_CLAIM, STAGED_EVIDENCE, STAGED_SCHEMA, authority_receipt, build, canonical, check_commands, check_component_controls, check_ownership, check_rejection, component_inputs, consumer, mutation_files, pin, prior_attempt, re, read_json, require, researcher_identity, same, source_pins, staged_identity
    value = read_json(directory / 'prebuilt.json')
    required = {'schema_version', 'status', *identity, 'system', 'machine', 'python_version', 'output_root', 'checkout_root', 'fixture', 'source_pins', 'artifacts', 'evidence', 'commands', 'cases', 'claim', 'python_semantic_authority', 'network', 'default_cutover'}
    if component_authority is not None:
        required |= {'component_originals', 'component_cases'}
    require(staged_path is None or component_authority is not None, 'Staged slot requires component authority')
    if staged_path is not None:
        required |= {'staged_originals'}
    require(researcher_path is None or staged_path is not None, 'Researcher slot requires preserved staged authority')
    if researcher_path is not None:
        required |= {'researcher_originals'}
    schema = RESEARCHER_SCHEMA if researcher_path is not None else STAGED_SCHEMA if staged_path is not None else COMPONENT_SCHEMA if component_authority is not None else SCHEMA
    claim = RESEARCHER_CLAIM if researcher_path is not None else STAGED_CLAIM if staged_path is not None else COMPONENT_CLAIM if component_authority is not None else 'supplied_prebuilt_material_profile_only'
    require(type(value) is dict and set(value) == required and (value['schema_version'] == schema) and (value['status'] == 'pass') and prior_attempt(value, identity), 'Stale, failed or incomplete prebuilt slot')
    slot = consumer.slot(value)
    require(slot in {(row[0], row[1], minor) for row in build.TARGETS.values() for minor in ('3.11', '3.14')}, 'Unexpected runtime slot')
    target = next((name for name, row in build.TARGETS.items() if row[:2] == slot[:2]))
    native = native_data[target]
    require(same(value['artifacts'], authority_receipt(candidate_path, sdk, sdk_stamp, native)) and same(value['source_pins'], source_pins()) and same(value['fixture'], pin(fixture)) and (value['cases'] == list(CASES)) and (value['claim'] == claim) and (value['python_semantic_authority'] == 'forbidden') and (value['network'] == 'consumer_required_os_denial') and (value['default_cutover'] == 'unassessed'), 'Prebuilt slot authority or scope differs')
    evidence_names = EVIDENCE + (COMPONENT_EVIDENCE if component_authority is not None else ()) + (STAGED_EVIDENCE if staged_path is not None else ()) + (RESEARCHER_EVIDENCE if researcher_path is not None else ())
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
    if staged_path is not None:
        import check_policy_staged_material_installed as staged
        require(same(value['staged_originals'], staged.input_pins()), 'Staged original authority differs')
        producer = data['staged-material']
        staged_identity(producer, {**identity, 'run_attempt': value['run_attempt']}, expected_binary, slot, ownership, authority['sources'])
        require(producer['python_version'] == value['python_version'], 'Staged child runtime differs')
        staged.validate_installed(producer, directory / 'evidence', staged_path, identity, expected_binary, expected_sources=authority['sources'], expected_slot=slot)
    if researcher_path is not None:
        import check_researcher_alpha_installed as researcher
        require(same(value['researcher_originals'], researcher.input_pins()), 'Researcher original authority differs')
        producer = data['researcher-alpha']
        researcher_identity(producer, {**identity, 'run_attempt': value['run_attempt']}, expected_binary, slot, ownership, authority['sources'])
        require(producer['python_version'] == value['python_version'], 'Researcher child runtime differs')
        researcher.validate_installed(producer, directory / 'evidence', researcher_path, identity, expected_binary, expected_sources=authority['sources'], expected_slot=slot)
    check_commands(directory, read_json(directory / 'commands.json'), origin, ownership, fixture, value, component_authority=component_authority[slot[:2]] if component_authority is not None else None, staged_path=staged_path, researcher_path=researcher_path)
    return (slot, data)
