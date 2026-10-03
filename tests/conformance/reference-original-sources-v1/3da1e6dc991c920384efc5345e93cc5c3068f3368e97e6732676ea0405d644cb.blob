"""Bounded sampled transport for an independently checked RNA architecture.

Each role still executes the original BehaviorProgram. This adapter supplies only
receiver-local numeric channel observations under declared transport assumptions;
it neither predicts physiology nor infers transport from emitted RNA sequences.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import ClassVar

from biocompiler.errors import EvaluationError
from biocompiler.ir.architecture_build import PayloadArchitectureBuild, PayloadArchitectureRequest
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import JsonArtifact
from biocompiler.semantics.evaluator import EvaluationResult, InputFrame, SignalSample, evaluate
from biocompiler.semantics.types import DURATION, ScalarLiteral, TypeSpec, decode_binding


TRANSPORT_PROFILE = "biocompiler.sampled_architecture_transport.v0.1"


def _require(condition, message):
    if not condition:
        raise EvaluationError(message)


def _seconds(value, label):
    if isinstance(value, ScalarLiteral):
        _require(value.dtype.compatible(DURATION), label + " must have duration units.")
        value = value.canonical_value
    _require(type(value) in (int, float) and math.isfinite(value)
             and value >= 0 and value == int(value), label + " must be an integer number of canonical seconds.")
    return int(value)


@dataclass(frozen=True)
class ArchitectureExecutionResult(JsonArtifact):
    """Execution receipt, conditional on source and declared transport authority."""
    request_fingerprint: str
    build_fingerprint: str
    step_seconds: int
    horizon_seconds: int
    histories: Mapping[str, tuple[InputFrame, ...]]
    results: Mapping[str, EvaluationResult]
    channel_frames: tuple[Mapping, ...]
    channels: tuple[Mapping, ...]
    failed_channels: Mapping[str, tuple[int, ...]]
    assumptions: tuple[str, ...]
    max_samples: int
    schema_version: ClassVar[str] = "biocompiler.architecture_execution_result.v0.1"

    def __post_init__(self):
        object.__setattr__(self,"histories",MappingProxyType({key:tuple(value) for key,value in self.histories.items()}))
        object.__setattr__(self,"results",MappingProxyType(dict(self.results)))
        object.__setattr__(self,"channel_frames",tuple(freeze_json(value) for value in self.channel_frames))
        object.__setattr__(self,"channels",tuple(freeze_json(value) for value in self.channels))
        object.__setattr__(self,"failed_channels",freeze_json(self.failed_channels))

    def to_dict(self):
        return {
            "schema_version":self.schema_version,"request_fingerprint":self.request_fingerprint,
            "build_fingerprint":self.build_fingerprint,"step_seconds":self.step_seconds,
            "horizon_seconds":self.horizon_seconds,
            "histories":{key:[frame.to_dict() for frame in value] for key,value in self.histories.items()},
            "results":{key:value.to_dict() for key,value in self.results.items()},
            "channel_frames":thaw_json(self.channel_frames),"channels":thaw_json(self.channels),
            "failed_channels":thaw_json(self.failed_channels),"assumptions":list(self.assumptions),
            "policies":{
                "profile":TRANSPORT_PROFILE,"max_samples":self.max_samples,"max_role_evaluations":10000,
                "channel_sampling":"settled_action_requests_at_declared_grid_only",
                "delivery":"prior_queued_outputs_delivered_before_all_current_role_evaluations",
                "latency":"strictly_positive_integer_grid_multiple",
                "persistence":"since_latest_delivery_exclusive_expiry; None_means_indefinite",
                "absent_signal":"declared_initial_value_when_no_active_sender_contribution",
                "failure":"delivery_tick; clear_discards_contribution; retain_last_freezes_for_failed_tick",
                "aggregation":"active_sender_contributions; single_sender_sum_or_max_as_declared",
                "qualitative_encoding":"unsupported_without_explicit_encoding_contract",
                "claim_scope":"sampled_abstract_execution_under_declared_contracts_no_physiological_prediction",
            },
        }


def evaluate_payload_architecture(build, expected_request, histories, *, until, step, max_samples=1000,
                                  failed_channels=None):
    """Execute coupled roles at a finite, explicitly declared transport grid.

    External snapshots are complete for their role, start at zero, and occur on
    the grid. Channel observations are generated exclusively from matched source
    action.emit requests. Source timers can run between grid points, but transport
    samples only the settled actions at grid points. Failure flags name plan
    channel identities and delivery ticks, not biological probabilities.
    """
    from biocompiler.verification.payload_architecture import check_payload_architecture
    _require(isinstance(build,PayloadArchitectureBuild) and isinstance(expected_request,PayloadArchitectureRequest),
             "Coupled execution requires a build and independent architecture request authority.")
    checked=check_payload_architecture(build,expected_request=expected_request)
    _require(checked.passed and checked.translation_complete and checked.construction_complete
             and build.status=="compiled" and build.plan is not None and build.execution.behavior is not None,
             "Coupled execution requires fresh complete independent architecture verification.")
    step=_seconds(step,"Transport step")
    horizon=_seconds(until,"Execution horizon")
    _require(step>0 and horizon%step==0,"Step must be positive and the horizon must lie on its grid.")
    _require(type(max_samples) is int and 1<=max_samples<=1000,"max_samples must be an integer from 1 to 1000.")
    sample_count=horizon//step+1
    _require(sample_count<=max_samples,"Transport grid exceeds declared max_samples.")
    behavior=build.execution.behavior
    nodes={node.id:node for node in behavior.nodes}
    roles=tuple(node.id for node in behavior.nodes if node.kind=="role")
    _require(sample_count*len(roles)<=10000,"Transport execution exceeds 10000 role evaluations.")
    aliases={node.attributes["name"]:node.id for node in behavior.nodes if node.kind=="role"}
    _require(isinstance(histories,Mapping),"External histories must be keyed by source role identity or name.")
    external={}
    for key,value in histories.items():
        role=key if key in roles else aliases.get(key)
        _require(role is not None and role not in external,"Unknown or duplicate external role history.")
        _require(isinstance(value,(tuple,list)) and 1<=len(value)<=max_samples
                 and all(isinstance(frame,InputFrame) for frame in value),"Each role needs bounded InputFrame snapshots.")
        _require(value[0].time==0 and all(left.time<right.time for left,right in zip(value,value[1:])),
                 "External histories must start at zero and strictly increase.")
        for frame in value:
            time=_seconds(frame.time,"External input timestamp")
            _require(time<=horizon and time%step==0,"External observations must lie on the declared transport grid.")
        external[role]=tuple(value)
    _require(set(external)==set(roles),"Supply exactly one external history for every source role.")
    channels=tuple(build.plan.channels)
    ids={item["id"] for item in channels}
    _require(len(ids)==len(channels),"Duplicate selected channel identities.")
    failures={} if failed_channels is None else failed_channels
    _require(isinstance(failures,Mapping) and set(failures)<=ids,"Failure flags must identify selected channels.")
    failure_ticks={}
    for key,times in failures.items():
        _require(isinstance(times,(tuple,list)) and len(times)<=max_samples,"Invalid channel failure history.")
        resolved=tuple(_seconds(time,"Channel failure timestamp") for time in times)
        _require(len(set(resolved))==len(resolved) and all(time<=horizon and time%step==0 for time in resolved),
                 "Channel failure timestamps must be unique grid points within the horizon.")
        failure_ticks[key]=tuple(sorted(resolved))
    groups={}
    initial={}
    for channel in channels:
        identity=channel["id"]
        delay=_seconds(channel["latency_seconds"],"Channel latency")
        _require(delay>0 and delay%step==0,"Zero-delay feedback and off-grid channel latency are unsupported.")
        persistence=channel["persistence_seconds"]
        if persistence is not None:
            persistence=_seconds(persistence,"Channel persistence")
            _require(persistence>0 and persistence%step==0,"Channel persistence must be positive and lie on the grid.")
        receiver=channel["receiver_node_id"]
        _require(not any(node.kind=="qualitative" and node.inputs[0]==receiver for node in behavior.nodes),
                 "Numeric channel transport cannot invent qualitative observation encoding.")
        emitter=nodes[channel["sender_node_id"]]
        if emitter.kind=="action.pulse":
            emitter=nodes[emitter.inputs[0]]
        _require(emitter.kind=="action.emit" and emitter.attributes["value"]=="expression",
                 "Channel transport requires an explicit numeric source emission value.")
        dtype=TypeSpec.from_dict(nodes[channel["source_channel_id"]].data_type)
        baseline=decode_binding(channel["initial_value"],dtype).canonical_value
        key=(channel["receiver_role"],receiver)
        if key in groups:
            first=groups[key][0]
            _require(first["aggregation"]==channel["aggregation"] and initial[key]==baseline,
                     "All contributions to one receiver must agree on aggregation and initial value.")
        groups.setdefault(key,[]).append(channel)
        initial[key]=baseline
    for key,group in groups.items():
        _require(group[0]["aggregation"]!="single_sender" or len(group)==1,
                 "single_sender transport cannot combine multiple sender declarations.")
    observed={channel["receiver_node_id"] for channel in channels}
    _require(observed=={node.id for node in behavior.nodes if node.kind=="channel_observation"},
             "Every source channel observation needs selected transport authority.")
    for role,frames in external.items():
        for frame in frames:
            refs=set(frame.signals)|{ref for samples in frame.contacts.values() for ref in samples}
            _require(not refs&observed,"External histories cannot override generated channel observations.")
    merged={role:[] for role in roles}
    indexes={role:0 for role in roles}
    queue={}
    retained={identity:None for identity in ids}
    trace=[]
    results={}
    for time in range(0,horizon+1,step):
        delivered=queue.pop(time,{})
        for channel in channels:
            identity=channel["id"]
            if time in failure_ticks.get(identity,()):
                mode=channel["failure_mode"]
                _require(mode!="unknown","An unknown channel failure has no executable numeric observation.")
                if mode=="clear":
                    retained[identity]=None
                continue
            if identity in delivered:
                expiry=None if channel["persistence_seconds"] is None else time+channel["persistence_seconds"]
                retained[identity]=(delivered[identity],expiry)
            elif retained[identity] is not None and retained[identity][1] is not None and time>=retained[identity][1]:
                retained[identity]=None
        generated={role:{} for role in roles}
        values={}
        for key,group in groups.items():
            contributions=[retained[channel["id"]][0] for channel in group if retained[channel["id"]] is not None]
            aggregation=group[0]["aggregation"]
            value=(initial[key] if not contributions else math.fsum(contributions) if aggregation=="sum"
                   else max(contributions) if aggregation=="max" else contributions[0])
            _require(math.isfinite(value),"Channel aggregation produced a non-finite observation.")
            generated[key[0]][key[1]]=SignalSample(value=value)
            values[key[1]]=value
        for role in roles:
            while indexes[role]+1<len(external[role]) and external[role][indexes[role]+1].time<=time:
                indexes[role]+=1
            frame=external[role][indexes[role]]
            merged[role].append(InputFrame(time,{**frame.signals,**generated[role]},frame.contacts))
            results[role]=evaluate(behavior,merged[role],role=role,until=time)
        sent={}
        for channel in channels:
            role=channel["sender_role"]
            matches=[action for action in results[role].frames[-1].actions
                     if (action.specification_id if nodes[channel["sender_node_id"]].kind=="action.pulse"
                         else action.action_id)==channel["sender_node_id"]]
            _require(len(matches)<=1,"Multiple active emitter requests need an explicit within-sender aggregation contract.")
            if matches:
                _require(matches[0].contact_id is None,"Contact-scoped emitter transport requires an identity policy.")
                value=matches[0].values.get("value")
                _require(type(value) in (int,float) and math.isfinite(value),"Emission must supply a finite canonical scalar value.")
                arrival=time+int(channel["latency_seconds"])
                if arrival<=horizon:
                    queue.setdefault(arrival,{})[channel["id"]]=value
                sent[channel["id"]]={"value":value,"delivery_time":arrival}
        trace.append({"time":time,"receiver_values":values,"sent":sent,
                      "failed_channel_ids":[key for key in sorted(failure_ticks) if time in failure_ticks[key]]})
    return ArchitectureExecutionResult(expected_request.fingerprint,build.fingerprint,step,horizon,
                                       merged,results,tuple(trace),channels,failure_ticks,
                                       build.plan.assumptions,max_samples)
