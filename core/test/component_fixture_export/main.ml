(* Hosted source-declaration export only. This executable links no producer,
   operational evaluator or acceptance checker; all expected material below is
   authored independently of any compilation result. *)
open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests

let bytes path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size=in_channel_length channel in
    require (size<=4_000_000) "Source fixture input exceeds its bound";
    really_input_string channel size)
let expected_molecule state_reading =
  let offset,length,sequence=if state_reading then 3,18,"CGCAUGGCUUAAGGAAAA" else 2,17,"CCAUGGCUUAAGGAAAA" in
  let frame="payload.frame" and p=M.Provenance.of_json provenance in
  N.make ~id:"payload" ~form:N.Delivered_rna ~space:(G.Space.of_json (space frame length))
    ~sequence ~sequence_extent:H.Complete ~coding_status:N.Coding
    ~assembly:[N.Assembly_origin.make ~id:"payload.origin" ~destination:(G.Path.of_json (path frame 0 length))
      ~source_space:(G.Space.of_json (space "join.frame" length)) ~source_path:(G.Path.of_json (path "join.frame" 0 length)) ~provenance:p]
    ~features:(List.map N.Feature.of_json [feature frame "cds" "coding_sequence" offset (offset+9) (Json.int 0);
      feature frame "poly_a" "poly_a_tail" (offset+11) length Json.Null;
      feature frame "utr3" "three_prime_utr" (offset+9) (offset+11) Json.Null;
      feature frame "utr5" "five_prime_utr" 0 offset Json.Null])
    ~chemistry:(H.of_json (chemistry frame true |> put ["terminal_tail";"path"] (path frame (offset+11) length))) ~provenance:p
let expected_projections state_reading request molecule =
  let components=items "components" (get "component_library" request) in
  let component slot=get "body" (List.nth components (if slot="decision" then 0 else 1)) in
  let source slot=if slot="driver" then "driver_body" else if state_reading then "leader_B" else "leader_A" in
  let project slot site =
    let feature=List.find (fun (feature:N.Feature.t) -> N.Feature.id feature=Json.string (get "feature" site)) (N.features molecule) in
    obj ["slot",str slot;"root",get "root" site;"source",str (source slot);"feature",get "feature" site;
      "local_path",get "path" site;"member",str "payload";"path",G.Path.to_json (Option.get (N.Feature.path feature))] in
  let carriers=List.concat_map (fun slot -> List.map (fun row ->
    obj ["slot",str slot;"target",get "target" row;"sites",arr (List.map (project slot) (items "sites" row))])
    (items "carriers" (component slot))) ["decision";"driver"] in
  let boundary_site slot id =
    let carrier=List.find (fun row -> get "target" row=target "boundary_port" id) (items "carriers" (component slot)) in
    project slot (List.hd (items "sites" carrier)) in
  let link id producer_slot producer_node producer_port consumer_slot consumer_node consumer_port =
    obj ["link",str id;"join",str "leader_to_driver";"offset",Json.int (if state_reading then 3 else 2);
      "producer_endpoint",er producer_slot producer_node producer_port;
      "consumer_endpoint",er consumer_slot consumer_node consumer_port;
      "producer",boundary_site producer_slot id;"consumer",boundary_site consumer_slot id] in
  let links=[link "product" "driver" "product" "out" "decision" "select_commit" "product0";
    link "request" "decision" "select_commit" "request0" "driver" "attempt" "request";
    link "authorization" "decision" (if state_reading then "select_guard" else "evidence")
      (if state_reading then "out" else "value") "driver" "attempt" "authorization"] in
  require (List.length carriers=(if state_reading then 107 else 96) && List.length links=3) "Original projection census changed";
  arr carriers,arr links
let case id state_reading fixture =
  let request,_=request_literal fixture state_reading in
  let molecule=expected_molecule state_reading in
  let carriers,links=expected_projections state_reading request molecule in
  obj ["id",str id;"request",request;"limits",get "limits" fixture;
    "expected",obj ["molecules",arr [N.to_json molecule];"carrier_projections",carriers;"link_projections",links;
      "histories",Json.int 9;"transitions",Json.int 47;"prefixes_started",Json.int 48;
      "obligations",at ["expected";"obligations"] fixture]]
let component_packet () =
  require (Array.length Sys.argv=6) "Supply original A, original B, literal source, request source and one output path";
  let inputs=List.map bytes [Sys.argv.(1);Sys.argv.(2);Sys.argv.(3);Sys.argv.(4)] in
  let a=Json.parse (List.nth inputs 0) and b=Json.parse (List.nth inputs 1) in
  let paths=["core/test/data/policy_material_request_v01.json";"core/test/data/policy_material_state_v01.json";
    "core/test/policy_component_support/literals.ml";"core/test/policy_component_support/requests.ml"] in
  let packet=obj ["schema_version",str "biocompiler.policy_component_original_fixture.v0.1";
    "status",str "source_declarations_only";"acceptance",Json.Bool false;
    "source_sha256",obj (List.map2 (fun path raw -> path,str (Canonical.sha256 raw)) paths inputs);
    "cases",arr [case "A" false a;case "B" true b]] in
  let encoded=Canonical.encode_bounded ~max_bytes:4_000_000 packet in
  let channel=open_out_gen [Open_wronly;Open_creat;Open_excl;Open_binary] 0o600 Sys.argv.(5) in
  Fun.protect ~finally:(fun () -> close_out_noerr channel) (fun () -> output_string channel encoded)


(* Separate source-only selection packet. The previous A/B packet and command
   remain byte-for-byte unchanged. Both alternatives here use the A program. *)
let selection_packet () =
  require (Array.length Sys.argv=7 && Sys.argv.(1)="--selection")
    "Supply selection mode, original A, literal source, request source, selection source and one output path";
  let inputs=List.map bytes [Sys.argv.(2);Sys.argv.(3);Sys.argv.(4);Sys.argv.(5)] in
  let fixture=Json.parse (List.hd inputs) in
  let original=Bioc_policy_component_test_support.Selection_requests.selection_literal fixture
    |> put ["budgets";"profile"] (str "biocompiler.policy_component_selection_resources.v0.2")
    |> put ["budgets";"max_report_nodes"] (Json.int 1000000) in
  let paths=["core/test/data/policy_material_request_v01.json";
    "core/test/policy_component_support/literals.ml";"core/test/policy_component_support/requests.ml";
    "core/test/policy_component_support/selection_requests.ml"] in
  let packet=obj ["schema_version",str "biocompiler.policy_component_selection_original_fixture.v0.1";
    "status",str "source_declarations_only";"acceptance",Json.Bool false;
    "source_sha256",obj (List.map2 (fun path raw -> path,str (Canonical.sha256 raw)) paths inputs);
    "request",original;"limits",get "limits" fixture;
    "expected",obj ["short_rna",str "CCAUGGCUUAAGGAAAA";"long_rna",str "CGCAUGGCUUAAGGAAAA";
      "histories",Json.int 9;"transitions",Json.int 47;"prefixes_started",Json.int 48;
      "obligations",at ["expected";"obligations"] fixture]] in
  let encoded=Canonical.encode_bounded ~max_bytes:4_000_000 packet in
  let channel=open_out_gen [Open_wronly;Open_creat;Open_excl;Open_binary] 0o600 Sys.argv.(6) in
  Fun.protect ~finally:(fun () -> close_out_noerr channel) (fun () -> output_string channel encoded)

let () =
  if Array.length Sys.argv=7 && Sys.argv.(1)="--selection" then selection_packet ()
  else component_packet ()
