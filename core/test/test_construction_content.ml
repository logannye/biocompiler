open Bioc_wire
open Bioc_domain
module C = Construction
module A = Construction_artifact
module K = Construction_content
module P = Bioc_compiler.Construction_producer
module Check = Bioc_checker.Construction_check
module E = Construction_assessment
module N = Molecule
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let field key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let str value = Json.String value
let rejected code run = incr checks; match run () with
  | _ -> failwith ("Expected rejection: " ^ code)
  | exception Diagnostic.Error value -> if value.code <> code then failwith ("Expected " ^ code ^ "; got " ^ value.code)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 500_000) "Fixture exceeds its frozen read bound";
    Json.parse (really_input_string channel size))
let () =
  let fixture = read Sys.argv.(1) in
  let request = C.Request.of_json (field "legacy_request" fixture) in
  let original = A.of_json (field "legacy_candidate" fixture) in
  require (str (C.Request.fingerprint request) = field "legacy_request_digest" fixture) "Legacy authority literal changed";
  require (str (A.fingerprint original) = field "legacy_candidate_digest" fixture) "Legacy candidate literal changed";
  let legacy = P.construct request in
  require (Canonical.encode (A.to_json legacy) = Canonical.encode (field "legacy_candidate" fixture))
    "Neutral extraction changed legacy candidate bytes";
  let report = Check.check ~expected_request:request legacy in
  require (E.passed report) "Legacy independent reconstruction regressed";
  require (Canonical.encode (E.to_json report) = Canonical.encode (field "legacy_assessment" fixture))
    "Neutral extraction changed legacy assessment bytes";
  ignore (Check.replay ~expected_request:request ~candidate:legacy report);
  let template = Payload_template.from_construction_request request in
  let order = List.map C.Output_member.id (Payload_template.output_members template) in
  let candidate = P.construct_template ~member_order:order template in
  let check candidate = Check.check_template ~expected_template:template ~expected_member_order:order candidate in
  let report = check candidate in
  require (Check.content_outcome report = E.Pass) "Neutral exact-content correspondence failed";
  let raw_report = Check.content_report report in
  require (field "context_status" raw_report = str "unassessed" && field "payload_completeness" raw_report = str "unassessed")
    "Molecular correspondence fabricated context or mRNA completeness";
  require (Option.map K.fingerprint (Check.checked_content report) = Some (K.fingerprint candidate)) "Checked result lost exact candidate";
  ignore (Check.replay_template ~expected_template:template ~expected_member_order:order ~candidate raw_report);
  let content = Option.get (K.inventory candidate) and bundle = Option.get (A.bundle legacy) in
  require (List.map N.to_json (K.Inventory.molecules content) = List.map N.to_json (Molecule_set.molecules bundle))
    "Neutral member content differs from frozen independent legacy content";
  require (List.map A.Value.to_json (K.values candidate) = List.map A.Value.to_json (A.values legacy))
    "Neutral derivations changed legacy transform values";
  require (List.map N.sequence (K.Inventory.molecules content) = [Json.string (field "expected_rna" fixture)])
    "Literal construction output differs";
  let no_accept label raw =
    let changed = K.of_json raw in
    require (K.fingerprint changed <> K.fingerprint candidate) (label ^ " did not change content identity");
    let result = check changed in
    require (Check.content_outcome result = E.Fail && Check.checked_content result = None) (label ^ " acquired checked content") in
  let raw = K.to_json candidate in
  no_accept "own authority pin" (set "authority_fingerprint" (str (String.make 64 '0')) raw);
  no_accept "missing inventory" (set "inventory" Json.Null raw);
  no_accept "invented diagnostic" (set "diagnostics" (Json.Array [str "claimed:pass"]) raw);
  no_accept "invented missing member" (set "missing_members" (Json.Array [str "foreign"]) raw);
  let values = Json.array (field "values" raw) in
  let first = List.hd values in
  let sequence = Json.string (field "sequence" first) in
  let changed_sequence = String.make 1 (if sequence.[0]='A' then 'C' else 'A') ^ String.sub sequence 1 (String.length sequence-1) in
  no_accept "basewise derivation" (set "values" (Json.Array (set "sequence" (str changed_sequence) first :: List.tl values)) raw);
  no_accept "source mapping" (set "values" (Json.Array (set "step_id" (str "foreign-step") first :: List.tl values)) raw);
  let shifted_template = Payload_template.of_json (set "id" (str "different-original-template") (Payload_template.to_json template)) in
  require (Check.content_outcome (Check.check_template ~expected_template:shifted_template ~expected_member_order:order candidate) = E.Fail)
    "Different independently supplied template accepted old content";
  let template_raw = Payload_template.to_json template in
  let sources = Json.array (field "sources" template_raw) in
  let source = List.hd sources in
  let molecule = field "molecule" source in
  let spelling = Json.string (field "sequence" molecule) in
  let spelling = String.make 1 (if spelling.[0]='A' then 'C' else 'A') ^ String.sub spelling 1 (String.length spelling-1) in
  let changed_source = set "molecule" (set "sequence" (str spelling) molecule) source in
  let changed_template = Payload_template.of_json (set "sources" (Json.Array (changed_source :: List.tl sources)) template_raw) in
  let rehashed = K.of_json (set "authority_fingerprint"
      (str (K.authority_fingerprint ~template:changed_template ~member_order:order)) raw) in
  require (Check.content_outcome (Check.check_template ~expected_template:changed_template ~expected_member_order:order rehashed) = E.Fail)
    "Recomputed candidate pins hid a change to original source bases";
  rejected "construction_content_assessment_mismatch" (fun () ->
    Check.replay_template ~expected_template:template ~expected_member_order:order ~candidate
      (set "context_status" (str "accepted") raw_report));
  rejected "invalid_construction_content" (fun () -> P.construct_template ~member_order:[] template);
  rejected "invalid_construction_content" (fun () -> P.construct_template ~member_order:(order @ order) template);
  rejected "invalid_construction_content" (fun () -> P.construct_template ~member_order:["foreign"] template);
  let rec cyclic = Json.Array [cyclic] in
  rejected "molecular_cycle" (fun () -> K.of_json cyclic);
  let rec cyclic_order = "payload" :: cyclic_order in
  rejected "molecular_resource_limit" (fun () -> K.authority_json ~template ~member_order:cyclic_order);
  let rec nested count raw = if count=0 then raw else nested (count-1) (Json.Array [raw]) in
  rejected "molecular_resource_limit" (fun () -> K.of_json (nested 100 Json.Null));
  rejected "construction_producer_limit" (fun () -> P.construct_template ~limits:(P.Limits.make ~work:0 ()) ~member_order:order template);
  rejected "construction_resource_limit" (fun () -> Check.check_template ~maximum:0 ~expected_template:template ~expected_member_order:order candidate);
  let limited = P.construct_template ~limits:(P.Limits.make ~final_residues:5 ()) ~member_order:order template in
  require (K.inventory limited = None && K.missing_members limited = order &&
    K.diagnostics limited = ["member:payload:unavailable_value";"step:step:residue_budget"])
    "Neutral transform residue preflight did not retain exact failure and missing member";
  require (Check.content_outcome (check limited) = E.Fail) "Limited producer result became complete content";
  let member = List.hd (Payload_template.output_members template) in
  let helper = C.Output_member.make ~id:"z-helper" ~value:(C.Output_member.value member) ~space_id:"z-helper.frame"
      ~form:(C.Output_member.form member) ~sequence_extent:(C.Output_member.sequence_extent member)
      ~coding_status:(C.Output_member.coding_status member) ~provenance:(C.Output_member.provenance member) in
  let role = C.Role.make ~id:"z-helper.role" ~role:"helper" ~purpose:N.Role.Helper ~compartment:"cytoplasm" in
  let helper_requirement = C.Member_requirement.make ~id:"z-helper.required" ~category:C.Member_requirement.Delivered_helper
      ~subject:(C.Member_requirement.Materialized "z-helper") ~roles:[role] in
  let pair = Payload_template.make ~id:"explicit-two-member-order" ~sources:(Payload_template.sources template)
      ~steps:(Payload_template.steps template) ~output_members:[member;helper]
      ~requirements:(Payload_template.requirements template @ [helper_requirement])
      ~payload_structures:(Payload_template.payload_structures template) () in
  let pair_order = ["z-helper";C.Output_member.id member] in
  require (List.map C.Output_member.id (Payload_template.output_members pair) <> pair_order) "Order fixture accidentally follows normalized IDs";
  let pair_candidate = P.construct_template ~member_order:pair_order pair in
  let pair_report = Check.check_template ~expected_template:pair ~expected_member_order:pair_order pair_candidate in
  require (Check.content_outcome pair_report = E.Pass) "Two-member content failed";
  require (List.map N.id (K.Inventory.molecules (Option.get (K.inventory pair_candidate))) = pair_order) "Explicit original order was normalized away";
  (* Each six-base transform fits separately; the two delivered members exceed
     the same total allowance. Exercise aggregate and transform limits apart. *)
  let pair_limited = P.construct_template ~limits:(P.Limits.make ~final_residues:6 ()) ~member_order:pair_order pair in
  require (K.inventory pair_limited = None && K.missing_members pair_limited = List.sort String.compare pair_order &&
    K.diagnostics pair_limited = ["bundle:residue_budget"])
    "Neutral delivered-member residue preflight did not retain exact aggregate failure";
  require (Check.content_outcome (Check.check_template ~expected_template:pair ~expected_member_order:pair_order pair_limited) = E.Fail)
    "Aggregate-limited producer result became complete content";
  let opposite = List.rev pair_order in
  let reordered = P.construct_template ~member_order:opposite pair in
  require (K.authority reordered <> K.authority pair_candidate) "Original order omitted from authority identity";
  require (Check.content_outcome (Check.check_template ~expected_template:pair ~expected_member_order:pair_order reordered) = E.Fail)
    "Recomputed candidate authority hid original order mutation";
  let unresolved_provider = C.Member_requirement.make ~id:"unresolved-host" ~category:C.Member_requirement.Host_provider
      ~subject:(C.Member_requirement.External {id="unresolved-host";fingerprint=String.make 64 '1'})
      ~roles:[C.Role.make ~id:"host.role" ~role:"host" ~purpose:N.Role.Host_provider ~compartment:"cytoplasm"] in
  let unbound = Payload_template.make ~id:"context-unassessed" ~sources:(Payload_template.sources template)
      ~steps:(Payload_template.steps template) ~output_members:(Payload_template.output_members template)
      ~requirements:(Payload_template.requirements template @ [unresolved_provider]) () in
  let unbound_candidate = P.construct_template ~member_order:order unbound in
  let unbound_report = Check.check_template ~expected_template:unbound ~expected_member_order:order unbound_candidate in
  require (Check.content_outcome unbound_report = E.Pass && field "context_status" (Check.content_report unbound_report) = str "unassessed")
    "Content leaf pretended to validate external provider context";
  rejected "invalid_construction" (fun () -> Payload_template.to_construction_request unbound (C.Request.circuit request));
  require (Check.content_outcome (Check.check_template ~expected_template:unbound ~expected_member_order:order candidate) = E.Fail)
    "Unresolved source obligations were dropped from content authority";
  Printf.printf "construction content: %d exact-content and legacy-equivalence checks\n" !checks
