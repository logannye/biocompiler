"""Author a bounded staged policy through the public Python SDK.

The reference project supplies complete original implementation/material inputs;
this script authors a new source and never changes those supplied contracts.
The example is an artificial software case, not a functional immune therapy.
Preparation does not execute Core or Verify. Compile the saved project using
researcher_alpha.py (or ResearchProject.compile) for fresh native assessment.

    python author_staged_research_project.py reference.project.json authored.project.json
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from typing import Sequence

from biocompiler import policy as p
from biocompiler.policy.research_project import ResearchProject, SourceRecord


def build_request() -> p.BuildRequest:
    """Declare the complete supported same-product, two-stage software source.

    These definition texts intentionally identify the supplied engineering
    contracts. Replacing the source or their meanings requires fresh native
    checking; it never implicitly authorizes matching component declarations.
    """
    interface = p.SemanticDefinition("staged.interface", "1", "interface", "Supplied abstract executor interface.")
    encounter_contract = p.SemanticDefinition("staged.encounter", "1", "encounter", "Explicit encounter identity and reset generation.")
    observation = p.SemanticDefinition("staged.observation", "1", "observation", "Timestamped supplied truth evidence.", result=p.TRUTH)
    operation = p.SemanticDefinition("staged.operation", "1", "operation",
        "Request the same abstract product in two distinctly identified stages.", parameters=(p.Parameter("product", p.TEXT),))
    lifecycle_contract = p.SemanticDefinition("staged.lifecycle", "1", "lifecycle",
        "Attempt/executor/subject-correlated completion or failure; explicit timeout.")
    chassis_contract = p.SemanticDefinition("exclusion.chassis", "1", "model",
        "Declared human immune context; executable binding pending.")
    environment = p.SemanticDefinition("exclusion.environment", "1", "environment",
        "Declared in-vivo context; executable domain pending.")
    delivery_contract = p.SemanticDefinition("exclusion.delivery", "1", "delivery",
        "Declared arrival, expression and activation interfaces; binding pending.")
    realization = p.SemanticDefinition("fixture.realization.primitives", "1", "model",
        "Explicit supplied primitive-library membership only; preservation, deployment, carriers and material remain unassessed.")
    semantics = p.SemanticBundle("staged.semantics", "1", (interface, encounter_contract, observation, operation,
        lifecycle_contract, chassis_contract, environment, delivery_contract, realization))
    builder = p.ProgramBuilder("bounded_staged_material", semantics=semantics)
    executor = builder.executor("executor", requires=(interface.ref,))
    encounter = builder.encounter("encounter", executor=executor, contract=encounter_contract.ref, termination="explicit_event")
    clock = builder.clock("clock", basis="logical", resolution=p.quantity(1, p.SECOND))
    condition = builder.observe("condition", observer=executor, subject=encounter.target, value_type=p.TRUTH,
        contract=observation.ref, clock=clock, access="cell", coverage="event", coherence="frame", freshness=p.quantity(10, p.SECOND))
    product = builder.add(p.Parameter("product", p.TEXT, value="fixture.product.alpha"))
    product_argument = p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.ref(product)))
    lifecycle = p.EffectLifecycle("continuous", "continue", "defer", "unsupported", "feedback", "feedback",
        lifecycle_contract.ref, p.quantity(2, p.SECOND))
    first = builder.effect("stage_one", contract=operation.ref, executor=executor, subject=encounter.target,
        lifecycle=lifecycle, parameters=(product_argument,))
    second = builder.effect("stage_two", contract=operation.ref, executor=executor, subject=encounter.target,
        lifecycle=lifecycle, parameters=(product_argument,))
    scope = p.Scope("encounter", p.ref(encounter))
    p.patterns.ordered_effects(builder, "regimen", executor=p.ref(executor), scope=scope,
        on=p.rising(condition.expression), permitted=condition.expression, first=first, second=second,
        handoff_when=p.TRUE, arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    for identity, effect in (("first_initiation", first), ("second_initiation", second)):
        builder.require(p.Requirement(identity, "progress",
            "Each requested attempt initiates under the supplied abstract lifecycle.", scope,
            trigger=effect.event("requested"), response=effect.event("initiated"), deadline=p.quantity(1, p.SECOND),
            horizon=p.quantity(5, p.SECOND), clock=p.ref(clock)))
    program = builder.freeze()
    # Keep actual authoring line numbers while making the source locator stable
    # when this same file is copied outside the checkout or installed elsewhere.
    program = replace(program, source_map=tuple(replace(span, file=Path(__file__).name) for span in program.source_map))
    chassis = p.ChassisProfile("exclusion.human_immune", "1", "abstract_immune", "supplied_profile", ("declared",),
        ("declared",), (interface.ref,), chassis_contract.ref, (environment.ref,), (interface.ref,))
    delivery = p.DeliveryContract("delivery", (p.ref(executor),), delivery_contract.ref, delivery_contract.ref,
        delivery_contract.ref, "none_required", delivery_contract.ref)
    deployment = p.Deployment("deployment", (p.RoleBinding(p.ref(executor), chassis),), (environment.ref,), delivery,
        p.RNAConstraints(design_count=1, member_count=1, helper_count=0, orf_count=1, product_count=1))
    implementation = p.ImplementationBinding("staged.same_product.primitives", "1", operation.ref, realization.ref,
        (chassis.id,), ("RNA",), (), ())
    return p.BuildRequest(program, deployment, p.ImplementationCatalogLock("staged.supplied.catalog", "1", (implementation,)),
        p.AssuranceRequest(("first_initiation", "second_initiation"), "bounded", p.quantity(5, p.SECOND)))


def author_project(reference: ResearchProject, *, project_id: str = "alpha.staged.authored",
                   title: str = "Typed staged engineering reference") -> ResearchProject:
    """Reuse independent supplied contracts; replace only the explicitly authored source."""
    document = build_request()
    # Pin the complete canonical source, including its actual source map.
    # document_digest intentionally omits provenance and is not this identity.
    source_digest = hashlib.sha256(p.dumps(document, indent=None).encode("utf-8")).hexdigest()
    return ResearchProject.from_build_request(project_id=project_id, title=title, document=document,
        inputs=reference.component_inputs, limits=reference.limits,
        sources=reference.sources + (
            SourceRecord("authoring-reference", "urn:biocompiler:project:" + reference.digest, "1", reference.digest,
                "caller_supplied_complete_contract", "Original terms remain in the independently retained reference project."),
            SourceRecord("authoring-source", "urn:biocompiler:canonical-policy:" + source_digest, "1", source_digest,
                "authored_policy", "Artificial software example; no biological efficacy claim."),
        ), assumptions=reference.assumptions + ("Supplied implementation contracts are premises; biological validity is unassessed.",
                        "Source changes require fresh native checking against the unchanged supplied authority."))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="Independently retained complete component-material project")
    parser.add_argument("output", type=Path, help="New project to assess with Core and Verify")
    parser.add_argument("--project-id", default="alpha.staged.authored")
    parser.add_argument("--title", default="Typed staged engineering reference")
    args = parser.parse_args(argv)
    reference = ResearchProject.load(args.reference)
    project = author_project(reference, project_id=args.project_id, title=args.title)
    project.dump(args.output)
    print(json.dumps(asdict(project.preflight()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
