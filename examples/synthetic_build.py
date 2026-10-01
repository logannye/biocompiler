"""Freeze and independently reproduce the temporal software-model package offline.

Run: PYTHONPATH=src python examples/synthetic_build.py --output generated/synthetic
"""

import argparse
import json
from pathlib import Path
import tempfile

from biocompiler.artifacts.synthetic_build import (
    SyntheticBuildRequest,
    SyntheticHistory,
)
from biocompiler.compiler.synthetic_build import (
    build_synthetic_package,
    publish_synthetic_package,
    verify_synthetic_package,
)
from biocompiler.registry.synthetic import TEMPORAL_PROFILE_VERSION
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig

if __package__:
    from .temporal_pipeline import build_request
else:
    from temporal_pipeline import build_request


def prepare_request():
    realization, history = build_request()
    return SyntheticBuildRequest(
        realization,
        SyntheticHistory(history),
        9,
        SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION),
    )


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    request = prepare_request()
    package = build_synthetic_package(request)
    # Independently retain complete input authority before later reconstruction.
    (output / "request.json").write_text(request.to_json() + "\n", encoding="utf-8")
    path = publish_synthetic_package(package, output / "temporal.bcb")
    restored = verify_synthetic_package(path.read_bytes(), expected_request=request)
    assert restored.data == package.data
    print(
        json.dumps(
            {
                "build_fingerprint": package.build_fingerprint,
                "archive_sha256": package.archive_sha256,
                "scope": "synthetic_realization",
                "profile": request.config.profile_version,
                "intended_use": "software_test",
                "human_therapeutic_admission": "not_admitted",
                "unresolved": ["molecular_behavior"],
                "verification": "fresh independent offline reconstruction passed",
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        run(args.output)
    else:
        with tempfile.TemporaryDirectory(
            prefix="biocompiler-synthetic-example-"
        ) as directory:
            run(Path(directory))


if __name__ == "__main__":
    main()
