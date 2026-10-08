"""Hosted declaration emission and inert provenance for grounded_helper originals.

This separately versioned route binds the private domain-only grounded-helper exporter
and all five original input files. The emitted packet grants no acceptance.
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from . import check_policy_component_fixture as shared
except ImportError:
    import check_policy_component_fixture as shared

SCHEMA = "biocompiler.policy_grounded_helper_fixture_provenance.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_grounded_helper_original_fixture.v0.1"
OUTPUT = "generated/core/grounded-helper-originals"
INPUTS = tuple(shared.development.GROUNDED_HELPER_ORIGINALS)
BINARIES = {
    "originals": shared.development.SDK_BINARIES["grounded_helper_originals"],
    "core": shared.development.SDK_BINARIES["core"],
    "verify": shared.development.SDK_BINARIES["verify"],
}
PROFILE = shared.FixtureProfile(SCHEMA, FIXTURE_SCHEMA, OUTPUT, INPUTS, tuple(BINARIES.items()))
MAX_FIXTURE, MAX_PROVENANCE, MAX_LOG = shared.MAX_FIXTURE, shared.MAX_PROVENANCE, shared.MAX_LOG
pin, read = shared.pin, shared.read


def logical_command():
    return shared.logical_command(profile=PROFILE)


def check_packet(root, path):
    return shared.check_packet(Path(root), path, profile=PROFILE)


def validate(root, fixture_path, provenance_path, *, identity, native_sha256, expected_platform=None):
    """Validate an externally bound grounded_helper packet without native execution."""
    return shared.validate(root, fixture_path, provenance_path, identity=identity,
        native_sha256=native_sha256, expected_platform=expected_platform, profile=PROFILE)


def emit(root):
    return shared.emit(root, profile=PROFILE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("emit",))
    parser.parse_args()
    emit(Path(__file__).resolve().parents[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
