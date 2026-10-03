"""Actual installed origins remain bound to unchanged original archive code."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHILD = """
import json,sys
from pathlib import Path
from types import FunctionType,ModuleType
sys.path.insert(0,sys.argv[1])
import biocompiler.artifacts.archive_container as installed
sys.path.insert(0,sys.argv[2])
from tools import capture_archive_container as authority
root=Path(sys.argv[2]).resolve()
actual=Path(installed.__file__).resolve()
assert not actual.is_relative_to(root)
assert authority.original is installed
mode=sys.argv[3]
if mode=='changed-file':
    actual.write_bytes(actual.read_bytes()+b'\\n# modified installed bytes\\n')
elif mode=='changed-code':
    original=installed.read_container
    compiled=compile('def read_container(data):\\n    return {}\\n',str(actual),'exec')
    replacement=next(value for value in compiled.co_consts if hasattr(value,'co_code'))
    original.__code__=replacement
elif mode=='foreign-globals':
    original=installed.read_container
    installed.read_container=FunctionType(original.__code__,dict(original.__globals__),
        original.__name__,original.__defaults__,original.__closure__)
elif mode=='replaced-module':
    sys.modules[installed.__name__]=ModuleType(installed.__name__)
if mode=='valid':
    captured=authority.capture()
    minor=''.join(map(str,sys.version_info[:2]))
    expected=json.loads((root/('tests/conformance/archive-container-'+minor+'.json')).read_bytes())
    assert captured==expected
    print(json.dumps({'cases':len(captured['cases']),'source':captured['source'],
        'installed_origin':True}))
else:
    try:
        authority.source_authority()
    except AssertionError:
        print(json.dumps({'rejected':mode,'installed_origin':True}))
    else:
        raise AssertionError('Changed installed archive authority was accepted')
"""


class ArchiveSourceOriginTests(unittest.TestCase):
    def child(self, mode):
        with tempfile.TemporaryDirectory(prefix="biocompiler-archive-origin-") as directory:
            root = Path(directory)
            site = root / "site"
            shutil.copytree(ROOT / "src/biocompiler", site / "biocompiler",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-c", CHILD, str(site), str(ROOT), mode],
                cwd=root, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr[-12000:])
            return json.loads(completed.stdout)

    def test_complete_original_corpus_runs_from_actual_installed_source(self):
        result = self.child("valid")
        self.assertEqual(result["cases"], 125)
        self.assertTrue(result["installed_origin"])
        self.assertEqual(result["source"], {
            "path": "src/biocompiler/artifacts/archive_container.py",
            "sha256": "36d598102ffea532b67a3a116266f573ccff07da39166230023d162fd675d43f",
        })

    def test_changed_installed_bytes_are_rejected(self):
        self.assertEqual(self.child("changed-file")["rejected"], "changed-file")

    def test_changed_executable_code_with_original_path_is_rejected(self):
        self.assertEqual(self.child("changed-code")["rejected"], "changed-code")

    def test_copied_globals_with_original_code_are_rejected(self):
        self.assertEqual(self.child("foreign-globals")["rejected"], "foreign-globals")

    def test_replaced_canonical_module_is_rejected(self):
        self.assertEqual(self.child("replaced-module")["rejected"], "replaced-module")
