(* Exact original-only fixture emission. This executable links neither producer
   nor checker and confers no acceptance. *)
open Bioc_wire
open Bioc_policy_multi_member_test_support.Literals
open Bioc_policy_multi_member_test_support.Requests
let bytes path=
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let size=in_channel_length channel in require(size<=4_000_000)"Oversized original fixture";
    really_input_string channel size)
let ()=
  require(Array.length Sys.argv=5)"Supply staged original, multi-member literals/requests, and output";
  let inputs=List.init 3(fun index->bytes Sys.argv.(index+1))in
  let paths=["core/test/data/policy_staged_material_v01.json";"core/test/policy_multi_member_support/literals.ml";
    "core/test/policy_multi_member_support/requests.ml"]in
  let fixture=Json.parse(List.hd inputs)in
  let packet=obj["schema_version",str "biocompiler.policy_multi_member_original_fixture.v0.1";
    "status",str "source_declarations_only";"acceptance",Json.Bool false;
    "source_sha256",obj(List.map2(fun path bytes->path,str(Canonical.sha256 bytes))paths inputs);
    "cases",arr[case fixture "A" false;case fixture "B" true]]in
  let encoded=Canonical.encode_bounded ~max_bytes:4_000_000 packet in
  let channel=open_out_gen[Open_wronly;Open_creat;Open_excl;Open_binary]0o600 Sys.argv.(4)in
  Fun.protect ~finally:(fun()->close_out_noerr channel)(fun()->output_string channel encoded)
