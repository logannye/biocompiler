"""Author circuit requirements alongside complete, independently frozen intent.

Builder operations never mutate or root the original therapy graph. They record
declarations; no observation binding establishes a cellular sensing mechanism.
"""

from __future__ import annotations

from biocompiler.errors import SerializationError
from biocompiler.frontend.graph import capture_source
from biocompiler.ir.circuit_intent import (
    MAX_REQUIREMENTS,
    CircuitBehavior,
    CircuitInputBinding,
    CircuitRequest,
    CircuitRequirement,
    same_authority,
    source_build_request,
)
from biocompiler.ir.circuit_logic import MAX_BOOLEAN_INPUTS, BooleanSpec, CircuitSignal
from biocompiler.ir.circuit_observations import CircuitObservation, _text
from biocompiler.ir.circuit_profile import CircuitProfileRequest
from biocompiler.ir.serialization import require


MAX_BUILDER_OBSERVATIONS = MAX_REQUIREMENTS * MAX_BOOLEAN_INPUTS
MAX_SOURCE_REFERENCES = 128


class CircuitBuilder:
    """Supplementary circuit authoring, with explicit original source authority.

    ``name`` is an authoring label. Requirement identities are the exact IDs
    passed to :meth:`require`. Frozen builders use original source node-ID
    strings; builders attached to cells use handles from that same live graph.
    """

    def __init__(self, name, profile, role_id=None):
        self._initialize(name)
        require(
            isinstance(profile, CircuitProfileRequest),
            "Expected circuit profile authority.",
        )
        self._profile = CircuitProfileRequest.from_dict(profile.to_dict())
        self._role_id = role_id
        if self._profile.purpose == "human_immune_payload":
            require(
                self._profile.source_request is not None,
                "Product circuits require original source authority.",
            )
            _text(role_id, "Explicit circuit role")
            self._nodes = {
                node.id: node
                for node in source_build_request(
                    self._profile.source_request
                ).intent.nodes
            }
            self._check_role(self._nodes.get(role_id))
        else:
            require(
                role_id is None, "Reference circuits cannot invent therapeutic roles."
            )

    def _initialize(self, name):
        _text(name, "Circuit authoring name")
        self.name = name
        self._profile = None
        self._graph = None
        self._role_id = None
        self._nodes = {}
        self._observations = {}
        self._observation_sources = {}
        self._requirements = {}

    @classmethod
    def for_cells(cls, cells, name):
        from biocompiler.frontend.api import CellProgram

        require(
            isinstance(cells, CellProgram), "Circuit authoring requires a CellProgram."
        )
        instance = cls.__new__(cls)
        instance._initialize(name)
        instance._graph = cells._graph
        instance._role_id = cells.role
        require(
            cells.node_id == cells.role, "CellProgram role identity is inconsistent."
        )
        instance._check_role(instance._get_live_node(cells.node_id))
        return instance

    @staticmethod
    def _check_role(node):
        require(
            node is not None
            and node.kind == "role"
            and node.attributes.get("engineering") == "in_vivo",
            "Circuit authoring requires an original in-vivo engineered role.",
        )

    def _get_live_node(self, node_id):
        try:
            return self._graph.get(node_id)
        except (KeyError, TypeError) as exc:
            raise SerializationError(
                "Source handle refers to an unknown graph node."
            ) from exc

    def _source_id(self, source):
        if self._graph is None:
            require(
                self._profile.purpose == "human_immune_payload",
                "Reference circuits cannot carry therapeutic source nodes.",
            )
            _text(source, "Frozen source node identity")
            node = self._nodes.get(source)
            require(node is not None, "Unknown frozen source node identity.")
            node_id = source
        else:
            from biocompiler.frontend.api import Handle
            from biocompiler.frontend.expressions import Expr

            require(
                isinstance(source, (Handle, Expr)),
                "Live circuit sources require graph handles.",
            )
            require(
                source._graph is self._graph,
                "Circuit source belongs to a different graph.",
            )
            require(
                source.role in (None, self._role_id),
                "Circuit source belongs to a different role.",
            )
            node_id = source.node_id
            node = self._get_live_node(node_id)
        require(
            node_id == self._role_id
            or (node.kind != "role" and node.role in (None, self._role_id)),
            "Circuit source node belongs to a different role.",
        )
        return node_id

    def observe(self, observation, source=None):
        """Record a nominal observation and an optional original-source link."""
        require(
            isinstance(observation, CircuitObservation),
            "Expected a typed circuit observation.",
        )
        require(
            observation.id not in self._observations,
            "Duplicate circuit observation identity.",
        )
        require(
            len(self._observations) < MAX_BUILDER_OBSERVATIONS,
            "Circuit observation inventory limit exceeded.",
        )
        original = CircuitObservation.from_dict(observation.to_dict())
        signal = CircuitSignal(original.id, original.fingerprint)
        node_id = None if source is None else self._source_id(source)
        self._observations[original.id] = original
        self._observation_sources[original.id] = node_id
        return signal

    def require(self, id, response, product, *, lifecycle, dependencies=(), source=()):
        """Bind a complete Boolean requirement to the recorded observations."""
        _text(id, "Circuit requirement identity")
        require(id not in self._requirements, "Duplicate circuit requirement identity.")
        require(
            len(self._requirements) < MAX_REQUIREMENTS,
            "Circuit requirement limit exceeded.",
        )
        if isinstance(response, CircuitSignal):
            response = response.expression()
        require(
            isinstance(response, BooleanSpec),
            "Circuit response requires an explicit Boolean specification.",
        )
        response = BooleanSpec.from_dict(response.to_dict())
        observations = []
        for signal in response.inputs:
            observation = self._observations.get(signal.id)
            require(
                observation is not None,
                "Response refers to an unregistered observation.",
            )
            require(
                observation.fingerprint == signal.observation_fingerprint,
                "Response contains a different observation binding.",
            )
            observations.append(observation)
        require(
            isinstance(source, (tuple, list)) and len(source) <= MAX_SOURCE_REFERENCES,
            "Source references require a bounded tuple or list.",
        )
        explicit = tuple(self._source_id(item) for item in source)
        require(
            len(set(explicit)) == len(explicit), "Duplicate explicit source references."
        )
        references = set(explicit)
        if self._role_id is not None:
            references.add(self._role_id)
        input_bindings = []
        for observation in observations:
            associated = self._observation_sources[observation.id]
            if associated is not None:
                references.add(associated)
                input_bindings.append(CircuitInputBinding(observation.id, associated))
        requirement = CircuitRequirement(
            id,
            CircuitBehavior(
                tuple(observations), response, product, lifecycle, dependencies
            ),
            self._role_id,
            tuple(sorted(references)),
            capture_source(),
            input_bindings=tuple(input_bindings),
        )
        self._requirements[id] = requirement
        return requirement

    @property
    def requirements(self):
        """Immutable, deterministic snapshot suitable for declared lock authoring."""
        return tuple(self._requirements[key] for key in sorted(self._requirements))

    def freeze(
        self,
        profile=None,
        *,
        requested_form,
        fidelity_scope,
        deployment_id,
        selected_realization=None,
        reference_lock=None,
    ):
        """Freeze declarations while preserving complete original source authority."""
        if self._graph is None:
            if profile is not None:
                require(
                    isinstance(profile, CircuitProfileRequest),
                    "Expected circuit profile authority.",
                )
                require(
                    same_authority(profile, self._profile),
                    "A frozen builder cannot substitute its profile authority.",
                )
            authority = self._profile
        else:
            require(
                isinstance(profile, CircuitProfileRequest),
                "Live circuit authoring requires a frozen profile at freeze.",
            )
            authority = CircuitProfileRequest.from_dict(profile.to_dict())
            require(
                authority.purpose == "human_immune_payload"
                and authority.source_request is not None,
                "Live cells require complete original product source authority.",
            )
            original = source_build_request(authority.source_request).intent
            current = self._graph.freeze(original.name)
            require(
                same_authority(current, original),
                "Live graph differs from the frozen original source, including source locations.",
            )
        return CircuitRequest(
            authority,
            self.requirements,
            requested_form,
            fidelity_scope,
            deployment_id,
            selected_realization,
            reference_lock,
        )
