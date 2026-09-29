"""Source-authoritative binding for the first human observation contract.

No source node is dropped or rewritten. A symbolic goal receives an explicitly
justified measurable refinement; satisfying that readout does not prove the goal.
"""

from dataclasses import dataclass
from typing import ClassVar

from cellweave.compiler.request import BuildRequest, _strict_import
from cellweave.ir.serialization import JsonArtifact, fields, fingerprint, require
from cellweave.semantics.context import HumanTargetContext
from cellweave.semantics.human_behavior import ConditionalSecretionContract
from cellweave.semantics.types import TypeSpec


@dataclass(frozen=True)
class HumanBehaviorRequest(JsonArtifact):
    build_request: BuildRequest
    contract: ConditionalSecretionContract
    schema_version: ClassVar[str] = "cellweave.human_behavior_request.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.build_request, BuildRequest),
            "Expected frozen BuildRequest authority.",
        )
        require(
            isinstance(self.target, HumanTargetContext),
            "Human behavior requires the versioned human target contract.",
        )
        require(
            isinstance(self.contract, ConditionalSecretionContract),
            "Expected ConditionalSecretionContract.",
        )
        contract = self.contract
        nodes = {node.id: node for node in self.build_request.intent.nodes}

        def source(ref, kind):
            require(
                ref in nodes and nodes[ref].kind == kind,
                f"Source {ref!r} must be {kind}.",
            )
            return nodes[ref]

        role = source(contract.input_measurement.observable.role, "role")
        goal = source(contract.goal_id, "goal")
        signal = source(contract.input_signal_id, "signal")
        predicate = source(contract.predicate.predicate_id, "qualitative")
        rule = source(contract.response.rule_id, "rule")
        action = source(contract.response.specification_id, "action.secrete")
        require(
            len(signal.inputs) == 1 and len(action.inputs) == 1,
            "This profile refines one observed signal and an unspecified secretion rate; explicit rate expressions require another profile.",
        )
        scope = source(signal.inputs[0], "scope")
        secretion = source(action.inputs[0], "secretion")
        require(
            set(nodes)
            == {
                node.id
                for node in (
                    role,
                    goal,
                    signal,
                    predicate,
                    rule,
                    action,
                    scope,
                    secretion,
                )
            },
            "Unsupported or unmapped source nodes: this profile covers exactly one goal, role, input, predicate and ongoing secretion rule.",
        )
        require(
            all(
                node.role == role.id
                for node in (signal, predicate, rule, action, scope, secretion)
            ),
            "All source observations/actions must belong to the selected role.",
        )
        require(
            role.attributes.get("engineering") == "in_vivo",
            "Source role must declare in-vivo engineering.",
        )
        require(
            scope.inputs == (role.id,)
            and scope.attributes.get("scope") == "external"
            and signal.attributes.get("scope") == "external",
            "First profile requires a cell-accessible external signal, without contact binding.",
        )
        require(
            TypeSpec.from_dict(signal.data_type)
            == contract.input_measurement.observable.dtype,
            "Input measurement must preserve the source signal type.",
        )
        require(
            predicate.inputs == (signal.id,),
            "Refinement must bind the exact source qualitative predicate.",
        )
        band = predicate.attributes.get("band")
        require(
            (band in {"high", "present"} and contract.predicate.operator in {">", ">="})
            or (band == "low" and contract.predicate.operator in {"<", "<="}),
            "Threshold direction conflicts with the source qualitative predicate.",
        )
        require(
            rule.inputs == (role.id, predicate.id, action.id)
            and rule.attributes.get("trigger") == "condition"
            and rule.attributes.get("execution") == "concurrent"
            and rule.attributes.get("priority") == "unspecified",
            "Unsupported source guard/action or rule execution policy.",
        )
        require(
            action.attributes.get("ongoing") is True
            and action.attributes.get("rate") == "unspecified",
            "The profile requires ongoing secretion with an explicitly refined rate.",
        )
        require(
            secretion.inputs == (role.id,)
            and secretion.attributes.get("product") == contract.product,
            "Output product must match the source secretion identity.",
        )
        require(
            set(self.build_request.intent.roots)
            == {role.id, goal.id, secretion.id, rule.id},
            "Source roots cannot be omitted or reinterpreted.",
        )
        for measurement in (contract.input_measurement, contract.output_measurement):
            require(
                measurement.observable.compartment in self.target.compartments
                and measurement.observable.compartment != "abstract",
                "Every measurement requires a declared physical target compartment.",
            )
        evidence_ids = {item.id for item in self.target.human_target.evidence}
        for path, claim in contract.claims:
            require(
                set(claim.evidence_ids) <= evidence_ids,
                f"Unknown target evidence reference in {path}.",
            )

    @property
    def target(self):
        return self.build_request.target

    @property
    def fingerprint(self):
        return fingerprint(
            {
                "schema_version": self.schema_version,
                "build_request": self.build_request.fingerprint,
                "contract": self.contract.fingerprint,
            }
        )

    @property
    def artifact_fingerprint(self):
        return fingerprint(self.to_dict())

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "build_request": self.build_request.to_dict(),
            "contract": self.contract.to_dict(),
        }

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        fields(data, {"schema_version", "build_request", "contract"}, cls.__name__)
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported human behavior request schema.",
        )
        return cls(
            BuildRequest.from_dict(data["build_request"]),
            ConditionalSecretionContract.from_dict(data["contract"]),
        )
