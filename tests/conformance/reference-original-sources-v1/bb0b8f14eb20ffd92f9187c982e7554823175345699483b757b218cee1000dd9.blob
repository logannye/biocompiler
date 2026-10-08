"""JSON-driven synthetic checks, bounded campaigns and selected-failure replay.

Imported records are historical. Fresh verification requires independent complete
operation authority and reruns current checkers; no Python callbacks are imported.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from biocompiler.compiler.request import RealizationRequest
from biocompiler.ir.serialization import require
from biocompiler.synthesis.synthetic import (
    SyntheticCandidate,
    check_synthetic_candidate,
)
from biocompiler.verification.evidence import CheckResult, DependencySnapshot
from biocompiler.verification.exploration import (
    BooleanContactConfig,
    BooleanInputExplorationReport,
    ExplorationReport,
    FailureSignature,
    ReductionResult,
    _Record,
    _frames,
    _history,
    _integer,
    _validate_result,
    boolean_config_from_dict,
    explore_boolean_histories,
    reduce_counterexample,
)
from biocompiler.verification.realization import check_realization

WORKFLOW_VERSION = "biocompiler.synthetic_verification_workflow.v0.1"
CLAIM_SCOPE = (
    "Historical finite-history software-model verification record; fresh replay requires "
    "independent complete operation authority. No universal, biological or human therapeutic claim."
)


@dataclass(frozen=True)
class SyntheticVerificationRequest(_Record):
    """Complete operation authority, including exact history/bounds/failure/budget."""

    realization: RealizationRequest
    candidate: SyntheticCandidate
    operation: str
    mode: str = "candidate"
    history: tuple = ()
    until: int | float | None = None
    bounds: BooleanContactConfig | None = None
    signature: FailureSignature | None = None
    max_evaluations: int | None = None
    schema_version: ClassVar[str] = "biocompiler.synthetic_verification_request.v0.1"
    _decoders: ClassVar[dict] = {
        "realization": RealizationRequest.from_dict,
        "candidate": SyntheticCandidate.from_dict,
        "history": _frames,
        "bounds": lambda value: (
            boolean_config_from_dict(value) if value is not None else None
        ),
        "signature": lambda value: (
            FailureSignature.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        require(
            isinstance(self.realization, RealizationRequest),
            "Expected realization authority.",
        )
        require(
            isinstance(self.candidate, SyntheticCandidate),
            "Expected explicit candidate authority.",
        )
        require(
            self.operation in {"check", "explore", "reduce"},
            "Unsupported verification operation.",
        )
        require(self.mode in {"candidate", "model"}, "Unsupported verification mode.")
        if self.operation == "explore":
            require(
                isinstance(self.bounds, BooleanContactConfig),
                "Exploration needs explicit Boolean bounds.",
            )
            require(
                isinstance(self.history, (tuple, list))
                and not self.history
                and self.until is self.signature is self.max_evaluations is None,
                "Exploration authority must contain bounds only, not separate history/reduction controls.",
            )
            object.__setattr__(self, "history", ())
        else:
            require(
                self.bounds is None,
                "Check/reduction authority cannot include unused exploration bounds.",
            )
            object.__setattr__(self, "history", _history(self.history, self.until))
            if self.operation == "check":
                require(
                    self.signature is self.max_evaluations is None,
                    "A check cannot contain unused reduction controls.",
                )
            else:
                require(
                    isinstance(self.signature, FailureSignature),
                    "Reduction needs an explicit selected failure.",
                )
                _integer(self.max_evaluations, 1, 100000, "reduction evaluation budget")


def _result_from_dict(data):
    require(isinstance(data, dict), "Verification result must be an object.")
    schema = data.get("schema_version")
    require(isinstance(schema, str), "Verification result schema must be text.")
    cls = {
        item.schema_version: item
        for item in (
            CheckResult,
            ExplorationReport,
            BooleanInputExplorationReport,
            ReductionResult,
        )
    }.get(schema)
    require(cls is not None, "Unsupported verification result schema.")
    return cls.from_dict(data)


@dataclass(frozen=True)
class SyntheticVerificationRecord(_Record):
    request: SyntheticVerificationRequest
    result: CheckResult | ExplorationReport | ReductionResult
    workflow_version: str = WORKFLOW_VERSION
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "biocompiler.synthetic_verification_record.v0.1"
    _decoders: ClassVar[dict] = {
        "request": SyntheticVerificationRequest.from_dict,
        "result": _result_from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(self.request, SyntheticVerificationRequest),
            "Expected complete verification authority.",
        )
        require(
            self.workflow_version == WORKFLOW_VERSION
            and self.claim_scope == CLAIM_SCOPE,
            "Unsupported workflow version or claim scope.",
        )
        operation = self.request.operation
        if operation == "check":
            require(
                isinstance(self.result, CheckResult),
                "Check operation requires CheckResult.",
            )
            _validate_result(self.result, self.request.history, self.request.until)
        elif operation == "explore":
            require(
                isinstance(self.result, ExplorationReport),
                "Explore operation requires ExplorationReport.",
            )
            require(
                self.result.config.fingerprint == self.request.bounds.fingerprint,
                "Exploration result changed the independently declared bounds.",
            )
        else:
            require(
                isinstance(self.result, ReductionResult),
                "Reduce operation requires ReductionResult.",
            )
            from biocompiler.ir.serialization import fingerprint

            require(
                fingerprint([frame.to_dict() for frame in self.result.original_history])
                == fingerprint([frame.to_dict() for frame in self.request.history])
                and fingerprint(self.result.until) == fingerprint(self.request.until)
                and self.result.signature == self.request.signature
                and self.result.evaluations <= self.request.max_evaluations,
                "Reduction result changed its original history, horizon, selected failure or budget.",
            )


def _checker(request):
    def check(history, *, until):
        if request.mode == "candidate":
            result = check_synthetic_candidate(
                request.realization,
                request.candidate,
                history,
                until=until,
            )
        else:
            realization = request.realization
            result = check_realization(
                realization.behavior,
                realization.contract,
                realization.domain,
                realization.target,
                request.candidate.mechanism,
                request.candidate.observation_map,
                history,
                until=until,
            )
        # This marks the precise wrapper/mode. Model mode does not pretend that
        # candidate provenance or component admission were accepted.
        dependencies = result.dependencies.values
        return replace(
            result,
            dependencies=DependencySnapshot(
                {
                    **dependencies,
                    "settings": {
                        **dependencies["settings"],
                        "verification_workflow": WORKFLOW_VERSION,
                        "verification_mode": request.mode,
                        "verification_candidate": request.candidate.fingerprint,
                        "verification_realization": request.realization.artifact_fingerprint,
                    },
                }
            ),
        )

    return check


def run_synthetic_verification(
    request: SyntheticVerificationRequest,
    *,
    core=None,
) -> SyntheticVerificationRecord:
    """Execute the declared operation; retain FAIL/UNKNOWN/UNSUPPORTED outcomes."""
    if core is not None:
        from biocompiler.workflow_backend import run_record

        return run_record(request, core=core)
    require(
        isinstance(request, SyntheticVerificationRequest),
        "Expected complete verification request.",
    )
    check = _checker(request)
    if request.operation == "check":
        result = check(request.history, until=request.until)
    elif request.operation == "explore":
        result = explore_boolean_histories(request.bounds, check)
    else:
        result = reduce_counterexample(
            request.history,
            request.until,
            check,
            request.signature,
            max_evaluations=request.max_evaluations,
        )
    return SyntheticVerificationRecord(request, result)


def replay_synthetic_verification(
    record: SyntheticVerificationRecord,
    *,
    expected_request: SyntheticVerificationRequest,
    core=None,
) -> SyntheticVerificationRecord:
    """Recompute against current trusted code and exact independently retained inputs."""
    if core is not None:
        from biocompiler.workflow_backend import replay_record

        return replay_record(record, expected_request=expected_request, core=core)
    require(
        isinstance(record, SyntheticVerificationRecord),
        "Expected historical verification record.",
    )
    require(
        isinstance(expected_request, SyntheticVerificationRequest),
        "Fresh replay needs independently trusted complete operation authority.",
    )
    require(
        record.request.fingerprint == expected_request.fingerprint,
        "Verification operation differs from independent authority.",
    )
    rebuilt = run_synthetic_verification(expected_request)
    require(
        rebuilt.fingerprint == record.fingerprint,
        "Verification evidence is stale, altered or unsupported by current tools.",
    )
    return rebuilt
