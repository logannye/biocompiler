"""Inspect versioned compiler artifacts and the compiler architecture."""

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from cellweave import __version__
from cellweave.compiler.request import BuildRequest, RealizationRequest
from cellweave.ir.stages import STAGE_ORDER
from cellweave.errors import SerializationError
from cellweave.ir.intent import IntentProgram
from cellweave.ir.behavior import BehaviorProgram, SCHEMA_VERSION as BEHAVIOR_SCHEMA
from cellweave.ir.intent import SCHEMA_VERSION as INTENT_SCHEMA
from cellweave.ir.mechanism import MechanismProgram
from cellweave.ir.serialization import parse_json
from cellweave.semantics.context import TargetContext
from cellweave.semantics.realization import BehaviorContract, OperatingDomain
from cellweave.verification.evidence import CheckResult
from cellweave.verification.exploration import (
    AdversarialConfig,
    BooleanContactConfig,
    ExplorationReport,
    ReductionResult,
)
from cellweave.verification.realization import ObservationMap
from cellweave.synthesis.synthetic import SyntheticCandidate, SyntheticGeneratorConfig
from cellweave.registry.synthetic import SyntheticCatalog
from cellweave.registry.references import ReferenceManifest
from cellweave.ir.component_assembly import ComponentAssembly
from cellweave.ir.component_contracts import ComponentRecord
from cellweave.ir.composition import CompositionRequest
from cellweave.registry.components import (
    ComponentRegistry,
    RegistryLock,
    SelectionRequest,
    SelectionResult,
)
from cellweave.registry.reference_components import ReferenceSelection
from cellweave.semantics.component_contracts import (
    OperatingDomain as ComponentOperatingDomain,
    PortContract,
    ValueDomain,
)
from cellweave.verification.components import CompositionResult
from cellweave.ir.construct import ConstructCandidate, ConstructRequest
from cellweave.verification.construct import ConstructResult
from cellweave.ir.molecular import MolecularArtifact
from cellweave.verification.molecular import MolecularResult
from cellweave.artifacts.archive import read_archive
from cellweave.artifacts.manifest import (
    BuildManifest,
    ReferenceBuildRequest,
    RunMetadata,
)
from cellweave.compiler.reference import (
    build_reference_package,
    prepare_reference_build,
    publish_reference_package,
    verify_reference_package,
)
from cellweave.compiler.pipeline import PipelineError


def _read_artifact(document):
    # Parse strictly before dispatch: duplicate schema keys must not select a
    # different parser or weaken an artifact's validation boundary.
    header = parse_json(document)
    schema = header.get("schema_version") if isinstance(header, dict) else None
    types = {INTENT_SCHEMA: IntentProgram, BEHAVIOR_SCHEMA: BehaviorProgram}
    types.update(
        {
            cls.schema_version: cls
            for cls in (
                BuildRequest,
                RealizationRequest,
                SyntheticCandidate,
                SyntheticGeneratorConfig,
                SyntheticCatalog,
                ReferenceManifest,
                MechanismProgram,
                TargetContext,
                BehaviorContract,
                OperatingDomain,
                ObservationMap,
                CheckResult,
                AdversarialConfig,
                BooleanContactConfig,
                ExplorationReport,
                ReductionResult,
                ComponentAssembly,
                ComponentRecord,
                CompositionRequest,
                ComponentRegistry,
                RegistryLock,
                SelectionRequest,
                SelectionResult,
                ReferenceSelection,
                ComponentOperatingDomain,
                PortContract,
                ValueDomain,
                CompositionResult,
                ConstructRequest,
                ConstructCandidate,
                ConstructResult,
                MolecularArtifact,
                MolecularResult,
                BuildManifest,
                ReferenceBuildRequest,
                RunMetadata,
            )
        }
    )
    if not isinstance(schema, str) or schema not in types:
        raise SerializationError(f"Unknown or missing artifact schema: {schema!r}.")
    return types[schema].from_dict(header)


def _summary(artifact):
    if isinstance(artifact, (IntentProgram, BehaviorProgram)):
        return artifact.summary()
    summary = {
        "schema_version": artifact.schema_version,
        "fingerprint": artifact.fingerprint,
    }
    for key in ("id", "name", "context_id", "outcome", "evidence_kind"):
        if hasattr(artifact, key):
            summary[key] = getattr(artifact, key)
    if isinstance(artifact, ReferenceManifest):
        summary["reference_set_id"] = artifact.reference_set_id
        summary["status"] = artifact.status
        summary["inspection"] = (
            "Schema/content inspection only; use load_reference_manifest with a trusted fingerprint to verify retained source files."
        )
    if isinstance(artifact, CheckResult):
        summary["counterexamples"] = len(artifact.counterexamples)
        summary["diagnostics"] = [item.to_dict() for item in artifact.diagnostics]
    if isinstance(
        artifact,
        (
            ComponentAssembly,
            CompositionResult,
            SelectionResult,
            ConstructRequest,
            ConstructCandidate,
            ConstructResult,
            MolecularArtifact,
            MolecularResult,
            ExplorationReport,
            ReductionResult,
            BuildManifest,
            ReferenceBuildRequest,
        ),
    ):
        summary["inspection"] = (
            "Historical content inspection only; recompute acceptance and freshness against current authoritative inputs before reuse."
        )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"cellweave {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "architecture", help="Show implemented and planned compiler stages"
    )
    inspect_command = commands.add_parser(
        "inspect", help="Inspect a saved versioned JSON artifact"
    )
    inspect_command.add_argument(
        "path",
        type=Path,
        help="Request, graph, component, construct, molecular, contract, context, or check JSON file",
    )
    inspect_command.add_argument(
        "--json", action="store_true", help="Print the normalized full graph"
    )
    reference_build = commands.add_parser(
        "reference-build", help="Build one pinned DNA/RNA reference CDS package offline"
    )
    source = reference_build.add_mutually_exclusive_group(required=True)
    source.add_argument("--alphabet", choices=("DNA", "RNA"))
    source.add_argument(
        "--request", type=Path, help="Frozen ReferenceBuildRequest JSON"
    )
    reference_build.add_argument("--reference-dir", type=Path, required=True)
    reference_build.add_argument(
        "--output", type=Path, required=True, help="Atomic .cwb package destination"
    )
    reference_build.add_argument(
        "--run-metadata",
        type=Path,
        help="Optional RunMetadata JSON, excluded from build identity",
    )
    reference_inspect = commands.add_parser(
        "reference-inspect",
        help="Inspect package integrity without granting fresh acceptance",
    )
    reference_inspect.add_argument("path", type=Path)
    reference_verify = commands.add_parser(
        "reference-verify", help="Rebuild and independently check a package offline"
    )
    reference_verify.add_argument("path", type=Path)
    authority = reference_verify.add_mutually_exclusive_group(required=True)
    authority.add_argument(
        "--expected-build", help="Independently retained canonical build fingerprint"
    )
    authority.add_argument(
        "--expected-request",
        type=Path,
        help="Independently retained ReferenceBuildRequest JSON",
    )
    args = parser.parse_args(argv)
    if args.command.startswith("reference-"):
        try:
            if args.command == "reference-build":
                request = (
                    ReferenceBuildRequest.from_json(
                        args.request.read_text(encoding="utf-8")
                    )
                    if args.request
                    else prepare_reference_build(args.alphabet, args.reference_dir)
                )
                metadata = (
                    RunMetadata.from_json(args.run_metadata.read_text(encoding="utf-8"))
                    if args.run_metadata
                    else None
                )
                package = build_reference_package(
                    request, args.reference_dir, run_metadata=metadata
                )
                output = publish_reference_package(package, args.output)
                print(
                    json.dumps(
                        {
                            "output": str(output),
                            "build_fingerprint": package.build_fingerprint,
                            "archive_sha256": package.archive_sha256,
                            "scope": "exact_cds",
                            "status": "complete",
                            "unresolved": [
                                "complete_payload_features",
                                "molecular_behavior",
                            ],
                        },
                        indent=2,
                    )
                )
            else:
                if args.path.stat().st_size > 64 * 1024 * 1024:
                    raise SerializationError(
                        "Reference archive exceeds the size limit."
                    )
                data = args.path.read_bytes()
                if args.command == "reference-verify":
                    expected = (
                        ReferenceBuildRequest.from_json(
                            args.expected_request.read_text(encoding="utf-8")
                        )
                        if args.expected_request
                        else None
                    )
                    package = verify_reference_package(
                        data,
                        expected_request=expected,
                        expected_build_fingerprint=args.expected_build,
                    )
                    print(
                        json.dumps(
                            {
                                "build_fingerprint": package.build_fingerprint,
                                "scope": "exact_cds",
                                "verification": "fresh independent offline reconstruction passed",
                                "unresolved": [
                                    "complete_payload_features",
                                    "molecular_behavior",
                                ],
                            },
                            indent=2,
                        )
                    )
                else:
                    manifest, _, metadata = read_archive(data)
                    print(
                        json.dumps(
                            {
                                "build_fingerprint": manifest.build_fingerprint,
                                "scope": manifest.scope,
                                "files": len(manifest.files),
                                "run_metadata": metadata.to_dict()
                                if metadata
                                else None,
                                "inspection": "Historical content and file integrity only; acceptance requires independent authority and current offline reconstruction.",
                            },
                            indent=2,
                        )
                    )
        except (
            OSError,
            UnicodeError,
            SerializationError,
            PipelineError,
            RecursionError,
        ) as exc:
            print(f"cellweave: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.command == "architecture":
        print(
            "CellWeave pipeline (checked synthetic generation, component linking, reference construct assembly and exact DNA/RNA CDS emission implemented; reproducible reference packaging implemented)"
        )
        print("Python authoring -> immutable intent graph")
        for stage in STAGE_ORDER:
            print(f"  -> {stage.value}")
        print("  -> packaged digital build artifact")
        print(
            "Independent checking: contract + domain + target + observation map + supplied history"
        )
    elif args.command == "inspect":
        try:
            document = args.path.read_text(encoding="utf-8")
            program = _read_artifact(document)
        except (
            OSError,
            UnicodeError,
            SerializationError,
            json.JSONDecodeError,
            RecursionError,
        ) as exc:
            print(f"cellweave: {exc}", file=sys.stderr)
            return 2
        print(
            program.to_json() if args.json else json.dumps(_summary(program), indent=2)
        )
    return 0
