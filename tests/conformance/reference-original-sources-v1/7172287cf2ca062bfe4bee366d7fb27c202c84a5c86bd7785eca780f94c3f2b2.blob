"""Independent interval checks for supplied RNA expression/deployment contracts.

This checker consumes reconstructed placements and pinned supplied windows. It
does not import the architecture selector, matcher or source-manifest producer.
It proves interval containment for all declared onset/duration choices, without
promoting declaration consistency to a prediction of delivery or expression.
"""

from fractions import Fraction

from biocompiler.ir.circuit_intent import source_build_request


def check_deployment_requirements(request, inventories):
    failures = []
    roles = {node.id for node in source_build_request(request.source).intent.find(kind="role")}
    compartments = set(request.circuit.profile.target.compartments)
    groups = {item.id: item for item in request.constraints.delivery_groups}
    windows = {item["placement_id"]: item for item in inventories["availability"]}
    for requirement in request.constraints.deployment_requirements:
        suffix = ":" + requirement.id
        group = groups.get(requirement.delivery_group_id)
        if group is None:
            failures.append("deployment_group_missing" + suffix)
            continue
        if requirement.recipient_role not in roles or requirement.recipient_role not in group.recipient_roles:
            failures.append("deployment_recipient_mismatch" + suffix)
        if requirement.compartment not in compartments or requirement.compartment == "abstract":
            failures.append("deployment_compartment_unknown" + suffix)
        if requirement.require_same_recipient and (not group.same_recipient or group.mode != "co_delivered"):
            failures.append("deployment_same_recipient_unproven" + suffix)
        placements = [item for item in inventories["placements"]
                      if item["delivery_group"] == group.id
                      and item["recipient_role"] == requirement.recipient_role]
        if not placements:
            failures.append("deployment_member_inventory_empty" + suffix)
        for placement in placements:
            detail = suffix + ":" + placement["id"]
            if placement["compartment"] != requirement.compartment:
                failures.append("deployment_destination_mismatch" + detail)
            window = windows.get(placement["id"])
            if window is None:
                failures.append("deployment_availability_missing" + detail)
                continue
            if window["clock"] != requirement.clock:
                failures.append("deployment_clock_mismatch" + detail)
            # JSON numeric spellings have exact decimal-second meaning here;
            # binary rounding must not manufacture or erase a boundary gap.
            onset_min = Fraction(str(window["onset_min_seconds"]))
            onset_max = Fraction(str(window["onset_max_seconds"]))
            duration_min = Fraction(str(window["duration_min_seconds"]))
            duration_max = Fraction(str(window["duration_max_seconds"]))
            if onset_max > Fraction(str(requirement.required_from_seconds)):
                failures.append("deployment_onset_deadline" + detail)
            # Compute directly from authority: never trust a cached interval or
            # add maximum onset to minimum duration (that would overclaim).
            if onset_min + duration_min < Fraction(str(requirement.required_until_seconds)):
                failures.append("deployment_common_window_insufficient" + detail)
            if (requirement.unavailable_after_seconds is not None
                and onset_max + duration_max > Fraction(str(requirement.unavailable_after_seconds))):
                failures.append("deployment_unavailability_deadline" + detail)
    return failures
