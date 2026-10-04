"""Missing or non-successful CI work must never produce a green merge gate."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_validation as ci


class ValidationGateTests(unittest.TestCase):
    def core_commands(self, block):
        from tools.ci_core_groups import load_plan
        run = "python tools/ci_core_groups.py run --output generated/core/command-groups --workers 2"
        check = "python tools/ci_core_groups.py check --output generated/core/command-groups"
        self.assertEqual(block.count(run), 1)
        self.assertEqual(block.count(check), 1)
        self.assertLess(block.index("tools/ci_native_bundle.py restore"), block.index(run))
        self.assertLess(block.index(run), block.index(check))
        self.assertLess(block.index(check), block.index("Record successful complete ocaml-core"))
        return "\n".join(row["run"] for row in load_plan(Path(__file__).resolve().parents[1]))

    def installed_commands(self, block):
        # Commands moved into one source-pinned driver; assert its actual pure
        # plan and the required YAML invocation, rather than synthetic text.
        from tools import prebuilt_release_pipeline as driver
        self.assertIn('needs: [ocaml-build, prebuilt-core-assembly]', block)
        self.assertIn('python tools/prebuilt_release_pipeline.py installed', block)
        self.assertLess(block.index('python tools/prebuilt_release_pipeline.py installed'),
            block.index('Record successful complete installed-campaigns'))
        for value in ('--sdk ', '--native ', '--environment "$RUNNER_TEMP/',
                      '--source-revision "$GITHUB_HEAD_SHA"', '--tested-revision "$GITHUB_SHA"',
                      '--run-id "$GITHUB_RUN_ID"', '--platform ${{ matrix.platform }}'):
            self.assertIn(value, block)
        ownership={'package_root':'/fresh/site/biocompiler_core','source_revision':'a'*40,
            'tested_revision':'b'*40,'native_platform':'linux-x86_64','files':{
                'bin/biocompiler-'+role:{'path':'/fresh/site/biocompiler_core/bin/biocompiler-'+role,
                    'sha256':str(index)*64} for index,role in enumerate(('core','verify'),1)}}
        rows=driver.campaign_plan(Path('/checkout'),Path('/fresh/bin/python'),ownership,Path('/evidence'))
        self.assertEqual(len(rows),17)
        result={Path(command[1]).name:(name,command) for name,command in rows}
        self.assertEqual(len(result),len(rows))
        for name,command in rows:
            self.assertEqual(command[0],'/fresh/bin/python')
            self.assertEqual(command[-2:],['--output','/evidence/'+name+'.json'])
            for role in ('core','verify'):
                self.assertEqual(command[command.index('--'+role)+1],ownership['files']['bin/biocompiler-'+role]['path'])
            if name not in ('protocol','routing'):
                for role in ('core','verify'):
                    self.assertEqual(command[command.index('--'+role+'-sha256')+1],ownership['files']['bin/biocompiler-'+role]['sha256'])
                self.assertEqual(command[command.index('--native-root')+1],ownership['package_root'])
                self.assertEqual(command[command.index('--platform')+1],'linux-x86_64')
        return result

    def test_callback_manager_compact_corpus_preserves_exact_original_authorities(self):
        root = Path(__file__).resolve().parents[1]
        full_path = root / 'tests/conformance/fixed-pipeline-literals-v1.json'
        full_raw = full_path.read_bytes()
        full = json.loads(full_raw)
        compact = json.loads((root / 'tests/conformance/fixed-pipeline-native-v1.json').read_bytes())
        self.assertEqual(compact['full_corpus']['sha256'], hashlib.sha256(full_raw).hexdigest())
        self.assertEqual(compact['full_corpus']['inventory_fingerprint'], full['inventory_fingerprint'])
        self.assertEqual(compact['document_directory'], full['document_directory'])
        ids = ('tests/test_component_pipeline.py::fixture.setUpClass/event/0',
            'tests/test_temporal_components.py::fixture.setUpClass/event/0',
            'tests/test_synthetic_design_workflows.py::fixture.setUpClass/event/0')
        for identity in ids:
            with self.subTest(case=identity):
                original = [row for row in full['cases'] if row['id'] == identity]
                selected = [row for row in compact['cases'] if row['id'] == identity]
                self.assertEqual(len(original), 1)
                self.assertEqual(selected, original)
                source = root / 'tests/conformance' / compact['document_directory'] / (selected[0]['authority']+'.json')
                value = json.loads(source.read_bytes())
                canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
                self.assertEqual(hashlib.sha256(canonical).hexdigest(), selected[0]['authority'])
        def nodes(value):
            pending, total = [value], 0
            while pending:
                item = pending.pop()
                total += 1
                if isinstance(item, dict):
                    total += len(item)
                    pending.extend(item.values())
                elif isinstance(item, list):
                    pending.extend(item)
            return total
        self.assertEqual(nodes(full), 2_023_131)
        self.assertEqual(nodes(compact), 83_007)
        self.assertLess(nodes(compact), 1_000_000)
        source = (root / 'core/test/test_pipeline_callback_manager.ml').read_text()
        self.assertIn('Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000', source)

    def fixture(self):
        expected = {"revision": "a" * 40, "run_id": "123", "run_attempt": "2"}
        needs = {job: {"result": "success"} for job in ci.REQUIRED_NEEDS}
        receipts = [{"schema_version": "biocompiler.ci_job_receipt.v0.1", **expected,
                     "job": job, "variant": variant, "status": "success",
                     "system": ci.RUNTIME_VARIANTS.get(variant, ci.CORE_PLATFORMS.get(variant, ("Linux", "x86_64")))[0],
                     "machine": ci.RUNTIME_VARIANTS.get(variant, ci.CORE_PLATFORMS.get(variant, ("Linux", "x86_64")))[1],
                     "python_version": (ci.RUNTIME_VARIANTS[variant][2] + ".7" if variant in ci.RUNTIME_VARIANTS
                                        else variant + ".7" if variant in ci.PYTHONS else "3.12.1")}
                    for job, variant in sorted(ci.EXPECTED_RECEIPTS)]
        accounting = [{"schema": "biocompiler.unittest_shard_accounting.v1",
                       "revision": expected["revision"], "python_version": version + ".7",
                       "status": "pass", "total_tests": 10, "shard_count": 5,
                       "expected_shards": 5, "verified_shards": list(range(5)),
                       "discovered_count": 10, "executed_count": 10,
                       "executed_ids": ["tests.test_" + str(index) for index in range(10)],
                       "shard_seconds": {str(index): 10.0 for index in range(5)},
                       "result_digests": [str(index) * 64 for index in range(5)],
                       "plan_fingerprint": "c" * 64,
                       "discovery_digest": "b" * 64} for version in ci.PYTHONS]
        return needs, receipts, accounting, expected

    def test_requires_independent_job_outcomes_despite_success_receipts(self):
        for state in ("failure", "cancelled", "skipped", "in_progress", None):
            with self.subTest(state=state):
                args = self.fixture()
                args[0]["unit-tests"]["result"] = state
                result = ci.validate(*args)
                self.assertEqual(result["status"], "fail")
                self.assertIn("prerequisite_not_successful:unit-tests", result["problems"])

    def test_all_required_jobs_and_variants_must_exist_exactly_once(self):
        self.assertEqual(ci.validate(*self.fixture())["status"], "pass")
        for mutation in ("missing_job", "unexpected_job", "missing_receipt", "duplicate_receipt",
                         "missing_python", "duplicate_python", "empty_tests", "missing_shard"):
            with self.subTest(mutation=mutation):
                needs, receipts, accounts, authority = self.fixture()
                if mutation == "missing_job":
                    needs.pop("installed-architecture")
                elif mutation == "unexpected_job":
                    needs["unregistered"] = {"result": "success"}
                elif mutation == "missing_receipt":
                    receipts.pop()
                elif mutation == "duplicate_receipt":
                    receipts.append(deepcopy(receipts[0]))
                elif mutation == "missing_python":
                    accounts.pop()
                elif mutation == "duplicate_python":
                    accounts.append(deepcopy(accounts[0]))
                elif mutation == "empty_tests":
                    accounts[0]["total_tests"] = 0
                else:
                    accounts[0]["shard_count"] = 4
                self.assertEqual(ci.validate(needs, receipts, accounts, authority)["status"], "fail")

    def test_stale_revision_run_python_or_accounting_cannot_pass(self):
        for field, value in (("revision", "c" * 40), ("run_id", "124"),
                             ("run_attempt", "3"), ("python_version", "3.9.0")):
            with self.subTest(field=field):
                args = self.fixture()
                target = next(item for item in args[1] if item["variant"] in ci.PYTHONS)
                target[field] = value
                self.assertEqual(ci.validate(*args)["status"], "fail")
        for change in ({"revision": "d" * 40}, {"status": "fail"}, {"python_version": "3.10.1"}):
            args = self.fixture()
            args[2][0].update(change)
            self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_preserved_success_from_same_run_retry_requires_real_job_success(self):
        args = self.fixture()
        args[1][0]["run_attempt"] = "1"
        self.assertEqual(ci.validate(*args)["status"], "pass")
        args[0][args[1][0]["job"]]["result"] = "cancelled"
        self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_accounting_must_retain_complete_inventory_authority_and_timings(self):
        for field, value in (("schema", "unknown"), ("executed_ids", []),
                             ("executed_ids", ["repeated"] * 10), ("executed_count", 9),
                             ("discovered_count", 9), ("verified_shards", [0, 1, 2, 3]),
                             ("result_digests", []), ("plan_fingerprint", ""),
                             ("discovery_digest", None), ("shard_seconds", {"0": 1}),
                             ("shard_seconds", {str(index): float("nan") for index in range(5)})):
            with self.subTest(field=field, value=value):
                args = self.fixture()
                args[2][0][field] = value
                self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_workflow_registry_detects_unaccounted_new_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ci.yml"
            base = "name: Test\njobs:\n" + "".join("  " + key + ":\n    runs-on: ubuntu-latest\n"
                for key in sorted(ci.REQUIRED_NEEDS | {"validation"}))
            path.write_text(base)
            self.assertEqual(ci.workflow_jobs(path), ci.REQUIRED_NEEDS | {"validation"})
            for extra in ("  forgotten_job:\n    runs-on: ubuntu-latest\n", "  inline: {}\n", "  validation:\n"):
                path.write_text(base + extra)
                with self.assertRaises(ValueError):
                    ci.workflow_jobs(path)

    def test_forged_start_identity_and_wrong_runtime_are_rejected(self):
        authority = self.fixture()[3]
        with patch.dict("os.environ", {"GITHUB_JOB": "installed-executable"}), \
             patch.object(ci.platform, "python_version", return_value="3.11.7"):
            start = ci.start_job("installed-executable", "3.11", authority)
            receipt = ci.finish_job(start, authority)
            self.assertEqual(receipt["status"], "success")
            self.assertGreaterEqual(receipt["duration_seconds"], 0)
            with self.assertRaises(ValueError):
                ci.finish_job({**start, "revision": "wrong"}, authority)
            with self.assertRaises(ValueError):
                ci.start_job("installed-executable", "3.14", authority)

    def test_duplicate_json_keys_and_non_object_receipts_cannot_hide_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text('{"status":"fail","status":"success"}')
            with self.assertRaises(ValueError):
                ci.read_json(path)
            path.write_text('{"duration_seconds":NaN}')
            with self.assertRaises(ValueError):
                ci.read_json(path)
            path.write_text(json.dumps({"status": "success"}))
            self.assertEqual(ci.read_json(path), {"status": "success"})
        args = self.fixture()
        args[1].append([])
        args[2].append(None)
        self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_native_platform_must_match_its_registered_variant(self):
        args = self.fixture()
        native = next(item for item in args[1] if item["job"] == "ocaml-core" and item["variant"] == "macos-arm64")
        native["machine"] = "x86_64"
        self.assertIn("wrong_core_platform:('ocaml-core', 'macos-arm64')", ci.validate(*args)["problems"])
        with patch.dict("os.environ", {"GITHUB_JOB": "ocaml-core"}), \
             patch.object(ci.platform, "system", return_value="Darwin"), \
             patch.object(ci.platform, "machine", return_value="x86_64"):
            with self.assertRaises(ValueError):
                ci.start_job("ocaml-core", "macos-arm64", args[3])

    def test_architecture_core_comparison_requires_success_and_exact_receipt(self):
        job = "architecture-core-reproducibility"
        self.assertIn(job, ci.REQUIRED_NEEDS)
        self.assertIn((job, "cross-platform"), ci.EXPECTED_RECEIPTS)
        for mutation in ("missing_job", "failure", "skipped", "cancelled", "missing_receipt",
                         "duplicate_receipt", "wrong_variant", "stale_revision"):
            with self.subTest(mutation=mutation):
                needs, receipts, accounts, authority = self.fixture()
                receipt = next(item for item in receipts if item["job"] == job)
                if mutation == "missing_job":
                    needs.pop(job)
                elif mutation in {"failure", "skipped", "cancelled"}:
                    needs[job]["result"] = mutation
                elif mutation == "missing_receipt":
                    receipts.remove(receipt)
                elif mutation == "duplicate_receipt":
                    receipts.append(deepcopy(receipt))
                elif mutation == "wrong_variant":
                    receipt["variant"] = "cross-python"
                else:
                    receipt["revision"] = "f" * 40
                self.assertEqual(ci.validate(needs, receipts, accounts, authority)["status"], "fail")

    def test_realization_matrix_requires_both_pythons_on_both_native_platforms(self):
        expected = {f"{name}-py{version}" for name in ci.CORE_PLATFORMS for version in ci.PYTHONS}
        self.assertEqual(set(ci.REALIZATION_VARIANTS), expected)
        for variant in expected:
            for field, invalid in (("system", "wrong"), ("machine", "wrong"), ("python_version", "3.10.9")):
                with self.subTest(variant=variant, field=field):
                    args = self.fixture()
                    receipt = next(row for row in args[1] if row["job"] == "realization-conformance" and row["variant"] == variant)
                    receipt[field] = invalid
                    self.assertIn("wrong_realization_runtime:" + str(("realization-conformance", variant)),
                                  ci.validate(*args)["problems"])
        authority = self.fixture()[3]
        with patch.dict("os.environ", {"GITHUB_JOB": "realization-conformance"}), \
             patch.object(ci.platform, "system", return_value="Darwin"), \
             patch.object(ci.platform, "machine", return_value="arm64"), \
             patch.object(ci.platform, "python_version", return_value="3.11.7"):
            self.assertEqual(ci.start_job("realization-conformance", "macos-arm64-py3.11", authority)["variant"],
                             "macos-arm64-py3.11")
            with self.assertRaisesRegex(ValueError, "runtime differs"):
                ci.start_job("realization-conformance", "macos-arm64-py3.14", authority)

    def test_secondary_python_cannot_relabel_native_job_runtime(self):
        authority = self.fixture()[3]
        with patch.dict("os.environ", {"GITHUB_JOB": "ocaml-core"}), \
             patch.object(ci.platform, "system", return_value="Linux"), \
             patch.object(ci.platform, "machine", return_value="x86_64"), \
             patch.object(ci.platform, "python_version", return_value="3.11.7") as version:
            start = ci.start_job("ocaml-core", "linux-x86_64", authority)
            version.return_value = "3.14.0"
            with self.assertRaisesRegex(ValueError, "runtime changed"):
                ci.finish_job(start, authority)

    def test_complete_workflow_campaign_is_required_before_matrix_receipts(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        matrix = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:", 1)[0]
        commands = ["tools/check_pipeline_session_install.py", "tools/check_realization_protocol.py", "tools/check_realization_routing.py",
                    "tools/check_native_workflow.py", "tools/check_native_workflow_presentation.py",
                    "tools/check_native_workflow_authority.py", "tools/check_native_workflow_public_sdk.py", "tools/check_native_workflow_cli.py",
                    "tools/check_native_synthetic_producer.py", "tools/check_native_synthetic_public_sdk.py",
                    "tools/check_native_synthetic_selection_cli.py", "tools/check_native_synthetic_inspection.py"]
        planned=self.installed_commands(matrix)
        for command in commands:
            self.assertIn(Path(command).name,planned)
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:", 1)[0]
        for command in ("tools/check_pipeline_session_install.py --compare", "tools/check_realization_reproducibility.py", "tools/check_workflow_reproducibility.py",
                        "tools/check_native_workflow_presentation.py --compare", "tools/check_native_workflow_authority.py --compare", "tools/check_native_workflow_public_sdk.py --compare", "tools/check_native_workflow_cli.py --compare",
                        "tools/check_native_synthetic_producer.py --compare", "tools/check_native_synthetic_public_sdk.py --compare",
                        "tools/check_native_synthetic_selection_cli.py --compare", "tools/check_native_synthetic_inspection.py --compare"):
            self.assertIn(command, comparison)
            self.assertLess(comparison.index(command), comparison.index("Record successful complete comparison"))
        self.assertIn("generated/realization-reproducibility/*.json", comparison)

    def test_public_synthetic_authority_suite_is_a_hosted_native_gate(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        native = text.split("\n  ocaml-core:\n", 1)[1].split("\n  architecture-sdk:\n", 1)[0]
        native = self.core_commands(native)
        self.assertIn("core/_build/default/test/test_synthetic_producer_public_protocol.exe | tee generated/core/test_synthetic_producer_public_protocol.txt", native)
        self.assertIn('core/_build/default/test/test_synthetic_inspection_protocol.exe "$GITHUB_WORKSPACE/tests/conformance/synthetic-inspection-supplemental-v1.json" "$GITHUB_WORKSPACE/protocol/synthetic-inspection-v1.json" | tee generated/core/test_synthetic_inspection_protocol.txt', native)

    def test_reference_foundation_suites_are_required_on_both_native_platforms(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / ".github/workflows/ci.yml").read_text()
        native = text.split("\n  ocaml-core:\n", 1)[1].split("\n  architecture-sdk:\n", 1)[0]
        self.assertEqual(ci.workflow_jobs(root / ".github/workflows/ci.yml"), ci.REQUIRED_NEEDS | {"validation"})
        # Preserve every original slot and require the separated execution jobs.
        self.assertEqual(len(ci.EXPECTED_RECEIPTS) + 2 + 10 + 2 + 1, 68)
        for platform in ci.CORE_PLATFORMS:
            self.assertEqual(native.count("            platform: " + platform + "\n"), 1)
        self.assertIn("runs-on: ${{ matrix.runner }}", native)
        self.assertIn("      fail-fast: false", native)
        runtest = text.split("\n  ocaml-native-tests:\n", 1)[1].split("\n  ocaml-core:", 1)[0]
        for variable, relative in (("BIOCOMPILER_ARCHIVE_PYTHON311_CORPUS", "tests/conformance/archive-container-311.json"),
                                   ("BIOCOMPILER_ARCHIVE_PYTHON314_CORPUS", "tests/conformance/archive-container-314.json"),
                                   ("BIOCOMPILER_REFERENCE_PACKAGE_PYTHON311_CORPUS", "tests/conformance/reference-package-domains-311.json"),
                                   ("BIOCOMPILER_REFERENCE_PACKAGE_PYTHON314_CORPUS", "tests/conformance/reference-package-domains-314.json"),
                                   ("BIOCOMPILER_REFERENCE_SEQUENCE_EXPORT_CORPUS", "tests/conformance/reference-sequence-export-314.json"),
                                   ("BIOCOMPILER_REFERENCE_INPUTS_CORPUS", "tests/conformance/reference-inputs-311.json"),
                                   ("BIOCOMPILER_REFERENCE_PACKAGE_WORKFLOW_CORPUS", "tests/conformance/reference-packages-311.json"),
                                   ("BIOCOMPILER_REFERENCE_CONTRACTS_DOCUMENTS", "tests/conformance/reference-contracts-v1"),
                                   ("BIOCOMPILER_REFERENCE_CONTRACTS_CORPUS", "tests/conformance/reference-contracts-v1.json"),
                                   ("BIOCOMPILER_REFERENCE_PIPELINE_DOCUMENTS", "tests/conformance/reference-pipeline-semantics-v1")):
            self.assertIn(variable + '="$GITHUB_WORKSPACE/' + relative + '" \\\n', runtest)
        self.assertIn("python tools/ci_native_bundle.py test --path generated/core/native-suites --workers 2 2>&1 | tee generated/core/native-tests.txt", runtest)
        commands = self.core_commands(native)
        arguments = {
            "test_work_budget_retention": "",
            "test_reference_inputs": ' "$GITHUB_WORKSPACE/tests/conformance/reference-inputs-314.json"',
            "test_reference_package_workflow": ' "$GITHUB_WORKSPACE/tests/conformance/reference-packages-314.json"',
            "test_stored_zip": ' "$GITHUB_WORKSPACE/tests/conformance/archive-container-311.json" "$GITHUB_WORKSPACE/tests/conformance/archive-container-314.json"',
            "test_reference_package_manifest": ' "$GITHUB_WORKSPACE/tests/conformance/reference-package-domains-311.json" "$GITHUB_WORKSPACE/tests/conformance/reference-package-domains-314.json"',
            "test_reference_sequence_export": ' "$GITHUB_WORKSPACE/tests/conformance/reference-sequence-export-314.json"',
            "test_legacy_json": "", "test_reference_domains": "",
            "test_reference_producer_budget": ' "$GITHUB_WORKSPACE/tests/conformance/reference-contracts-v1"',
            "test_reference_checkers": ' "$GITHUB_WORKSPACE/tests/conformance/reference-contracts-v1"',
            "test_reference_contracts_corpus": ' "$GITHUB_WORKSPACE/tests/conformance/reference-contracts-v1.json"',
            "test_reference_construct_pipeline": ' "$GITHUB_WORKSPACE/tests/conformance/reference-pipeline-semantics-v1"',
            "test_reference_molecular_pipeline": ' "$GITHUB_WORKSPACE/tests/conformance/reference-pipeline-semantics-v1"',
            "test_reference_workflow": ' "$GITHUB_WORKSPACE/tests/conformance/reference-pipeline-semantics-v1"',
            "test_reference_molecular_attempts": ' "$GITHUB_WORKSPACE/tests/conformance/reference-pipeline-semantics-v1"',
            "test_reference_callback_manager": ' "$GITHUB_WORKSPACE/protocol/pipeline-callback-manager-v1.json" "$GITHUB_WORKSPACE/tests/conformance/reference-pipeline-semantics-v1"',
        }
        for name, argument in arguments.items():
            command = "core/_build/default/test/" + name + ".exe" + argument + " | tee generated/core/" + name + ".txt"
            with self.subTest(suite=name):
                self.assertEqual(commands.count(command), 1)
                self.assertIn("needs: ocaml-build", native)
                self.assertNotIn("continue-on-error", native)
        artifact = native.split("      - uses: actions/upload-artifact@v4\n", 1)[1].split("      - name:", 1)[0]
        self.assertIn("if: always()", artifact)
        self.assertIn("name: native-checks-${{ matrix.platform }}", artifact)
        self.assertIn("path: generated/core/", artifact)

    def test_checked_manager_and_contract_suites_are_hosted_gates(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        native = text.split("\n  ocaml-core:\n", 1)[1].split("\n  architecture-sdk:\n", 1)[0]
        native = self.core_commands(native)
        self.assertIn('core/_build/default/test/test_pipeline_session.exe "$GITHUB_WORKSPACE/protocol/pipeline-session-v1.json" "$GITHUB_WORKSPACE/tests/conformance/fixed-pipeline-native-v1.json" | tee generated/core/test_pipeline_session.txt', native)
        self.assertIn("core/_build/default/test/test_pipeline_host_bridge.exe | tee generated/core/test_pipeline_host_bridge.txt", native)
        self.assertIn('core/_build/default/test/test_pipeline_callback_manager.exe "$GITHUB_WORKSPACE/protocol/pipeline-callback-manager-v1.json" "$GITHUB_WORKSPACE/tests/conformance/pipeline-contract-literals-v1.json" "$GITHUB_WORKSPACE/tests/conformance/fixed-pipeline-native-v1.json" | tee generated/core/test_pipeline_callback_manager.txt', native)
        self.assertIn('core/_build/default/test/test_deferred_pass_manager.exe "$GITHUB_WORKSPACE/tests/conformance/pipeline-contract-literals-v1.json" | tee generated/core/test_deferred_pass_manager.txt', native)
        self.assertIn('core/_build/default/test/test_pipeline_callback_channel.exe "$GITHUB_WORKSPACE/protocol/pipeline-callback-channel-v1.json" | tee generated/core/test_pipeline_callback_channel.txt', native)
        for name in ("test_pipeline_contract", "test_pass_manager"):
            self.assertIn('core/_build/default/test/' + name + '.exe "$GITHUB_WORKSPACE/tests/conformance/pipeline-contract-literals-v1.json" | tee generated/core/' + name + '.txt', native)
        self.assertIn('core/_build/default/test/test_checked_pipeline_corpus.exe "$GITHUB_WORKSPACE/tests/conformance/checked-pipeline-v1.json" | tee generated/core/test_checked_pipeline_corpus.txt', native)
        self.assertIn('core/_build/default/test/test_lowering_budget.exe "$GITHUB_WORKSPACE/tests/conformance/lowering-v1.json" | tee generated/core/test_lowering_budget.txt', native)
        self.assertIn('core/_build/default/test/test_provider_comparison.exe "$GITHUB_WORKSPACE/tests/conformance/pipeline-callback-semantics-v1.json" | tee generated/core/test_provider_comparison.txt', native)
        self.assertIn('core/_build/default/test/test_fixed_pipeline_corpus.exe "$GITHUB_WORKSPACE/tests/conformance/fixed-pipeline-native-v1.json" "$GITHUB_WORKSPACE/tests/conformance/fixed-pipeline-continuations-native-v1.json" | tee generated/core/test_fixed_pipeline_corpus.txt', native)

    def test_live_manager_campaign_requires_all_installed_runtimes_and_comparison(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        installed = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:\n", 1)[0]
        self.assertEqual(self.installed_commands(installed)['check_pipeline_manager_install.py'][0],'pipeline-manager')
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  validation:\n", 1)[0]
        command = "python tools/check_pipeline_manager_install.py --compare --root artifacts/realization --native-root artifacts/core --output generated/realization-reproducibility/pipeline-manager.json"
        self.assertIn(command, comparison)
        self.assertLess(comparison.index(command), comparison.index("Record successful complete comparison"))

    def test_fixed_provider_campaign_requires_all_installed_runtimes_and_comparison(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        installed = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:\n", 1)[0]
        self.assertEqual(self.installed_commands(installed)['check_pipeline_fixed_provider_install.py'][0],'pipeline-fixed-providers')
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  validation:\n", 1)[0]
        command = "python tools/check_pipeline_fixed_provider_install.py --compare --root artifacts/realization --native-root artifacts/core --output generated/realization-reproducibility/pipeline-fixed-providers.json"
        self.assertIn(command, comparison)
        self.assertLess(comparison.index(command), comparison.index("Record successful complete comparison"))

    def test_fixed_continuation_campaign_is_bound_before_installed_and_comparison_success(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        installed = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:\n", 1)[0]
        self.assertEqual(self.installed_commands(installed)['check_pipeline_fixed_continuation_install.py'][0],'pipeline-fixed-continuations')
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  validation:\n", 1)[0]
        command = "python tools/check_pipeline_fixed_continuation_install.py --compare --root artifacts/realization --native-root artifacts/core --output generated/realization-reproducibility/pipeline-fixed-continuations.json"
        self.assertIn(command, comparison)
        self.assertLess(comparison.index(command), comparison.index("Record successful complete comparison"))

    def test_fixed_registration_campaign_is_bound_before_installed_and_comparison_success(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        installed = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:\n", 1)[0]
        self.assertEqual(self.installed_commands(installed)['check_pipeline_fixed_registration_install.py'][0],'pipeline-fixed-registration')
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  validation:\n", 1)[0]
        command = "python tools/check_pipeline_fixed_registration_install.py --compare --root artifacts/realization --native-root artifacts/core --output generated/realization-reproducibility/pipeline-fixed-registration.json"
        self.assertIn(command, comparison)
        self.assertLess(comparison.index(command), comparison.index("Record successful complete comparison"))

    def test_checked_in_workflow_registers_cross_platform_architecture_gate(self):
        workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
        self.assertEqual(ci.workflow_jobs(workflow), ci.REQUIRED_NEEDS | {"validation"})
        text = workflow.read_text(encoding="utf-8")
        comparison = text.split("\n  architecture-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:", 1)[0]
        self.assertIn("    needs: [ocaml-build, architecture-sdk]\n", comparison)
        for target in ("artifacts/core/linux-x86_64", "artifacts/core/macos-arm64",
                       "--root artifacts/core --output generated/core-reproducibility/receipt.json"):
            self.assertIn(target, comparison)
        self.assertIn("      - architecture-core-reproducibility\n", text.split("\n  validation:\n", 1)[1])
        native = text.split("\n  ocaml-core:\n", 1)[1].split("\n  architecture-sdk:\n", 1)[0]
        sdk = text.split("\n  architecture-sdk:\n", 1)[1].split("\n  architecture-core-reproducibility:", 1)[0]
        for version in ci.PYTHONS:
            self.assertEqual(sdk.count('python-version: "'+version+'"'), 2)
        self.assertIn("architecture-routing-${{ matrix.python-version }}.json", sdk)
        self.assertIn("needs: ocaml-build", sdk)

    def test_reference_campaign_requires_native_execution_and_same_runtime_reconstruction(self):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
        text = workflow.read_text()
        self.assertEqual(ci.workflow_jobs(workflow), ci.REQUIRED_NEEDS | {"validation"})
        installed = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:\n", 1)[0]
        self.assertEqual(self.installed_commands(installed)['check_pipeline_reference_install.py'][0],'pipeline-reference')
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:\n", 1)[0]
        self.assertIn('id: reference_python311\n        with:\n          python-version: "3.11"', comparison)
        self.assertIn('id: reference_python314\n        with:\n          python-version: "3.14"\n          update-environment: false', comparison)
        compare_start = comparison.index("python tools/check_pipeline_reference_install.py --compare")
        compare_end = comparison.index("      - name: Retain complete comparison receipt", compare_start)
        compare_command = comparison[compare_start:compare_end]
        for version in ("311", "314"):
            interpreter = '${{ steps.reference_python' + version + '.outputs.python-path }}'
            install = '"' + interpreter + '" -m pip install .'
            self.assertIn(install, comparison)
            self.assertLess(comparison.index(install), compare_start)
            self.assertIn('--python' + version + ' "' + interpreter + '"', compare_command)
        for binding in ('--root artifacts/realization', '--native-root artifacts/core',
                        '--output generated/realization-reproducibility/pipeline-reference.json'):
            self.assertIn(binding, compare_command)
        self.assertLess(compare_start, comparison.index("Record successful complete comparison"))


    def test_realization_campaigns_are_required_on_every_runtime_and_compared_whole(self):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
        self.assertEqual(ci.workflow_jobs(workflow), ci.REQUIRED_NEEDS | {"validation"})
        text = workflow.read_text()
        matrix = text.split("\n  installed-campaigns:\n", 1)[1].split("\n  realization-conformance:\n", 1)[0]
        self.assertIn("    needs: [ocaml-build, prebuilt-core-assembly]\n", matrix)
        for target in ci.CORE_PLATFORMS:
            self.assertEqual(matrix.count("            platform: " + target + "\n"), 10)
        for version in ci.PYTHONS:
            self.assertEqual(matrix.count('            python-version: "' + version + '"\n'), 10)
        planned=self.installed_commands(matrix)
        for command in ("check_realization_protocol.py", "check_realization_routing.py"):
            self.assertIn(command, planned)
        self.assertNotIn("--sample", matrix)
        self.assertNotIn("continue-on-error", matrix)
        self.assertIn("          fail-fast: false", matrix.replace("      fail-fast", "          fail-fast"))
        gate = text.split("\n  validation:\n", 1)[1]
        self.assertIn("      - realization-conformance\n", gate)
        self.assertIn("      - realization-core-reproducibility\n", gate)
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:\n", 1)[0]
        self.assertIn("needs: [ocaml-build, realization-conformance]", comparison)
        self.assertIn("check_realization_reproducibility.py", comparison)
        self.assertIn("--native-root artifacts/core", comparison)


if __name__ == "__main__":
    unittest.main()
