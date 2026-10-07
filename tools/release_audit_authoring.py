"""Additive, inert release auditing for public typed researcher authoring.

The historical researcher adapter remains unchanged. This profile delegates to
its retained-byte checks only after requiring the exact reviewed typed census.
All source functions are additionally pinned by the independently prepared plan.
No source authoring, native checker, hosted assembler or Git helper runs here.
"""
from __future__ import annotations

from release_audit_researcher import _require, audit_installed_profiles as _audit_installed_profiles
from release_audit_researcher import audit_starter as _audit_starter

CASE_IDS = ('staged', 'comparison')
PROJECT_IDS = (*CASE_IDS, 'authored')
OBSERVATIONS = tuple(case + '-' + name for case in CASE_IDS for name in (
    'preflight', 'compile-core', 'export-verify', 'reverify-verify', 'paired-publication',
    'changed-candidate', 'changed-fasta', 'changed-originals')) + (
    'staged-insufficient-capacity', 'staged-capacity-no-publication',
    'staged-completion-without-feedback', 'incomplete-reference') + tuple(
    'authored-' + name for name in ('preflight', 'compile-core', 'export-verify',
    'reverify-verify', 'paired-publication', 'changed-originals',
    'completion-without-feedback', 'completion-no-publication',
    'catalog-authorization', 'catalog-no-publication'))
INPUTS = tuple('data/researcher_alpha/' + name for name in (
    'staged-input.json', 'comparison-input.json', 'expected.json', 'provenance.json',
    'qualification.json', 'negative-controls.json')) + (
    'examples/researcher_alpha.py', 'src/biocompiler/policy/research_project.py',
    'examples/author_staged_research_project.py', 'src/biocompiler/policy/component_inputs.py')
EVIDENCE_FILES = tuple(sorted(
    ['researcher-alpha/' + name + '.json' for name in OBSERVATIONS]
    + ['researcher-alpha/' + case + suffix for case in PROJECT_IDS for suffix in ('-project.json', '.zip')]
    + ['researcher-alpha/' + case + '-changed-' + kind + '.zip'
       for case in CASE_IDS for kind in ('candidate', 'fasta')]))
INSTALLED_SCHEMA = 'biocompiler.researcher_alpha_installed_campaign.v0.2'


def check_profile_sources():
    """Refuse a historical, partial or broadened validator under this profile."""
    import check_researcher_alpha_installed as installed
    import researcher_alpha_starter as starter
    from release_audit_plan import AUTHORING_STARTER_SOURCE_FILES

    source = installed.researcher
    _require(installed.SCHEMA == INSTALLED_SCHEMA
             and source.SCHEMA == 'biocompiler.researcher_alpha_sdk_development.v0.2'
             and installed.FOLDER == 'researcher-alpha'
             and source.CASE_IDS == CASE_IDS and source.PROJECT_IDS == PROJECT_IDS
             and source.OBSERVATIONS == OBSERVATIONS and source.INPUTS == INPUTS,
             'Typed researcher source profile differs')
    _require(installed.COPY_INPUTS == tuple(name for name in INPUTS if not name.startswith('src/'))
             and len(OBSERVATIONS) == 30 and len(EVIDENCE_FILES) == 40 and len(INPUTS) == 10,
             'Typed researcher input or retained evidence census differs')
    _require(len(starter.SOURCE_FILES) == 12
             and set(starter.SOURCE_FILES) == set(AUTHORING_STARTER_SOURCE_FILES)
             and starter.researcher_evidence_files() == EVIDENCE_FILES,
             'Typed researcher starter source or retained evidence census differs')


def audit_installed_profiles(*args, **kwargs):
    """Preserve staged and all original researcher checks, adding typed scope."""
    check_profile_sources()
    result = _audit_installed_profiles(*args, **kwargs)
    _require(set(result['researcher_originals']) == set(INPUTS)
             and result['researcher_project']['schema_version'] == INSTALLED_SCHEMA
             and set(result['researcher_project']['inputs']) == set(INPUTS),
             'Reconstructed typed researcher comparison scope differs')
    check_profile_sources()
    return result


def audit_starter(*args, **kwargs):
    """Require the complete receipt-relative evidence handoff without copies."""
    check_profile_sources()
    result = _audit_starter(*args, **kwargs)
    _require(result['schema_version'] == 'biocompiler.researcher_alpha_starter.v0.2'
             and len(result['files']) == 58
             and {name for name in result['files'] if name.startswith('evidence/researcher-alpha/')}
                 == {'evidence/' + name for name in EVIDENCE_FILES}
             and not any(name.startswith('verified-examples/') for name in result['files']),
             'Reconstructed typed researcher starter scope differs')
    check_profile_sources()
    return result

# Closed source-function authority for this additive profile. The older profile's
# pins remain unchanged in release_audit_researcher and its original JSON file.
SOURCE_FUNCTION_PINS = {'tools/check_policy_component_fixture.py:validate': 'eb9b1f1ec59ff3a0a5b87c78f4f20ba0751abe6731d06a8c0bf7ea4d23a75d87',
 'tools/check_policy_component_material.py:compare_installed': 'ae6193fa956b28bf679b91ecd72d00cb031c40765b9890988093e763a9384800',
 'tools/check_policy_component_material.py:validate_installed': 'b1c0cf46478fd228aab8a8b7bb5dc09edd8967d75bb81c5e5ddea1265e0132b6',
 'tools/check_policy_core.py:compare_receipts': '820cd55c349691218abdd04e616fc18ede3e79f8b6cc867fe1f71008572e011b',
 'tools/check_policy_development.py:source_snapshot': '3f72c19c070beac560cbcf3a1f31688df47a9f078b8c0a74aa4c1a9fd6185c60',
 'tools/check_policy_implementation.py:compare': 'e61bd5055f3d0d73f1dab4df5232891611d2a602a00a1d88551295fae94ca97e',
 'tools/check_policy_material.py:compare': 'b6c58ba74e603bad00b3b8aae509355cb841e8236ab488c25b1fc1b96651a438',
 'tools/check_policy_material_consumer.py:compare': '30d3ca8643cb24c46964f23bcc16b77b146477dafea2cd878db3dee72d488ee5',
 'tools/check_policy_material_consumer.py:validate_component_producer': '685165a98b68ad70333ad0c8e8a1ceb84b400b44c96ae6623268e35f355f3221',
 'tools/check_policy_material_prebuilt.py:check_commands': '8bc3d1888b75cc2327ebbaad880cee2ca4e158b5e9e9bcd3a4814031bf795e6a',
 'tools/check_policy_material_prebuilt.py:component_authorities': '23a217446ad05f69a75ff456e751b74dc9015c6e998955e0ef598fa6a059a518',
 'tools/check_policy_material_prebuilt.py:component_inputs': '5b37252bcd2bd8dd65eddfb354b144bc5d506aee693f3afe819e3aaac3805ef2',
 'tools/check_policy_material_prebuilt.py:researcher_identity': '7945ffab5bae34e17446919fdf9fe67993d35bf5da342cbaf2d1d81a14ba1733',
 'tools/check_policy_material_prebuilt.py:staged_identity': 'e23dffcc5792f030c9c234e4900f4444ef12ce255de4d014268c2fec2167bd0a',
 'tools/check_policy_material_prebuilt.py:verify_slot': 'ee5a4902928d87709a580498e42b02171596b7693a1f16a6b6e2ce24284e3ca3',
 'tools/check_policy_operational.py:compare': 'ea04128df0e6d828de9f8bb8d9ed4b7a9e0038d9d7813da6d28fbd0e99320814',
 'tools/check_policy_staged_material_installed.py:check_observations': '1b8eb7f1e3e92895bc0e7f4d624975d563cb7e68ab0bd292eac2db7aac55e9fe',
 'tools/check_policy_staged_material_installed.py:compare_installed': 'c960ee089fd8bc4677ec005d4ee62125985e790b470c6cf14a6091b98751c7ab',
 'tools/check_policy_staged_material_installed.py:input_pins': 'bbbe9efc28de280c066f52396c23496e170f67789e1553d8ef990bd07f62d2e4',
 'tools/check_policy_staged_material_installed.py:validate_installed': '47d7352dc47c3a9707d6a9ce6d95dc80dcd6ef63ab6ef060eef11c055a689f57',
 'tools/check_researcher_alpha.py:authored_original': '20625b6c7070481163cef64a61aebad76fdaa65da039dc3eceff225323596a3f',
 'tools/check_researcher_alpha.py:catalog_request': 'd371ebaddceee772a8f0bcfbb12e326216c9422e37a31e6e27e049233679bda3',
 'tools/check_researcher_alpha.py:check_authored_observations': 'b4f3324a762cf1b87d257751f3db2732278bff6d98bf2b520d91cfd06391b7e6',
 'tools/check_researcher_alpha.py:check_catalog_failure': '3bb48f73ce76ee94f862363ad7c7389218a0f432fedc98af03105d3d98bcdd87',
 'tools/check_researcher_alpha.py:check_census': '9727fcc6a5e5fc9e034dbde642c08f1fba5433856ec081484370a2f2364779eb',
 'tools/check_researcher_alpha.py:check_observations': '3fdf2437cb9af7afb30c5b2c5e5cc55d1bc12a23d4c14121646e904961562747',
 'tools/check_researcher_alpha.py:checked_assets': '2998b69b3e45fa30eefdf29c6e4ba19078c213cde05313e430009e08c12989d6',
 'tools/check_researcher_alpha.py:checked_result': '06aaae0ca46f28c3d2386826fe89aebe85adf6d0144631ebfe36252bba09e157',
 'tools/check_researcher_alpha.py:completion_request': '6376f9a2722784517efa006099e95c7734c2a970cde83fa140edf3a5492581ed',
 'tools/check_researcher_alpha.py:exact_json': '49d7878013d2488df9bd08feb3dcd70b6ffc378b6d0f460d05b45de2eacec0dc',
 'tools/check_researcher_alpha.py:expected_authored_project': 'b5539a5bee9ef1ea6a2ec416379aa8ef1f50a358c21a3c6dac5033161dbdff79',
 'tools/check_researcher_alpha.py:expected_project': 'ea00ae940a95be4259a4a7eba0042c9dec399df37eb89642a70947266aa1d332',
 'tools/check_researcher_alpha_installed.py:check_mutant': '8bb0bbabecae72cf64d7123409c253cd1a7c4ea19196f3e6c6e5012722478abf',
 'tools/check_researcher_alpha_installed.py:check_origins': '028faee38c1ba811b34a7125107951420b0c960ca4c5e37e1cc879f1b2b42293',
 'tools/check_researcher_alpha_installed.py:compare_installed': '64c3d318928e9a156ebee6a1b400f978ebbb969bf8870c940daf5c7e2883ee30',
 'tools/check_researcher_alpha_installed.py:expected_project': '0d64ae7966f80f7a1dc337e5427b47bd8c38418bf526df362409682205f10ee4',
 'tools/check_researcher_alpha_installed.py:input_pins': '4c14086054db4ba0e955ed9008ce32b41b4948c1ae445ffd43ad186d635fb8a8',
 'tools/check_researcher_alpha_installed.py:validate_installed': 'ca6709f1b8fa9b47071208b391e88c8a4a515cc35cb2c1bb52fd0604048ac9b8',
 'tools/researcher_alpha_starter.py:plan': 'b9fc60740352b5d9fc378b129ab1c1fba0d0f44e3d0da22793de47582212a318',
 'tools/researcher_alpha_starter.py:researcher_evidence_files': 'ab68352e6608600e0859ebdf0cc5c6c1740336c33630b6a00564b5d47997a75f'}
