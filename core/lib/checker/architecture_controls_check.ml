open Bioc_wire
open Bioc_domain
module A = Architecture_contract
module N = Runtime_number
module Names = Map.Make (String)
module Seen = Set.Make (String)
module Atoms = Set.Make (struct type t = string * string let compare = compare end)
let checker_version = "biocompiler.ocaml.architecture_controls.v0.1"
type budget = Work_budget.t
let max_work = 10_000_000
let make_budget ?parent ?(maximum=max_work) () =
  Diagnostic.require (maximum > 0 && maximum <= max_work) "architecture_control_limit" "Invalid native control work limit.";
  match parent with
  | None -> Work_budget.create ~profile:checker_version ~error_code:"architecture_control_limit" ~maximum ()
  | Some parent -> Work_budget.nested ~parent ~profile:checker_version ~error_code:"architecture_control_limit" ~maximum ()
let str s = Json.String s
let obj v = Json.Object v
let arr v = Json.Array v
let field k v = Json.field k (Json.object_fields v)
let optional k v = Option.value ~default:Json.Null (List.assoc_opt k (Json.object_fields v))
let text k v = Json.string (field k v)
let inputs v = Json.array (field "inputs" v) |> List.map Json.string
let attrs v = field "attributes" v
let kind v = text "kind" v
let id v = text "id" v
let role v = field "role" v
exception Unsupported of string
let fail reason = raise (Unsupported reason)
let require condition reason = if not condition then fail reason
let malformed () = fail "malformed_or_unsupported_control_source"
let at index v = match List.nth_opt (inputs v) index with Some v -> v | None -> malformed ()
let rec hashable spend value = spend (); match value with
  | Json.Object _ -> malformed ()
  | Json.Array values -> List.iter (hashable spend) values
  | _ -> ()
let numeric = function Json.Bool value -> Some (Json.int (if value then 1 else 0))
  | (Json.Int _ | Json.Float _) as value -> Some value | _ -> None
let rec python_equal spend a b =
  spend ();
  match numeric a,numeric b with
  | Some a,Some b -> Json.number_compare a b = 0
  | _ -> (match a,b with
      | Json.Array a,Json.Array b -> List.length a = List.length b && List.for_all2 (python_equal spend) a b
      | _ -> Json.equal a b)
let typed_equal spend a b =
  hashable spend a;hashable spend b;
  match a,b with
  | Json.Bool _,Json.Bool _ | Json.Int _,Json.Int _ | Json.Float _,Json.Float _
  | Json.String _,Json.String _ | Json.Array _,Json.Array _ | Json.Null,Json.Null -> python_equal spend a b
  | _ -> false
let unique equal values = List.fold_left (fun found value -> if List.exists (equal value) found then found else found @ [value]) [] values
let kind_of_string = function
  | "activation" -> A.Activation | "shutdown" -> A.Shutdown | "memory_reset" -> A.Memory_reset
  | "production_adjustment" -> A.Production_adjustment | "activity_control" -> A.Activity_control
  | "physical_separation" -> A.Physical_separation | "dependency_disjointness" -> A.Dependency_disjointness
  | _ -> Diagnostic.fail "invalid_control_input" "Unknown control theorem kind."
module Input = struct
  type bindings = Defaults | Frozen of Json.t
  type t = {source:Human_request.t; target:string; controllers:string list; kind:A.control_kind; bindings:bindings}
  let to_json v = obj ["source",Human_request.to_json v.source;"target",str v.target;
      "controlling_node_ids",arr (List.map str v.controllers);"kind",str (A.control_kind_name v.kind);
      "parameter_bindings",(match v.bindings with Defaults -> Json.Null | Frozen raw -> raw)]
  let of_json raw =
    Source_execution_manifest.reserve_json (Source_execution_manifest.create_resource_budget ()) raw;
    let fields = Json.object_fields raw in
    Json.exact_fields ["source";"target";"controlling_node_ids";"kind";"parameter_bindings"] fields;
    let get key = Json.field key fields in
    let controllers = Json.array (get "controlling_node_ids") in
    Diagnostic.require (List.length controllers <= 4096) "architecture_control_limit" "Controller inventory exceeds the native bound.";
    let bindings = match get "parameter_bindings" with Json.Null -> Defaults | raw -> ignore (Json.object_fields raw); Frozen raw in
    {source=Human_request.of_json (get "source");target=Json.string (get "target");controllers=List.map Json.string controllers;
     kind=kind_of_string (Json.string (get "kind"));bindings}
  let make ~source ~target ~controlling_node_ids ~kind ~bindings =
    let rec bound n = function [] -> () | _::rest -> Diagnostic.require (n < 4096) "architecture_control_limit" "Controller inventory exceeds the native bound."; bound (n+1) rest in
    bound 0 controlling_node_ids;
    of_json (to_json {source;target;controllers=controlling_node_ids;kind;bindings})
end
type outcome = Proved | Not_proved of string
type result = {outcome:outcome;targets:string list;witnesses:Json.t list;work:int}
type context = {nodes:Json.t list;by_id:Json.t Names.t; mutable work:int; work_budget:Work_budget.t; mutable witnesses:Json.t list; budget:Source_execution_manifest.resource_budget}
let charge c = Work_budget.charge c.work_budget 1; c.work <- c.work + 1; Diagnostic.require (c.work <= max_work) "architecture_control_limit" "Control theorem work bound exhausted."
let context ?budget source =
  let nodes = Human_request.build_request source |> Build_request.intent |> Intent.to_json |> field "nodes" |> Json.array in
  Diagnostic.require (List.length nodes <= 4096) "architecture_control_limit" "Control theorem source-node bound exhausted.";
  {nodes;by_id=List.fold_left (fun m node -> Names.add (id node) node m) Names.empty nodes;work=0;work_budget=make_budget ?parent:budget ();witnesses=[];
   budget=Source_execution_manifest.create_resource_budget ()}
let lookup c name = charge c; match Names.find_opt name c.by_id with Some node -> node | None -> malformed ()
let witness c raw = Source_execution_manifest.reserve_json c.budget raw; c.witnesses <- raw :: c.witnesses
let atom node = at 0 node,Canonical.fingerprint (attrs node)
let primitive c ref =
  let rec loop seen ref = let node = lookup c ref in if kind node <> "action.pulse" then node else (
      require (not (Seen.mem ref seen)) "cyclic_action_wrapper"; loop (Seen.add ref seen) (at 0 node)) in
  loop Seen.empty ref
let uses c predicate = List.concat_map (fun rule -> charge c; if kind rule <> "rule" then [] else
    let actions = match inputs rule with _::_::actions -> actions | _ -> malformed () in
    List.filter_map (fun ref -> let installed = lookup c ref and action = primitive c ref in
        if predicate action then Some (rule,installed,action) else None) actions) c.nodes
let target_store c target =
  let node = lookup c target in
  let node = if List.mem (kind node) ["memory.is_set";"state.is"] then lookup c (at 0 node) else node in
  require (List.mem (kind node) ["memory";"state"]) "target_not_memory_or_state"; node
let target_actions c target =
  let node = lookup c target in
  let refs = if kind node = "rule" then (match inputs node with _::_::rest -> rest | _ -> []) else [target] in
  require (refs <> [] && List.for_all (fun ref -> String.starts_with ~prefix:"action." (kind (lookup c ref))) refs)
    "target_not_installed_ongoing_action"; refs
let production_uses c target =
  let target_node = lookup c target in
  let declarations = if kind target_node = "secretion" then [target_node] else
    List.map (fun ref -> let action = lookup c ref in require (kind action = "action.secrete") "target_not_production_action";
        lookup c (at 0 action)) (target_actions c target) in
  let products = List.filter (fun node -> kind node = "secretion") declarations
      |> List.map (fun node -> role node,field "product" (attrs node)) |> unique (fun (a,b) (x,y) -> Json.equal a x && Json.equal b y) in
  require (List.length products = 1 && List.for_all (fun node -> kind node = "secretion") declarations) "ambiguous_production_product";
  let product_role,product = List.hd products in
  let declarations = List.filter (fun node -> charge c; kind node = "secretion" && Json.equal (role node) product_role && Json.equal (field "product" (attrs node)) product) c.nodes
      |> List.map id in
  let found = uses c (fun action -> kind action = "action.secrete" && Json.equal (role action) product_role && List.mem (at 0 action) declarations) in
  require (found <> []) "target_not_installed_ongoing_action";
  if kind target_node <> "secretion" then require (List.for_all (fun ref -> List.exists (fun (_,_,action) -> id action = ref) found) (target_actions c target)) "target_not_installed_ongoing_action";
  product_role,found
let resolve c target = function
  | A.Production_adjustment -> let _,found = production_uses c target in List.map (fun (_,_,a) -> id a) found |> unique String.equal
  | A.Memory_reset -> [id (target_store c target)]
  | A.Activity_control -> target_actions c target |> unique String.equal
  | _ -> if Names.mem target c.by_id then [target] else []
type space = {ctx:context;role:Json.t;controller:string;mutable atoms:Atoms.t;mutable control_atoms:Atoms.t}
let add space ?(controller=false) ?state ?(contacts=false) identity =
  let rec loop seen = function
    | [] -> ()
    | ref::rest when Seen.mem ref seen -> loop seen rest
    | ref::rest ->
        let node = lookup space.ctx ref in
        let dtype = field "data_type" node in
        require (dtype <> Json.Null && optional "kind" dtype = str "condition") (if controller then "non_boolean_control" else "non_boolean_guard");
        require (role node = Json.Null || Json.equal (role node) space.role) "cross_role_control_expression";
        let next = match kind node with
          | "qualitative" ->
              let signal = lookup space.ctx (at 0 node) in
              require (kind signal = "signal" && Json.equal (role signal) space.role) "unsupported_observation_atom";
              let contact = optional "scope" (attrs signal) = str "contact" || optional "scope" (attrs (lookup space.ctx (at 0 signal))) = str "contact" in
              require (not contact || contacts) (if controller then "non_cell_local_control" else "non_cell_local_guard");
              require (List.mem (optional "band" (attrs node)) [str "present";str "high";str "low"]) "unsupported_observation_band";
              space.atoms <- Atoms.add (atom node) space.atoms; rest
          | "signature" -> at 0 node :: rest
          | "not" | "and" | "or" -> List.rev_append (inputs node) rest
          | "state.is" when not controller && Option.is_some state ->
              let store = Option.get state in require (inputs node = [store]) "other_store_guard";
              let options = Json.array (field "values" (attrs (lookup space.ctx store))) in
              List.iter (hashable (fun () -> charge space.ctx)) options;
              hashable (fun () -> charge space.ctx) (field "value" (attrs node));
              require (List.exists (typed_equal (fun () -> charge space.ctx) (field "value" (attrs node))) options) "undeclared_state_predicate"; rest
          | _ -> fail (if controller then "unsupported_control_expression" else "unsupported_guard_expression") in
        loop (Seen.add ref seen) next in
  loop Seen.empty [identity]; require (Atoms.cardinal space.atoms <= 8) "boolean_control_proof_bound"
let controller c refs =
  require (List.length refs = 1) "requires_one_boolean_condition";
  let ref = List.hd refs in
  if kind (lookup c ref) <> "signal" then ref else (
    let predicates = List.filter (fun node -> charge c; kind node = "qualitative" && inputs node = [ref]) c.nodes in
    require (List.length predicates = 1) "ambiguous_signal_predicate"; id (List.hd predicates))
let space c refs role =
  let s = {ctx=c;role;controller=controller c refs;atoms=Atoms.empty;control_atoms=Atoms.empty} in
  add s ~controller:true s.controller; s.control_atoms <- s.atoms;
  require (not (Atoms.is_empty s.atoms)) "vacuous_control_condition"; s
let rows atoms =
  let atoms = Atoms.elements atoms in
  List.init (1 lsl List.length atoms) (fun index -> List.mapi (fun position atom -> atom,(index land (1 lsl (List.length atoms-position-1))) <> 0) atoms)
let row_json row = arr (List.map (fun ((signal,band),value) -> obj ["signal",str signal;"attributes_fingerprint",str band;"value",Json.Bool value]) row)
let value s row ?(state=Json.Null) ref =
  let cache = Hashtbl.create 32 in
  let rec run depth ref =
    charge s.ctx; Diagnostic.require (depth <= 512) "architecture_control_limit" "Native Boolean depth bound exhausted.";
    match Hashtbl.find_opt cache ref with Some value -> value | None ->
      let node = lookup s.ctx ref in
      let result = match kind node with
        | "qualitative" -> List.assoc (atom node) row
        | "state.is" -> typed_equal (fun () -> charge s.ctx) state (field "value" (attrs node))
        | "signature" -> run (depth+1) (at 0 node)
        | "not" -> not (run (depth+1) (at 0 node))
        | ("and" | "or") as k -> let values = List.map (run (depth+1)) (inputs node) in if k = "and" then List.for_all Fun.id values else List.exists Fun.id values
        | _ -> malformed () in
      Hashtbl.add cache ref result; result in
  run 0 ref
let all_rows s =
  let rows = rows s.atoms in
  let observed = List.map (fun row -> value s row s.controller) rows in
  require (List.mem false observed && List.mem true observed) "vacuous_control_condition"; rows
let dtype node = Type_spec.of_json (field "data_type" node)
let scalar name dimensions = Type_spec.of_json (obj ["kind",str "scalar";"name",str name;"dimensions",obj (List.map (fun (k,n) -> k,Json.int n) dimensions);"arguments",arr []])
let duration = scalar "Duration" ["time",1]
let rate_type = scalar "ProductionRate" ["amount",1;"time",-1]
let combined left right divide =
  if Type_spec.kind left <> Type_spec.Scalar || Type_spec.kind right <> Type_spec.Scalar then malformed ();
  let dimensions t = Json.object_fields (field "dimensions" (Type_spec.to_json t)) |> List.map (fun (k,v) -> k,Json.integer v) in
  let map = List.fold_left (fun m (k,v) -> Names.add k v m) Names.empty (dimensions left) in
  let map = List.fold_left (fun m (k,v) -> let v = if divide then Z.neg v else v in
      Names.add k (Z.add v (Option.value ~default:Z.zero (Names.find_opt k m))) m) map (dimensions right) in
  Type_spec.of_json (obj ["kind",str "scalar";"name",str "Derived";"dimensions",obj (Names.bindings map |> List.map (fun (k,v)->k,Json.Int v));"arguments",arr []])
let constant c bindings ref =
  let cache = Hashtbl.create 16 in
  let rec run depth ref =
    charge c; Diagnostic.require (depth <= 512) "architecture_control_limit" "Native constant depth bound exhausted.";
    match Hashtbl.find_opt cache ref with Some v -> v | None ->
      let node = lookup c ref in let typ = dtype node in require (Type_spec.kind typ = Type_spec.Scalar) "non_scalar_constant";
      let result = match kind node with
        | ("literal" | "parameter") as k ->
            let raw = if k = "literal" then field "value" (attrs node) else match bindings with
              | Input.Defaults -> let raw = optional "default" (attrs node) in require (raw <> Json.Null) "unbound_parameter"; raw
              | Input.Frozen raw -> (match List.assoc_opt (text "name" (attrs node)) (Json.object_fields raw) with Some raw -> raw | None -> fail "unbound_parameter") in
            Type_spec.normalize_binding ~expected:typ raw |> field "canonical_value" |> N.of_json
        | "negate" -> let child = lookup c (at 0 node) in require (Type_spec.compatible typ (dtype child)) "constant_type_mismatch"; N.neg (run (depth+1) (id child))
        | ("add" | "subtract" | "multiply" | "divide") as k ->
            require (List.length (inputs node) = 2) "malformed_or_unsupported_control_source";
            let a = at 0 node and b = at 1 node in
            let left = dtype (lookup c a) and right = dtype (lookup c b) in
            let expected = if k = "add" || k = "subtract" then (require (Type_spec.compatible left right) "constant_type_mismatch";left) else combined left right (k = "divide") in
            require (Type_spec.compatible typ expected) "constant_type_mismatch";
            let a = run (depth+1) a in let b = run (depth+1) b in
            require (k <> "divide" || not (N.equal b N.zero)) "undefined_constant";
            (try (match k with "add" -> N.add a b | "subtract" -> N.sub a b | "multiply" -> N.mul a b | _ -> N.div a b)
             with Diagnostic.Error error when error.code = "evaluation_overflow" ->
               match a,b with N.Integer _,N.Integer _ when k <> "divide" -> malformed () | _ -> fail "non_finite_constant")
        | _ -> fail "non_constant_rate_or_duration" in
      ignore (N.to_float result); Hashtbl.add cache ref result; result in
  run 0 ref
let ongoing rule installed action =
  require (kind installed <> "action.pulse" && optional "trigger" (attrs rule) = str "condition" && optional "ongoing" (attrs action) = Json.Bool true)
    "persistent_or_event_installation"
let state_reset c store refs =
  let a = attrs store in let options = Json.array (field "values" a) in
  require (List.length options <= 16) "state_reset_proof_bound";
  require (optional "observation" a = str "prior_state" && optional "arbitration" a = str "unspecified") "unsupported_state_policy";
  let initial = field "initial" a in
  let equal = typed_equal (fun () -> charge c) in
  List.iter (hashable (fun () -> charge c)) options;hashable (fun () -> charge c) initial;
  require (List.length (unique equal options) = List.length options && List.exists (equal initial) options) "invalid_state_domain";
  let writers = uses c (fun action -> kind action = "action.state_set" && inputs action = [id store]) in
  require (writers <> []) "state_reset_writer_missing";
  let s = space c refs (role store) in
  List.iter (fun (rule,installed,action) ->
      require (kind installed <> "action.pulse" && optional "trigger" (attrs rule) = str "condition") "persistent_or_event_state_writer";
      require (optional "idempotent" (attrs action) = Json.Bool true && optional "ongoing" (attrs action) = Json.Bool false
        && List.exists (equal (field "value" (attrs action))) options) "unsupported_state_assignment";
      add s ~state:(id store) (at 1 rule)) writers;
  let rows = Array.of_list (all_rows s) and options = Array.of_list options in
  let option_index value = let found = ref None in Array.iteri (fun i v -> if equal value v then found := Some i) options; Option.get !found in
  let transitions = Array.init (Array.length rows) (fun index -> Array.init (Array.length options) (fun before ->
      let row = rows.(index) in
      let written = List.filter_map (fun (rule,_,action) -> if value s row ~state:options.(before) (at 1 rule) then Some (field "value" (attrs action)) else None) writers |> unique equal in
      require (List.length written <= 1) "conflicting_state_writers";
      let after = match written with [] -> before | first::_ -> option_index first in
      witness c (obj ["kind",str "state_transition";"observations",row_json row;"before",options.(before);"after",options.(after)]);
      require (not (value s row s.controller) || equal options.(after) initial) "assertion_does_not_reset_state";after)) in
  let stable = Array.make_matrix (Array.length rows) (Array.length options) 0 in
  Array.iteri (fun row_index row -> if not (value s row s.controller) then Array.iteri (fun before _ ->
      let rec settle seen current = charge c; require (not (List.mem current seen)) "nonsettling_state_writers";
        let after = transitions.(row_index).(current) in if after = current then current else settle (current::seen) after in
      stable.(row_index).(before) <- settle [] before) options) rows;
  let rec reachable seen = function [] -> seen | before::rest ->
    let next = ref rest and seen = ref seen in
    Array.iteri (fun row_index row -> if not (value s row s.controller) then let after = stable.(row_index).(before) in
        if not (List.mem after !seen) then (seen := after::!seen;next := after::!next)) rows;
    reachable !seen !next in
  require (List.length (reachable [option_index initial] [option_index initial]) >= 2) "state_never_changes_without_control"
let memory_reset c target refs bindings =
  let store = target_store c target in if kind store = "state" then state_reset c store refs else (
    let a = attrs store in
    require (optional "initial" a = Json.Bool false && optional "setting" a = str "onset" && optional "initial_true_is_onset" a = Json.Bool true && optional "reset_priority" a = Json.Bool true) "unsupported_memory_policy";
    let names = Json.array (field "input_names" a) |> List.map Json.string in
    let rec zip a b = match a,b with x::xs,y::ys -> (x,y)::zip xs ys | _ -> [] in
    let fields = List.rev (zip names (inputs store)) in
    require (List.mem_assoc "reset_when" fields) "memory_reset_missing";
    let expiry = if List.mem_assoc "duration" fields then "latest_setting_onset" else "until_reset" in
    require (optional "expiry" a = str expiry) "unsupported_memory_policy";
    (match List.assoc_opt "duration" fields with None -> () | Some ref ->
      require (Type_spec.compatible (dtype (lookup c ref)) duration && N.compare (constant c bindings ref) N.zero > 0) "unsupported_memory_duration");
    let s = space c refs (role store) in
    let setting = List.assoc "set_when" fields and reset = List.assoc "reset_when" fields in
    add s setting;add s reset;
    let can_set = ref false in
    List.iter (fun row -> let asserted = value s row s.controller in let resetting = value s row reset in
        if asserted && not resetting then (
          witness c (obj ["kind",str "memory";"observations",row_json row;"asserted",Json.Bool asserted;"reset",Json.Bool resetting;"set",Json.Null]);
          fail "assertion_does_not_reset");
        let setting = if not asserted && not resetting then Some (value s row setting) else None in
        witness c (obj ["kind",str "memory";"observations",row_json row;"asserted",Json.Bool asserted;"reset",Json.Bool resetting;
          "set",(match setting with None -> Json.Null | Some value -> Json.Bool value)]);
        can_set := !can_set || setting = Some true) (all_rows s);
    require !can_set "memory_never_set_without_control")
let production c target refs bindings =
  let role,uses = production_uses c target in let s = space c refs role in
  let branches = List.map (fun (rule,installed,action) -> ongoing rule installed action;add s (at 1 rule);
      require (optional "rate" (attrs action) = str "expression" && List.length (inputs action) = 2) "unspecified_production_rate";
      require (Type_spec.compatible (dtype (lookup c (at 1 action))) rate_type) "production_rate_type_mismatch";
      let rate = constant c bindings (at 1 action) in require (N.compare rate N.zero >= 0) "negative_production_rate"; at 1 rule,rate) uses in
  let others = Atoms.diff s.atoms s.control_atoms |> Atoms.elements in
  let groups = Hashtbl.create 16 and order = ref [] in
  List.iter (fun row ->
      let rates = List.filter_map (fun (guard,rate) -> if value s row guard then Some rate else None) branches in
      require (List.length rates <= 1) "overlapping_production_requests";
      let rate = match rates with [] -> N.zero | first::_ -> first in
      let key = List.map (fun atom -> List.assoc atom row) others in
      if not (Hashtbl.mem groups key) then (Hashtbl.add groups key ([],[]);order := key::!order);
      let off,on = Hashtbl.find groups key and asserted = value s row s.controller in
      let append values = if List.exists (N.equal rate) values then values else values @ [rate] in
      Hashtbl.replace groups key (if asserted then off,append on else append off,on);
      witness c (obj ["kind",str "production";"observations",row_json row;"asserted",Json.Bool asserted;"requested_rate",N.to_json rate])) (all_rows s);
  let directions = List.filter_map (fun key -> let off,on = Hashtbl.find groups key in
      require (List.length off = 1 && List.length on = 1) "ambiguous_production_control_state";
      let order = N.compare (List.hd on) (List.hd off) in if order = 0 then None else Some (if order > 0 then 1 else -1)) (List.rev !order) |> unique Int.equal in
  require (directions <> []) "production_rate_unchanged";
  require (List.length directions = 1) "nonmonotone_production_adjustment"
let activity c target refs =
  let actions = target_actions c target in
  require (List.for_all (fun ref -> List.mem (kind (lookup c ref)) ["action.eliminate";"action.engulf";"action.rest"]) actions) "target_not_explicit_activity_action";
  let roles = List.map (fun ref -> role (lookup c ref)) actions |> unique Json.equal in require (List.length roles = 1) "ambiguous_activity_role";
  let s = space c refs (List.hd roles) in
  let guards = List.map (fun action -> let uses = uses c (fun node -> id node = action) in
      require (uses <> []) "target_not_installed_ongoing_action";
      action,List.map (fun (rule,installed,primitive) -> ongoing rule installed primitive;add s ~contacts:true (at 1 rule);at 1 rule) uses) actions in
  let witnessed = ref Seen.empty in
  List.iter (fun row -> let asserted = value s row s.controller in
      List.iter (fun (action,guards) -> let enabled = List.exists (fun ref -> value s row ref) guards in
          witness c (obj ["kind",str "activity";"action",str action;"observations",row_json row;"asserted",Json.Bool asserted;"enabled",Json.Bool enabled]);
          require (not enabled || asserted) "deassertion_does_not_gate_activity";
          if enabled then witnessed := Seen.add action !witnessed) guards) (all_rows s);
  require (Seen.equal !witnessed (Seen.of_list actions)) "activity_never_enabled"
let simple c target refs theorem_kind =
  let controller = controller c refs and atoms = ref Atoms.empty in
  let rec visit seen = function [] -> () | ref::rest when Seen.mem ref seen -> visit seen rest | ref::rest ->
    let node = lookup c ref in let dt = field "data_type" node in
    require (dt <> Json.Null && optional "kind" dt = str "condition") "non_boolean_control";
    let next = match kind node with
      | "qualitative" -> let signal = lookup c (at 0 node) in
          require (kind signal = "signal" && optional "scope" (attrs signal) <> str "contact" && optional "scope" (attrs (lookup c (at 0 signal))) <> str "contact") "non_cell_local_control";
          atoms := Atoms.add (atom node) !atoms;rest
      | "signature" -> at 0 node::rest
      | "not" | "and" | "or" -> List.rev_append (inputs node) rest
      | _ -> fail "unsupported_control_expression" in visit (Seen.add ref seen) next in
  visit Seen.empty [controller];require (not (Atoms.is_empty !atoms) && Atoms.cardinal !atoms <= 8) "boolean_control_proof_bound";
  let guards = List.concat_map (fun action_id -> let action = lookup c action_id in
      require (not (List.mem (kind action) ["action.pulse";"action.state_set"]) && optional "ongoing" (attrs action) = Json.Bool true) "persistent_or_nonongoing_action";
      let found = uses c (fun primitive -> id primitive = action_id) in
      require (found <> []) "target_not_installed_ongoing_action";
      List.map (fun (rule,installed,_) -> require (kind installed <> "action.pulse" && optional "trigger" (attrs rule) = str "condition") "persistent_or_event_installation"; at 1 rule) found) (target_actions c target) in
  let observed = ref [] in
  List.iter (fun row ->
      let cache = Hashtbl.create 32 in
      let rec cofactor depth ref = charge c; Diagnostic.require (depth <= 512) "architecture_control_limit" "Native cofactor depth bound exhausted.";
        match Hashtbl.find_opt cache ref with Some value -> value | None ->
          let node = lookup c ref in
          let value = match kind node with
            | "qualitative" -> List.assoc_opt (atom node) row
            | ("not" | "signature") as k -> Option.map (fun value -> if k = "not" then not value else value) (cofactor (depth+1) (at 0 node))
            | ("and" | "or") as k -> let children = List.map (cofactor (depth+1)) (inputs node) in
                if k = "and" then (if List.mem (Some false) children then Some false else if List.for_all ((=) (Some true)) children then Some true else None)
                else if List.mem (Some true) children then Some true else if List.for_all ((=) (Some false)) children then Some false else None
            | _ -> None in Hashtbl.add cache ref value;value in
      let asserted = cofactor 0 controller in observed := asserted::!observed;
      let nullable = function None -> Json.Null | Some v -> Json.Bool v in
      let shutdown = theorem_kind = A.Shutdown in
      let record values = witness c (obj ["kind",str "gate";"observations",row_json row;"asserted",nullable asserted;
          "guards_checked",Json.Bool (asserted = Some shutdown);"guards",arr (List.map nullable values)]) in
      if asserted <> Some shutdown then record [] else (
        let rec check_guards checked = function
          | [] -> record (List.rev checked)
          | guard::rest -> let value = cofactor 0 guard in
              if value <> Some false then (record (List.rev (value::checked));fail (if shutdown then "assertion_does_not_veto" else "deassertion_does_not_gate"));
              check_guards (value::checked) rest in
        check_guards [] guards)) (rows !atoms);
  require (List.mem (Some false) !observed && List.mem (Some true) !observed && not (List.mem None !observed)) "vacuous_control_condition"
let guarded budget operation = try operation () with
  | Unsupported _ as error -> raise error
  | Diagnostic.Error error when Work_budget.is_exhaustion budget error || String.ends_with ~suffix:"_limit" error.code -> raise (Diagnostic.Error error)
  | Diagnostic.Error _ | Not_found | Invalid_argument _ | Failure _ -> malformed ()
let extended_targets ?budget ~source ~target ~kind () = let c = context ?budget source in try guarded c.work_budget (fun () -> resolve c target kind) with Unsupported _ -> []
let prove ?budget (input:Input.t) =
  let c = context ?budget input.source in
  let targets = try guarded c.work_budget (fun () -> resolve c input.target input.kind) with Unsupported _ -> [] in
  let outcome = try guarded c.work_budget (fun () -> match input.kind with
      | A.Memory_reset -> memory_reset c input.target input.controllers input.bindings
      | A.Production_adjustment -> production c input.target input.controllers input.bindings
      | A.Activity_control -> activity c input.target input.controllers
      | A.Activation | A.Shutdown -> simple c input.target input.controllers input.kind
      | _ -> fail "kind_not_implemented"); Proved
    with Unsupported reason -> Not_proved reason in
  {outcome;targets;witnesses=List.rev c.witnesses;work=c.work}
let reason result = match result.outcome with Proved -> None | Not_proved reason -> Some reason
let prove_source ?budget ~source ~target ~controlling_node_ids ~kind () =
  let bindings = Human_request.build_request source |> Build_request.resolved_bindings in
  prove ?budget (Input.make ~source ~target ~controlling_node_ids ~kind ~bindings:(Input.Frozen (obj bindings)))
