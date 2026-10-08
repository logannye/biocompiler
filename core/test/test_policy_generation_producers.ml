open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module Admission = Bioc_checker.Policy_admission
module Realization = Bioc_checker.Policy_realization_admission
module Lower = Bioc_compiler.Policy_lowering
module Graph = Bioc_compiler.Policy_implementation_lowering
module Arrange = Bioc_compiler.Policy_component_lowering
module Construct = Bioc_compiler.Construction_producer
module Recoding = Bioc_compiler.Recoding_producer
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module Q = Bioc_domain.Policy_component_assembly_proposal
module K = Bioc_domain.Construction_content
let text key value = Json.string (get key value)
let controls = ref 0
let reject code run =
  incr controls;
  match run () with
  | _ -> failwith ("Metered producer unexpectedly completed: " ^ code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code=code)
      ("Metered producer changed injected diagnostic: " ^ diagnostic.code)
let fail_charge _ = Diagnostic.fail "literal_producer_outer_limit" "Injected count-only outer exhaustion."
let measured run =
  let work=ref 0 in let result=run (fun amount -> require (amount>=0) "Negative producer charge"; work:= !work+amount) in
  require (!work>0) "Producer did not debit enclosing meter"; result,!work
let limit maximum =
  let spent=ref 0 in
  (fun amount -> require (amount>=0) "Negative producer charge";
    if amount>maximum - !spent then fail_charge amount; spent:= !spent+amount),spent
let same label encode old metered =
  require (Canonical.encode (encode old)=Canonical.encode (encode metered)) (label ^ " changed candidate bytes")
let graph_json (value:Graph.proposal) = obj ["implementation",I.to_json value.implementation;"binding",U.to_json value.binding]
let arrangement_json (value:Arrange.proposal) = obj ["implementation",I.to_json value.implementation;
  "binding",U.to_json value.binding;"assembly",Q.to_json value.assembly]
let source_admission original = Admission.admit ~document:(RR.document original) ~descriptors:(RR.definitions original)
let realization original behavior = Realization.admit ~request:original ~behavior
let run fixture state_reading =
  let raw,_=request_literal fixture state_reading in
  let request=R.of_json raw in
  let original=R.implementation_request request in
  let source=source_admission original in
  let behavior=Lower.lower source in
  let metered_behavior,lower_work=measured (fun charge -> Lower.lower ~charge source) in
  same "operational lowering" O.behavior_to_json behavior metered_behavior;
  reject "literal_producer_outer_limit" (fun () -> Lower.lower ~charge:fail_charge source);
  let charge,_=limit (lower_work/2) in
  reject "literal_producer_outer_limit" (fun () -> Lower.lower ~charge source);
  let admitted=realization original behavior and library=RR.implementation_library original in
  let graph=Graph.lower ~admitted ~library in
  let metered_graph,graph_work=measured (fun charge -> Graph.lower_metered ~charge ~admitted ~library) in
  same "implementation lowering" graph_json graph metered_graph;
  reject "literal_producer_outer_limit" (fun () -> Graph.lower_metered ~charge:fail_charge ~admitted ~library);
  let charge,_=limit (graph_work-1) in
  reject "literal_producer_outer_limit" (fun () -> Graph.lower_metered ~charge ~admitted ~library);
  let rule=R.composition_rule request in
  let arrangement=Arrange.arrange ~library ~rule graph in
  let metered_arrangement,arrange_work=measured (fun charge -> Arrange.arrange ~charge ~library ~rule graph) in
  same "component arrangement" arrangement_json arrangement metered_arrangement;
  reject "literal_producer_outer_limit" (fun () -> Arrange.arrange ~charge:fail_charge ~library ~rule graph);
  let charge,_=limit (arrange_work-1) in
  reject "literal_producer_outer_limit" (fun () -> Arrange.arrange ~charge ~library ~rule graph);
  let authority=A.material_authority rule in
  let template=PM.template authority and member_order=PM.member_order authority in
  let module Payload=Bioc_domain.Payload_template in
  let module Recipe=Bioc_domain.Construction in
  let root=Recoding.Root (Recipe.Root_source.molecule (List.hd (Payload.sources template))) in
  let maximum=Recipe.max_sources+Recipe.max_products in
  let oversized=List.init (maximum+1) (fun _ -> "repeated",root) in
  let rec cyclic=("cyclic",root)::cyclic in
  (* Native callers can supply cyclic list spines; preserve the original
     bounded-prefix diagnostic before duplicate IDs or any unbounded scan. *)
  List.iter (fun bindings ->
    reject "molecular_resource_limit" (fun () -> Recoding.Available.of_bindings bindings);
    let calls=ref 0 in
    reject "molecular_resource_limit" (fun () -> Recoding.Available.of_bindings
      ~charge:(fun _ -> incr calls) bindings);
    require (!calls=maximum+1) "Available input preflight exceeded its original bounded prefix") [oversized;cyclic];
  reject "literal_producer_outer_limit" (fun () -> Recoding.Available.of_bindings ~charge:fail_charge cyclic);
  let content=Construct.construct_template ~member_order template in
  let metered_content,construction_work=measured (fun charge -> Construct.construct_template ~charge ~member_order template) in
  same "template construction" K.to_json content metered_content;
  reject "literal_producer_outer_limit" (fun () -> Construct.construct_template ~charge:fail_charge ~member_order template);
  let charge,_=limit (construction_work-1) in
  reject "literal_producer_outer_limit" (fun () -> Construct.construct_template ~charge ~member_order template);
  let serialized,serialization_work=measured (fun charge -> Construct.content_json ~charge content) in
  require (Json.equal serialized (Construct.content_json content)) "Final typed content serialization changed bytes";
  reject "literal_producer_outer_limit" (fun () -> Construct.content_json ~charge:fail_charge content);
  let charge,_=limit (serialization_work-1) in
  reject "literal_producer_outer_limit" (fun () -> Construct.content_json ~charge content);
  (* A larger enclosing allowance never disables the existing construction cap. *)
  reject "construction_producer_limit" (fun () -> Construct.construct_template
    ~charge:(fun _ -> ()) ~limits:(Construct.Limits.make ~work:0 ()) ~member_order template);
  (* Output reservation uses outer-only accounting: it must still fit the same
     one-unit local owner, and a callback failure must survive protected recovery. *)
  let output=Json.String "outer-only output pass" in
  let budget=Recoding.make_budget ~maximum:1 () in
  Recoding.protect (fun () -> Recoding.reserve_output budget output;Recoding.reserve_staged budget output;Recoding.charge budget 1);
  let budget=Recoding.make_budget ~maximum:1 ~charge:fail_charge () in
  reject "literal_producer_outer_limit" (fun () -> Recoding.protect (fun () -> Recoding.reserve_output budget output));
  lower_work,graph_work,arrange_work,construction_work
let failed_layout fixture =
  let original=get "implementation_request" (get "request" fixture) in
  let models=items "models" (get "implementation_library" original) in
  let evidence=List.find (fun row -> text "primitive" (get "body" row)="evidence_bank") models in
  let added=evidence |> put ["body";"replication";"layout_id"] (str "0.incomplete.layout")
    |> put ["identity";"id"] (str "fixture.earlier.incomplete.layout") in
  let added=put ["identity";"content_fingerprint"] (str (Canonical.fingerprint (get "body" added))) added in
  let changed=original |> put ["implementation_library";"models"] (arr (models@[added]))
    |> edit ["catalog_bindings";"0";"models"] (fun values -> arr (Json.array values@[get "identity" added])) in
  let generate raw charge =
    let original=RR.of_json raw in
    let admitted=realization original (Lower.lower (source_admission original)) in
    Graph.lower_metered ~charge ~admitted ~library:(RR.implementation_library original) in
  let _,baseline=measured (generate original) in
  let produced,with_failed_layout=measured (generate changed) in
  require ((I.slot_layout produced.implementation).layout_id="encounters") "Failed early layout changed selected implementation";
  require (with_failed_layout>baseline) "Failed layout/model scans were refunded or uncharged";
  let charge,spent=limit baseline in
  reject "literal_producer_outer_limit" (fun () -> generate changed charge);
  require (!spent>0) "Failed layout did not retain previous work"
let () =
  require (Array.length Sys.argv=3) "Supply independent material A/B originals";
  let a=read Sys.argv.(1) and b=read Sys.argv.(2) in
  let aw=run a false and bw=run b true in
  failed_layout a;
  Printf.printf "metered producer controls=%d A=%s B=%s\n" !controls
    (let a,b,c,d=aw in Printf.sprintf "%d/%d/%d/%d" a b c d)
    (let a,b,c,d=bw in Printf.sprintf "%d/%d/%d/%d" a b c d)
