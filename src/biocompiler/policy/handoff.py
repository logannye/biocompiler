"""Immutable authoring submissions and explicit feature comparisons.

Nothing here discovers or executes a compiler. Structural authoring closure and
caller-declared feature coverage grant no semantic, biological or export acceptance.
"""
from __future__ import annotations

from dataclasses import fields

from . import model
from .model import BackendCapabilities, CapabilityAssessment, CompilationSubmission
from .serialization import dumps, document_digest, to_data


class SubmissionError(ValueError):
    """Authoring data cannot yet be prepared for an explicit backend."""


def _document(document: model.Record) -> model.PolicyProgram | model.BuildRequest:
    if not isinstance(document, (model.PolicyProgram, model.BuildRequest)) or type(document) not in (model.PolicyProgram, model.BuildRequest):
        raise SubmissionError('Finalize a PolicyDraft before preparing a PolicyProgram or BuildRequest submission.')
    to_data(document)
    return document


def _dependencies(document: model.Record) -> tuple[model.DefinitionRef, ...]:
    retained: set[tuple[str, str, str]] = set()

    def visit(value: object) -> None:
        if isinstance(value, model.DefinitionRef):
            retained.add((value.id, value.version, value.digest))
        elif isinstance(value, model.Record):
            for item in fields(value):
                if item.name != 'source_map':
                    visit(getattr(value, item.name))
        elif isinstance(value, tuple):
            for element in value:
                visit(element)

    # Serialization has already bounded this closed immutable graph.
    visit(document)
    return tuple(model.DefinitionRef(*item) for item in sorted(retained))


def prepare_submission(document: model.Record) -> CompilationSubmission:
    """Freeze a structurally complete BuildRequest into an unexecuted submission."""
    from .validation import check

    candidate = _document(document)
    if not isinstance(candidate, model.BuildRequest):
        raise SubmissionError('Submission requires a BuildRequest with explicit deployment, catalog and assurance.')
    report = check(candidate)
    if report.status != 'complete' or report.errors:
        raise SubmissionError('Submission requires structurally complete authoring; resolve errors and design holes first.')
    program = candidate.program
    result = CompilationSubmission(
        request=candidate, profile=candidate.profile,
        document_digest=document_digest(candidate), program_digest=document_digest(program),
        semantic_bundle=model.DefinitionRef(program.semantics.id, program.semantics.version,
                                            document_digest(program.semantics)),
        implementation_catalog=model.DefinitionRef(candidate.implementations.id, candidate.implementations.version,
                                                   document_digest(candidate.implementations)),
        dependencies=_dependencies(candidate), required_features=report.required_features,
        assumptions=report.assumptions, outstanding_obligations=report.deferred_obligations,
    )
    # Use the same bounded wire contract as every other policy document.
    dumps(result, indent=None)
    return result


def assess_capabilities(document: model.Record, capabilities: BackendCapabilities) -> CapabilityAssessment:
    """Compare required features to an explicit declaration without dispatch."""
    from .validation import check

    candidate = _document(document)
    if type(capabilities) is not BackendCapabilities:
        raise SubmissionError('Supply an explicit BackendCapabilities declaration.')
    to_data(capabilities)
    report = check(candidate)
    required = tuple(sorted(set(report.required_features)))
    supported = set(capabilities.features)
    missing = tuple(value for value in required if value not in supported)
    profile_supported = candidate.profile in capabilities.profiles
    complete = report.status == 'complete' and not report.errors
    return CapabilityAssessment(
        backend_id=capabilities.backend_id, backend_version=capabilities.version,
        profile=candidate.profile, profile_supported=profile_supported,
        document_digest=document_digest(candidate), authoring_status=report.status,
        required_features=required, supported_features=tuple(value for value in required if value in supported),
        unsupported_features=missing,
        status='declared_compatible' if complete and profile_supported and not missing else 'unsupported',
        target_status='unassessed' if isinstance(candidate, model.BuildRequest) else 'unbound',
    )
