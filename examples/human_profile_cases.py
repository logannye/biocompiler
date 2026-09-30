"""M10.6 request cases: software observations, never admitted human payloads.

Run with --output DIRECTORY to retain evidence, or --verify DIRECTORY to compare
it with fresh results from the current, independently retained example authority.
"""

import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path

import biocompiler as bc
from biocompiler.ir.serialization import fingerprint, require

if __package__:
    from .human_acceptance import make_human_acceptance, example_trace, sample
    from .human_deployment import PLATFORM_SOURCE, co_payload_fixture, seconds
else:
    from human_acceptance import make_human_acceptance, example_trace, sample
    from human_deployment import PLATFORM_SOURCE, co_payload_fixture, seconds

PROFILE = "biocompiler.proposed_conditional_secretion_examples.v0.1"
SCOPE = "artificial_request_and_supplied_observation_examples_only"


@dataclass(frozen=True)
class RequestCase:
    id: str
    category: str
    description: str
    request: bc.HumanAcceptanceRequest
    trace: tuple[bc.AcceptanceSample, ...]
    expected_outcome: str
    expected_diagnostic: str | None = None


def portable_request():
    """Retain authored lines/functions under their logical checkout-relative path."""
    request = make_human_acceptance()
    build = request.build_request
    nodes = []
    for node in build.intent.nodes:
        require(node.source is not None, "Example source correspondence is required.")
        require(
            Path(node.source.file).name == "human_behavior.py",
            "Unexpected fixture source.",
        )
        nodes.append(
            replace(
                node, source=replace(node.source, file="examples/human_behavior.py")
            )
        )
    behavior = replace(
        request.behavior_request,
        build_request=replace(build, intent=replace(build.intent, nodes=tuple(nodes))),
    )
    portable = replace(
        request,
        deployment_request=replace(
            request.deployment_request, behavior_request=behavior
        ),
    )
    require(
        portable.fingerprint == request.fingerprint,
        "Logical source paths must not change semantic authority.",
    )
    return portable


def make_cases():
    request, trace = portable_request(), example_trace()
    deployment = request.deployment_request.deployment

    def with_deployment(**changes):
        return replace(
            request,
            deployment_request=replace(
                request.deployment_request, deployment=replace(deployment, **changes)
            ),
        )

    silent = tuple(replace(item, output_value=bc.ProductionRate(0)) for item in trace)
    peak = (*trace[:2], sample(2, cue=6, rate=5), *trace[2:])
    missing = tuple(
        replace(item, output_value=None) if i == 2 else item
        for i, item in enumerate(trace)
    )
    conflicting = replace(
        request,
        acceptance=replace(
            request.acceptance,
            healthy_range=bc.Interval(bc.Level(0), bc.Level(0.8), type=bc.Level),
        ),
    )
    conflicting_trace = tuple(
        replace(item, context_value=bc.Level(0.6)) if i in (1, 2) else item
        for i, item in enumerate(missing)
    )
    unknown_deployment = with_deployment(
        timing=replace(
            deployment.timing,
            onset=None,
            duration=None,
            unknown_reason="No applicable expression bounds are supplied.",
        ),
        exposures=tuple(
            replace(
                item, domain=bc.ValueDomain.unknown(reason="Exposure bounds missing.")
            )
            for item in deployment.exposures
        ),
    )
    return (
        RequestCase(
            "positive",
            "positive",
            "Full finite fixture coverage and compatible invented bounds.",
            request,
            trace,
            "pass",
        ),
        RequestCase(
            "negative_silent",
            "negative",
            "Inactivity cannot satisfy the required active secretion response.",
            request,
            silent,
            "fail",
            "active_range_violation_at:",
        ),
        RequestCase(
            "negative_peak",
            "negative",
            "An observed peak violates the ceiling even during activation grace.",
            request,
            peak,
            "fail",
            "peak_ceiling_exceeded_at:",
        ),
        RequestCase(
            "negative_expression_window",
            "negative",
            "The declared expression duration cannot cover the required behavior horizon.",
            with_deployment(
                timing=replace(deployment.timing, duration=seconds(10, 15))
            ),
            trace,
            "fail",
            "expression_duration_does_not_cover_behavior",
        ),
        RequestCase(
            "conflicting_healthy",
            "conflicting",
            "A broader healthy-context requirement conflicts with the due source response.",
            conflicting,
            conflicting_trace,
            "fail",
            "required_active_conflicts_with_healthy_at:",
        ),
        RequestCase(
            "underspecified_deployment",
            "underspecified",
            "Absent exposure and expression bounds remain explicit unknowns.",
            unknown_deployment,
            trace,
            "unknown",
            "expression_window_unknown",
        ),
        RequestCase(
            "underspecified_observations",
            "underspecified",
            "An unmeasured output is not a measured zero or a demonstrated violation.",
            request,
            missing,
            "unknown",
            "output_unobserved_at:",
        ),
        RequestCase(
            "unsupported_co_payload",
            "unsupported",
            "A same-cell co-payload requirement has no supported deployment implementation.",
            with_deployment(co_payloads=(co_payload_fixture(),)),
            trace,
            "unsupported",
            "same_cell_co_payload_delivery_unsupported",
        ),
        RequestCase(
            "unsupported_destination",
            "unsupported",
            "The declared RNA destination lies outside the supported deployment profile.",
            with_deployment(intracellular_destination="extracellular"),
            trace,
            "unsupported",
            "deployment_destination_profile_unsupported",
        ),
        RequestCase(
            "failure_with_unknown",
            "negative",
            "A known peak violation remains a failure when another output is unobserved.",
            request,
            (*missing[:2], sample(2, cue=6, rate=5), *missing[2:]),
            "fail",
            "peak_ceiling_exceeded_at:",
        ),
    )


def assess_case(case):
    """Run current checks; expected labels are regression assertions, never evidence."""
    request = case.request
    result = bc.check_human_acceptance(request, case.trace)
    require(
        result.outcome == case.expected_outcome,
        f"Unexpected outcome for {case.id}: {result.diagnostics}",
    )
    if case.expected_diagnostic:
        require(
            any(
                item.startswith(case.expected_diagnostic) for item in result.diagnostics
            ),
            f"Missing diagnostic for {case.id}: {result.diagnostics}",
        )
    deployment = bc.check_deployment(request.deployment_request)
    admission_request = bc.AdmissionRequest(
        request.target, "human_therapeutic", "planning"
    )
    admission = bc.assess_admission(admission_request)
    require(
        admission.decision == "not_admitted",
        "This example suite cannot admit human profiles.",
    )
    try:
        bc.compile(request)
    except bc.CompilationUnavailableError as error:
        compilation = {
            "status": "unavailable",
            "diagnostics": [item.code for item in error.diagnostics],
        }
    else:
        raise RuntimeError("M10.6 examples must not enable human payload compilation.")
    artifacts = {
        "request.json": request.to_dict(),
        "trace.json": [item.to_dict() for item in case.trace],
        "acceptance.json": result.to_dict(),
        "deployment.json": deployment.to_dict(),
        "admission-request.json": admission_request.to_dict(),
        "admission.json": admission.to_dict(),
        "compilation.json": compilation,
    }
    row = {
        "id": case.id,
        "category": case.category,
        "description": case.description,
        "request_fingerprint": request.fingerprint,
        "request_artifact_fingerprint": request.artifact_fingerprint,
        "trace_fingerprint": result.trace_fingerprint,
        "acceptance": result.outcome,
        "deployment": deployment.compatibility,
        "diagnostics": list(result.diagnostics),
        "coverage": list(result.coverage),
        "unresolved_evidence": list(result.unresolved_evidence),
        "admission": admission.decision,
        "compilation": compilation["status"],
        "mechanism_search": "not_performed",
        "biological_feasibility": "unestablished",
    }
    return row, artifacts


def explore_traces(request, candidates, *, budget):
    """Enumerate supplied artificial traces only; never search molecules/mechanisms.

    Exhaustion cannot produce an infeasibility result. Every checked outcome and
    the exact ordered candidate inventory remain visible, including UNKNOWN.
    """
    require(
        type(budget) is int and budget >= 0, "Budget must be a nonnegative integer."
    )
    candidates = tuple((name, tuple(trace)) for name, trace in candidates)
    require(
        all(isinstance(name, str) and name for name, _ in candidates),
        "Candidate IDs required.",
    )
    require(
        len({name for name, _ in candidates}) == len(candidates),
        "Duplicate candidate IDs.",
    )
    inventory = [
        {"id": name, "trace": [item.to_dict() for item in trace]}
        for name, trace in candidates
    ]
    checked, witness = [], None
    for name, trace in candidates[:budget]:
        result = bc.check_human_acceptance(request, trace)
        checked.append({"id": name, "result": result.to_dict()})
        if result.outcome == "pass":
            witness = name
            break
    outcome = (
        "witness_found"
        if witness is not None
        else "budget_exhausted"
        if len(checked) < len(candidates)
        else "candidate_set_exhausted"
    )
    return {
        "schema_version": "biocompiler.example_trace_search.v0.1",
        "scope": "supplied_artificial_trace_candidates_only",
        "request_fingerprint": request.fingerprint,
        "candidate_set_fingerprint": fingerprint(inventory),
        "candidates": inventory,
        "budget": budget,
        "checked": checked,
        "unchecked_count": len(candidates) - len(checked),
        "outcome": outcome,
        "witness": witness,
        "infeasibility": "not_established",
        "biological_feasibility": "unestablished",
        "mechanism_search": "not_performed",
        "human_therapeutic_admission": "not_admitted",
    }


def explain_healthy_rate_conflict(request):
    """A narrow interval contradiction, independently of candidate output values.

    This is conditional on a due active source requirement in an observed healthy
    context. It proves neither reachability nor biological infeasibility.
    """
    request = bc.HumanAcceptanceRequest.from_dict(request.to_dict())
    contract = request.behavior_request.contract
    acceptance = request.acceptance
    lower = contract.response.active_range.lower
    upper = acceptance.background_ceiling
    require(
        lower.canonical_value > upper.canonical_value,
        "No disjoint rate-bound proof is established.",
    )
    return {
        "schema_version": "biocompiler.example_rate_conflict.v0.1",
        "request_fingerprint": request.fingerprint,
        "condition": "source_active_requirement_due_and_context_observed_in_healthy_range",
        "required_lower_bound": lower.to_dict(),
        "prohibited_upper_bound": upper.to_dict(),
        "context_domain": acceptance.context_domain.to_dict(),
        "healthy_range": acceptance.healthy_range.to_dict(),
        "proof": "required_lower_bound_strictly_greater_than_prohibited_upper_bound",
        "formal_feasibility": "infeasible_under_stated_condition",
        "scope": "simultaneous_output_rate_constraints_only",
        "reachability": "not_proved",
        "biological_feasibility": "unestablished",
        "human_therapeutic_admission": "not_admitted",
    }


def json_bytes(data):
    return (
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def generate_artifacts():
    cases = make_cases()
    rows, artifacts = [], {"platform-fixture.txt": PLATFORM_SOURCE}
    for case in cases:
        row, records = assess_case(case)
        rows.append(row)
        artifacts.update(
            {f"{case.id}/{name}": json_bytes(data) for name, data in records.items()}
        )
    by_id = {case.id: case for case in cases}
    candidates = tuple(
        (name, by_id[name].trace)
        for name in ("negative_silent", "underspecified_observations")
    )
    request = by_id["positive"].request
    expanded = (*candidates, ("positive", by_id["positive"].trace))
    searches = {
        "candidate_set_exhausted": explore_traces(request, candidates, budget=2),
        "budget_exhausted": explore_traces(request, expanded, budget=1),
        "witness_found": explore_traces(request, expanded, budget=3),
    }
    for name, data in searches.items():
        require(data["outcome"] == name, "Trace-search example outcome changed.")
        artifacts[f"search/{name}.json"] = json_bytes(data)
    artifacts["conflicting_healthy/rate-conflict.json"] = json_bytes(
        explain_healthy_rate_conflict(by_id["conflicting_healthy"].request)
    )
    summary = {
        "schema_version": "biocompiler.human_profile_example_suite.v0.1",
        "profile": PROFILE,
        "scope": SCOPE,
        "cases": rows,
        "human_therapeutic_admission": "not_admitted",
        "compilation": "unavailable",
        "biological_applicability": "unestablished",
        "search_examples": {name: data["outcome"] for name, data in searches.items()},
        "inspection": "Example evidence only. Recompute against current independent fixture authority; saved summaries do not grant admission.",
    }
    artifacts["summary.json"] = json_bytes(summary)
    return artifacts


def verify_saved(directory, expected):
    """Compare to fresh fixture results, never expectations read from this directory."""
    directory = Path(directory)
    require(
        directory.is_dir() and not directory.is_symlink(),
        "Expected regular evidence directory.",
    )
    entries = tuple(directory.rglob("*"))
    require(
        not any(path.is_symlink() for path in entries),
        "Evidence symlinks are unsupported.",
    )
    files = {
        path.relative_to(directory).as_posix(): path
        for path in entries
        if path.is_file()
    }
    require(
        set(files) == set(expected),
        "Example evidence inventory differs from current fixture authority.",
    )
    for name, content in expected.items():
        require(
            files[name].stat().st_size == len(content)
            and files[name].read_bytes() == content,
            f"Stale or altered example evidence: {name}",
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--output", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args(argv)
    artifacts = generate_artifacts()
    if args.verify:
        verify_saved(args.verify, artifacts)
        print("Example evidence matches fresh current fixture checks.")
    if args.output:
        for name, content in artifacts.items():
            path = args.output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    for row in json.loads(artifacts["summary.json"])["cases"]:
        print(
            f"{row['id']}: acceptance={row['acceptance']}; deployment={row['deployment']}; admission={row['admission']}"
        )
    print(
        "Trace candidates: exhausted set / exhausted budget / witness found; no infeasibility inferred."
    )
    print(
        "Healthy-context rate contradiction: infeasible only under the stated simultaneous-constraint condition."
    )
    print(
        "All cases: human compilation unavailable; biological applicability unestablished."
    )


if __name__ == "__main__":
    main()
