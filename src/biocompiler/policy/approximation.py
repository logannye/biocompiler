"""Exact bounded approximation originals; authoring never grants acceptance.

Every link is checked afresh against its complete laws and selected material.
Finite uncertainty denotes every grid value in the declared closed intervals.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
from typing import Literal, cast

from biocompiler.core_client import CoreProtocolError, JsonValue, encode_json, _object
from . import model as m
from .quantitative import SampledTransferNetwork, ReservoirCompartment, TransferEdge, _name, _require, _value, _scaled
from .serialization import to_data, from_data as source_from_data

SCHEMA = "biocompiler.policy_approximation_contract.v0.1"
PROFILE = "biocompiler.policy_bounded_sampled_network_approximation.v0.1"


@dataclass(frozen=True, slots=True)
class RationalErrorBound:
    numerator: int
    denominator: int
    unit: m.Unit

    def __post_init__(self) -> None:
        _require(type(self.numerator) is int and type(self.denominator) is int
                 and self.numerator >= 0 and self.denominator > 0, "Use exact nonnegative rational bounds with a positive denominator")
        _require(type(self.unit) is m.Unit, "An error bound requires its complete nominal Unit")
        to_data(self.unit)
        value = Fraction(self.numerator, self.denominator)
        _require(len(str(value.numerator)) <= 256 and len(str(value.denominator)) <= 256, "Rational error bounds exceed the bounded integer spelling")
        object.__setattr__(self, "numerator", value.numerator)
        object.__setattr__(self, "denominator", value.denominator)

    def to_data(self) -> dict[str, JsonValue]:
        return {"numerator": str(self.numerator), "denominator": str(self.denominator), "unit": cast(JsonValue, to_data(self.unit))}


@dataclass(frozen=True, slots=True)
class ApproximationEndpoint:
    mechanism: SampledTransferNetwork
    observation: tuple[str, ...]

    def __post_init__(self) -> None:
        _require(type(self.mechanism) is SampledTransferNetwork, "An approximation endpoint requires a complete exact network law")
        self.mechanism.to_data()
        _require(type(self.observation) is tuple and 1 <= len(self.observation) <= 4
                 and len(set(self.observation)) == len(self.observation), "Use one to four distinct ordered observed compartments")
        compartments = {row.compartment for row in self.mechanism.reservoirs}
        for name in self.observation:
            _name(name)
            _require(name in compartments, "Every observed compartment must belong to the complete endpoint law")

    def to_data(self) -> dict[str, JsonValue]:
        return {"mechanism": self.mechanism.to_data(), "observation": list(self.observation)}


@dataclass(frozen=True, slots=True)
class ParameterInterval:
    parameter: Literal["initial", "transfer_amount"]
    id: str
    lower_quanta: int
    upper_quanta: int

    def __post_init__(self) -> None:
        _require(self.parameter in ("initial", "transfer_amount"), "Only closed initial and transfer-amount grid intervals are supported")
        _name(self.id)
        _require(type(self.lower_quanta) is int and type(self.upper_quanta) is int
                 and 0 <= self.lower_quanta <= self.upper_quanta <= 15, "Uncertainty requires exact ordered finite quantum bounds")
        _require(self.parameter != "transfer_amount" or self.lower_quanta > 0, "Transfer uncertainty cannot include zero or negative amounts")

    def to_data(self) -> dict[str, JsonValue]:
        return {"parameter": self.parameter, "id": self.id, "lower_quanta": self.lower_quanta, "upper_quanta": self.upper_quanta}


@dataclass(frozen=True, slots=True)
class ApproximationLink:
    id: str
    source: ApproximationEndpoint
    target: ApproximationEndpoint
    maximum_error: RationalErrorBound
    uncertainty: tuple[ParameterInterval, ...] = ()

    def __post_init__(self) -> None:
        _name(self.id)
        _require(type(self.source) is ApproximationEndpoint and type(self.target) is ApproximationEndpoint
                 and type(self.maximum_error) is RationalErrorBound, "Approximation links require typed original endpoints and an explicit rational error budget")
        source, target = self.source.mechanism, self.target.mechanism
        _require(source.unit == target.unit == self.maximum_error.unit and source.substance == target.substance
                 and source.sample_period == target.sample_period, "Links must preserve the complete unit, substance and sampling clock")
        _require(len(self.source.observation) == len(self.target.observation), "Both endpoint maps must cover the same semantic coordinate count")
        _require(type(self.uncertainty) is tuple and len(self.uncertainty) <= 8
                 and all(type(row) is ParameterInterval for row in self.uncertainty), "Use a bounded immutable uncertainty census")
        _require(len({(row.parameter, row.id) for row in self.uncertainty}) == len(self.uncertainty), "An uncertainty parameter may appear only once")
        cases = 1
        for interval in self.uncertainty:
            if interval.parameter == "initial":
                selected = next((row for row in source.reservoirs if row.compartment == interval.id), None)
                _require(selected is not None, "Initial uncertainty must name a declared reservoir")
                assert selected is not None
                nominal, maximum = _value(selected.initial), _value(selected.capacity)
            else:
                transfer = next((row for row in source.transfers if row.id == interval.id), None)
                _require(transfer is not None, "Transfer uncertainty must name a declared edge")
                assert transfer is not None
                donor = next(row for row in source.reservoirs if row.compartment == transfer.source)
                nominal, maximum = _value(transfer.amount), _value(donor.capacity)
            quantum = _value(source.quantum)
            _require(interval.lower_quanta <= nominal / quantum <= interval.upper_quanta <= maximum / quantum,
                     "Every interval must include the nominal value and remain inside its original reservoir grid")
            cases *= interval.upper_quanta - interval.lower_quanta + 1
            _require(cases <= 8, "The complete Cartesian uncertainty set exceeds eight; clipping and interval sampling are forbidden")

    def to_data(self) -> dict[str, JsonValue]:
        return {"id": self.id, "source": self.source.to_data(), "target": self.target.to_data(),
                "maximum_error": self.maximum_error.to_data(), "uncertainty": [row.to_data() for row in self.uncertainty]}

    def then(self, following: ApproximationLink) -> ApproximationChain:
        """Compose original declarations only; this is not evidence composition."""
        return ApproximationChain((self, following))


@dataclass(frozen=True, slots=True)
class ApproximationChain:
    links: tuple[ApproximationLink, ...]

    def __post_init__(self) -> None:
        _require(type(self.links) is tuple and 1 <= len(self.links) <= 4
                 and all(type(row) is ApproximationLink for row in self.links), "An approximation chain requires one to four typed links")
        _require(len({row.id for row in self.links}) == len(self.links), "Approximation link identities must be unique")
        for previous, following in zip(self.links, self.links[1:]):
            _require(previous.target.to_data() == following.source.to_data(), "Chaining requires the same complete middle mechanism and observation map")
            _require(not following.uncertainty, "Only the original reference endpoint may introduce uncertainty in this chain profile")

    def then(self, following: ApproximationLink) -> ApproximationChain:
        return ApproximationChain(self.links + (following,))


@dataclass(frozen=True, slots=True)
class ApproximationContract:
    horizon_steps: int
    coordinates: tuple[str, ...]
    chain: ApproximationChain
    maximum_error: RationalErrorBound

    def __post_init__(self) -> None:
        _require(type(self.horizon_steps) is int and 1 <= self.horizon_steps <= 64, "Declare one to sixty-four complete sample rounds")
        _require(type(self.coordinates) is tuple and 1 <= len(self.coordinates) <= 4
                 and len(set(self.coordinates)) == len(self.coordinates), "Semantic coordinates must be a nonempty ordered unique census")
        for coordinate in self.coordinates:
            _name(coordinate)
        _require(type(self.chain) is ApproximationChain and type(self.maximum_error) is RationalErrorBound, "Use a typed immutable chain and complete rational budget")
        for link in self.chain.links:
            _require(len(link.source.observation) == len(self.coordinates) and link.maximum_error.unit == self.maximum_error.unit,
                     "Every link must preserve the complete common unit and observation-coordinate census")

    def to_data(self) -> dict[str, JsonValue]:
        return {"schema_version": "biocompiler.policy_approximation_contract.v0.1",
            "profile": "biocompiler.policy_bounded_sampled_network_approximation.v0.1", "horizon_steps": self.horizon_steps,
            "metric": "coordinatewise_absolute_prefix_error", "coordinates": list(self.coordinates),
            "unit": cast(JsonValue, to_data(self.maximum_error.unit)), "maximum_error": self.maximum_error.to_data(),
            "links": [link.to_data() for link in self.chain.links]}

    @classmethod
    def from_data(cls, raw: JsonValue) -> ApproximationContract:
        """Decode complete original declarations; no assessment is imported."""
        encode_json(raw, limit=1048576)
        value = _object(raw, {"schema_version", "profile", "horizon_steps", "metric", "coordinates", "unit", "maximum_error", "links"}, "Approximation original")
        _require(value["schema_version"] == SCHEMA and value["profile"] == PROFILE
                 and value["metric"] == "coordinatewise_absolute_prefix_error", "Unknown approximation contract profile or metric")
        unit = source_from_data(value["unit"], m.Unit)

        def bound(raw: JsonValue) -> RationalErrorBound:
            record = _object(raw, {"numerator", "denominator", "unit"}, "Exact rational bound")
            for field in ("numerator", "denominator"):
                text = record[field]
                _require(type(text) is str and 1 <= len(text) <= 256 and text.isascii() and text.isdigit()
                         and (len(text) == 1 or text[0] != "0"), "Use canonical bounded rational digits")
            result = RationalErrorBound(int(cast(str, record["numerator"])), int(cast(str, record["denominator"])), source_from_data(record["unit"], m.Unit))
            _require(result.to_data() == raw and result.unit == unit, "Rational bound must retain normalized values and the common unit")
            return result

        def endpoint(raw: JsonValue) -> ApproximationEndpoint:
            record = _object(raw, {"mechanism", "observation"}, "Approximation endpoint")
            law = _object(record["mechanism"], {"schema_version", "profile", "substance", "unit", "quantum", "reservoirs", "transfers", "threshold", "sample_period", "arbitration", "ownership"}, "Exact endpoint network")
            reservoirs = []
            for raw_row in _sequence(law["reservoirs"], 4):
                row = _object(raw_row, {"compartment", "capacity", "initial"}, "Endpoint reservoir")
                reservoirs.append(ReservoirCompartment(cast(str, row["compartment"]), source_from_data(row["capacity"], m.Quantity), source_from_data(row["initial"], m.Quantity)))
            transfers = []
            for raw_row in _sequence(law["transfers"], 8):
                row = _object(raw_row, {"id", "source", "destination", "amount", "when"}, "Endpoint transfer")
                transfers.append(TransferEdge(cast(str, row["id"]), cast(str, row["source"]), cast(str, row["destination"]), source_from_data(row["amount"], m.Quantity), cast(bool, row["when"])))
            threshold = _object(law["threshold"], {"compartment", "amount"}, "Endpoint threshold")
            mechanism = SampledTransferNetwork(cast(str, law["substance"]), source_from_data(law["unit"], m.Unit), source_from_data(law["quantum"], m.Quantity),
                tuple(reservoirs), tuple(transfers), cast(str, threshold["compartment"]), source_from_data(threshold["amount"], m.Quantity), source_from_data(law["sample_period"], m.Quantity))
            _require(mechanism.to_data() == law, "Endpoint network retains its exact schema, units and reservation semantics")
            return ApproximationEndpoint(mechanism, tuple(cast(str, name) for name in _sequence(record["observation"], 4)))

        links = []
        for raw_link in _sequence(value["links"], 4):
            row = _object(raw_link, {"id", "source", "target", "maximum_error", "uncertainty"}, "Approximation link")
            intervals = []
            for raw_interval in _sequence(row["uncertainty"], 8):
                interval = _object(raw_interval, {"parameter", "id", "lower_quanta", "upper_quanta"}, "Finite uncertainty interval")
                intervals.append(ParameterInterval(cast(Literal["initial", "transfer_amount"], interval["parameter"]), cast(str, interval["id"]), cast(int, interval["lower_quanta"]), cast(int, interval["upper_quanta"])))
            links.append(ApproximationLink(cast(str, row["id"]), endpoint(row["source"]), endpoint(row["target"]), bound(row["maximum_error"]), tuple(intervals)))
        result = cls(cast(int, value["horizon_steps"]), tuple(cast(str, name) for name in _sequence(value["coordinates"], 4)), ApproximationChain(tuple(links)), bound(value["maximum_error"]))
        _require(result.to_data() == raw, "Approximation originals must retain complete exact canonical descriptions")
        return result


def _sequence(raw: JsonValue, maximum: int) -> list[JsonValue]:
    _require(type(raw) is list and len(raw) <= maximum, "Expected a bounded explicit ordered list")
    return cast(list[JsonValue], raw)


def _cases(link: ApproximationLink) -> list[SampledTransferNetwork]:
    cases = [link.source.mechanism]
    for interval in link.uncertainty:
        next_cases = []
        for law in cases:
            for multiple in range(interval.lower_quanta, interval.upper_quanta + 1):
                amount = _scaled(law.quantum, multiple)
                if interval.parameter == "initial":
                    next_cases.append(replace(law, reservoirs=tuple(replace(row, initial=amount) if row.compartment == interval.id else row for row in law.reservoirs)))
                else:
                    next_cases.append(replace(law, transfers=tuple(replace(row, amount=amount) if row.id == interval.id else row for row in law.transfers)))
        cases = next_cases
    return cases


def validate_assessment(report: JsonValue, contract: JsonValue, material_request: JsonValue, material_report: JsonValue) -> None:
    """Validate evidence transport and exact error composition, never grant proof.

    Native product exploration remains authoritative. This checks the original
    identities, complete case inventory, error envelopes and monotone chain sum.
    Its caller must independently obtain fresh accepted native material evidence.
    """
    try:
        _validate_assessment(report, contract, material_request, material_report)
    except CoreProtocolError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, ZeroDivisionError) as error:
        raise CoreProtocolError("Invalid approximation assessment transport") from error


def _validate_assessment(report: JsonValue, contract: JsonValue, material_request: JsonValue, material_report: JsonValue) -> None:
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise CoreProtocolError("Approximation evidence: " + message)

    def fingerprint(value: JsonValue) -> str:
        return hashlib.sha256(encode_json(value)).hexdigest()

    def obj(raw: JsonValue, keys: set[str]) -> dict[str, JsonValue]:
        return _object(raw, keys, "Approximation evidence")

    def integer(raw: JsonValue, low: int, high: int) -> int:
        require(type(raw) is int and low <= raw <= high, "integer bound changed")
        return cast(int, raw)

    for raw in (report, contract, material_request, material_report):
        encode_json(raw)
    original = ApproximationContract.from_data(contract)
    unit = cast(JsonValue, to_data(original.maximum_error.unit))
    horizon, size = original.horizon_steps, len(original.coordinates)
    request = cast(dict[str, JsonValue], material_request)
    material = cast(dict[str, JsonValue], material_report)
    selected = cast(dict[str, JsonValue], request["quantitative"])
    if request["profile"] == "biocompiler.policy_coupled_transfer_network_component_mrna.v0.1":
        selected = cast(dict[str, JsonValue], selected["network"])
    else:
        require(request["profile"] == "biocompiler.policy_sampled_transfer_network_component_mrna.v0.1", "unsupported material family")
    require(material["status"] == "checked_component_material" and material["request_fingerprint"] == fingerprint(material_request), "fresh exact material pins changed")
    report_value = obj(report, {"schema_version", "profile", "implementation", "outcome", "contract_fingerprint", "material_request_fingerprint", "material_report_fingerprint", "claim_scope", "links", "composition", "issues", "empirical", "artifact", "export", "usage"})
    for key, expected in {"schema_version": "biocompiler.policy_approximation_assessment.v0.1", "profile": PROFILE,
            "implementation": "biocompiler.ocaml.policy_approximation_check.v0.1", "contract_fingerprint": fingerprint(contract),
            "material_request_fingerprint": fingerprint(material_request), "material_report_fingerprint": fingerprint(material_report),
            "claim_scope": "bounded_model_conditional_observation_error_and_exact_request_labels", "empirical": "unassessed", "artifact": "withheld", "export": "withheld"}.items():
        require(report_value[key] == expected, key + " changed")
    usage = obj(report_value["usage"], {"unit", "charged_work"})
    require(usage["unit"] == "logical_data_visits_and_synchronized_product_work", "work semantics changed")
    integer(usage["charged_work"], 0, 134217728)
    issues = _sequence(report_value["issues"], 64)
    require(all(type(issue) is str and bool(issue) for issue in issues), "issue shape changed")
    if report_value["outcome"] == "fail":
        require(bool(issues) and report_value["links"] == [] and report_value["composition"] is None, "failed product published evidence")
        return
    require(report_value["outcome"] == "pass" and not issues, "unsupported or inconsistent assessment outcome")
    implementation = cast(dict[str, JsonValue], request["implementation_request"])
    domain = cast(dict[str, JsonValue], implementation["operating_domain"])
    require(horizon == cast(int, domain["horizon_ticks"]) + 1, "evidence shortened the complete material horizon")
    require(original.chain.links[-1].target.mechanism.to_data() == selected["mechanism"], "final exact selected mechanism changed")

    def rational(raw: JsonValue) -> Fraction:
        row = obj(raw, {"numerator", "denominator", "unit"})
        require(row["unit"] == unit, "error unit changed")
        for key in ("numerator", "denominator"):
            text = row[key]
            require(type(text) is str and 1 <= len(text) <= 256 and text.isascii() and text.isdigit()
                    and (len(text) == 1 or text[0] != "0"), "error rational spelling changed")
        numerator, denominator = int(cast(str, row["numerator"])), int(cast(str, row["denominator"]))
        require(denominator > 0, "error denominator is not positive")
        value = Fraction(numerator, denominator)
        require(value.numerator == numerator and value.denominator == denominator, "error rational is not normalized")
        return value

    def envelope(row: dict[str, JsonValue], declared: RationalErrorBound) -> list[list[Fraction]]:
        values = _sequence(row["envelope"], 65)
        require(len(values) == horizon + 1, "prefix envelope omitted rounds")
        result = []
        previous = [Fraction(0)] * size
        for round_index, raw_round in enumerate(values):
            current = obj(raw_round, {"round", "coordinates"})
            require(integer(current["round"], 0, horizon) == round_index, "prefix rounds reordered")
            errors = [rational(value) for value in _sequence(current["coordinates"], 4)]
            require(len(errors) == size and all(new >= old for new, old in zip(errors, previous)), "prefix error is not coordinatewise monotone")
            result.append(errors)
            previous = errors
        bounds = [rational(value) for value in _sequence(row["coordinate_bounds"], 4)]
        require(bounds == result[-1] and rational(row["maximum_error"]) == max(bounds), "aggregate error differs from complete coordinate envelope")
        require(row["declared_maximum_error"] == declared.to_data() and max(bounds) <= Fraction(declared.numerator, declared.denominator), "derived error exceeds the original budget")
        return result

    base_scope: dict[str, JsonValue] = {"horizon_steps": horizon, "metric": "coordinatewise_absolute_prefix_error", "coordinates": list(original.coordinates), "unit": unit,
        "sample_period": cast(JsonValue, to_data(original.chain.links[0].source.mechanism.sample_period))}
    links = _sequence(report_value["links"], 4)
    require(len(links) == len(original.chain.links), "evidence omitted an original chain link")
    envelopes = []
    for raw_link, declaration in zip(links, original.chain.links):
        link = obj(raw_link, {"id", "relation", "source_fingerprint", "target_fingerprint", "scope", "uncertainty_cases", "case_count", "envelope", "coordinate_bounds", "maximum_error", "declared_maximum_error", "request_labels"})
        for key, expected in {"id": declaration.id, "relation": "bounded_sampled_observation_error", "source_fingerprint": fingerprint(declaration.source.to_data()),
                "target_fingerprint": fingerprint(declaration.target.to_data()), "request_labels": "exact_on_all_checked_synchronized_transitions"}.items():
            require(link[key] == expected, "link " + key + " changed")
        require(link["scope"] == base_scope, "link metric, map or horizon changed")
        cases = _cases(declaration)
        case_rows = _sequence(link["uncertainty_cases"], 8)
        require(integer(link["case_count"], 1, 8) == len(cases) == len(case_rows), "complete uncertainty census changed")
        initial = [Fraction(0)] * size
        for case_raw, law in zip(case_rows, cases):
            case = obj(case_raw, {"mechanism_fingerprint", "visited_pair_rounds", "checked_transition_rows"})
            require(case["mechanism_fingerprint"] == fingerprint(law.to_data()), "uncertainty case identity changed")
            integer(case["visited_pair_rounds"], horizon + 1, 1 + horizon * 256)
            rows = integer(case["checked_transition_rows"], horizon * 8, horizon * 256 * 8)
            require(rows % 8 == 0, "synchronized product lost sample or reset alternatives")
            left = {row.compartment: _value(row.initial) for row in law.reservoirs}
            right = {row.compartment: _value(row.initial) for row in declaration.target.mechanism.reservoirs}
            for index, (source_name, target_name) in enumerate(zip(declaration.source.observation, declaration.target.observation)):
                initial[index] = max(initial[index], abs(left[source_name] - right[target_name]))
        current = envelope(link, declaration.maximum_error)
        require(current[0] == initial, "initial error omitted complete uncertainty cases")
        envelopes.append(current)
    composition = obj(report_value["composition"], {"relation", "rule", "source_fingerprint", "target_fingerprint", "material_request_fingerprint", "material_report_fingerprint", "selected_mechanism_fingerprint", "selection", "source", "scope", "inputs", "envelope", "coordinate_bounds", "maximum_error", "declared_maximum_error"})
    assembly = cast(dict[str, JsonValue], material["assembly"])
    expected_scope = dict(base_scope, operating_domain_fingerprint=fingerprint(cast(JsonValue, domain)),
        samples=["true", "false", "unknown", "no_update"], lifecycle="synchronized_reset_before_each_sample_or_keep",
        uncertainty="all_closed_grid_cases_fixed_within_each_encounter_generation")
    for key, expected_value in {"relation": "conditional_approximate_source_material_correspondence", "rule": "monotone_triangle_error_chain_with_exact_material",
            "source_fingerprint": fingerprint(original.chain.links[0].source.to_data()), "target_fingerprint": assembly["candidate_fingerprint"],
            "material_request_fingerprint": fingerprint(material_request), "material_report_fingerprint": fingerprint(material_report),
            "selected_mechanism_fingerprint": fingerprint(selected["mechanism"]), "selection": selected["selection"], "source": selected["source"],
            "scope": expected_scope, "inputs": [fingerprint(link) for link in links]}.items():
        require(composition[key] == expected_value, "composition " + key + " changed")
    composed = envelope(composition, original.maximum_error)
    expected_sum = [[sum((value[round_index][coordinate] for value in envelopes), Fraction(0)) for coordinate in range(size)] for round_index in range(horizon + 1)]
    require(composed == expected_sum, "composition cancelled or omitted a child error envelope")


__all__ = ["RationalErrorBound", "ApproximationEndpoint", "ParameterInterval", "ApproximationLink", "ApproximationChain", "ApproximationContract"]
