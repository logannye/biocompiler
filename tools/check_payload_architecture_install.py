"""Exercise installed architecture APIs and CLI from outside the checkout.

The repository supplies artificial fixtures only. Import the installed package
before exposing the examples directory, and reject a source-tree package import.
All retained outputs are deterministic contract artifacts, without runtime paths.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import biocompiler as bc


REPOSITORY = Path(__file__).resolve().parents[1]


def _save(path, record):
    path.write_text(record.to_json() + "\n", encoding="utf-8")


def _command(command, directory, stem, expected=0):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    (directory / (stem + ".json")).write_text(result.stdout, encoding="utf-8")
    if result.returncode != expected:
        raise AssertionError(
            f"{stem}: expected exit {expected}, received {result.returncode}: {result.stderr}"
        )
    return result


def check_install(output, *, cli=("biocompiler",)):
    # Only fixture modules live at repository root: the package itself is in src.
    # Main has already checked the installed import origin before this addition.
    sys.path.insert(0, str(REPOSITORY))
    from examples.payload_architectures import make_architecture_request
    from examples.architecture_automation import make_automatic_case, make_automation_request
    from examples.architecture_control_designs import make_control_request

    output = Path(output)
    cases = [(case, make_architecture_request(case,
                variants=("one_rna", "many_components_one_rna", "two_rna", "one_rna_helper"),
                independent_shutdown=True) if case == "A" else make_architecture_request(case))
             for case in "ABCDEF"]
    cases += [("automatic_timing", make_automation_request())]
    cases += [("automatic_" + case.lower(), make_automatic_case(case)) for case in "BF"]
    cases += [(case, make_control_request(case)) for case in
              ("memory_reset", "state_reset", "production_adjustment", "activity_control")]
    for case, request in cases:
        directory = output / case.lower()
        directory.mkdir(parents=True, exist_ok=True)
        request_path, build_path = directory / "request.json", directory / "build.json"
        _save(request_path, request)
        # Roundtrip the independently retained request before API compilation.
        restored = bc.PayloadArchitectureRequest.from_json(request_path.read_text(encoding="utf-8"))
        assert restored.fingerprint == request.fingerprint
        build = bc.compile(restored)
        assert build.status == "compiled", (case, build.diagnostics)
        _save(build_path, build)
        checked = bc.check_payload_architecture(build, expected_request=request)
        assert checked.passed and checked.translation_complete and checked.construction_complete
        _save(directory / "api.verification.json", checked)
        exported = bc.export_payload_architecture(build, expected_request=request)
        _save(directory / "api.export.json", exported)
        (directory / "payloads.fasta").write_text(exported.fasta, encoding="utf-8")
        manifest = exported.to_dict()["manifest"]
        (directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        cli_build, cli_export = directory / "cli.build.json", directory / "cli.export.json"
        _command([*cli, "architecture-build", "--request", str(request_path),
                  "--output", str(cli_build)], directory, "cli.build-summary")
        _command([*cli, "architecture-verify", str(cli_build), "--expected-request", str(request_path)],
                 directory, "cli.verification")
        _command([*cli, "architecture-export", str(cli_build), "--expected-request", str(request_path),
                  "--output", str(cli_export)], directory, "cli.export-summary")
        _command([*cli, "inspect", str(cli_build)], directory, "cli.inspection")
        assert cli_build.read_bytes() == build_path.read_bytes(), case
        assert cli_export.read_bytes() == (directory / "api.export.json").read_bytes(), case
        assert json.loads(cli_export.read_text(encoding="utf-8"))["fasta"] == exported.fasta
        replay = bc.PayloadArchitectureBuild.from_json(cli_build.read_text(encoding="utf-8"))
        assert bc.check_payload_architecture(replay, expected_request=restored).passed
        if case == "A":
            stale = replace(request, library=replace(request.library,
                            assumptions=(*request.library.assumptions, "Changed independent supply assumption.")))
            stale_path = directory / "stale.request.json"
            _save(stale_path, stale)
            _command([*cli, "architecture-verify", str(cli_build), "--expected-request", str(stale_path)],
                     directory, "stale.verification", expected=1)
            refused_path = directory / "refused.export.json"
            result = subprocess.run([*cli, "architecture-export", str(cli_build),
                                     "--expected-request", str(stale_path), "--output", str(refused_path)],
                                    capture_output=True, text=True, check=False)
            assert result.returncode == 2 and not refused_path.exists(), result.stderr
            (directory / "stale.export-rejection.json").write_text(json.dumps(
                {"returncode": result.returncode, "error": result.stderr.strip(), "artifact_created": False},
                sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(case, build.status, len(manifest["delivered_member_ids"]), "exact RNA members", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    package = Path(bc.__file__).resolve()
    assert not package.is_relative_to(REPOSITORY), "Installed smoke imported the checkout package."
    assert not Path.cwd().resolve().is_relative_to(REPOSITORY), "Run installed smoke outside the checkout."
    print("Installed package:", package, flush=True)
    check_install(args.output)


if __name__ == "__main__":
    main()
