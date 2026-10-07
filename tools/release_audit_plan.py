"""Re-derive inert run plans for explicitly selected complete-release profiles.

The profile is fixed source authority, not supplied by a hosted producer. Its
workflow hash prevents an old scope from accepting changed workflow semantics.
No test discovery, native code, subprocess or network occurs in build_plan.
Read-only Git catalog/identity capture belongs to the CLI before its inert guard.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
import stat
from typing import Any


COMPONENT_SOURCE_ROOTS = ('core', 'src', 'tools', 'protocol', '.github', 'pyproject.toml')
RESEARCHER_SOURCE_ROOTS = ('core', 'src', 'tools', 'protocol', '.github',
                         'data/researcher_alpha', 'examples/researcher_alpha.py', 'pyproject.toml')
STARTER_SOURCE_FILES = ('examples/researcher_alpha.py',
    'docs/researcher-alpha-quickstart.md', 'docs/researcher-alpha-reference-qualification.md',
    'docs/researcher-alpha-review.md', 'docs/researcher-alpha-roadmap.md',
    *("data/researcher_alpha/" + name for name in ('staged-input.json', 'comparison-input.json',
      'expected.json', 'provenance.json', 'qualification.json', 'negative-controls.json')))
BASE_COUNTS = {
    'architecture_policy_comparisons': 6, 'direct_core_groups': 67, 'download_artifacts': 102,
    'installed_campaigns': 17, 'installed_group_receipts': 20, 'installed_runtime_slots': 4,
    'native_executables': 151, 'native_fixtures': 23, 'native_suites': 149,
    'ordinary_receipts': 59, 'physical_jobs': 74, 'required_metadata': 128, 'unit_artifacts': 14,
}


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def derive_component_sources(root: Path, component_source_rows: list[str], tracked: list[str],
                             *, source_roots=COMPONENT_SOURCE_ROOTS, check_census=True) -> dict[str, Any]:
    """Bind exact Git rows to current files, then independently recheck the census."""
    try:
        from .release_audit_component import audit_sources
    except ImportError:
        from release_audit_component import audit_sources
    root = Path(root)
    require(type(tracked) is list and all(type(name) is str for name in tracked)
            and len(tracked) == len(set(tracked)), 'Malformed tracked component source catalog')
    require(type(component_source_rows) is list and component_source_rows,
            'Complete component Git source rows are required')
    expected = {name for name in tracked if any(name == base or
                name.startswith(base + '/') for base in source_roots)}
    result = {}
    for row in component_source_rows:
        require(type(row) is str and row.count('\t') == 1 and not any(char in row for char in '\0\n\r'),
                'Malformed component Git source row')
        header, name = row.split('\t')
        fields = header.split(' ')
        require(len(fields) == 3 and fields[0] in {'100644', '100755'} and fields[1] == 'blob'
                and re.fullmatch(r'[0-9a-f]{40}', fields[2]) is not None, 'Unsupported component Git source metadata')
        mode, _, blob = fields
        require(name and not name.startswith('/') and '\\' not in name
                and all(part not in {'', '.', '..'} for part in name.split('/'))
                and name in expected and name not in result, 'Unsafe, duplicate or out-of-scope component source')
        path = root / name
        require(path.is_file() and not any(parent.is_symlink() for parent in (path, *path.parents)),
                'Missing or redirected component source: ' + name)
        require(path.stat().st_size <= 128 * 1024**2, 'Component source exceeds reviewed bound')
        raw = path.read_bytes()
        require(len(raw) <= 128 * 1024**2
                and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == blob
                and bool(path.stat().st_mode & stat.S_IXUSR) == (mode == '100755'),
                'Component source bytes or executable mode differ from Git: ' + name)
        result[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw),
                        'git_blob': blob, 'mode': mode}
    require(set(result) == expected, 'Component Git rows omit tracked source files')
    if check_census:
        checked = audit_sources(root, audited_sources=result)
        require(checked == result, 'Component source reconstruction differs')
    return dict(sorted(result.items()))


def build_plan(root: Path, *, identity: dict[str, str], tree: str, base: str,
               profile: dict[str, Any], profile_sha256: str,
               tracked: list[str], source_rows: list[str],
               component_source_rows: list[str] | None = None,
               starter_source_rows: list[str] | None = None) -> dict[str, Any]:
    """Caller supplies fresh read-only Git catalogs for authenticated clean H."""
    # Source-root original modules are loaded only after CLI inventory/identity
    # capture. Their exact bytes become this independent source plan's authority.
    import ci_native_bundle
    import ci_core_groups
    import ci_validation
    require(profile['schema'] == 'biocompiler.release_audit_profile.v1'
            and profile['id'] in {'complete-release-v1', 'complete-component-release-v1',
                                  'complete-researcher-alpha-release-v1'},
            'Unsupported audit profile')
    researcher_profile = profile['id'] == 'complete-researcher-alpha-release-v1'
    component_profile = profile['id'] in {'complete-component-release-v1', 'complete-researcher-alpha-release-v1'}
    expected_counts = {**BASE_COUNTS, **({'native_executables': 174, 'native_suites': 171, 'native_fixtures': 26}
        if researcher_profile else {'native_executables': 158, 'native_suites': 156} if component_profile else {})}
    require(type(profile['counts']) is dict and profile['counts'] == expected_counts
            and all(type(value) is int for value in profile['counts'].values()),
            'Complete profile count scope differs')
    require(component_profile or component_source_rows is None, 'Component catalog supplied to the legacy profile')
    require(researcher_profile or starter_source_rows is None, 'Starter catalog supplied to a historical profile')
    require(sha(root / profile['workflow_path']) == profile['workflow_sha256'],
            'Workflow differs from reviewed complete-release profile')
    require(len(tracked) == len(set(tracked)), 'Duplicate Git source catalog')
    require(all((root / name).is_file() and not (root / name).is_symlink() for name in tracked),
            'Audited source checkout must contain every tracked source file')
    inventory_paths = set(tracked) | {path.relative_to(root).as_posix() for path in (root / 'tests').rglob('*.py')}
    inventory = {}
    for name in sorted(inventory_paths):
        path = root / name
        require(path.is_file() and not path.is_symlink(), 'Missing or redirected source file: ' + name)
        inventory[name] = sha(path)
    component_sources = (derive_component_sources(root, component_source_rows, tracked,
                         source_roots=RESEARCHER_SOURCE_ROOTS if researcher_profile else COMPONENT_SOURCE_ROOTS)
                         if component_profile else None)
    starter_sources = (derive_component_sources(root, starter_source_rows, tracked,
                       source_roots=STARTER_SOURCE_FILES, check_census=False) if researcher_profile else None)
    if researcher_profile:
        require(set(starter_sources) == set(STARTER_SOURCE_FILES), 'Starter source catalog is incomplete')
    archive_files = {}
    for row in source_rows:
        metadata, name = row.split('\t'); mode, kind, _ = metadata.split()
        require(kind == 'blob' and mode in ('100644', '100755') and name not in archive_files,
                'Unsupported or duplicate source archive entry')
        path = root / name
        archive_files[name] = {'sha256': sha(path), 'size': path.stat().st_size,
                               'git_mode': mode, 'mode': 0o664 if mode == '100644' else 0o775}
    native_plan = ci_native_bundle.test_plan((root / 'core/test/dune').read_text())
    members = sorted(ci_native_bundle.expected_members(root))
    fixtures = ci_native_bundle.dependency_members(root)
    fixture_pins = {name: {'sha256': sha(root / source), 'size': (root / source).stat().st_size}
                    for name, source in fixtures.items()}
    groups = ci_core_groups.load_plan(root)
    counts = profile['counts']
    require(sha(root / 'core/test/dune') == profile['dune_sha256'], 'Native source plan changed')
    require(ci_core_groups.PLAN_SHA256 == profile['direct_group_plan_sha256'], 'Direct-core plan changed')
    require(len(native_plan) == counts['native_suites'] and len(fixtures) == counts['native_fixtures']
            and len(members) - len(fixtures) == counts['native_executables'], 'Native coverage changed')
    require(len(groups) == counts['direct_core_groups'], 'Direct-core coverage changed')
    require(set(ci_validation.REQUIRED_NEEDS) == set(profile['required_needs']), 'Required final jobs changed')
    require({(r['job'], r['variant']) for r in profile['ordinary_receipts']} == ci_validation.EXPECTED_RECEIPTS,
            'Ordinary receipt coverage changed')
    require({k: list(v) for k, v in ci_validation.CORE_PLATFORMS.items()} == profile['platforms'],
            'Native platform coverage changed')
    for location, expected in profile['policy_comparison_function_pins'].items():
        path, function = location.rsplit(':', 1)
        text = (root / path).read_text()
        node = next(node for node in ast.parse(text).body
                    if isinstance(node, ast.FunctionDef) and node.name == function)
        require(hashlib.sha256(ast.get_source_segment(text, node).encode()).hexdigest() == expected,
                'Original policy comparison body changed; review adapter correspondence: ' + location)
    schemas = {}
    for name, supplied in profile['legacy_comparison_schemas'].items():
        cli, producer = supplied['cli'], supplied['producer']
        text = (root / producer).read_text()
        compare = next(node for node in ast.parse(text).body
                       if isinstance(node, ast.FunctionDef) and node.name == supplied['function'])
        returns = [node for node in compare.body if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)]
        require(len(returns) == 1, 'Legacy comparator return shape changed')
        literal = [value.value for key, value in zip(returns[0].value.keys, returns[0].value.values)
                   if isinstance(key, ast.Constant) and key.value == 'schema_version' and isinstance(value, ast.Constant)]
        require(literal == [supplied['schema_version']], 'Legacy comparator schema changed')
        if producer != cli:
            forwarded_name = 'compare' if 'registration' in cli else 'main'
            forwarded = next(node for node in ast.parse((root / cli).read_text()).body
                             if isinstance(node, ast.FunctionDef) and node.name == forwarded_name)
            expected = ("return providers.tool('pipeline_fixed_registration_runtime').compare(*args, **kwargs)"
                        if forwarded_name == 'compare' else "return tool('pipeline_reference_runtime').main(argv)")
            require(len(forwarded.body) == 1 and ast.unparse(forwarded.body[0]) == expected,
                    'Legacy comparator forwarding changed')
        schemas[name] = {**supplied, 'cli_sha256': sha(root / cli), 'producer_sha256': sha(root / producer),
                         'literal_return_line': returns[0].lineno}
    fields = ('physical_jobs', 'required_needs', 'ordinary_receipts', 'unit_artifacts',
              'permitted_artifact_names', 'required_metadata_names', 'download_artifact_names',
              'native_environment_paths', 'platforms', 'legacy_comparison_receipts')
    plan = {'schema': 'biocompiler.release_audit_plan.v1', 'status': 'prepared_not_executed',
            'identity': identity, 'tree': tree, 'base': base, 'profile': profile['id'],
            'profile_sha256': profile_sha256, 'counts': dict(counts), **{key: profile[key] for key in fields},
            'source_inventory': inventory, 'source_archive_files': archive_files,
            'native_plan': native_plan, 'native_members': members, 'fixture_pins': fixture_pins,
            'dune_sha256': profile['dune_sha256'], 'direct_groups': groups,
            'direct_group_plan_sha256': profile['direct_group_plan_sha256'],
            'legacy_comparison_schemas': schemas, 'limitations': profile['limitations']}
    if component_profile:
        plan['component_sources'] = component_sources
    if researcher_profile:
        plan['starter_sources'] = starter_sources
    for field, count in [('physical_jobs', 'physical_jobs'), ('ordinary_receipts', 'ordinary_receipts'),
                         ('unit_artifacts', 'unit_artifacts'), ('download_artifact_names', 'download_artifacts'),
                         ('required_metadata_names', 'required_metadata')]:
        require(len(plan[field]) == counts[count], 'Complete profile census changed: ' + field)
    return plan
