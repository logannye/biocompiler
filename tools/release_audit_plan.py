"""Re-derive inert run plans for the single versioned complete-release profile.

The profile is fixed source authority, not supplied by a hosted producer. Its
workflow hash prevents an old scope from accepting changed workflow semantics.
No test discovery, native code, subprocess or network occurs in build_plan.
Read-only Git catalog/identity capture belongs to the CLI before its inert guard.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build_plan(root: Path, *, identity: dict[str, str], tree: str, base: str,
               profile: dict[str, Any], profile_sha256: str,
               tracked: list[str], source_rows: list[str]) -> dict[str, Any]:
    """Caller supplies fresh read-only Git catalogs for authenticated clean H."""
    # Source-root original modules are loaded only after CLI inventory/identity
    # capture. Their exact bytes become this independent source plan's authority.
    import ci_native_bundle
    import ci_core_groups
    import ci_validation
    require(profile['schema'] == 'biocompiler.release_audit_profile.v1'
            and profile['id'] == 'complete-release-v1', 'Unsupported audit profile')
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
            'profile_sha256': profile_sha256, **{key: profile[key] for key in fields},
            'source_inventory': inventory, 'source_archive_files': archive_files,
            'native_plan': native_plan, 'native_members': members, 'fixture_pins': fixture_pins,
            'dune_sha256': profile['dune_sha256'], 'direct_groups': groups,
            'direct_group_plan_sha256': profile['direct_group_plan_sha256'],
            'legacy_comparison_schemas': schemas, 'limitations': profile['limitations']}
    for field, count in [('physical_jobs', 'physical_jobs'), ('ordinary_receipts', 'ordinary_receipts'),
                         ('unit_artifacts', 'unit_artifacts'), ('download_artifact_names', 'download_artifacts'),
                         ('required_metadata_names', 'required_metadata')]:
        require(len(plan[field]) == counts[count], 'Complete profile census changed: ' + field)
    return plan
