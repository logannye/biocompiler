open Bioc_wire
open Bioc_domain
module R = Circuit_request.Requirement
module B = Payload_circuit_binding
module Names = Set.Make (String)
let resource_profile = "biocompiler.circuit_binding_check.resources.v1"
let default_max_work = 10_000_000
type budget = Work_budget.t
let make_budget ?parent ?(max_work = default_max_work) () =
  Diagnostic.require (max_work >= 0 && max_work <= default_max_work) "circuit_binding_resource_limit" "Invalid supplementary checker work allowance.";
  match parent with
  | None -> Work_budget.create ~profile:resource_profile ~error_code:"circuit_binding_resource_limit" ~maximum:max_work ()
  | Some parent -> Work_budget.nested ~parent ~profile:resource_profile ~error_code:"circuit_binding_resource_limit" ~maximum:max_work ()
let spend = Work_budget.charge
let invalid condition message = Diagnostic.require condition "invalid_circuit_binding_check" message
let get key raw = Json.field key (Json.object_fields raw)
type node = {id:string;kind:string;inputs:string list;attributes:(string * Json.t) list;role:string option}
let node raw = {id=Json.string (get "id" raw);kind=Json.string (get "kind" raw);
  inputs=List.map Json.string (Json.array (get "inputs" raw));attributes=Json.object_fields (get "attributes" raw);
  role=(match get "role" raw with Json.Null -> None | value -> Some (Json.string value))}
let attribute node key = Option.value ~default:Json.Null (List.assoc_opt key node.attributes)
let input node index = match List.nth_opt node.inputs index with Some value -> value
  | None -> Diagnostic.fail "invalid_circuit_binding_check" "Source operation lacks a required input."
let lookup nodes id = match Hashtbl.find_opt nodes id with Some value -> value
  | None -> Diagnostic.fail "invalid_circuit_binding_check" "Source operation refers to a missing node."
exception Input_binding
exception Temporal_projection
type task = Visit of string | Finish of node
let check ?budget ~source ~requirements ~bindings () =
  let budget = match budget with Some value -> value | None -> make_budget () in
  ignore (Molecular_record.bounded_length ~maximum:32 requirements);
  ignore (Molecular_record.bounded_length ~maximum:32 bindings);
  let unique ids = List.length ids = Names.cardinal (Names.of_list ids) in
  invalid (unique (List.map R.id requirements)) "Duplicate expected supplementary requirements.";
  invalid (unique (List.map B.requirement_id bindings)) "Duplicate supplied supplementary bindings.";
  let expected = Hashtbl.create 32 in
  List.iter (fun requirement ->
      invalid (Option.is_some (R.boolean_response requirement)) "Executable Behavior needs the full architecture supplementary checker.";
      Hashtbl.add expected (R.id requirement) requirement) requirements;
  List.iter (fun binding -> invalid (Hashtbl.mem expected (B.requirement_id binding)) "Supplied binding refers to an unknown requirement.") bindings;
  let raw_nodes = Human_request.build_request source |> Build_request.intent |> Intent.to_json |> get "nodes" |> Json.array in
  spend budget (List.length raw_nodes);
  let nodes = Hashtbl.create (List.length raw_nodes) in
  List.iter (fun raw -> let value = node raw in Hashtbl.add nodes value.id value) raw_nodes;
  let problems = ref [] in
  let output = Work_budget.create_output ~profile:resource_profile ~error_code:"circuit_binding_output_limit"
      ~max_bytes:Molecular_record.max_json_bytes ~max_nodes:Molecular_record.max_items () in
  let problem value =
    spend budget (String.length value + 1);
    (* A singleton array conservatively reserves each item's share of the
       returned list's brackets, separators and root node before retention. *)
    Work_budget.reserve_json output (Json.Array [Json.String value]);
    problems := value :: !problems in
  List.iter (fun requirement -> List.iter (fun provider ->
      problem ("unsupported:circuit_provider_mapping:" ^ R.id requirement ^ ":" ^ Circuit_request.Provider.id provider))
      (R.dependencies requirement)) requirements;
  let bound = Names.of_list (List.map B.requirement_id bindings) in
  Names.diff (Names.of_list (List.map R.id requirements)) bound |> Names.iter (fun id -> problem ("unsupported:circuit_binding_missing:" ^ id));
  List.iter (fun binding ->
      spend budget 1;
      let identity = B.requirement_id binding and rule_id = B.rule_id binding and action_id = B.action_id binding in
      let item = Hashtbl.find expected identity in
      let installed rule = match rule.inputs with _ :: _ :: actions -> List.mem action_id actions | _ -> false in
      match Hashtbl.find_opt nodes rule_id with
      | None -> problem ("fail:circuit_source_action:" ^ identity)
      | Some rule when rule.kind <> "rule" || not (installed rule) -> problem ("fail:circuit_source_action:" ^ identity)
      | Some rule ->
          let lineage = R.source_nodes item |> List.map Identity.Node.to_string |> Names.of_list in
          if Option.map Identity.Role.to_string (R.role item) <> rule.role || not (Names.mem rule_id lineage && Names.mem action_id lineage) then
            problem ("fail:circuit_source_role_or_lineage:" ^ identity);
          let authored = R.input_bindings item |> List.map (fun (key,value) -> key,Identity.Node.to_string value)
            |> List.sort compare in
          if authored <> [] && authored <> B.signals binding then problem ("fail:circuit_original_input_binding:" ^ identity);
          let action = lookup nodes action_id in
          let primitive = if action.kind = "action.pulse" then lookup nodes (input action 0) else action in
          if primitive.kind = "action.secrete" then (
            let product = attribute (lookup nodes (input primitive 0)) "product" in
            if product <> Json.Null && not (Json.equal product (Json.String (Circuit_request.Product.id (R.product item)))) then
              problem ("fail:circuit_source_product:" ^ identity));
          let lifecycle = R.lifecycle item in
          if List.exists Option.is_some [Circuit_request.Lifecycle.onset lifecycle;Circuit_request.Lifecycle.cessation lifecycle;
                                        Circuit_request.Lifecycle.clearance lifecycle] then
            problem ("unsupported:circuit_lifecycle:" ^ identity);
          let signals,outputs = match R.boolean_response item with Some value -> value | None -> assert false in
          let pairs = B.signals binding in
          if not (Names.equal (Names.of_list (List.map fst pairs)) (Names.of_list signals)) || Names.cardinal (Names.of_list (List.map snd pairs)) <> List.length signals then
            problem ("fail:circuit_input_inventory:" ^ identity)
          else (
            let inverse = Hashtbl.create 8 in List.iter (fun (key,value) -> Hashtbl.add inverse value key) pairs;
            let bands = Hashtbl.create 8 and seen = Hashtbl.create 32 and pending = ref [input rule 1] in
            while !pending <> [] do
              spend budget 1;
              let ref_id = List.hd !pending in pending := List.tl !pending;
              if not (Hashtbl.mem seen ref_id) then (
                Hashtbl.add seen ref_id ();
                let value = lookup nodes ref_id in
                if value.kind = "qualitative" then (
                  let signal = input value 0 and band = match List.assoc_opt "band" value.attributes with
                    | Some band -> band
                    | None -> Diagnostic.fail "invalid_circuit_binding_check" "Source qualitative predicate lacks its declared band." in
                  let old = Option.value ~default:[] (Hashtbl.find_opt bands signal) in
                  if not (List.exists (Json.equal band) old) then Hashtbl.replace bands signal (band :: old));
                let children = match value.role with None -> value.inputs | Some role -> role :: value.inputs in
                spend budget (List.length children);
                pending := List.rev_append children !pending)
            done;
            let used = ref Names.empty in
            let evaluate row =
              let cache = Hashtbl.create 32 and active = Hashtbl.create 32 and tasks = ref [Visit (input rule 1)] in
              let value id = match Hashtbl.find_opt cache id with Some value -> value | None -> raise Input_binding in
              let bool_signal id =
                let index = List.find_index ((=) id) signals in
                match index with None -> raise Input_binding
                | Some index -> row land (1 lsl (List.length signals - index - 1)) <> 0 in
              while !tasks <> [] do
                spend budget 1;
                let task = List.hd !tasks in tasks := List.tl !tasks;
                match task with
                | Visit id when Hashtbl.mem cache id -> ()
                | Visit id ->
                    if Hashtbl.mem active id then raise Input_binding;
                    let current = lookup nodes id in
                    if current.kind = "qualitative" then (
                      let signal = input current 0 in
                      let bound = if Hashtbl.mem inverse id then id else signal in
                      let count = List.length (Option.value ~default:[] (Hashtbl.find_opt bands bound)) in
                      if not (Hashtbl.mem inverse bound && (bound = id || count = 1)) then raise Input_binding;
                      used := Names.add bound !used;
                      Hashtbl.add cache id (bool_signal (Hashtbl.find inverse bound))
                    ) else if List.mem current.kind ["signature";"not";"and";"or"] then (
                      Hashtbl.add active id ();
                      let children = if List.mem current.kind ["signature";"not"] then [input current 0] else current.inputs in
                      spend budget (List.length children);
                      tasks := List.rev_append (List.rev_map (fun id -> Visit id) children) (Finish current :: !tasks)
                    ) else raise Temporal_projection
                | Finish current ->
                    let result = match current.kind with
                      | "signature" -> value (input current 0)
                      | "not" -> not (value (input current 0))
                      | "and" -> List.for_all value current.inputs
                      | "or" -> List.exists value current.inputs
                      | _ -> assert false in
                    Hashtbl.remove active current.id; Hashtbl.add cache current.id result
              done;
              value (input rule 1) in
            try
              let trigger = match List.assoc_opt "trigger" rule.attributes with Some value -> value | None -> raise Input_binding in
              if trigger <> Json.String "condition" then raise Temporal_projection;
              let values = List.init (1 lsl List.length signals) evaluate in
              if not (Names.equal !used (Names.of_list (List.map snd pairs))) then raise Input_binding;
              if values <> outputs then problem ("fail:circuit_guard_contradiction:" ^ identity)
            with
            | Temporal_projection -> problem ("unsupported:circuit_temporal_or_input_refinement:" ^ identity)
            | Input_binding -> problem ("fail:circuit_source_input_binding:" ^ identity)
          )) bindings;
  List.rev !problems
