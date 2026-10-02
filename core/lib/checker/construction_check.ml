open Bioc_wire
open Bioc_domain
module C = Construction
module A = Construction_artifact
module E = Construction_assessment
let implementation_version = "biocompiler.ocaml.construction_check.v0.1"
module Names = Map.Make (String)
module Ids = Set.Make (String)
module Inventory = E.Inventory
let status diagnostic = match String.index_opt diagnostic ':' with Some index -> String.sub diagnostic 0 index
  | None -> Diagnostic.fail "invalid_construction_check" "Internal diagnostic lacks outcome prefix."

let candidate_differences actual expected =
  let diagnostics = Inventory.create () in
  let add = Inventory.add diagnostics in
  if A.request_fingerprint actual <> A.request_fingerprint expected then add "fail:candidate_request_authority";
  let inventory values = List.fold_left (fun map value -> Names.add (A.Value.id value) value map) Names.empty values in
  let observed = inventory (A.values actual) and wanted = inventory (A.values expected) in
  let keys map = Names.fold (fun id _ set -> Ids.add id set) map Ids.empty in
  if not (Ids.equal (keys observed) (keys wanted)) then add "fail:constructed_value_inventory";
  Ids.iter (fun id ->
      let actual = A.Value.to_json (Names.find id observed) |> Json.object_fields
      and expected = A.Value.to_json (Names.find id wanted) |> Json.object_fields in
      List.iter (fun key -> if not (Json.equal (Json.field key actual) (Json.field key expected)) then add ("fail:value:" ^ id ^ ":" ^ key))
        ["space";"sequence";"chemistry";"features";"segments";"consumed";"step_id";"sequence_extent"]) (Ids.inter (keys observed) (keys wanted));
  if Option.map Molecule_set.fingerprint (A.bundle actual) <> Option.map Molecule_set.fingerprint (A.bundle expected) then add "fail:final_molecule_inventory_or_authority";
  if A.missing_members actual <> A.missing_members expected then add "fail:missing_member_inventory";
  if A.diagnostics actual <> A.diagnostics expected then add "fail:construction_diagnostic_inventory";
  if List.map Molecule_set.Amount.fingerprint (A.experimental_amounts actual) <> List.map Molecule_set.Amount.fingerprint (A.experimental_amounts expected) then add "fail:experimental_amount_authority";
  if A.fingerprint actual <> A.fingerprint expected && Inventory.elements diagnostics = [] then add "fail:complete_candidate_identity";
  diagnostics
let resource_profile = "biocompiler.construction_check.resources.v1"
let max_work = 50_000_000
let make_budget ?parent ?(maximum=max_work) () =
  Diagnostic.require (maximum>=0 && maximum<=max_work) "construction_resource_limit" "Construction check exceeds its fixed work ceiling.";
  match parent with None -> Work_budget.create ~profile:resource_profile ~error_code:"construction_resource_limit" ~maximum ()
  | Some parent -> Work_budget.nested ~parent ~profile:resource_profile ~error_code:"construction_resource_limit" ~maximum ()
let check ?parent ?(maximum=max_work) ~expected_request candidate = Construction_reconstruction.protect (fun () ->
  let budget=make_budget ?parent ~maximum () in
  Work_budget.charge budget 1;
  Construction_reconstruction.reserve_json budget (C.Request.to_json expected_request);
  Construction_reconstruction.reserve_json budget (A.to_json candidate);
  let request = C.Request.of_json (C.Request.to_json expected_request) in
  let actual = A.of_json (A.to_json candidate) in
  let expected,transitions = Construction_reconstruction.reconstruct ~budget request in
  Construction_reconstruction.reserve_json budget (A.to_json actual);
  Construction_reconstruction.reserve_json budget (A.to_json expected);
  let diagnostics = candidate_differences actual expected in
  let add = Inventory.add diagnostics in
  List.iter (fun step -> match C.Operation.specification (C.Transform_step.operation step) with
      | C.Operation.Conditional_translation branches -> List.iter (fun branch -> if C.Translation_branch.port_id branch = None then
            add ("unsupported:step:" ^ C.Transform_step.id step ^ ":no_product_branch_semantics:" ^ C.Translation_branch.id branch)) branches
      | _ -> ()) (C.Request.steps request);
  List.iter (fun code ->
      let last = match String.rindex_opt code ':' with None -> code | Some index -> String.sub code (index + 1) (String.length code - index - 1) in
      let status = if last = "nominal_incomplete" then "unknown" else if String.starts_with ~prefix:"invalid_" last then "fail" else "unsupported" in
      add (status ^ ":" ^ code)) (A.diagnostics expected);
  let transition_budget = Transition_check.make_budget ~parent:budget () in
  List.iter (fun (transition : Construction_reconstruction.transition) ->
      let resolution = Transition_check.resolve ~budget:transition_budget (C.Product_port.chemistry_transition transition.port)
          (C.Product_port.feature_transition transition.port) ~inputs:transition.inputs ~output_sequence:(A.Value.sequence transition.product)
          ~output_space:(A.Value.space transition.product) ~derivation:(A.Value.segments transition.product) ~sequence_extent:(A.Value.sequence_extent transition.product) in
      List.iter (fun item -> add ("fail:step:" ^ C.Transform_step.id transition.step ^ ":" ^ item)) (Transition_check.diagnostics resolution);
      List.iter (fun item -> add ("unsupported:step:" ^ C.Transform_step.id transition.step ^ ":" ^ item)) (Transition_check.unsupported resolution)) transitions;
  Option.iter (fun bundle -> let result = Payload_structure_check.check_with_parent ~parent:(Some budget) ~contracts:(C.Request.payload_structures request) ~bundle in
      List.iter (fun item -> add ("fail:" ^ item)) result.diagnostics;
      List.iter (fun item -> add ("unsupported:" ^ item)) result.unsupported) (A.bundle expected);
  if A.bundle expected = None && Inventory.elements diagnostics = [] then add "fail:missing_final_bundle";
  let values = Inventory.elements diagnostics in
  let statuses = List.map status values in
  let outcome = if List.mem "fail" statuses then E.Fail else if List.mem "unsupported" statuses then E.Unsupported
    else if List.mem "unknown" statuses then E.Unknown else E.Pass in
  E.make ~request_fingerprint:(C.Request.fingerprint request) ~candidate_fingerprint:(A.fingerprint actual)
    ~reconstructed_fingerprint:(A.fingerprint expected) ~outcome ~complete:(outcome = E.Pass) ~diagnostics:values)
let replay ?parent ?maximum ~expected_request ~candidate assessment =
  let saved = E.of_json (E.to_json assessment) in
  let fresh = check ?parent ?maximum ~expected_request candidate in
  Diagnostic.require (E.fingerprint saved = E.fingerprint fresh) "construction_assessment_mismatch" "Construction assessment differs from fresh complete replay.";
  fresh
