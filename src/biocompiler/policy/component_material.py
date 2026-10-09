"""Inert reusable-component requests and fresh native paired publication."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_component_material import (
    ACCEPTED_STATUS, REQUEST_PROFILE, REQUEST_SCHEMA, INSTANCE_REQUEST_PROFILE, INSTANCE_REQUEST_SCHEMA, PolicyComponentMaterialClient, PolicyComponentMaterialResult, _original,
    PREREQUISITE_REQUEST_PROFILE, PREREQUISITE_REQUEST_SCHEMA,
    TWO_OBSERVATION_REQUEST_PROFILE, TWO_OBSERVATION_REQUEST_SCHEMA,
    MULTI_MEMBER_REQUEST_PROFILE, MULTI_MEMBER_REQUEST_SCHEMA,
    GROUNDED_HELPER_REQUEST_PROFILE, GROUNDED_HELPER_REQUEST_SCHEMA,
    FINITE_MACHINE_REQUEST_PROFILE, FINITE_MACHINE_REQUEST_SCHEMA,
    NETWORK_REQUEST_PROFILE, NETWORK_REQUEST_SCHEMA,
    QUANTITATIVE_REQUEST_PROFILE, QUANTITATIVE_REQUEST_SCHEMA, STEP_QUANTITATIVE_REQUEST_PROFILE, STEP_QUANTITATIVE_REQUEST_SCHEMA,
    TRANSFER_PAIR_REQUEST_PROFILE, TRANSFER_PAIR_REQUEST_SCHEMA,
    TRANSFER_NETWORK_REQUEST_PROFILE, TRANSFER_NETWORK_REQUEST_SCHEMA,
)
from .material import _publish_fresh


def prepare_request(*, implementation_request: JsonValue, component_library: JsonValue,
                    composition_rule: JsonValue, catalog_binding: JsonValue, input_bindings: JsonValue,
                    resource_bindings: JsonValue, context: JsonValue, budgets: JsonValue,
                    instanced: bool = False, prerequisites: bool = False,
                    two_observations: bool = False, multi_member: bool = False,
                    grounded_helper: bool = False, finite_machine: bool = False,
                    quantitative: JsonValue = None, network: bool = False, multi_site: bool = False, transfer_pair: bool = False, transfer_network: bool = False) -> dict[str, JsonValue]:
    """Snapshot all original authority unchanged; perform no semantic admission."""
    if transfer_network and (not multi_site or transfer_pair):
        raise ValueError("Transfer network requires its distinct multiple-site route")
    if transfer_pair and not multi_site:
        raise ValueError("Transfer-pair material requires the explicit multiple-site quantitative route")
    if multi_site and (not finite_machine or quantitative is None or network):
        raise ValueError("Multiple-site material requires the explicit step quantitative finite-machine route")
    if network and (not (instanced and prerequisites) or finite_machine or quantitative is not None or grounded_helper or multi_member or two_observations):
        raise ValueError("Network compilation requires its distinct explicit named-instance prerequisite route")
    if finite_machine and (not (instanced and prerequisites) or grounded_helper or multi_member or two_observations):
        raise ValueError("Finite-machine compilation requires its distinct explicit named-instance prerequisite route")
    if quantitative is not None and not finite_machine:
        raise ValueError("Quantitative compilation requires its explicit finite-machine backing route")
    if prerequisites and not instanced:
        raise ValueError("Prerequisite closure requires the explicit named-instance profile")
    if grounded_helper and (not (prerequisites and instanced) or multi_member or two_observations):
        raise ValueError("Grounded helper compilation requires its distinct explicit prerequisite route")
    if multi_member and (not (prerequisites and instanced) or two_observations):
        raise ValueError("Multi-member compilation requires its distinct explicit prerequisite route")
    if two_observations and not (prerequisites and instanced):
        raise ValueError("Two observations require explicit named instances and prerequisite closure")
    request: dict[str, JsonValue] = {"schema_version": TRANSFER_NETWORK_REQUEST_SCHEMA if transfer_network else TRANSFER_PAIR_REQUEST_SCHEMA if transfer_pair else STEP_QUANTITATIVE_REQUEST_SCHEMA if multi_site else NETWORK_REQUEST_SCHEMA if network else QUANTITATIVE_REQUEST_SCHEMA if quantitative is not None else FINITE_MACHINE_REQUEST_SCHEMA if finite_machine else GROUNDED_HELPER_REQUEST_SCHEMA if grounded_helper else MULTI_MEMBER_REQUEST_SCHEMA if multi_member else TWO_OBSERVATION_REQUEST_SCHEMA if two_observations else PREREQUISITE_REQUEST_SCHEMA if prerequisites else INSTANCE_REQUEST_SCHEMA if instanced else REQUEST_SCHEMA,
        "profile": TRANSFER_NETWORK_REQUEST_PROFILE if transfer_network else TRANSFER_PAIR_REQUEST_PROFILE if transfer_pair else STEP_QUANTITATIVE_REQUEST_PROFILE if multi_site else NETWORK_REQUEST_PROFILE if network else QUANTITATIVE_REQUEST_PROFILE if quantitative is not None else FINITE_MACHINE_REQUEST_PROFILE if finite_machine else GROUNDED_HELPER_REQUEST_PROFILE if grounded_helper else MULTI_MEMBER_REQUEST_PROFILE if multi_member else TWO_OBSERVATION_REQUEST_PROFILE if two_observations else PREREQUISITE_REQUEST_PROFILE if prerequisites else INSTANCE_REQUEST_PROFILE if instanced else REQUEST_PROFILE,
        "implementation_request": implementation_request, "component_library": component_library,
        "composition_rule": composition_rule, "catalog_binding": catalog_binding, "input_bindings": input_bindings,
        "resource_bindings": resource_bindings, "context": context, "budgets": budgets}
    if quantitative is not None:
        request["quantitative"] = quantitative
    return _original(decode_json(encode_json(request)))


def compile(request: JsonValue, *, limits: JsonValue, client: PolicyComponentMaterialClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    return client.compile(request, limits, cancelled=cancelled)


def check(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyComponentMaterialClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    return client.check(request, candidate, limits, cancelled=cancelled)


def replay(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyComponentMaterialClient, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    """Replay the complete wrapper against independently supplied current originals."""
    return client.replay(request, candidate, limits, report, cancelled=cancelled)


def export(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyComponentMaterialClient,
           output: Path, input_paths: Iterable[Path] = (), replace: bool = False,
           cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    """Fresh native check/export followed by exact atomic FASTA/manifest publication."""
    return _publish_fresh(lambda: client.export(request, candidate, limits, cancelled=cancelled),
        operation="export-policy-component-material", status=ACCEPTED_STATUS, output=output,
        input_paths=input_paths, replace=replace, cancelled=cancelled)
