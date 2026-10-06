open Bioc_wire
let () = Printexc.register_printer (function
  | Diagnostic.Error diagnostic -> Some (Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      diagnostic.code (Option.value ~default:"<none>" diagnostic.path) diagnostic.message)
  | _ -> None)
module C = Bioc_domain.Policy_material_contract
module I = Bioc_domain.Policy_implementation
module R = Bioc_domain.Policy_realization_request
module U = Bioc_domain.Policy_implementation_binding
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module P = Bioc_realization_checker.Policy_preservation_check
module Check = Bioc_realization_checker.Policy_material_binding_check
let require condition message=if not condition then failwith message
let obj fields=Json.Object fields
let arr values=Json.Array values
let str value=Json.String value
let get name value=Json.field name(Json.object_fields value)
let items name value=Json.array(get name value)
let text name value=Json.string(get name value)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:4000000 ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Missing literal field "^key);
      obj(List.map(fun(name,value)->name,if name=key then set rest replacement value else value)fields)
  |index::rest,Json.Array values->let index=int_of_string index in
      require(index>=0 && index<List.length values)"Array mutation outside literal";
      arr(List.mapi(fun i value->if i=index then set rest replacement value else value)values)
  |_->failwith "Mutation escaped literal fixture"
let repin raw=set["identity";"content_fingerprint"](str(Canonical.fingerprint(get "body" raw)))raw
let controls=ref 0
let rejected label action=incr controls;match action()with
  |()->failwith("Accepted malformed "^label)
  |exception Diagnostic.Error _->()
let scope result=let report=Check.report result in
  List.iter(fun name->require(text name report="unassessed")("Material leaf promoted "^name))
    ["context";"resource_capacity";"input_compatibility";"source_obligation_discharge";"empirical"];
  List.iter(fun name->require(text name report="withheld")("Material leaf authorized "^name))["artifact";"export"]
let ()=
  require(Array.length Sys.argv=2)"Supply independently authored material case fixture";
  let fixture=read Sys.argv.(1)in
  let source=get "source_case" fixture in
  let request=R.of_json(get "request" source)in
  let library=R.implementation_library request in
  let behavior=Bioc_compiler.Policy_lowering.lower(Bioc_checker.Policy_admission.admit
    ~document:(R.document request) ~descriptors:(R.definitions request))in
  let preservation=P.check ~request ~behavior
    ~implementation:(I.of_json ~library(get "implementation" source))
    ~proposed:(U.of_json(get "proposed" source)) ~limits:(P.limits_of_json(get "limits" fixture))in
  let implementation=match P.accepted preservation with
    |Some value->value|None->failwith("Literal source/graph preservation failed: "^Canonical.encode(P.report preservation))in
  let coverage=get "coverage"(P.report preservation)in
  List.iter(fun(name,count)->require(get name coverage=Json.int count)("Independent source-domain census changed: "^name))
    ["histories",9;"transitions",47;"prefixes_started",48];
  let raw=get "contract" fixture and candidate_raw=get "candidate" fixture in
  let contract=C.of_json ~library raw and proposed=C.proposal_of_json(get "proposed" fixture)
  and candidate=K.of_json candidate_raw in
  require(Canonical.encode(C.to_json contract)=Canonical.encode raw)"Contract decoder lost full supplied authority";
  require(Canonical.encode(C.proposal_to_json proposed)=Canonical.encode(get "proposed" fixture))"Proposal round trip changed ordered bijection";
  require(List.length(C.nodes(C.kernel contract))=15 && List.length(C.target_inventory(C.kernel contract))=92)
    "Independent graph/material inventory census changed";
  let run ?(contract=contract) ?(proposed=proposed) ?(candidate=candidate) ()=
    Check.check ~contract ~implementation ~proposed ~candidate ()in
  let positive=run()in scope positive;
  require(Check.outcome positive=E.Pass)("Exact independent material case did not pass: "^Canonical.encode(Check.report positive));
  let accepted=match Check.accepted positive with Some value->value|None->failwith "Exact case lacks private checked leaf"in
  require(C.fingerprint(Check.contract accepted)=C.fingerprint contract)"Private leaf detached from original case";
  require(Json.equal(Check.evidence accepted)(Check.report positive))"Private leaf evidence changed";
  let literal_sequence=match K.inventory candidate with Some inventory->
    Bioc_domain.Molecule.sequence(List.hd(K.Inventory.molecules inventory))|None->failwith "Missing literal molecule"in
  require(literal_sequence="CCAUGGCUUAAGGAAAA")"Material spelling changed";
  let fail_result label result=incr controls;scope result;
    require(Check.outcome result<>E.Pass && Option.is_none(Check.accepted result))("Accepted "^label)in
  let mutated label changed=
    let contract=C.of_json ~library(repin changed)in
    let proposed=C.proposal_of_json(set["contract_digest"](str(C.fingerprint contract))(C.proposal_to_json proposed))in
    fail_result label(run ~contract ~proposed ())in
  rejected "extra contract field"(fun()->ignore(C.of_json ~library(obj(("accept",Json.Bool true)::Json.object_fields raw))));
  rejected "unknown fixed phase profile"(fun()->ignore(C.of_json ~library(repin(set["body";"kernel";"phase_profile"](str "candidate.phases")raw))));
  rejected "unknown observable profile"(fun()->ignore(C.of_json ~library(repin(set["body";"kernel";"observable_profile"](str "hidden_outputs")raw))));
  rejected "changed complete model body"(fun()->ignore(C.of_json ~library(repin(set["body";"kernel";"nodes";"0";"model";"body";"configuration";"freshness_ticks"](Json.int 99)raw))));
  rejected "recomputed model pin without independent model"(fun()->
    let changed=set["body";"kernel";"nodes";"0";"model";"body";"configuration";"freshness_ticks"](Json.int 99)raw in
    let model=get "model"(List.hd(items "nodes"(get "kernel"(get "body" changed))))in
    ignore(C.of_json ~library(repin(set["body";"kernel";"nodes";"0";"model";"identity";"content_fingerprint"]
      (str(Canonical.fingerprint(get "body" model)))changed))));
  rejected "empty material carrier"(fun()->ignore(C.of_json ~library(repin(set["body";"carriers";"0";"sites"](arr[])raw))));
  rejected "partial provider identity"(fun()->ignore(C.of_json ~library(repin(set["body";"allocations";"0";"provider";"digest"](str "abc")raw))));
  rejected "unknown resource unit"(fun()->ignore(C.of_json ~library(repin(set["body";"resources";"0";"unit"](str "software_work")raw))));
  rejected "duplicate proposal alias"(fun()->ignore(C.proposal_of_json(set["nodes";"1";"node_id"](str "evidence")(C.proposal_to_json proposed))));
  let kernel=get "kernel"(get "body" raw)in
  mutated "different independently supplied primitive"(set["body";"kernel";"nodes";"0";"model"]
    (get "model"(List.nth(items "nodes" kernel)1))raw);
  mutated "omitted kernel node"(set["body";"kernel";"nodes"](arr(List.tl(items "nodes" kernel)))raw);
  mutated "changed wire with recomputed case pins"(set["body";"kernel";"wires";"0";"from";"port"](str "updated")raw);
  mutated "omitted wire"(set["body";"kernel";"wires"](arr(List.tl(items "wires" kernel)))raw);
  mutated "wire reorder"(set["body";"kernel";"wires"](arr(List.rev(items "wires" kernel)))raw);
  mutated "collapsed encounter slots"(set["body";"kernel";"layout";"slots"](Json.int 1)raw);
  mutated "changed external input route"(set["body";"kernel";"inputs";"0";"to";"node"](str "local.attempt")raw);
  mutated "missing atomic commit"(set["body";"kernel";"atomic_groups";"0";"commits"](arr[])raw);
  mutated "hidden semantic export"(set["body";"kernel";"semantic_exports"](arr(List.tl(items "semantic_exports" kernel)))raw);
  mutated "missing primitive material disposition"(set["body";"carriers"](arr(List.tl(items "carriers"(get "body" raw))))raw);
  mutated "wrong material feature"(set["body";"carriers";"0";"sites";"0";"feature"](str "absent")raw);
  mutated "wrong material coordinate"(set["body";"carriers";"0";"sites";"0";"path";"spans";"0";"start"](Json.int 3)raw);
  mutated "changed exact material key"(set["body";"material_key";"0";"sequence"](str "GCAUGGCUUAAGGAAAA")raw);
  mutated "changed product interpretation"(set["body";"products";"0";"symbol"](str "unrelated_product")raw);
  mutated "absent product member"(set["body";"products";"0";"member"](str "absent")raw);
  mutated "resource assigned to absent node"(set["body";"resources";"0";"owner";"id"](str "local.absent")raw);
  mutated "missing exclusive allocation"(set["body";"allocations"](arr(List.tl(items "allocations"(get "body" raw))))raw);
  mutated "missing input provider witness"(set["body";"input_witnesses"](arr[])raw);
  let changed_candidate=set["inventory";"molecules";"0";"sequence"](str "GCAUGGCUUAAGGAAAA")candidate_raw in
  (* Even replacing the candidate's role fingerprint cannot change fresh
     independently reconstructed bases from the original supplied template. *)
  let molecule=List.hd(items "molecules"(get "inventory" changed_candidate))in
  let changed_candidate=set["inventory";"role_instances";"0";"subject_fingerprint"](str(Canonical.fingerprint molecule))changed_candidate in
  fail_result "altered candidate bases and recomputed local pins"(run ~candidate:(K.of_json changed_candidate)());
  fail_result "wrong original contract pin"(run ~proposed:(C.proposal_of_json(set["contract_digest"](str(String.make 64 '0'))(C.proposal_to_json proposed)))());
  fail_result "ordered node binding permutation"(run ~proposed:(C.proposal_of_json(set["nodes"]
    (arr(List.rev(items "nodes"(C.proposal_to_json proposed))))(C.proposal_to_json proposed)))());
  rejected "zero work budget"(fun()->ignore(Check.check ~maximum:0 ~contract ~implementation ~proposed ~candidate ()));
  let rec deep=Json.Array[deep]in
  rejected "cyclic direct contract"(fun()->ignore(C.of_json ~library deep));
  require(Check.outcome(run())=E.Pass)"Rejected successor altered immutable original authority";
  Printf.printf "policy_material_binding: exact conditional case, %d rejection controls, context/export withheld\n" !controls
