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
    if isinstance(artifact, (ComponentAssembly, CompositionResult, SelectionResult)):
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
        "architecture", help="Show planned intermediate representations"
    )
    inspect_command = commands.add_parser(
        "inspect", help="Inspect a saved versioned JSON artifact"
    )
    inspect_command.add_argument(
        "path",
        type=Path,
        help="Request, intent, behavior, mechanism, contract, domain, context, map, or check JSON file",
    )
    inspect_command.add_argument(
        "--json", action="store_true", help="Print the normalized full graph"
    )
    args = parser.parse_args(argv)
    if args.command == "architecture":
        print(
            "CellWeave pipeline (frozen requests, checked synthetic generation and component linking implemented; molecular lowering planned)"
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
