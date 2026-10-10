(* Source declarations only. No producer, evaluator or acceptance checker is
   linked: closure roots, edges and allocations are independently authored. *)
open Bioc_wire
open Bioc_policy_prerequisite_test_support.Literals
open Bioc_policy_prerequisite_test_support.Requests

let bytes path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let size=in_channel_length channel in
    require(size<=4_000_000) "Source fixture exceeds bounded input";
    really_input_string channel size)
let case id state_reading fixture =
  let request,_=request_literal fixture state_reading in
  let carriers,links=expected_projections state_reading (original_library fixture) in
  obj ["id",str id;"request",request;"limits",get "limits" fixture;
    "expected",obj ["sequence",str expected_sequence;"molecules",arr [N.to_json(expected_molecule())];
      "carrier_projections",carriers;"link_projections",links;
      "histories",Json.int 9;"transitions",Json.int 47;"prefixes_started",Json.int 48;
      "obligations",arr expected_obligations;"prerequisite_closure",expected_closure request]]
let () =
  require(Array.length Sys.argv=9)
    "Supply original A/B, component literals, instance literals/requests, prerequisite literals/requests and output";
  let inputs=List.init 7(fun index->bytes Sys.argv.(index+1)) in
  let paths=["core/test/data/policy_material_request_v01.json";"core/test/data/policy_material_state_v01.json";
    "core/test/policy_component_support/literals.ml";"core/test/policy_instance_support/literals.ml";
    "core/test/policy_instance_support/requests.ml";"core/test/policy_prerequisite_support/literals.ml";
    "core/test/policy_prerequisite_support/requests.ml"] in
  let packet=obj ["schema_version",str "biocompiler.policy_prerequisite_original_fixture.v0.1";
    "status",str "source_declarations_only";"acceptance",Json.Bool false;
    "source_sha256",obj(List.map2(fun path raw->path,str(Canonical.sha256 raw))paths inputs);
    "cases",arr [case "A" false(Json.parse(List.nth inputs 0));case "B" true(Json.parse(List.nth inputs 1))]] in
  let encoded=Canonical.encode_bounded ~max_bytes:4_000_000 packet in
  let channel=open_out_gen [Open_wronly;Open_creat;Open_excl;Open_binary] 0o600 Sys.argv.(8) in
  Fun.protect ~finally:(fun()->close_out_noerr channel)(fun()->output_string channel encoded)
