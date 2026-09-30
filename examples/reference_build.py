"""Build, relocate and independently reconstruct separate pinned CDS packages."""

from pathlib import Path
import tempfile

from biocompiler import (
    build_reference_package,
    prepare_reference_build,
    publish_reference_package,
    verify_reference_package,
)


def main():
    reference_directory = (
        Path(__file__).resolve().parents[1] / "data/references/fap_car"
    )
    with tempfile.TemporaryDirectory() as temporary:
        for alphabet in ("DNA", "RNA"):
            request = prepare_reference_build(alphabet, reference_directory)
            package = build_reference_package(request, reference_directory)
            path = publish_reference_package(
                package, Path(temporary) / f"{alphabet}.bcb"
            )
            restored = verify_reference_package(
                path.read_bytes(), expected_request=request
            )
            assert restored.data == package.data
            print(f"{alphabet}-CDS: complete; build {package.build_fingerprint}")
            print("Offline reconstruction: pass; whole-CDS scope only")
            print("Unresolved: complete_payload_features, molecular_behavior")


if __name__ == "__main__":
    main()
