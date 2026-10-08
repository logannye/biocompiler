"""Synthetic archive/runtime bootstrap controls; never acquire or execute Python."""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import bootstrap_hosted_python as helper

ROOT = Path(__file__).resolve().parents[1]


def synthetic_archive(path, rows):
    """Independent tiny tar author; row order, links and contents are literal."""
    with tarfile.open(path, "w:gz", format=tarfile.USTAR_FORMAT) as archive:
        for name, kind, value, mode in rows:
            member = tarfile.TarInfo(name)
            member.mode, member.mtime, member.uid, member.gid = mode, 0, 0, 0
            if kind == "file":
                member.size = len(value)
                archive.addfile(member, BytesIO(value))
            else:
                member.type = {"dir": tarfile.DIRTYPE, "symlink": tarfile.SYMTYPE,
                               "hardlink": tarfile.LNKTYPE, "fifo": tarfile.FIFOTYPE,
                               "device": tarfile.CHRTYPE}[kind]
                if kind in ("symlink", "hardlink"):
                    member.linkname = value
                archive.addfile(member)
    return path


ROWS = (
    ("python", "dir", None, 0o755),
    ("python/bin", "dir", None, 0o755),
    ("python/bin/python3.11", "file", b"INERT Python placeholder\n", 0o755),
    ("python/bin/python3", "symlink", "python3.11", 0o777),
    ("python/bin/python", "symlink", "python3", 0o777),
    ("python/lib", "dir", None, 0o755),
    ("python/lib/python3.11", "dir", None, 0o755),
    ("python/lib/python3.11/literal.py", "file", b"VALUE = 17\n", 0o644),
)


class HostedPythonBootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.guard = ExitStack()
        self.addCleanup(self.guard.close)
        self.stdout = StringIO()
        self.guard.enter_context(redirect_stdout(self.stdout))
        self.network = self.guard.enter_context(patch("urllib.request.urlopen", side_effect=AssertionError("No real network in bootstrap tests")))
        self.process = self.guard.enter_context(patch("subprocess.run", side_effect=AssertionError("No real subprocess in bootstrap tests")))
        self.guard.enter_context(patch("subprocess.Popen", side_effect=AssertionError("No native launch in bootstrap tests")))

        self.guard.enter_context(patch("socket.socket", side_effect=AssertionError("No real socket in bootstrap tests")))
        self.guard.enter_context(patch("socket.create_connection", side_effect=AssertionError("No real connection in bootstrap tests")))
        self.guard.enter_context(patch("ctypes.CDLL", side_effect=AssertionError("No native loading in bootstrap tests")))
        self.guard.enter_context(patch("os.system", side_effect=AssertionError("No shell in bootstrap tests")))

    def specification(self, archive=None):
        specification = deepcopy(helper.load_manifest(ROOT))
        if archive is not None:
            content = archive.read_bytes()
            specification["archive"].update(size=len(content), sha256=hashlib.sha256(content).hexdigest())
        return specification

    def archive(self, rows=ROWS, name="python.tar.gz"):
        return synthetic_archive(self.directory / name, rows)

    def environment(self):
        tool_cache = self.directory / "tool-cache"
        tool_cache.mkdir(exist_ok=True)
        return {
            "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
            "RUNNER_TOOL_CACHE": str(tool_cache), "GITHUB_WORKSPACE": str(ROOT),
            "GITHUB_RUN_ID": "37539833174", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_SHA": "1" * 40,
        }

    def runtime(self, executable):
        executable = executable.resolve()
        prefix = executable.parent.parent
        return {"version": "3.11.15", "implementation": "CPython", "system": "Darwin",
                "machine": "arm64", "executable": str(executable),
                "prefix": str(prefix), "base_prefix": str(prefix)}

    def test_reviewed_provider_manifest_has_exact_supported_runtime_and_asset(self):
        specification = self.specification()
        self.assertEqual(specification["python_version"], "3.11.15")
        self.assertEqual((specification["implementation"], specification["system"], specification["machine"]),
                         ("CPython", "Darwin", "arm64"))
        self.assertEqual(specification["cache"], {"version": "3.11.15", "architecture": "arm64"})
        archive = specification["archive"]
        self.assertEqual(archive["release_tag"], "20260325")
        self.assertEqual(archive["asset_id"], 381125647)
        self.assertEqual(archive["size"], 20082612)
        self.assertEqual(archive["sha256"], "054a5e5645c87538df903aa5ffee9ae6b84323545b63bcd0e01285bda8898b6c")
        self.assertTrue(archive["url"].startswith("https://github.com/astral-sh/python-build-standalone/releases/download/20260325/"))
        self.assertIn("3.11.15", archive["url"])
        self.assertIn("aarch64-apple-darwin", archive["url"])
        self.assertEqual(set(specification["limits"]), {"members", "expanded_bytes", "file_bytes"})
        self.assertLessEqual(specification["limits"]["expanded_bytes"], 268435456)

    def test_hosted_environment_requires_matching_runner_and_real_fresh_cache_root(self):
        environment = self.environment()
        expected = Path(environment["RUNNER_TOOL_CACHE"])
        self.assertEqual(helper.validate_hosted_environment(environment, system="Darwin", machine="arm64"), expected)
        for name, value in (("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
                            ("RUNNER_OS", "Linux"), ("RUNNER_ARCH", "X64"),
                            ("RUNNER_TOOL_CACHE", "relative/cache"), ("RUNNER_TOOL_CACHE", "")):
            changed = dict(environment, **{name: value})
            with self.subTest(name=name, value=value), self.assertRaises((ValueError, AssertionError)):
                helper.validate_hosted_environment(changed, system="Darwin", machine="arm64")
        for system, machine in (("Linux", "arm64"), ("Darwin", "x86_64")):
            with self.subTest(system=system, machine=machine), self.assertRaises((ValueError, AssertionError)):
                helper.validate_hosted_environment(environment, system=system, machine=machine)
        link = self.directory / "cache-link"
        link.symlink_to(expected, target_is_directory=True)
        with self.assertRaises((ValueError, AssertionError)):
            helper.validate_hosted_environment(dict(environment, RUNNER_TOOL_CACHE=str(link)), system="Darwin", machine="arm64")
        self.network.assert_not_called()
        self.process.assert_not_called()

    def test_archive_accepts_literal_safe_files_and_internal_symlinks(self):
        archive = self.archive()
        specification = self.specification(archive)
        members = helper.validate_archive(archive, specification)
        self.assertEqual([member.name for member in members], [row[0] for row in ROWS])
        destination = self.directory / "extracted"
        helper.extract_archive(archive, destination, specification)
        self.assertEqual((destination / "bin/python3.11").read_bytes(), b"INERT Python placeholder\n")
        self.assertEqual((destination / "lib/python3.11/literal.py").read_bytes(), b"VALUE = 17\n")
        self.assertEqual(os.readlink(destination / "bin/python3"), "python3.11")
        self.assertEqual((destination / "bin/python").resolve(), destination / "bin/python3.11")
        self.process.assert_not_called()

    def test_archive_rejects_hash_size_and_synthetic_expansion_bounds(self):
        archive = self.archive()
        specification = self.specification(archive)
        changed = []
        for key, value in (("size", archive.stat().st_size + 1), ("sha256", "0" * 64)):
            row = deepcopy(specification)
            row["archive"][key] = value
            changed.append(row)
        for key, value in (("members", len(ROWS) - 1), ("expanded_bytes", 10), ("file_bytes", 10)):
            row = deepcopy(specification)
            row["limits"][key] = value
            changed.append(row)
        for index, row in enumerate(changed):
            with self.subTest(index=index), self.assertRaises((ValueError, AssertionError)):
                helper.validate_archive(archive, row)

    def test_archive_rejects_untrusted_names_types_duplicates_and_parent_redirection(self):
        mutations = (
            (("/python/absolute", "file", b"x", 0o644),),
            (("python/../outside", "file", b"x", 0o644),),
            (("python/bin/../ambiguous", "file", b"x", 0o644),),
            (("python//ambiguous", "file", b"x", 0o644),),
            (("python/./ambiguous", "file", b"x", 0o644),),
            (("python\\ambiguous", "file", b"x", 0o644),),
            (("foreign/file", "file", b"x", 0o644),),
            (("python/bin/python3.11", "file", b"duplicate", 0o755),),
            (("python/device", "device", "", 0o600),),
            (("python/fifo", "fifo", "", 0o600),),
            (("python/bin/python3.11/child", "file", b"x", 0o644),),
            (("python/bin/python3/child", "file", b"x", 0o644),),
        )
        for index, extra in enumerate(mutations):
            archive = self.archive(ROWS + extra, name=f"invalid-{index}.tar.gz")
            with self.subTest(index=index), self.assertRaises((ValueError, AssertionError)):
                helper.validate_archive(archive, self.specification(archive))

    def test_archive_rejects_escaping_broken_and_cyclic_links(self):
        mutations = (
            (("python/escape", "symlink", "../outside", 0o777),),
            (("python/absolute", "symlink", "/tmp/outside", 0o777),),
            (("python/missing", "symlink", "absent", 0o777),),
            (("python/a", "symlink", "b", 0o777), ("python/b", "symlink", "a", 0o777)),
            (("python/hard", "hardlink", "python/bin/python3.11", 0o755),),
            (("python/traverse", "symlink", "bin/../../outside", 0o777),),
        )
        for index, extra in enumerate(mutations):
            archive = self.archive(ROWS + extra, name=f"link-{index}.tar.gz")
            with self.subTest(index=index), self.assertRaises((ValueError, AssertionError)):
                helper.validate_archive(archive, self.specification(archive))

    def test_archive_requires_executable_and_refuses_preexisting_extraction(self):
        for index, rows in enumerate((tuple(row for row in ROWS if row[0] != "python/bin/python3.11"),
                tuple((name, kind, value, 0o644 if name == "python/bin/python3.11" else mode)
                      for name, kind, value, mode in ROWS))):
            archive = self.archive(rows, name=f"runtime-{index}.tar.gz")
            with self.subTest(index=index), self.assertRaises((ValueError, AssertionError)):
                helper.validate_archive(archive, self.specification(archive))
        archive = self.archive()
        destination = self.directory / "existing"
        destination.mkdir()
        sentinel = destination / "keep"
        sentinel.write_bytes(b"preserve user data")
        with self.assertRaises((ValueError, AssertionError, FileExistsError)):
            helper.extract_archive(archive, destination, self.specification(archive))
        self.assertEqual(sentinel.read_bytes(), b"preserve user data")

    def test_runtime_probe_requires_exact_patch_role_platform_and_prefix(self):
        executable = self.directory / "cache/bin/python3.11"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"INERT placeholder")
        expected = self.runtime(executable)
        specification = self.specification()
        with patch.dict(os.environ, {"PYTHONPATH": "unreviewed", "DYLD_LIBRARY_PATH": "unreviewed", "LD_PRELOAD": "unreviewed"}), patch("subprocess.run", return_value=Mock(returncode=0, stdout=json.dumps(expected), stderr="")) as invoke:
            self.assertEqual(helper.verify_runtime(executable, specification), expected)
        argv = invoke.call_args.args[0]
        self.assertEqual(argv[:4], [str(executable), "-I", "-S", "-B"])
        self.assertEqual(argv[4], "-c")
        self.assertNotIn("shell", invoke.call_args.kwargs)
        self.assertFalse(any(key.startswith(("PYTHON", "DYLD_", "LD_")) for key in invoke.call_args.kwargs["env"]))
        self.assertLessEqual(invoke.call_args.kwargs["timeout"], 60)
        for key, value in (("version", "3.11.17"), ("implementation", "PyPy"), ("system", "Linux"),
                           ("machine", "x86_64"), ("executable", "/foreign/python"),
                           ("prefix", "/foreign"), ("base_prefix", "/foreign")):
            changed = dict(expected, **{key: value})
            with self.subTest(key=key), patch("subprocess.run", return_value=Mock(returncode=0, stdout=json.dumps(changed), stderr="")), self.assertRaises((ValueError, AssertionError)):
                helper.verify_runtime(executable, specification)
        for stdout, stderr, returncode in (("not-json", "", 0), (json.dumps(expected), "unexpected output", 0),
                                         (json.dumps(expected), "", 1), (json.dumps(expected) + "\n{}", "", 0)):
            with self.subTest(stdout=stdout, returncode=returncode), patch("subprocess.run", return_value=Mock(returncode=returncode, stdout=stdout, stderr=stderr)), self.assertRaises((ValueError, AssertionError)):
                helper.verify_runtime(executable, specification)

    def test_manifest_rejects_authority_expansion_or_provider_substitution(self):
        original = self.specification()
        protocol = self.directory / "protocol"
        protocol.mkdir()
        path = protocol / "hosted-python-macos-arm64-v1.json"
        mutations = []
        for key, value in (("python_version", "3.11.17"), ("system", "Linux"), ("machine", "x86_64"),
                           ("implementation", "PyPy"), ("unknown", "extra")):
            mutations.append(dict(original, **{key: value}))
        for key, value in (("sha256", "0" * 64), ("size", True), ("url", "https://example.test/foreign.tar.gz"),
                           ("release_tag", "latest"), ("asset_id", 1)):
            changed = deepcopy(original)
            changed["archive"][key] = value
            mutations.append(changed)
        changed = deepcopy(original)
        changed["cache"]["version"] = "3.11"
        mutations.append(changed)
        for index, changed in enumerate(mutations):
            path.write_text(json.dumps(changed))
            with self.subTest(index=index), self.assertRaises((ValueError, AssertionError)):
                helper.load_manifest(self.directory)

    def test_extraction_closure_detects_extra_missing_modified_link_and_mode(self):
        archive = self.archive()
        destination = self.directory / "tree"
        expected = helper.extract_archive(archive, destination, self.specification(archive))
        self.assertEqual(set(expected), {row[0].removeprefix("python/") for row in ROWS if row[0] != "python"})
        self.assertEqual(expected["bin/python3.11"], {
            "kind": "file", "sha256": hashlib.sha256(b"INERT Python placeholder\n").hexdigest(),
            "size": len(b"INERT Python placeholder\n"), "mode": 0o755})
        self.assertEqual(expected["bin/python3"], {"kind": "symlink", "target": "python3.11"})
        self.assertEqual(helper.closure_snapshot(destination), expected)
        executable = destination / "bin/python3.11"
        original = executable.read_bytes()
        executable.write_bytes(b"edited")
        self.assertNotEqual(helper.closure_snapshot(destination), expected)
        executable.write_bytes(original)
        executable.chmod(0o644)
        self.assertNotEqual(helper.closure_snapshot(destination), expected)
        executable.chmod(0o755)
        extra = destination / "extra"
        extra.write_bytes(b"extra")
        self.assertNotEqual(helper.closure_snapshot(destination), expected)
        extra.unlink()
        literal = destination / "lib/python3.11/literal.py"
        literal.unlink()
        self.assertNotEqual(helper.closure_snapshot(destination), expected)
        literal.write_bytes(b"VALUE = 17\n")
        link = destination / "bin/python3"
        link.unlink()
        link.symlink_to("python")
        self.assertNotEqual(helper.closure_snapshot(destination), expected)

    def bootstrap_inputs(self):
        root = self.directory / "checkout"
        (root / "protocol").mkdir(parents=True)
        (root / "protocol/hosted-python-macos-arm64-v1.json").write_bytes(
            (ROOT / "protocol/hosted-python-macos-arm64-v1.json").read_bytes())
        archive = self.archive()
        specification = self.specification(archive)
        environment = dict(self.environment(), GITHUB_WORKSPACE=str(root))
        output = root / "generated/bootstrap.json"
        cache = Path(environment["RUNNER_TOOL_CACHE"]) / "Python/3.11.15/arm64"
        marker = cache.with_name("arm64.complete")
        return root, archive, specification, environment, output, cache, marker

    def bootstrap_stubs(self, archive, specification):
        stack = ExitStack()
        stack.enter_context(patch.object(helper.platform, "system", return_value="Darwin"))
        stack.enter_context(patch.object(helper.platform, "machine", return_value="arm64"))
        stack.enter_context(patch.object(helper, "load_manifest", return_value=specification))
        stack.enter_context(patch.object(helper, "download_archive", side_effect=lambda spec, destination: destination.write_bytes(archive.read_bytes())))
        return stack

    def test_bootstrap_marks_only_complete_exact_closure_after_mocked_runtime(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        def observe(executable, spec):
            self.assertEqual(executable, cache / "bin/python")
            self.assertEqual(spec, specification)
            self.assertFalse(marker.exists())
            self.assertFalse(output.exists())
            self.assertEqual((cache / "bin/python3.11").read_bytes(), b"INERT Python placeholder\n")
            return self.runtime(executable)
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "verify_runtime", side_effect=observe) as probe:
            receipt = helper.bootstrap(root, output, environ=environment)
        probe.assert_called_once()
        self.assertEqual(receipt["status"], "ready")
        self.assertIs(receipt["acceptance"], False)
        self.assertEqual(receipt["runtime"], self.runtime(cache / "bin/python"))
        closure = helper.closure_snapshot(cache)
        self.assertEqual(receipt["closure_entries"], 7)
        self.assertEqual(receipt["closure_bytes"], 36)
        expected_digest = hashlib.sha256(json.dumps(closure, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(receipt["closure_sha256"], expected_digest)
        self.assertTrue(marker.is_file())
        self.assertEqual(marker.read_bytes(), b"")
        self.assertEqual(json.loads(output.read_text()), receipt)
        self.assertEqual(json.loads(self.stdout.getvalue()), receipt)
        self.network.assert_not_called()
        self.process.assert_not_called()

    def test_bootstrap_refuses_existing_cache_or_marker_without_adoption(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        cache.mkdir(parents=True)
        sentinel = cache / "keep"
        sentinel.write_bytes(b"preexisting cache")
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "download_archive") as download, patch.object(helper, "verify_runtime") as runtime:
            with self.assertRaises((ValueError, AssertionError)):
                helper.bootstrap(root, output, environ=environment)
            self.assertEqual(sentinel.read_bytes(), b"preexisting cache")
            download.assert_not_called()
            runtime.assert_not_called()
            self.assertFalse(output.exists())
            sentinel.unlink()
            cache.rmdir()
            marker.write_bytes(b"old marker")
            with self.assertRaises((ValueError, AssertionError)):
                helper.bootstrap(root, output, environ=environment)
            self.assertEqual(marker.read_bytes(), b"old marker")
            download.assert_not_called()
            runtime.assert_not_called()

    def test_bootstrap_failed_runtime_retains_cache_and_failed_receipt_without_marker(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "verify_runtime", side_effect=ValueError("Literal wrong runtime patch")):
            with self.assertRaisesRegex(ValueError, "Literal wrong runtime patch"):
                helper.bootstrap(root, output, environ=environment)
        self.assertTrue(cache.is_dir())
        self.assertFalse(marker.exists())
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertIs(receipt["acceptance"], False)
        self.assertEqual(receipt["error"], "Literal wrong runtime patch")
        self.assertNotIn("closure_sha256", receipt)
        self.assertEqual((cache / "bin/python3.11").read_bytes(), b"INERT Python placeholder\n")

    def test_bootstrap_checks_full_closure_before_any_runtime_probe(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        extractor = helper.extract_archive
        def edited_extract(path, destination, spec):
            closure = extractor(path, destination, spec)
            (destination / "lib/python3.11/literal.py").write_bytes(b"changed after extraction")
            return closure
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "extract_archive", side_effect=edited_extract), patch.object(helper, "verify_runtime") as probe:
            with self.assertRaisesRegex(ValueError, "closure changed before publication"):
                helper.bootstrap(root, output, environ=environment)
        probe.assert_not_called()
        self.assertFalse(cache.exists())
        self.assertFalse(marker.exists())
        self.assertEqual(json.loads(output.read_text())["status"], "failed")

    def test_bootstrap_rechecks_all_files_after_runtime_before_complete_marker(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        def edited_probe(executable, spec):
            self.assertFalse(marker.exists())
            (cache / "lib/python3.11/literal.py").write_bytes(b"changed during runtime")
            return self.runtime(executable)
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "verify_runtime", side_effect=edited_probe):
            with self.assertRaisesRegex(ValueError, "closure changed during runtime probe"):
                helper.bootstrap(root, output, environ=environment)
        self.assertTrue(cache.exists())
        self.assertFalse(marker.exists())
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertNotIn("closure_sha256", receipt)

    def test_bootstrap_local_environment_fails_before_download_probe_or_receipt(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        environment["GITHUB_ACTIONS"] = "false"
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "download_archive") as download, patch.object(helper, "verify_runtime") as runtime:
            with self.assertRaisesRegex(ValueError, "requires hosted macOS ARM64"):
                helper.bootstrap(root, output, environ=environment)
        download.assert_not_called()
        runtime.assert_not_called()
        self.assertFalse(output.exists())
        self.assertFalse(cache.exists())
        self.assertFalse(marker.exists())

    def test_download_accepts_only_bounded_exact_bytes_from_reviewed_https_hosts(self):
        payload = b"tiny inert archive input"
        specification = self.specification()
        specification["archive"].update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        def response(content=payload, url="https://release-assets.githubusercontent.com/literal", length=None):
            stream = BytesIO(content)
            stream.headers = {} if length is None else {"Content-Length": length}
            stream.geturl = lambda: url
            return stream
        destination = self.directory / "downloaded.tar.gz"
        with patch("urllib.request.urlopen", return_value=response()) as download:
            helper.download_archive(specification, destination)
        self.assertEqual(destination.read_bytes(), payload)
        self.assertEqual(download.call_args.kwargs["timeout"], 30)
        self.assertEqual(download.call_args.args[0].full_url, specification["archive"]["url"])
        cases = (
            {"content": payload + b"extra"},
            {"content": payload[:-1]},
            {"content": b"X" * len(payload)},
            {"length": str(len(payload) + 1)},
            {"url": "http://github.com/plaintext"},
            {"url": "https://example.test/foreign"},
            {"url": "https://github.com.attacker.test/foreign"},
        )
        for index, arguments in enumerate(cases):
            target = self.directory / f"rejected-download-{index}.tar.gz"
            with self.subTest(index=index), patch("urllib.request.urlopen", return_value=response(**arguments)), self.assertRaises(ValueError):
                helper.download_archive(specification, target)
        with patch("urllib.request.urlopen", return_value=response()), patch.object(helper.time, "monotonic", side_effect=[0, 181]), self.assertRaisesRegex(ValueError, "time bound"):
            helper.download_archive(specification, self.directory / "expired-download.tar.gz")
        with patch("urllib.request.urlopen") as download, self.assertRaisesRegex(ValueError, "overwrite"):
            helper.download_archive(specification, destination)
        download.assert_not_called()
        self.assertEqual(destination.read_bytes(), payload)

    def test_bootstrap_checks_published_cache_again_before_runtime(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        snapshot = helper.closure_snapshot
        def inspect(directory):
            if directory == cache:
                (cache / "extra-after-rename").write_bytes(b"unreviewed file")
            return snapshot(directory)
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "closure_snapshot", side_effect=inspect), patch.object(helper, "verify_runtime") as probe:
            with self.assertRaisesRegex(ValueError, "closure changed before execution"):
                helper.bootstrap(root, output, environ=environment)
        probe.assert_not_called()
        self.assertTrue(cache.exists())
        self.assertFalse(marker.exists())
        self.assertEqual(json.loads(output.read_text())["status"], "failed")

    def test_bootstrap_failed_acquisition_retains_failure_without_cache_or_marker(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "download_archive", side_effect=ValueError("Literal truncated provider response")), patch.object(helper, "verify_runtime") as probe:
            with self.assertRaisesRegex(ValueError, "Literal truncated provider response"):
                helper.bootstrap(root, output, environ=environment)
        probe.assert_not_called()
        self.assertFalse(cache.exists())
        self.assertFalse(marker.exists())
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"], "Literal truncated provider response")
        self.assertNotIn("runtime", receipt)
        self.assertIs(receipt["acceptance"], False)

    def test_extraction_does_not_follow_existing_destination_or_ancestor_symlink(self):
        archive = self.archive()
        specification = self.specification(archive)
        protected = self.directory / "protected"
        protected.mkdir()
        sentinel = protected / "sentinel"
        sentinel.write_bytes(b"unaltered")
        link = self.directory / "redirect"
        link.symlink_to(protected, target_is_directory=True)
        for destination in (link, link / "fresh"):
            with self.subTest(destination=destination), self.assertRaisesRegex(ValueError, "Symlink"):
                helper.extract_archive(archive, destination, specification)
        self.assertEqual(list(protected.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"unaltered")

    def test_manifest_rejects_duplicate_keys_float_aliases_and_oversized_bytes(self):
        root = self.directory / "checkout"
        (root / "protocol").mkdir(parents=True)
        path = root / "protocol/hosted-python-macos-arm64-v1.json"
        encoded = json.dumps(self.specification())
        mutations = (
            encoded.replace('"python_version": "3.11.15"', '"python_version": "3.11.15", "python_version": "3.11.15"'),
            encoded.replace('"size": 20082612', '"size": 20082612.0'),
            encoded.replace('"members": 30000', '"members": 30000.0'),
            encoded.replace('"size": 20082612', '"size": NaN'),
            encoded + " " * 16384,
        )
        for index, value in enumerate(mutations):
            path.write_text(value)
            with self.subTest(index=index), self.assertRaises(ValueError):
                helper.load_manifest(root)

    def test_bootstrap_rejects_receipt_path_escape_before_acquisition(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        for target in (root / "../outside.json", self.directory / "absolute-outside.json"):
            with self.subTest(target=target), self.bootstrap_stubs(archive, specification), patch.object(helper, "download_archive") as download, self.assertRaisesRegex(ValueError, "remain in checkout"):
                helper.bootstrap(root, target, environ=environment)
            download.assert_not_called()
            self.assertFalse(target.exists())
        self.assertFalse(cache.exists())
        self.assertFalse(marker.exists())

    def test_bootstrap_detects_source_changes_during_admission_and_before_marker(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        original = {"manifest_sha256": "1" * 64, "helper_sha256": "2" * 64}
        altered = {"manifest_sha256": "3" * 64, "helper_sha256": "2" * 64}
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "_source_pins", side_effect=[original, altered]), patch.object(helper, "download_archive") as download:
            with self.assertRaisesRegex(ValueError, "sources changed during admission"):
                helper.bootstrap(root, output, environ=environment)
        download.assert_not_called()
        self.assertFalse(output.exists())
        self.assertFalse(cache.exists())
        self.assertFalse(marker.exists())
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "_source_pins", side_effect=[original, original, altered]), patch.object(helper, "verify_runtime", side_effect=lambda executable, specification: self.runtime(executable)):
            with self.assertRaisesRegex(ValueError, "sources changed before completion"):
                helper.bootstrap(root, output, environ=environment)
        self.assertTrue(cache.exists())
        self.assertFalse(marker.exists())
        self.assertEqual(json.loads(output.read_text())["status"], "failed")

    def test_receipt_persistence_failure_cannot_publish_complete_marker(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        def failure(path, receipt, **kwargs):
            self.assertEqual(path, output)
            self.assertFalse(marker.exists())
            raise OSError("Literal receipt storage failure")
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "verify_runtime", side_effect=lambda executable, specification: self.runtime(executable)), patch.object(helper, "_persist_receipt", side_effect=failure):
            with self.assertRaisesRegex(OSError, "Literal receipt storage failure"):
                helper.bootstrap(root, output, environ=environment)
        self.assertTrue(cache.exists())
        self.assertFalse(marker.exists())
        self.assertFalse(output.exists())

    def test_marker_publication_failure_retains_failed_receipt(self):
        root, archive, specification, environment, output, cache, marker = self.bootstrap_inputs()
        original_open = Path.open
        def open_file(path, *args, **kwargs):
            if path == marker:
                self.assertEqual(args[0], "x")
                self.assertEqual(json.loads(output.read_text())["status"], "ready")
                raise OSError("Literal marker storage failure")
            return original_open(path, *args, **kwargs)
        with self.bootstrap_stubs(archive, specification), patch.object(helper, "verify_runtime", side_effect=lambda executable, specification: self.runtime(executable)), patch.object(Path, "open", autospec=True, side_effect=open_file):
            with self.assertRaisesRegex(OSError, "Literal marker storage failure"):
                helper.bootstrap(root, output, environ=environment)
        self.assertTrue(cache.exists())
        self.assertFalse(marker.exists())
        receipt = json.loads(output.read_text())
        self.assertEqual(receipt["status"], "failed")
        self.assertIs(receipt["acceptance"], False)
        self.assertEqual(receipt["error"], "Literal marker storage failure")
        self.assertEqual(json.loads(self.stdout.getvalue()), receipt)
