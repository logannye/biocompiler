open Bioc_wire
open Bioc_domain
module A = Architecture_contract
module B = Architecture_build
module R = Architecture_refinement
module E = Source_execution_manifest
module Check = Bioc_checker.Architecture_check
module Work = Bioc_checker.Work_budget
module Names = Map.Make (String)
module Ids = Set.Make (String)
let implementation_version = "biocompiler.ocaml.architecture_producer.v0.1"
let resource_profile = "biocompiler.architecture_producer.resources.v1"
let max_work = 200_000_000
let create_budget = function None -> Work.create ~profile:resource_profile ~error_code:"architecture_producer_limit" ~maximum:max_work ()
  | Some parent -> Work.nested ~parent ~profile:resource_profile ~error_code:"architecture_producer_limit" ~maximum:max_work ()
let str value = Json.String value
let strings values = Json.Array (List.map str values)
let field key raw = Json.field key (Json.object_fields raw)
let hash = Canonical.fingerprint
let node_id node = Identity.Node.to_string (Behavior.node_id node)
let node_inputs node = Behavior.inputs node |> List.map Identity.Node.to_string
let kind node = Behavior.kind_name (Behavior.operation node)
let runtime node = List.mem (kind node) ["rule"; "state"; "memory"] || String.starts_with ~prefix:"action." (kind node)
let bindings refinement = R.source_bindings refinement |> List.map (fun (local, remote) -> Identity.Node.to_string local, Identity.Node.to_string remote)
let gap ?(requirements=[]) ?(candidates=[]) ?message ?(conflict_set=[]) category code =
  let message = match message with Some value when value <> "" -> value | _ -> String.map (fun character -> if character = '_' then ' ' else character) code in
  B.Gap.make ~category ~code ~requirement_ids:requirements ~candidate_ids:candidates ~message ~conflict_set
let receipt_cost ?(nested=false) raw =
  Molecular_record.bounded_tree raw;
  let pending = ref [raw] and count = ref 0 and newlines = ref 0 in
  while !pending <> [] do
    let value = List.hd !pending in pending := List.tl !pending; incr count;
    match value with
    | Json.Object fields ->
        let length = List.length fields in count := !count + length;
        if length > 0 then newlines := !newlines + length + 1;
        pending := List.rev_append (List.map snd fields) !pending
    | Json.Array values ->
        let length = List.length values in if length > 0 then newlines := !newlines + length + 1;
        pending := List.rev_append values !pending
    | _ -> ()
  done;
  !count, Molecular_record.pretty_size raw + (if nested then 4 * (!newlines + 1) + 16 else 1)
let pattern_gaps refinement behavior =
  let source = Behavior.nodes behavior |> List.fold_left (fun map node -> Names.add (node_id node) node map) Names.empty in
  let mapping = bindings refinement in
  let remap identity = List.assoc identity mapping in
  let gaps = ref [] in
  if hash (Behavior.policies (R.behavior refinement)) <> hash (Behavior.policies behavior) then
    gaps := [gap ~candidates:[R.id refinement] B.Gap.Incompatible_composition "execution_policy_mismatch"];
  List.iter (fun node ->
      let identity = remap (node_id node) in
      match Names.find_opt identity source with
      | None -> gaps := gap ~requirements:["source:" ^ identity] ~candidates:[R.id refinement] B.Gap.Missing_implementation "absent_source_correspondence" :: !gaps
      | Some wanted ->
          let meaning ~remap node = Json.Object ["kind", str (kind node); "inputs", strings (List.map remap (node_inputs node));
              "role", (match Behavior.role node with None -> Json.Null | Some role -> str (remap (Identity.Role.to_string role)));
              "attributes", Behavior.attributes node; "data_type", field "data_type" (Behavior.node_json node);
              "contact_bound", Json.Bool (Behavior.contact_bound node)] in
          if hash (meaning ~remap node) <> hash (meaning ~remap:Fun.id wanted) then
            gaps := gap ~requirements:["source:" ^ identity] ~candidates:[R.id refinement]
              ~message:"The supplied model changes the source operation, inputs, type, role or parameters."
              B.Gap.Incompatible_composition "source_model_meaning_mismatch" :: !gaps) (Behavior.nodes (R.behavior refinement));
  List.rev !gaps
let coverage_gaps selected behavior =
  let covered = selected |> List.concat_map (fun refinement -> List.map snd (bindings refinement)) |> Ids.of_list in
  let owned = List.fold_left (fun map refinement -> List.fold_left (fun map local ->
      let identity = List.assoc (Identity.Node.to_string local) (bindings refinement) in
      let previous = Option.value ~default:[] (Names.find_opt identity map) in
      Names.add identity (previous @ [R.id refinement]) map) map (R.owned_node_ids refinement)) Names.empty selected in
  let identifiers = List.map R.id selected in
  Behavior.nodes behavior |> List.filter_map (fun node ->
      let identity = node_id node in
      if not (Ids.mem identity covered) || (runtime node && not (Names.mem identity owned)) then
        Some (gap ~requirements:["source:" ^ identity] ~candidates:identifiers B.Gap.Missing_implementation "uncovered_source_requirement")
      else if runtime node && List.length (Names.find identity owned) <> 1 then
        Some (gap ~requirements:["source:" ^ identity] ~candidates:(Names.find identity owned)
          ~message:"Runtime rules and stores need one supplied owner; label or byte identity cannot merge them."
          B.Gap.Incompatible_composition "duplicate_runtime_ownership") else None)
let contains text token =
  let rec scan offset = offset + String.length token <= String.length text &&
      (String.sub text offset (String.length token) = token || scan (offset + 1)) in scan 0
let candidate_gaps receipt selected request =
  let constraints = Architecture_request.constraints request in
  Architecture_assessment.diagnostics receipt |> List.map (fun diagnostic ->
      let code = B.Gap.code diagnostic in
      let implicated = ref (Ids.of_list (B.Gap.requirement_ids diagnostic)) in
      let add value = implicated := Ids.add value !implicated in
      List.iter (fun (source, target) -> if code = source then add ("constraint:" ^ target))
        ["exact_rna_count", "exact_count"; "maximum_rna_count", "max_count"; "maximum_rna_member_length", "max_member_bases"; "maximum_rna_total_length", "max_total_bases"];
      List.iter (fun item -> if contains code (A.Control_requirement.id item) then add ("constraint:control:" ^ A.Control_requirement.id item)) (A.Constraints.control_requirements constraints);
      List.iter (fun item -> if contains code (A.Delivery_group.id item) then add ("constraint:delivery:" ^ A.Delivery_group.id item)) (A.Constraints.delivery_groups constraints);
      List.iter (fun item -> if contains code (Architecture_deployment.Requirement.id item) then add ("constraint:deployment:" ^ Architecture_deployment.Requirement.id item)) (A.Constraints.deployment_requirements constraints);
      List.iter (fun refinement ->
          List.iter (fun (local, original) -> if String.ends_with ~suffix:(":" ^ local) code || String.ends_with ~suffix:(":" ^ original) code then add ("source:" ^ original)) (bindings refinement);
          List.iter (fun helper -> if contains code (A.Helper.id helper) || contains code (A.Helper.capability helper) then (
              let consumers = A.Helper.consumer_component_ids helper |> List.map Identity.Component.to_string |> Ids.of_list in
              List.iter (fun binding ->
                  if List.exists (fun component -> Ids.mem (Identity.Component.to_string component) consumers) (A.Binding.component_ids binding) then
                    List.iter (fun reference -> add ("source:" ^ List.assoc (Identity.Node.to_string reference) (bindings refinement))) (A.Binding.behavior_node_ids binding)) (R.bindings refinement))) (R.helpers refinement)) selected;
      let category = if List.exists (contains code) ["unsupported"; "external_observation_unbound"; "unowned_executable_state"; "unowned_executable_memory"; "unowned_executable_action"] then B.Gap.Unsupported_semantics else B.Gap.Incompatible_composition in
      let category = if List.exists (contains code) ["construction_"; "molecule_"; "template_"; "delivered_member_not_rna"] then B.Gap.Missing_sequence_authority else category in
      let category = if List.exists (fun prefix -> String.starts_with ~prefix code) ["plan_"; "source_manifest"; "request_authority"; "malformed_architecture"] then B.Gap.Independent_verification_failure else category in
      let requirements = Ids.elements !implicated in
      gap ~requirements ~candidates:(List.map R.id selected) ~message:(B.Gap.message diagnostic) ~conflict_set:requirements category code)
let tuple_repr values = "(" ^ String.concat ", " (List.map Diagnostic_text.repr values) ^ (if List.length values = 1 then "," else "") ^ ")"
let producer_resource budget (error : Diagnostic.t) =
  Work.is_exhaustion budget error || List.mem error.code
    ["architecture_material_output_limit"; "construction_producer_output_limit";
     "construction_producer_limit"; "construction_resource_limit";
     "transition_resource_limit"; "payload_structure_resource_limit";
     "architecture_output_limit"; "architecture_report_limit";
     "source_manifest_limit"; "lowering_lineage_limit"; "lowering_report_limit";
     "architecture_control_limit"; "architecture_deployment_limit";
     "circuit_binding_output_limit"]
let construction_rejection_message (error : Diagnostic.t) =
  if error.code = "architecture_synthesized_identity" then error.message
  else error.code ^ ": " ^ error.message
exception Finished of (B.t * Architecture_assessment.t)
let compile_checked ?budget request =
  let budget = create_budget budget in
  let request = Architecture_request.of_json (Architecture_request.to_json request) in
  let constraints = Architecture_request.constraints request in
  let execution = Source_execution.derive (Architecture_request.source request) in
  let diagnostics = E.diagnostics execution |> List.map (fun diagnostic ->
      gap ~requirements:(List.map (fun identity -> "source:" ^ identity) (E.Diagnostic_record.source_node_ids diagnostic))
        ~message:(E.Diagnostic_record.message diagnostic)
        (if E.Diagnostic_record.category diagnostic = E.Diagnostic_record.Contradiction then B.Gap.Contradictory_requirements else B.Gap.Unsupported_semantics)
        (E.Diagnostic_record.code diagnostic)) in
  let alternatives = ref [] and match_instances = ref [] and prefiltered = ref 0 and explored = ref 0
  and retained_items = ref 0 and retained_bytes = ref 0 and match_states = ref 0 in
  let build ~status ~plan ~construction ~extra = B.make ~request_fingerprint:(Architecture_request.fingerprint request) ~execution ~plan ~construction
      ~alternatives:(List.rev !alternatives) ~diagnostics:(diagnostics @ extra) ~status ~match_instances:(List.rev !match_instances) in
  let baseline = build ~status:B.Search_exhausted ~plan:None ~construction:None ~extra:[] in
  let baseline_items, baseline_bytes = receipt_cost (B.to_json baseline) in
  let item_budget = min 50_000 (max 0 (Molecular_record.max_items - baseline_items - 4096))
  and byte_budget = min 1_000_000 (max 0 (Molecular_record.max_json_bytes - baseline_bytes - 64_000)) in
  let finish ?(plan=None) ?(construction=None) ?(extra=[]) status =
    let candidate = try build ~status ~plan ~construction ~extra with
      | Diagnostic.Error error when error.code = "molecular_resource_limit" && plan <> None ->
          let selected = match plan with Some value -> B.Plan.selected_refinement_ids value | None -> [] in
          let message = "The selected construction exceeds the bounded reviewable output; retained candidate records remain available. " ^ error.code ^ ": " ^ error.message in
          build ~status:B.Search_exhausted ~plan:None ~construction:None ~extra:[gap ~candidates:selected ~message B.Gap.Search_budget_exhausted "architecture_selected_output_budget_exhausted"] in
    let receipt = Check.check ~budget ~expected_request:request candidate in
    Diagnostic.require (Architecture_assessment.passed receipt) "architecture_producer_verification" "Independent architecture verification rejected the produced candidate.";
    candidate, receipt in
  let retain_raw raw =
    let items, bytes = receipt_cost ~nested:true raw in
    if !retained_items + items > item_budget || !retained_bytes + bytes > byte_budget then false
    else (retained_items := !retained_items + items; retained_bytes := !retained_bytes + bytes; true) in
  let retain alternative = if retain_raw (B.Alternative.to_json alternative) then (alternatives := alternative :: !alternatives; true) else false in
  let retain_instance instance = if retain_raw (A.Instance.to_json instance) then (match_instances := instance :: !match_instances; true) else false in
  let retention_exhausted candidates =
    let message = Printf.sprintf "Examined %d of %d supplied refinement patterns and %d candidate subsets; retained %d complete alternative records. The next record exceeds the retained diagnostic budget of %d JSON items or %d serialized bytes. No infeasibility or optimality claim."
        !prefiltered (List.length (R.Library.refinements (Architecture_request.library request))) !explored (List.length !alternatives) item_budget byte_budget in
    finish ~extra:[gap ~candidates ~message B.Gap.Search_budget_exhausted "architecture_record_budget_exhausted"] B.Search_exhausted in
  try
    if E.behavior execution = None || diagnostics <> [] && A.Constraints.require_complete constraints then raise (Finished (finish B.Unsupported));
    let behavior = Option.get (E.behavior execution) in
    let choices = ref [] in
    List.iter (fun refinement ->
        incr prefiltered; Work.charge budget 1;
        let instances, exhausted, matching_diagnostics, gaps = match R.match_policy refinement with
          | None -> let gaps = pattern_gaps refinement behavior in
              let instances = if gaps <> [] then [] else [A.Instance.make ~id:(R.id refinement) ~refinement_id:(R.id refinement) ~source_bindings:(R.source_bindings refinement)] in
              instances, false, [], gaps
          | Some _ ->
              let result = Architecture_matching.match_refinement ~budget ~circuit:(Architecture_request.circuit request)
                  ~max_states:(A.Constraints.max_match_states constraints - !match_states)
                  ~max_instances:(A.Constraints.max_match_instances constraints - List.length !match_instances) refinement behavior in
              match_states := !match_states + Architecture_matching.states_examined result;
              let exhausted = Architecture_matching.exhausted result and messages = Architecture_matching.diagnostics result in
              Architecture_matching.instances result, exhausted, messages,
              (if exhausted then [] else List.map (fun code -> gap ~candidates:[R.id refinement] B.Gap.Missing_implementation code) messages) in
        List.iter (fun instance ->
            if List.exists (fun item -> A.Instance.id item = A.Instance.id instance) !match_instances then
              raise (Finished (finish ~extra:[gap ~candidates:[A.Instance.id instance]
                ~message:"Two supplied correspondences produce the same architecture instance identity; the library cannot be searched without ambiguity. No selected payload is emitted."
                B.Gap.Contradictory_requirements "architecture_instance_identity_collision"] B.Unsupported));
            if List.length !match_instances >= A.Constraints.max_match_instances constraints then
              raise (Finished (finish ~extra:[gap ~candidates:[R.id refinement]
                ~message:(Printf.sprintf "Retained %d complete instances; the request-wide instance bound prevents another candidate." (List.length !match_instances))
                B.Gap.Search_budget_exhausted "architecture_matching_instance_budget_exhausted"] B.Search_exhausted));
            if not (retain_instance instance) then
              raise (Finished (finish ~extra:[gap ~candidates:[A.Instance.id instance]
                ~message:(Printf.sprintf "Retained %d complete mappings after %d node-pair checks; the next mapping exceeds the bounded matching/alternative receipt. No selected payload is emitted." (List.length !match_instances) !match_states)
                B.Gap.Search_budget_exhausted "architecture_matching_record_budget_exhausted"] B.Search_exhausted));
            choices := Architecture_matching.instantiate refinement instance :: !choices) instances;
        if exhausted then raise (Finished (finish ~extra:(List.map (fun code -> gap ~candidates:[R.id refinement]
              ~message:(Printf.sprintf "Examined %d node-pair constraints across %d supplied refinements; retained %d complete mappings. Matching is incomplete and no selected payload is emitted." !match_states !prefiltered (List.length !match_instances))
              B.Gap.Search_budget_exhausted code) matching_diagnostics) B.Search_exhausted));
        if gaps <> [] && not (retain (B.Alternative.make ~refinement_ids:[R.id refinement] ~gaps)) then raise (Finished (retention_exhausted [R.id refinement])))
      (R.Library.refinements (Architecture_request.library request));
    let choices = List.sort (fun left right -> String.compare (R.id left) (R.id right)) !choices |> Array.of_list in
    let instances_by_id = List.fold_left (fun map value -> Names.add (A.Instance.id value) value map) Names.empty !match_instances in
    let total = Z.pred (Z.shift_left Z.one (Array.length choices)) in
    let winner = ref None in
    let examine selected =
      incr explored; Work.charge budget 1;
      let identifiers = List.map R.id selected in
      let gaps = ref (coverage_gaps selected behavior) in
      let eligible = ref None in
      if !gaps = [] then (
        try
          let instances = List.map (fun refinement -> Names.find (R.id refinement) instances_by_id) selected in
          let plan = Architecture_material.plan selected execution request instances in
          let construction = Architecture_material.construction_request selected request |> Construction_workflow.build ~parent:budget in
          let assessment = Construction_build.assessment construction in
          if not (Construction_assessment.passed assessment && Construction_assessment.complete assessment) then
            gaps := [gap ~candidates:identifiers ~message:(tuple_repr (Construction_assessment.diagnostics assessment)) B.Gap.Missing_sequence_authority "incomplete_construction"]
          else (
            let trial = B.make ~request_fingerprint:(Architecture_request.fingerprint request) ~execution ~plan:(Some plan) ~construction:(Some construction)
                ~alternatives:[] ~diagnostics ~status:B.Partial ~match_instances:(List.rev !match_instances) in
            let receipt = Check.check ~budget ~expected_request:request trial in
            if not (Architecture_assessment.passed receipt) then gaps := candidate_gaps receipt selected request
            else if Architecture_assessment.unresolved receipt <> [] && A.Constraints.require_complete constraints then
              gaps := [gap ~candidates:identifiers ~message:(String.concat "; " (Architecture_assessment.unresolved receipt)) B.Gap.Unsupported_semantics "unresolved_architecture_obligations"];
            if !gaps = [] then eligible := Some (plan, construction, receipt))
        with
        | Diagnostic.Error error when not (producer_resource budget error) ->
            gaps := !gaps @ [gap ~candidates:identifiers ~message:(construction_rejection_message error) B.Gap.Missing_sequence_authority "construction_authority_rejected"]);
      if not (retain (B.Alternative.make ~refinement_ids:identifiers ~gaps:!gaps)) then raise (Finished (retention_exhausted identifiers));
      match !eligible with
      | None -> ()
      | Some (plan, construction, receipt) ->
          let preference = A.Constraints.preferred_refinement_ids constraints in
          let rank identity = let rec find index = function [] -> List.length preference | value :: _ when value = identity -> index | _ :: rest -> find (index + 1) rest in find 0 preference in
          let rank_sum = List.fold_left (fun sum identity -> sum + rank (A.Instance.refinement_id (Names.find identity instances_by_id))) 0 identifiers in
          let delivered = Architecture_material.delivered construction in
          let score = rank_sum, List.length delivered, List.fold_left (fun count member -> count + String.length (Molecule.sequence member)) 0 delivered, identifiers in
          (match !winner with Some (previous, _, _, _) when Stdlib.compare score previous >= 0 -> ()
            | _ -> winner := Some (score, plan, construction, receipt)) in
    (* Lexicographic combinations use O(number of choices) storage and stop at
       the exact supplied subset limit; the complete count uses arbitrary ints. *)
    let width = Array.length choices in
    for size = 1 to width do
      if !explored < A.Constraints.max_combinations constraints then (
        let indices = Array.init size Fun.id and active = ref true in
        while !active && !explored < A.Constraints.max_combinations constraints do
          examine (Array.to_list indices |> List.map (Array.get choices));
          let position = ref (size - 1) in
          while !position >= 0 && indices.(!position) = !position + width - size do decr position done;
          if !position < 0 then active := false
          else (
            indices.(!position) <- indices.(!position) + 1;
            for index = !position + 1 to size - 1 do indices.(index) <- indices.(index - 1) + 1 done)
        done)
    done;
    if Z.compare total (Z.of_int (A.Constraints.max_combinations constraints)) > 0 then
      finish ~extra:[gap ~message:(Printf.sprintf "Examined %d of %s compatible-model subsets; no optimality or infeasibility claim." (A.Constraints.max_combinations constraints) (Z.to_string total)) B.Gap.Search_budget_exhausted "architecture_search_budget_exhausted"] B.Search_exhausted
    else match !winner with
    | None ->
        let implicated = !alternatives |> List.concat_map B.Alternative.gaps |> List.concat_map B.Gap.requirement_ids |> Ids.of_list |> Ids.elements in
        finish ~extra:[gap ~requirements:implicated ~candidates:(Array.to_list choices |> List.map R.id) ~conflict_set:implicated
          ~message:"No examined supplied architecture met all source, composition and construction requirements; the identified conflict set is not claimed minimal."
          B.Gap.Missing_implementation "no_supplied_architecture_satisfies_requirements"] B.No_solution
    | Some (_, plan, construction, receipt) ->
        finish ~plan:(Some plan) ~construction:(Some construction) (if diagnostics <> [] || Architecture_assessment.unresolved receipt <> [] then B.Partial else B.Compiled)
  with Finished candidate -> candidate

let compile ?budget request = fst (compile_checked ?budget request)

let export_checked ?budget ~expected_request build =
  let budget = create_budget budget in
  let receipt = Check.check ~budget ~expected_request build in
  Diagnostic.require (Architecture_assessment.passed receipt && Architecture_assessment.construction_complete receipt && B.construction build <> None)
    "architecture_export_rejected" "Architecture export requires fresh independent construction verification.";
  let delivered = Architecture_material.delivered (Option.get (B.construction build)) in
  Diagnostic.require (delivered <> []) "architecture_export_rejected" "No delivered RNA payloads in this architecture.";
  let output = Buffer.create 256 in
  List.iter (fun member ->
      Diagnostic.require (Molecule_coordinates.Space.alphabet (Molecule.space member) = Molecule_coordinates.Rna)
        "architecture_export_rejected" "Every delivered genetic member must be RNA.";
      Buffer.add_string output (">" ^ Molecule.id member ^ " alphabet=RNA\n");
      let sequence = Molecule.sequence member in
      let position = ref 0 in
      while !position < String.length sequence do
        let count = min 80 (String.length sequence - !position) in
        Buffer.add_substring output sequence !position count; Buffer.add_char output '\n'; position := !position + count
      done) delivered;
  let manifest = Json.Object ["request_fingerprint", str (Architecture_request.fingerprint expected_request);
      "build", B.to_json build; "verification", Architecture_assessment.to_json receipt;
      "delivered_member_ids", strings (List.map Molecule.id delivered); "source_authority", str "Retain the independently supplied request separately."] in
  B.Export.make ~fasta:(Buffer.contents output) ~manifest, receipt

let export ?budget ~expected_request build = fst (export_checked ?budget ~expected_request build)
