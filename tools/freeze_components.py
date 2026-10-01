#!/usr/bin/env python3
"""Freeze complete component declarations and contextual operator checks."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import (SyntheticOperatorModel, PinnedIdentity, ParameterProvenance,
    DependencyRequirement, ProvidedCapability, ResourceReservation, SequenceReferenceMetadata, ComponentRecord)
from biocompiler.semantics.component_contracts import (ValueDomain, OperatingDomain, PortContract,
    STATELESS_TIMING, TEMPORAL_LEVEL_TIMING, TEMPORAL_EVENT_TIMING)
from biocompiler.semantics.types import BOOLEAN, LEVEL, DURATION, Duration, Level, TypeSpec

SCHEMA = "biocompiler.components_conformance.v1"
CORPUS = ROOT / "tests/conformance/components-v1.json"
KINDS = {"pin": PinnedIdentity, "synthetic_operator": SyntheticOperatorModel, "parameter": ParameterProvenance,
         "dependency": DependencyRequirement, "capability": ProvidedCapability, "resource": ResourceReservation,
         "sequence_reference": SequenceReferenceMetadata, "component": ComponentRecord}
OPERATIONS = ("input", "constant", "and", "or", "not", "compare", "select", "any_contact", "output", "held_for", "onset", "pulse", "memory")
CENSUS = (60, 112, 42)
REJECTION_CODES_SHA256 = "aa047609532ac9a7aa3e30bdea22d4bf805d245ced830a3cefb43c86546bbf0b"
CASE_IDS_SHA256 = "72742695a3bc4e4ffccfbfe672d311563fc1ea8bb47984a4d513e8b5acf3644e"

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
def pin(kind="model", identity="model"):
    return PinnedIdentity(kind, identity, "1", "a" * 64)
def port(identity="out", direction="output", *, dtype=BOOLEAN, unit="1", scope="cell", timing=STATELESS_TIMING, initial=None, domain=None, role="cell", compartment="abstract"):
    known = ValueDomain.boolean() if dtype.kind == "condition" else ValueDomain.interval(-1, 1, dtype, unit)
    return PortContract(identity, direction, "meaning", dtype, unit, role, scope, compartment, timing,
                        known if initial is None else initial, known if domain is None else domain)
def historical(**changes):
    value = ComponentRecord("historical", "1", "synthetic_model", "historical", ("RNA", "synthetic"), (), OperatingDomain(), (pin(),),
                            assumptions=("second", "first"), guarantees=("declared only",))
    return replace(value, **changes)
def executable(operation):
    count = {"input": 0, "constant": 0, "and": 2, "or": 2, "not": 1, "compare": 2, "select": 3,
             "any_contact": 1, "output": 1, "held_for": 1, "onset": 1, "pulse": 1, "memory": 2}[operation]
    names = tuple("in" + str(i) for i in range(count))
    temporal = operation in {"held_for", "onset", "pulse", "memory"}
    timing = TEMPORAL_LEVEL_TIMING if temporal else STATELESS_TIMING
    incoming = tuple(port(name, "input", dtype=LEVEL if operation == "compare" else BOOLEAN,
        scope="contact" if operation == "any_contact" else "cell",
        timing=TEMPORAL_EVENT_TIMING if operation in {"pulse", "memory"} and i == 0 else timing)
        for i, name in enumerate(names))
    output = port(timing=TEMPORAL_EVENT_TIMING if operation == "onset" else timing,
                  initial=ValueDomain.boolean((False,)) if operation == "held_for" else None)
    attributes = {"value": True} if operation == "constant" else {"operator": "eq"} if operation == "compare" else {"duration": Duration(2).to_dict()} if operation in {"held_for", "pulse"} else {"duration": None} if operation == "memory" else {}
    model = SyntheticOperatorModel(operation, attributes, names)
    return ComponentRecord("operator:" + operation, "1", "synthetic_model", operation, ("synthetic", "RNA"),
                           (*incoming, output), OperatingDomain(), (pin(),), synthetic_model=model)

def inspect(kind, raw):
    value = KINDS[kind].from_dict(raw)
    checks = []
    if isinstance(value, ComponentRecord) and value.synthetic_model is not None:
        checks = [item.to_dict() for item in value.synthetic_model.domain_checks(value.ports, value.supported_domain)]
    return value.to_dict(), checks

def build_corpus():
    cases, rejected = [], []
    def record(identity, kind, value, mutate=None):
        raw = deepcopy(value.to_dict())
        if mutate: mutate(raw)
        normalized, checks = inspect(kind, raw)
        cases.append({"id": identity, "record_kind": kind, "input": raw, "normalized": normalized,
                      "fingerprint": fingerprint(normalized), "domain_checks": checks})
    def reject(identity, kind, value, mutate, code="component_record"):
        raw = deepcopy(value.to_dict()); mutate(raw)
        try: inspect(kind, raw)
        except SerializationError as error:
            rejected.append({"id": identity, "record_kind": kind, "input": raw, "expected_code": code,
                             "python_error": str(error)})
        else: raise AssertionError("Accepted intended component mutation " + identity)
    for kind in ("model", "reference", "registry", "source", "evidence"):
        record("pin_" + kind, "pin", pin(kind))
    parameter = ParameterProvenance("parameter", ValueDomain.interval(1, 2), pin("source"), "declared")
    dependency = DependencyRequirement("dependency", "energy", "cell", "cell", "abstract")
    capability = ProvidedCapability("energy", "cell", "contact", "abstract")
    resource = ResourceReservation("resource", "capacity", 3, "1")
    reference = SequenceReferenceMetadata("coding_rna", 3, ("z", "a"))
    record("parameter", "parameter", parameter)
    record("parameter_model_pin_retained", "parameter", replace(parameter, source=pin()))
    record("dependency", "dependency", dependency)
    record("dependency_optional_contact", "dependency", replace(dependency, required=False, scope="contact"))
    record("capability", "capability", capability)
    record("resource", "resource", resource)
    record("resource_unknown", "resource", replace(resource, amount=None, reusable=True))
    record("resource_signed_zero", "resource", replace(resource, amount=-0.0, scope="contact"))
    record("resource_explicit_noncanonical_unit", "resource", replace(resource, dtype=DURATION, unit="minutes", amount=2.0))
    for artifact in ("coding_dna", "coding_rna", "protein"):
        record("reference_" + artifact, "sequence_reference", replace(reference, artifact_class=artifact))
    record("reference_arbitrary_precision_length", "sequence_reference", replace(reference, sequence_length=10**40))
    record("historical_synthetic_no_executable_model", "component", historical())
    record("modeled_component", "component", historical(classification="modeled_component"))
    sequence = historical(classification="sequence_reference", identities=(pin("reference"),), reference_metadata=reference,
                          parameters=(parameter,), evidence=(pin("registry", "registry"),), supported_domain=OperatingDomain({"unresolved":ValueDomain.unknown()}))
    record("sequence_reference_retains_parameters_evidence_domain", "component", sequence)
    full = historical(ports=(port("z"), port("a")), identities=(pin("source", "z"), pin("model", "a")),
        evidence=(pin("model", "z"), pin("registry", "a")), parameters=(replace(parameter,id="z"), replace(parameter,id="a")),
        dependencies=(replace(dependency,id="z"), replace(dependency,id="a")), capabilities=(replace(capability,id="z"),replace(capability,id="a")),
        resources=(replace(resource,id="z"),replace(resource,id="a")))
    arrays = ("ports", "identities", "evidence", "parameters", "dependencies", "capabilities", "resources")
    record("all_component_arrays_sort_by_id_only", "component", full,
           lambda data: [data.update({key:list(reversed(data[key]))}) for key in arrays])
    record("component_names_preserve_whitespace_order", "component", historical(id=" component ", supported_targets=("RNA", "synthetic")))
    originals = {operation: executable(operation) for operation in OPERATIONS}
    for operation, value in originals.items():
        record("declaration_" + operation, "synthetic_operator", value.synthetic_model)
        record("executable_" + operation, "component", value)
    # A declaration alone does not yet know its output dtype, arity or timing.
    record("declaration_context_validation_deferred", "synthetic_operator", SyntheticOperatorModel("constant", {"value":"not a typed literal"}, ("extra",)))
    model = replace(originals["memory"].synthetic_model, attributes={"duration": Duration(3).to_dict()})
    record("memory_with_expiry", "component", replace(originals["memory"], synthetic_model=model))
    event_agg = replace(originals["any_contact"], ports=tuple(replace(x,timing=TEMPORAL_EVENT_TIMING) for x in originals["any_contact"].ports))
    record("any_contact_event", "component", event_agg)
    zero = ValueDomain.boolean((False,))
    zero_agg = replace(originals["any_contact"], supported_domain=OperatingDomain({"concurrent_contacts":ValueDomain.interval(0,0)}),
        ports=tuple(replace(x,initialization=zero,domain=zero) if x.id=="out" else x for x in originals["any_contact"].ports))
    record("any_contact_zero_capacity", "component", zero_agg)
    unknown = ValueDomain.unknown(BOOLEAN, "1", "not established")
    record("executable_unknown_is_not_failure", "component", replace(originals["output"],
        ports=tuple(replace(x,initialization=unknown,domain=unknown) if x.id=="in0" else x for x in originals["output"].ports)))
    scalar_domain = ValueDomain.interval(0, 200, DURATION, "s")
    constant = replace(originals["constant"], ports=(port(dtype=DURATION,unit="s",domain=scalar_domain,initial=scalar_domain),),
        synthetic_model=SyntheticOperatorModel("constant", {"value":Duration(2,unit="min").to_dict()}))
    record("constant_explicit_literal_unit", "component", constant)
    record("constant_numeric_equivalent_attribute_spelling", "component", constant,
        lambda d: d["synthetic_model"]["attributes"]["value"].update(canonical_value=120.0))
    alias = TypeSpec("scalar", "Alias")
    compare = replace(originals["compare"], ports=tuple(replace(x,dtype=alias,initialization=ValueDomain.interval(-1,1,alias),domain=ValueDomain.interval(-1,1,alias)) if x.id=="in0" else x for x in originals["compare"].ports))
    record("comparison_dimensional_alias", "component", compare)
    scalar_select = replace(originals["select"], ports=tuple(port(x.id,x.direction,dtype=LEVEL) if x.id!="in0" else x for x in originals["select"].ports))
    record("selection_scalar", "component", scalar_select)
    record("input_port_order_is_authority", "component", replace(scalar_select, synthetic_model=replace(scalar_select.synthetic_model,input_ports=("in0","in2","in1"))))
    request = json.loads((ROOT / "tests/conformance/case-b/base/request.json").read_bytes())
    case_b = request["library"]["refinements"][0]["components"][0]
    record("retained_case_b_modeled_component", "component", ComponentRecord.from_dict(case_b))
    representatives = {"pin":pin(),"synthetic_operator":originals["input"].synthetic_model,"parameter":parameter,
        "dependency":dependency,"capability":capability,"resource":resource,"sequence_reference":reference,"component":historical()}
    for kind, value in representatives.items():
        reject(kind+"_missing_field",kind,value,lambda d:d.pop("schema_version"),"missing_field")
        reject(kind+"_unknown_field",kind,value,lambda d:d.update(extra=None),"unknown_field")
        reject(kind+"_schema",kind,value,lambda d:d.update(schema_version="unsupported"),"unsupported_identity_schema" if kind=="pin" else "unsupported_schema")
    reject("pin_kind","pin",pin(),lambda d:d.update(kind="untrusted"),"invalid_identity_kind")
    reject("pin_hash","pin",pin(),lambda d:d.update(content_fingerprint="A"*64),"invalid_identity_fingerprint")
    for kind, value, key in (("parameter",parameter,"method"),("dependency",dependency,"capability"),("capability",capability,"role"),("resource",resource,"resource"),("component",historical(),"id")):
        reject(kind+"_blank_name",kind,value,lambda d,key=key:d.update({key:" \t"}),"invalid_name")
    for kind, value in (("dependency",dependency),("capability",capability),("resource",resource)):
        reject(kind+"_scope",kind,value,lambda d:d.update(scope="tissue"))
    reject("dependency_boolean","dependency",dependency,lambda d:d.update(required=1),"invalid_type")
    reject("resource_boolean","resource",resource,lambda d:d.update(reusable=1),"invalid_type")
    reject("resource_negative","resource",resource,lambda d:d.update(amount=-1))
    reject("resource_bool_amount","resource",resource,lambda d:d.update(amount=True))
    reject("resource_overflow","resource",resource,lambda d:d.update(amount=10**400))
    reject("resource_condition","resource",resource,lambda d:d.update(dtype=BOOLEAN.to_dict()))
    for field, value in (("artifact_class","genomic_dna"),("sequence_length",0),("completeness","complete"),("unknown_features",["same","same"])):
        reject("reference_"+field,"sequence_reference",reference,lambda d,field=field,value=value:d.update({field:value}))
    reject("reference_boolean_length","sequence_reference",reference,lambda d:d.update(sequence_length=True),"invalid_type")
    reject("reference_float_length","sequence_reference",reference,lambda d:d.update(sequence_length=3.0),"invalid_type")
    for key in ("supported_targets","assumptions","guarantees"):
        reject("component_duplicate_"+key,"component",historical(),lambda d,key=key:d.update({key:["same","same"]}))
    reject("component_no_targets","component",historical(),lambda d:d.update(supported_targets=[]))
    reject("component_classification","component",historical(),lambda d:d.update(classification="empirical"))
    reject("component_missing_model_pin","component",historical(),lambda d:d.update(identities=[pin("reference").to_dict()]))
    reject("component_reference_metadata","component",historical(),lambda d:d.update(reference_metadata=reference.to_dict()))
    for key in arrays:
        reject("duplicate_inventory_"+key,"component",full,lambda d,key=key:d.update({key:[d[key][0],d[key][0]]}))
    reject("duplicate_pin_id_across_kinds","component",historical(),lambda d:d.update(identities=[pin("model","same").to_dict(),pin("source","same").to_dict()]))
    reject("sequence_missing_reference_pin","component",sequence,lambda d:d.update(identities=[]))
    reject("sequence_missing_metadata","component",sequence,lambda d:d.update(reference_metadata=None))
    for key, value in (("identities",[pin("reference","ref").to_dict(),pin().to_dict()]),("ports",[port().to_dict()]),("capabilities",[capability.to_dict()]),("dependencies",[dependency.to_dict()]),("resources",[resource.to_dict()])):
        reject("sequence_dynamic_"+key,"component",sequence,lambda d,key=key,value=value:d.update({key:value}))
    for field, value in (("operation","delay"),("attributes",{"value":True}),("input_ports",["x","x"]),("output_port","in0"),("policy","other")):
        reject("operator_"+field,"synthetic_operator",originals["not"].synthetic_model,lambda d,field=field,value=value:d.update({field:value}))
    reject("operator_attributes_array","synthetic_operator",originals["input"].synthetic_model,lambda d:d.update(attributes=[]),"invalid_type")
    reject("executable_classification","component",originals["input"],lambda d:d.update(classification="modeled_component"))
    reject("executable_role","component",originals["input"],lambda d:d.update(implementation_role="output"))
    def mutate_port(raw, identity, **updates):
        item = next(x for x in raw["ports"] if x["id"]==identity); item.update(updates)
    reject("executable_extra_port","component",originals["not"],lambda d:d["ports"].append(port("extra").to_dict()))
    reject("executable_missing_port","component",originals["not"],lambda d:d.update(ports=[x for x in d["ports"] if x["id"]=="out"]))
    reject("executable_direction","component",originals["not"],lambda d:mutate_port(d,"in0",direction="output"))
    reject("executable_arity","component",originals["and"],lambda d:(d.update(ports=[x for x in d["ports"] if x["id"]!="in1"]),d["synthetic_model"].update(input_ports=["in0"])))
    for field,value in (("role","other"),("compartment","other"),("scope","contact")):
        reject("executable_input_"+field,"component",originals["not"],lambda d,field=field,value=value:mutate_port(d,"in0",**{field:value}))
    reject("executable_memory_contact","component",originals["memory"],lambda d:[x.update(scope="contact") for x in d["ports"]])
    reject("executable_aggregation_cell_input","component",originals["any_contact"],lambda d:mutate_port(d,"in0",scope="cell"))
    for operation in ("onset","pulse","memory","held_for","input","any_contact"):
        reject("executable_output_timing_"+operation,"component",originals[operation],lambda d:mutate_port(d,"out",timing="unknown"))
    for operation in ("pulse","memory","and","onset","any_contact"):
        reject("executable_input_timing_"+operation,"component",originals[operation],lambda d:mutate_port(d,"in0",timing="unknown"))
    reject("executable_stateless_hold","component",originals["held_for"],lambda d:[x.update(timing=STATELESS_TIMING) for x in d["ports"]])
    reject("executable_boolean_literal","component",originals["constant"],lambda d:d["synthetic_model"]["attributes"].update(value=1))
    reject("executable_comparison_operator","component",originals["compare"],lambda d:d["synthetic_model"]["attributes"].update(operator="approx"))
    reject("executable_duration_zero","component",originals["held_for"],lambda d:d["synthetic_model"]["attributes"].update(duration=Duration(0).to_dict()))
    reject("executable_duration_unit","component",originals["pulse"],lambda d:d["synthetic_model"]["attributes"].update(duration=Level(1).to_dict()))
    reject("executable_noncanonical_literal_shape","component",constant,lambda d:d["synthetic_model"]["attributes"]["value"]["type"].pop("arguments"))
    reject("executable_scalar_plain_literal","component",constant,lambda d:d["synthetic_model"]["attributes"].update(value=1))
    reject("executable_unknown_attribute_literal_type","component",constant,lambda d:d["synthetic_model"]["attributes"]["value"].update(canonical_value=121))
    def output_false(raw):
        mutate_port(raw,"out",initialization=zero.to_dict(),domain=zero.to_dict())
    reject("executable_runtime_domain_exclusion","component",originals["constant"],output_false)
    reject("executable_initial_domain_exclusion","component",originals["onset"],lambda d:mutate_port(d,"out",initialization=zero.to_dict()))
    def scalar_port(raw, identity, dtype=LEVEL, unit="1"):
        item = next(x for x in raw["ports"] if x["id"]==identity)
        raw["ports"][raw["ports"].index(item)] = port(identity,item["direction"],dtype=dtype,unit=unit).to_dict()
    reject("executable_logical_scalar_input","component",originals["and"],lambda d:scalar_port(d,"in0"))
    reject("executable_comparison_dimension_mismatch","component",originals["compare"],lambda d:scalar_port(d,"in0",DURATION,"s"))
    reject("executable_selection_branch_mismatch","component",originals["select"],lambda d:scalar_port(d,"in1"))
    reject("executable_selection_nonboolean_guard","component",scalar_select,lambda d:scalar_port(d,"in0"))
    reject("executable_output_type_mismatch","component",originals["output"],lambda d:scalar_port(d,"in0"))
    reject("executable_noncanonical_port_unit","component",constant,lambda d:scalar_port(d,"out",DURATION,"minutes"))
    document = {"schema_version":SCHEMA,"claim_scope":"Complete component declarations and contextual local operator contracts only; no registry resolution, composition acceptance, candidate execution or molecular implementation.",
                "cases":cases,"rejections":rejected}
    document["coverage"] = coverage(document)
    return document

def coverage(document):
    return {"record_kinds":sorted({x["record_kind"] for x in document["cases"]}),"positive_count":len(document["cases"]),"rejection_count":len(document["rejections"]),
            "executable_operations":sorted({x["normalized"]["synthetic_model"]["operation"] for x in document["cases"] if x["record_kind"]=="component" and x["normalized"]["synthetic_model"] is not None}),
            "domain_check_count":sum(len(x["domain_checks"]) for x in document["cases"])}
def check_corpus(document):
    assert document["schema_version"]==SCHEMA
    assert document["coverage"]==coverage(document),"Changed component census"
    assert document["coverage"]["record_kinds"]==sorted(KINDS),"Missing component schema"
    assert document["coverage"]["executable_operations"]==sorted(OPERATIONS),"Missing executable operator"
    assert (len(document["cases"]),len(document["rejections"]),document["coverage"]["domain_check_count"])==CENSUS,"Truncated component cases"
    ids=[x["id"] for key in ("cases","rejections") for x in document[key]]
    assert len(ids)==len(set(ids)),"Duplicate component case"
    assert fingerprint(sorted(ids))==CASE_IDS_SHA256,"Changed retained case inventory"
    for item in document["cases"]:
        normalized,checks=inspect(item["record_kind"],item["input"])
        assert canonical(normalized)==canonical(item["normalized"]),"Changed complete component record"
        assert fingerprint(normalized)==item["fingerprint"],"Changed component fingerprint"
        assert canonical(checks)==canonical(item["domain_checks"]),"Changed local assessment"
    assert fingerprint(sorted([x["id"],x["expected_code"]] for x in document["rejections"]))==REJECTION_CODES_SHA256,"Changed intended native rejection categories"
    for item in document["rejections"]:
        try:inspect(item["record_kind"],item["input"])
        except SerializationError as error:assert str(error)==item["python_error"],"Wrong intended component rejection"
        else:raise AssertionError("Accepted negative component fixture")
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group();modes.add_argument("--write",action="store_true");modes.add_argument("--check",action="store_true")
    parser.add_argument("--output",type=Path,default=CORPUS);args=parser.parse_args(argv)
    document=build_corpus();check_corpus(document);content=encoded(document)
    if args.write:args.output.write_bytes(content)
    else:assert args.output.read_bytes()==content,"Components corpus drifted; inspect before --write"
    print(json.dumps({"status":"written" if args.write else "checked","bytes":len(content),**document["coverage"]},sort_keys=True))
if __name__=="__main__":main()
