"""Real CLI children with an explicitly selected Python protocol fixture.

These tests establish CLI transport, ordering and presentation, not native
semantic correctness. Full hosted OCaml campaigns remain mandatory.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from biocompiler.core_workflow import effective_resources, presentation_capability_profile
from biocompiler.core_workflow_authority import capability_profile as authority_profile
from test_core_workflow import canonical, fixture_records, capabilities as workflow_capabilities
from test_core_workflow_authority import capabilities as authority_capabilities

ROOT = Path(__file__).resolve().parents[1]

# A separate executable implements only fixed byte fixtures and protocol
# receipts. It never invokes a Python workflow evaluator or constructor.
CHILD = r'''
import hashlib,json,os,sys
from pathlib import Path
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def sha(x): return hashlib.sha256(x).hexdigest()
def desc(x): return {'bytes':len(x),'sha256':sha(x)}
config=json.loads(Path(__file__).with_suffix('.json').read_bytes())
control=json.load(sys.stdin); action=control['operation']; role=config['role']
def reply(result,status='ok',diagnostics=None):
 print(json.dumps({'protocol':'biocompiler.core.v1','request_id':control['request_id'],
  'operation':action,'status':status,'result':result,'diagnostics':diagnostics or [],
  'core':{'implementation':'ocaml','version':'0.1.0','protocol':'biocompiler.core.v1','executable':role}}))
 sys.exit(0 if status=='ok' else 2)
if action=='capabilities': reply(config['capabilities'])
assert sys.argv[1]=='--artifact-fds-v1' and len(sys.argv)==5
source=os.fdopen(int(sys.argv[2]),'rb').read()
historical=None if sys.argv[3]=='-' else os.fdopen(int(sys.argv[3]),'rb').read()
with Path(config['log']).open('a') as log:
 log.write(json.dumps({'operation':action,'source_sha256':sha(source),
  'record_sha256':None if historical is None else sha(historical),
  'command':control['payload']['operation_payload'].get('command')})+'\n')
if config.get('reject')==action:
 reply(None,'error',[{'code':config.get('code','workflow_source'),
  'message':config.get('message','Fixture source authority rejected.'),'path':'authority'}])
request=json.loads(source); authority_only=action=='validate-verification-workflow-authority'
profile=config['authority_profile'] if authority_only else config['presentation_profile']
record=config['record']; output=canonical(request if authority_only else record)
receipt={'schema_version':('biocompiler.core.verification_workflow_authority_result.v1' if authority_only else 'biocompiler.core.verification_workflow_result.v2'),
 'profile':profile['profile'],'operation':action,'executable':role,'request_id':control['request_id'],
 'validation_scope':profile['validation_scope'],'implementation_version':profile['implementation_version'],
 'workflow_version':profile['workflow_version'],'workflow_operation':request['operation'],'mode':request['mode'],
 'authority_fingerprint':sha(canonical(request)),
 'request_fingerprint':sha(canonical(request if authority_only else record['request'])),
 'resources':config['resources']}
if not authority_only:
 receipt.update(retained_record_fingerprint=None if historical is None else sha(canonical(json.loads(historical))),
  record_fingerprint=sha(output),command=control['payload']['operation_payload']['command'],
  presentation=config['presentation'])
with os.fdopen(int(sys.argv[4]),'wb') as out: out.write(output)
if authority_only and config.get('change_source'):
 Path(config['change_source']).write_text('{"changed":"after preflight"}')
reply({'schema_version':'biocompiler.core.artifact_response.v1','transport':control['payload']['transport'],
 'authority':desc(source),'retained_record':None if historical is None else desc(historical),
 'artifact':desc(output),'result':receipt})
'''

GUARDED_MAIN = r'''
from contextlib import ExitStack
import sys
from unittest.mock import patch
from biocompiler.cli import main
from biocompiler.compiler.verification_workflow import SyntheticVerificationRequest,SyntheticVerificationRecord
from biocompiler.verification.exploration import BooleanContactConfig,BooleanInputConfig,ExplorationReport,BooleanInputExplorationReport,ReductionResult
from biocompiler.verification.evidence import CheckResult
def forbidden(*args,**kwargs): raise AssertionError('Selected CLI executed legacy workflow semantics')
with ExitStack() as guard:
 for cls in (SyntheticVerificationRequest,SyntheticVerificationRecord,BooleanContactConfig,BooleanInputConfig,ExplorationReport,BooleanInputExplorationReport,ReductionResult):
  for name in ('from_dict','from_json','__post_init__'):
   if hasattr(cls,name): guard.enter_context(patch.object(cls,name,forbidden))
 for cls,names in ((ExplorationReport,ExplorationReport._derived),(BooleanContactConfig,('state_count','possible_histories')),(CheckResult,('passed',))):
  for name in names: guard.enter_context(patch.object(cls,name,property(forbidden)))
 for name in ('run_synthetic_verification','replay_synthetic_verification'):
  guard.enter_context(patch('biocompiler.cli.'+name,forbidden))
 sys.exit(main(sys.argv[1:]))
'''


class NativeWorkflowCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = fixture_records()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="biocompiler-workflow-cli-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.binary = self.root / "fixture-core"
        self.binary.write_text(f"#!{sys.executable}\n" + CHILD)
        self.binary.chmod(0o700)
        self.request = self.root / "request.json"
        self.historical = self.root / "historical.json"
        self.output = self.root / "output.json"
        self.log = self.root / "calls.jsonl"
        self.configure(self.records[0])

    def configure(self, record, *, role="core", **options):
        caps = workflow_capabilities()
        authority = authority_capabilities()
        caps["operations"].extend(authority["operations"][1:])
        caps["validation_scopes"].extend(authority["validation_scopes"])
        caps["profiles"].update(authority["profiles"])
        action, result = record["request"]["operation"], record["result"]
        passed = (result["outcome"] == "pass" if action == "check" else
                  result["all_passed"] if action == "explore" else result["one_minimal"])
        self.config = {"role": role, "capabilities": caps, "authority_profile": authority_profile(),
            "presentation_profile": presentation_capability_profile(), "record": deepcopy(record),
            "resources": effective_resources(), "log": str(self.log),
            "presentation": {"profile": "biocompiler.core.verification_workflow.presentation.v1",
                "command_exit_code": 0 if passed else 1,
                "original_frames": len(result["original_history"]) if action == "reduce" else None,
                "reduced_frames": len(result["history"]) if action == "reduce" else None}, **options}
        self.request.write_bytes(json.dumps(record["request"], ensure_ascii=False, indent=2).encode())
        self.historical.write_bytes(canonical(record))
        self.log.unlink(missing_ok=True)
        self.save_config()

    def save_config(self):
        self.binary.with_suffix(".json").write_bytes(canonical(self.config))

    def command(self, *, replay=False, output=True):
        command = (["synthetic-replay", str(self.historical), "--expected-request", str(self.request)] if replay else
            ["synthetic-" + self.config["record"]["request"]["operation"], "--request", str(self.request)])
        if output:
            command.extend(("--output", str(self.output)))
        return command

    def invoke(self, command=None, *, selected=True, option=None):
        argv = self.command() if command is None else command
        if selected:
            argv = [*argv, option or ("--verify-executable" if self.config["role"] == "verify" else "--core-executable"), str(self.binary)]
        return subprocess.run([sys.executable, "-c", GUARDED_MAIN, *argv], cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, timeout=20)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_all_six_complete_pairs_both_roles_with_original_summary_and_publication(self):
        for role in ("core", "verify"):
            for record in self.records:
                with self.subTest(role=role, operation=record["request"]["operation"], mode=record["request"]["mode"]):
                    self.configure(record, role=role)
                    original = subprocess.run([sys.executable, "-m", "biocompiler", *self.command()],
                        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, timeout=20)
                    original_output = self.output.read_bytes()
                    selected = self.invoke()
                    self.assertEqual((selected.returncode, selected.stdout, selected.stderr),
                                     (original.returncode, original.stdout, original.stderr))
                    self.assertEqual(self.output.read_bytes(), original_output)
                    self.assertEqual([row["operation"] for row in self.calls()], ["run-verification-workflow"])
                    self.assertEqual(self.calls()[0]["command"], "synthetic-" + record["request"]["operation"])

    def test_replay_all_six_pairs_preflights_then_freshly_replays_original_bytes(self):
        for record in self.records:
            self.configure(record, role="verify")
            self.config["presentation"]["command_exit_code"] = 0
            self.save_config()
            original_source = self.request.read_bytes()
            process = self.invoke(self.command(replay=True))
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Fresh execution reproduced", json.loads(process.stdout)["replay"])
            calls = self.calls()
            self.assertEqual([row["operation"] for row in calls],
                ["validate-verification-workflow-authority", "replay-verification-workflow"])
            self.assertEqual([row["source_sha256"] for row in calls],
                [hashlib.sha256(original_source).hexdigest()] * 2)
            self.assertIsNone(calls[0]["record_sha256"])
            self.assertEqual(calls[1]["record_sha256"], hashlib.sha256(self.historical.read_bytes()).hexdigest())

    def test_preflight_failure_precedes_missing_historical_file_and_preserves_message(self):
        self.configure(self.records[0], reject="validate-verification-workflow-authority")
        self.historical.unlink()
        self.output.write_text("original destination")
        process = self.invoke(self.command(replay=True))
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stdout, b"")
        self.assertEqual(process.stderr, b"biocompiler: Fixture source authority rejected.\n")
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.output.read_text(), "original destination")

    def test_source_is_not_reread_after_preflight(self):
        self.config.update(change_source=str(self.request))
        self.config["presentation"]["command_exit_code"] = 0
        self.save_config()
        original = self.request.read_bytes()
        process = self.invoke(self.command(replay=True))
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertNotEqual(self.request.read_bytes(), original)
        self.assertEqual([c["source_sha256"] for c in self.calls()], [hashlib.sha256(original).hexdigest()] * 2)

    def test_native_exit_and_reduction_counts_are_projected_without_inference(self):
        self.config["presentation"]["command_exit_code"] = 1
        self.save_config()
        process = self.invoke()
        self.assertEqual(process.returncode, 1, process.stderr)
        self.configure(self.records[3])
        self.config["presentation"].update(command_exit_code=0, original_frames=997, reduced_frames=991)
        self.save_config()
        process = self.invoke()
        self.assertEqual(process.returncode, 0, process.stderr)
        summary = json.loads(process.stdout)
        self.assertEqual((summary["original_frames"], summary["reduced_frames"]), (997, 991))

    def test_native_command_rejection_preserves_diagnostic_message(self):
        self.configure(self.records[0], reject="run-verification-workflow",
            code="workflow_protocol_command", message="Command and frozen verification operation disagree.")
        argv = self.command()
        argv[0] = "synthetic-reduce"
        process = self.invoke(argv)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stderr, b"biocompiler: Command and frozen verification operation disagree.\n")
        self.assertEqual(self.calls()[0]["command"], "synthetic-reduce")
        self.assertFalse(self.output.exists())

    def test_hidden_options_do_not_change_help_and_are_mutually_exclusive(self):
        for command in ("synthetic-check", "synthetic-explore", "synthetic-reduce", "synthetic-replay"):
            process = self.invoke([command, "--help"], selected=False)
            self.assertEqual(process.returncode, 0)
            for option in (b"--core-executable", b"--verify-executable", b"--core-sha256", b"--core-timeout"):
                self.assertNotIn(option, process.stdout)
        process = self.invoke([*self.command(), "--verify-executable", str(self.binary)])
        self.assertEqual(process.returncode, 2)
        self.assertIn(b"not allowed with argument", process.stderr)
        self.assertEqual(self.calls(), [])

    def test_invalid_controls_and_unavailable_binary_fail_closed_before_execution(self):
        for options, message in (
                (["--core-timeout", "1"], b"require an explicit executable"),
                (["--core-sha256", "0" * 64], b"require an explicit executable"),
                (["--core-executable", "relative"], b"explicit absolute executable path"),
                (["--core-executable", str(self.binary), "--core-timeout", "nan"], b"finite positive"),
                (["--core-executable", str(self.binary), "--core-sha256", "wrong"], b"lowercase SHA-256"),
                (["--core-executable", str(self.root / "missing")], b"not executable")):
            process = self.invoke([*self.command(), *options], selected=False)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertIn(message, process.stderr)
            self.assertTrue(process.stderr.startswith(b"biocompiler: "))
            self.assertEqual(process.stdout, b"")
            self.assertEqual(self.calls(), [])

    def test_input_utf8_and_size_errors_precede_native_transport(self):
        for data, message in ((b"\xff", b"utf-8"), (b" " * (16 * 1024 * 1024 + 1), b"Input JSON exceeds the size limit.")):
            self.request.write_bytes(data)
            process = self.invoke()
            self.assertEqual(process.returncode, 2)
            self.assertIn(message, process.stderr)
            self.assertEqual(self.calls(), [])

    def test_source_syntax_errors_match_original_exactly(self):
        for payload in (b"{", b" ", b'{"duplicate":1,"duplicate":2}', b'{"value":NaN}'):
            self.request.write_bytes(payload)
            original = subprocess.run([sys.executable, "-m", "biocompiler", *self.command()],
                cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, timeout=20)
            selected = self.invoke()
            self.assertEqual((selected.returncode, selected.stdout, selected.stderr),
                             (original.returncode, original.stdout, original.stderr))
            self.assertEqual(self.calls(), [])

    def test_historical_syntax_error_matches_original_after_native_preflight(self):
        self.historical.write_bytes(b"{")
        original = subprocess.run([sys.executable, "-m", "biocompiler", *self.command(replay=True)],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, timeout=20)
        selected = self.invoke(self.command(replay=True))
        self.assertEqual((selected.returncode, selected.stdout, selected.stderr),
                         (original.returncode, original.stdout, original.stderr))
        self.assertEqual([row["operation"] for row in self.calls()], ["validate-verification-workflow-authority"])

    def test_publication_protection_runs_after_native_execution_and_preserves_authority(self):
        original = self.request.read_bytes()
        argv = [*self.command(output=False), "--output", str(self.request)]
        process = self.invoke(argv)
        self.assertEqual(process.returncode, 2)
        self.assertEqual(process.stderr, b"biocompiler: A report cannot overwrite its independent input authority.\n")
        self.assertEqual(self.request.read_bytes(), original)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(list(self.root.glob(".*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
