"""Fresh-process authoring imports retain the original closed import boundaries."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PolicyAuthoringImportTests(unittest.TestCase):
    def fresh(self, source: str) -> None:
        # A clean interpreter is essential: an already-loaded forbidden module
        # would not pass through the actual campaign import guard again.
        prelude = """
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root / 'src'), str(root)]
import subprocess
def forbidden_process(*args, **kwargs):
    raise AssertionError('Importing an authoring facade must not execute a process')
subprocess.run = forbidden_process
subprocess.Popen = forbidden_process
assert not any(name == 'biocompiler' or name.startswith('biocompiler.') for name in sys.modules)
"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-B", "-c", textwrap.dedent(prelude) + textwrap.dedent(source), str(ROOT)],
                cwd=directory, text=True, capture_output=True, timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def guarded_imports(self, guard_module: str, *, execution_guard: bool) -> None:
        self.fresh(f"""
from {guard_module} import ImportBoundary
boundary = ImportBoundary(root / 'src')
sys.meta_path.insert(0, boundary)
if {execution_guard!r}:
    sys.settrace(boundary.trace)
import biocompiler.policy as policy
from biocompiler.policy import refinement, quantitative_assurance
assert policy.refinement is refinement
assert policy.quantitative_assurance is quantitative_assurance
assert callable(refinement.check) and callable(refinement.replay)
assert callable(quantitative_assurance.QuantitativeAssuranceRequest)
for module in (policy, refinement, quantitative_assurance):
    before = set(sys.modules)
    assert set(module.__all__).issubset(dir(module))
    try:
        getattr(module, 'not_a_public_export')
    except AttributeError:
        pass
    else:
        raise AssertionError('Unknown name acquired an export')
    assert set(sys.modules) == before
origins = boundary.origins()
assert boundary.denied == []
assert {{'biocompiler.policy', 'biocompiler.policy.refinement',
         'biocompiler.policy.quantitative_assurance'}}.issubset(origins)
assert not any(name.startswith('biocompiler.core_') for name in origins)
sys.settrace(None)
""")

    def test_plain_and_facade_imports_preserve_installed_authoring_guard(self) -> None:
        self.guarded_imports("tools.check_policy_install", execution_guard=False)

    def test_plain_and_facade_imports_preserve_source_campaign_guard(self) -> None:
        self.guarded_imports("tools.check_policy_core", execution_guard=True)

    def test_optional_namespaces_are_real_modules_loaded_only_when_requested(self) -> None:
        self.fresh("""
import importlib
from types import ModuleType
import biocompiler.policy as policy
names = ('refinement', 'quantitative', 'quantitative_composition', 'module_linking',
         'approximation', 'realization_evidence', 'quantitative_assurance')
assert set(names).issubset(policy.__all__)
assert set(names).issubset(dir(policy))
assert all('biocompiler.policy.' + name not in sys.modules for name in names)
assert not any(name.startswith('biocompiler.core_') for name in sys.modules)
for name in names:
    module = getattr(policy, name)
    assert isinstance(module, ModuleType)
    assert module is importlib.import_module('biocompiler.policy.' + name)
    assert getattr(policy, name) is module
""")

    def test_explicit_transport_exports_preserve_class_identity_and_signatures(self) -> None:
        self.fresh("""
import inspect
from biocompiler.policy import refinement, quantitative_assurance
assert 'biocompiler.core_policy_refinement' not in sys.modules
assert 'biocompiler.core_policy_quantitative_assurance' not in sys.modules
assert list(inspect.signature(refinement.check).parameters) == ['request', 'candidate', 'limits', 'client', 'cancelled']
assert list(inspect.signature(refinement.replay).parameters) == ['request', 'candidate', 'limits', 'report', 'client', 'cancelled']
assert list(inspect.signature(quantitative_assurance.QuantitativeAssuranceRequest).parameters) == [
    'material_request', 'approximation', 'realization_evidence', 'max_work']
for name in ('compile', 'check', 'replay', 'export'):
    assert inspect.signature(getattr(quantitative_assurance, name)).parameters['cancelled'].default is None
refinement_class = refinement.PolicyRefinementClient
from biocompiler import core_policy_refinement
assert refinement_class is core_policy_refinement.PolicyRefinementClient
for name in ('Stage', 'Relation', 'PremiseKind', 'DerivationRule', 'StageIdentity', 'RefinementScope',
             'RefinementClaim', 'RefinementPremise', 'RefinementDerivation', 'RefinementEvidence',
             'PolicyRefinementResult', 'PolicyRefinementClient'):
    assert getattr(refinement, name) is getattr(core_policy_refinement, name)
assurance_class = quantitative_assurance.PolicyQuantitativeAssuranceClient
from biocompiler import core_policy_quantitative_assurance
assert assurance_class is core_policy_quantitative_assurance.PolicyQuantitativeAssuranceClient
assert quantitative_assurance.PolicyQuantitativeAssuranceResult is core_policy_quantitative_assurance.PolicyQuantitativeAssuranceResult
for name in ('MAX_WORK', 'REQUEST_SCHEMA', 'REQUEST_PROFILE'):
    assert getattr(quantitative_assurance, name) == getattr(core_policy_quantitative_assurance, name)
""")

    def test_typed_assurance_request_retains_validated_independent_snapshots(self) -> None:
        self.fresh("""
import json
from copy import deepcopy
from biocompiler.policy import quantitative_assurance as facade
original = json.loads((root / 'core/test/data/policy_quantitative_network_v01.json').read_text())['request']
saved = deepcopy(original)
request = facade.QuantitativeAssuranceRequest(original)
snapshot = request.to_data()
assert snapshot == {'schema_version': facade.REQUEST_SCHEMA, 'profile': facade.REQUEST_PROFILE,
    'material_request': saved, 'approximation': None, 'realization_evidence': None, 'max_work': facade.MAX_WORK}
original['budgets']['max_work'] = 1
snapshot['material_request']['budgets']['max_work'] = 2
snapshot['max_work'] = 1
assert request.to_data()['material_request'] == saved
assert request.to_data()['max_work'] == facade.MAX_WORK
from biocompiler.core_client import CoreProtocolError
for maximum in (0, True, facade.MAX_WORK + 1):
    try:
        facade.QuantitativeAssuranceRequest(saved, max_work=maximum)
    except CoreProtocolError:
        pass
    else:
        raise AssertionError('Typed facade bypassed the unchanged transport limit')
""")


if __name__ == "__main__":
    unittest.main()
