(* Independent literal originals and adversarial admission controls. Hosted only;
   no construction, mechanism execution or empirical claim is tested here. *)
open Bioc_wire
module R=Bioc_domain.Policy_controlled_composition_request
module A=Bioc_checker.Policy_controlled_composition_admission
let checks=ref 0
let require condition message=incr checks;if not condition then failwith message
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let get key value=Json.field key(Json.object_fields value)
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let rec edit path change raw=match path with []->change raw|key::rest->match raw with
  |Json.Array values->arr(List.mapi(fun index value->if index=int_of_string key then edit rest change value else value)values)
  |_->set key(edit rest change(get key raw))raw
let put path value=edit path(fun _->value)
let reject label action=incr checks;match action()with _->failwith("Unexpected controlled admission: "^label)
  |exception Diagnostic.Error _->()
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  let size=in_channel_length channel in require(size>0 && size<1000000)"Literal read bound";Json.parse(really_input_string channel size))
let admit raw=A.admit ~charge:(fun _->())(R.of_json raw)
let repin_model raw=let fingerprint=Canonical.fingerprint(at["mechanism_model";"body"]raw)in
  raw|>put["mechanism_model";"identity";"content_fingerprint"](str fingerprint)
     |>put["catalog_binding";"model_identity";"content_fingerprint"](str fingerprint)
let run path=
  let raw=read path in
  let decoded=R.of_json raw in require(Json.equal raw(R.to_json decoded))"Original authority was rewritten";
  require(R.decoding_work decoded>0)"Decode was not metered";
  let admitted=A.admit ~charge:(fun _->())decoded in let report=A.report admitted in
  require(get "status" report=str "admitted" && get "stage" report=str "admission")"Wrong admission stage";
  List.iter(fun key->require(get key report=str "not_performed")"Static admission promoted a later gate")
    ["construction_status";"behavior_status"];
  require(get "empirical_status" report=str "unassessed")"Static admission promoted empirical evidence";
  require(at["authority_inventory";"members"]report=Json.int 2 && at["authority_inventory";"model_ports"]report=Json.int 5)
    "Incomplete original inventory";
  require(at["domain_counters";"histories"]report=Json.int 1 && at["domain_counters";"transitions"]report=Json.int 11 &&
    at["domain_counters";"prefixes"]report=Json.int 12)"Fixed original domain was not completely counted";
  require(get "source_fingerprint" report=str(Canonical.fingerprint(at["source_authority";"document"]raw)))"Source artifact identity lost";
  List.iter(fun(label,path,value)->reject label(fun()->admit(put path value raw)))[
    "missing authority",["material_authority"],Json.Null;
    "wrong version",["schema_version"],str "biocompiler.policy_component_material_request.v0.13";
    "third member",["material_authority";"member_order"],arr[str "rna-a";str "rna-b";str "helper"];
    "partial body",["material_authority";"template";"sources";"0";"molecule";"sequence_extent"],str "exact_core";
    "unresolved region",["material_authority";"members";"0";"regions";"utr5"],str "unknown";
    "output chemistry changed",["material_authority";"members";"0";"chemistry";"cap";"identity";"accession"],str "changed";
    "protein changed",["material_authority";"members";"0";"product";"sequence"],str "MG";
    "product mapping swapped",["assembly";"product_bindings";"0";"member_id"],str "rna-b";
    "co-delivery absent",["context";"co_delivery";"mode"],str "independent";
    "source recipient mismatch",["context";"deployment";"bindings";"0";"chassis";"species"],str "mouse";
    "unresolved conditional premise",["context";"co_delivery";"assumptions"],arr[str "not supplied"];
    "unresolved provenance",["context";"empirical_assertions";"0";"source_ids"],arr[str "absent"];
    "unresolved molecular provenance",["material_authority";"template";"sources";"0";"provenance";"authority";"0";"id"],str "absent";
    "payload compartment",["material_authority";"template";"requirements";"0";"roles";"0";"compartment"],str "nucleus";
    "empirical promotion",["context";"empirical_assertions";"0";"status"],str "validated";
    "RNA length resource",["resources";"max_member_rna_nt"],Json.int 16;
    "total RNA resource",["resources";"max_total_rna_nt"],Json.int 33;
    "boolean capacity",["resources";"timer_cells"],Json.Bool true;
    "model stale pin",["mechanism_model";"body";"delays";"onset_ticks"],Json.int 2;
    "deadline substitution",["source_authority";"control_contract";"requested_deadlines";"onset_ticks"],Json.int 1;
    "domain freshness substitution",["operating_domain";"inputs";"0";"freshness_ticks"],Json.int 2;
    "domain exhaustion",["operating_domain";"limits";"max_prefixes"],Json.int 1;
    "work exhaustion",["budgets";"max_work"],Json.int 1;
    "report byte exhaustion",["budgets";"max_report_bytes"],Json.int 1;
    "report node exhaustion",["budgets";"max_report_nodes"],Json.int 1];
  reject "unrecognized extra authority"(fun()->admit(set "checked_material"(obj[])raw));
  reject "missing body"(fun()->admit(edit["mechanism_model"](fun value->obj(List.remove_assoc "body"(Json.object_fields value)))raw));
  reject "self-repinned wrong activity scope"(fun()->admit(repin_model(put["mechanism_model";"body";"ports";"4";"scope"](str "encounter_generation")raw)));
  reject "self-repinned wrong source product"(fun()->admit(repin_model(put["mechanism_model";"body";"ports";"2";"reference";"id"](str "product-b")raw)));
  (* Admission does not conflate supplied actual delay with a source deadline,
     or claim it satisfies the latter. RC5 must decide behavioral compliance. *)
  let slower=raw|>put["mechanism_model";"body";"delays";"onset_ticks"](Json.int 3)
    |>put["source_authority";"control_contract";"actual_delays";"onset_ticks"](Json.int 3)|>repin_model in
  require(get "behavior_status"(A.report(admit slower))=str "not_performed")"Static admission became behavioral execution";
  require(R.fingerprint(R.of_json slower)<>R.fingerprint decoded)"Changed actual model parameters failed to change authority identity";
  let changed_provenance=put["source_authority";"project_context";"title"](str "Another original caller title")raw in
  require(R.fingerprint(R.of_json changed_provenance)<>R.fingerprint decoded)"Full original project authority not bound";
  let charged=ref 0 in ignore(A.admit ~charge:(fun amount->charged:= !charged+amount)decoded);
  require(!charged>R.decoding_work decoded)"Admission traversals were not independently charged";
  let stopped=try ignore(A.admit ~charge:(fun _->raise Exit)decoded);false with Exit->true in
  require stopped "Enclosing guard exception was swallowed";
  Printf.printf "controlled composition admission: %d checks\n" !checks
let ()=if Array.length Sys.argv<>2 then failwith "Expected independent controlled request fixture" else run Sys.argv.(1)
