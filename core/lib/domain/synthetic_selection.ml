open Bioc_wire
module A = Synthetic_authority
module C = A.Candidate
module E = Realization_evidence
module N = Runtime_number
let resource_profile = "biocompiler.synthetic_selection.resources.v1"
let selection_version = "biocompiler.synthetic.selection.v0.1"
let cost_version = "biocompiler.synthetic.gate_count.v0.1"
let strategies = ["native"; "de_morgan"]
let str value = Json.String value
let option_json encode = function None -> Json.Null | Some value -> encode value
let require ?path condition message = Diagnostic.require ?path condition "synthetic_selection" message
let limit ?path condition = Diagnostic.require ?path condition "synthetic_selection_limit"
    "Synthetic selection exceeds its native resource boundary."
(* Preflight uses the bounded, cycle-safe ASCII wire envelope (32 MiB /
   250,000 value nodes, excluding object keys). Identities remain compact UTF-8.
   Checker publication separately counts keys as well as values. *)
let measure ?path raw =
  try Legacy_ascii.measure ?path raw with
  | Diagnostic.Error error when error.code = "legacy_ascii_limit" ->
      Diagnostic.fail ?path "synthetic_selection_limit" error.message
  | Diagnostic.Error error when error.code = "legacy_ascii_cycle" ->
      Diagnostic.fail ?path "synthetic_selection_cycle" error.message
type budget = { mutable bytes:int; mutable nodes:int }
let budget () = {bytes=0;nodes=0}
let reserve budget raw =
  let size = measure raw in
  limit (size.bytes <= Limits.max_response_bytes - budget.bytes &&
    size.nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + size.bytes; budget.nodes <- budget.nodes + size.nodes
let bounded values =
  let rec loop count = function [] -> () | _ :: rest ->
    limit (count < Limits.max_json_nodes); loop (count+1) rest in
  loop 0 values; values
let reserve_list budget encode values =
  let rec loop first = function [] -> () | value :: rest ->
    if not first then (limit (budget.bytes < Limits.max_response_bytes); budget.bytes <- budget.bytes+1);
    reserve budget (encode value); loop false rest in
  loop true values
let finish json =
  ignore (measure json);
  let canonical = Canonical.encode json in json,Canonical.sha256 canonical,String.length canonical
let record ~path keys label raw =
  ignore (measure ~path raw);
  match raw with
  | Json.Object fields ->
      require ~path (List.sort String.compare (List.map fst fields) = List.sort String.compare keys)
        ("Invalid fields in " ^ label ^ "."); fields
  | _ -> Diagnostic.fail ~path "synthetic_selection" ("Invalid fields in " ^ label ^ ".")
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let optional decode = function Json.Null -> None | raw -> Some (decode raw)
let identity ~path label = function
  | Json.String value when String.length value=64 &&
      String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) value -> value
  | _ -> Diagnostic.fail ~path "synthetic_selection" (label ^ " must be a SHA-256 identity.")
let valid_horizon = function
  | None -> true
  | Some (N.Integer value) -> Z.sign value >= 0 && Float.is_finite (Z.to_float value)
  | Some (N.Real value) -> Float.is_finite value && value >= 0.
let horizon ~path raw =
  let value = match raw with Json.Null -> None | Json.Int value -> Some (N.Integer value)
    | Json.Float value -> Some (N.Real value)
    | _ -> Diagnostic.fail ~path "synthetic_selection" "Invalid selection horizon." in
  require ~path (valid_horizon value) "Invalid selection horizon."; value
let horizon_equal left right = match left,right with
  | None,None -> true | Some left,Some right -> N.equal left right | _ -> false
let raw_number = function N.Integer value -> Json.Int value | N.Real value -> Json.Float value
let names ~path raw =
  let values = match raw with Json.Array values -> values | _ ->
    Diagnostic.fail ~path "synthetic_selection" "Constraint violations must be an array." in
  let values = List.map (fun raw ->
    try Json.name ~path raw with Diagnostic.Error _ ->
      Diagnostic.fail ~path "synthetic_selection" "Constraint violations must be a nonempty string.") values in
  let seen = Hashtbl.create 16 in
  List.iter (fun value -> require ~path (not (Hashtbl.mem seen value)) "Constraint violations must be unique.";
    Hashtbl.add seen value ()) values; values
let gate_count candidate = List.fold_left (fun count node ->
  if List.mem (Mechanism.Node.kind node) ["input";"constant";"output"] then count else count+1)
  0 (Mechanism.nodes (C.mechanism candidate))
let outcome = function E.Pass -> "pass" | E.Fail -> "fail" | E.Unknown -> "unknown" | E.Unsupported -> "unsupported"
let dependency check key = Json.field key (Json.object_fields
  (E.Dependency_snapshot.to_json (E.Check_result.dependencies check)))
let setting check key = List.assoc_opt key (Json.object_fields (dependency check "settings"))

module Alternative = struct
  type t = {json:Json.t;fingerprint:string;size:int;strategy:string;candidate:C.t option;
    constraint_violations:string list;check:E.Check_result.t option;generation_error:string option;
    gate_count:int option;status:string}
  let schema_version = "biocompiler.synthetic_alternative.v0.1"
  let build ~path ~strategy ~candidate ~constraint_violations ~check ~generation_error =
    require ~path (List.mem strategy (List.map str strategies)) "Unknown bounded strategy.";
    let strategy = Json.string strategy in
    let constraint_violations = names ~path constraint_violations in
    (match candidate with
    | None -> require ~path
        ((match generation_error with Json.String value -> value <> "" | _ -> false) &&
         check=None && constraint_violations=[])
        "Ungenerated alternatives require an explicit error only."
    | Some candidate ->
        require ~path (A.Config.conjunction_strategy (C.generator_config candidate)=strategy && generation_error=Json.Null)
          "Strategy and candidate disagree.";
        require ~path ((constraint_violations<>[] && check=None) || (constraint_violations=[] && check<>None))
          "Every structurally eligible alternative needs an independent check.";
        Option.iter (fun check -> require ~path
          (dependency check "mechanism" = str (Mechanism.fingerprint (C.mechanism candidate)) &&
           dependency check "observation_map" = str (Observation_map.fingerprint (C.observation_map candidate)) &&
           setting check "synthetic_candidate" = Some (str (C.fingerprint candidate)))
          "Alternative check identifies another candidate.") check);
    let gate_count = Option.map gate_count candidate in
    let generation_error = optional Json.string generation_error in
    let status = if generation_error<>None then "unsupported" else if constraint_violations<>[] then "hard_rejected"
      else outcome (E.Check_result.outcome (Option.get check)) in
    let skeleton = ["schema_version",str schema_version;"strategy",str strategy;
      "candidate",option_json C.to_json candidate;"constraint_violations",Json.Array [];
      "check",option_json E.Check_result.to_json check;"generation_error",option_json str generation_error;
      "gate_count",option_json Json.int gate_count;"status",str status] in
    let budget = budget () in reserve budget (Json.Object skeleton);
    reserve_list budget str constraint_violations;
    let json,fingerprint,size = finish (Json.Object (("constraint_violations",Json.Array (List.map str constraint_violations)) ::
      List.remove_assoc "constraint_violations" skeleton)) in
    {json;fingerprint;size;strategy;candidate;constraint_violations;check;generation_error;gate_count;status}
  let make ~strategy ?candidate ?(constraint_violations=[]) ?check ?generation_error () =
    let budget = budget () in
    reserve_list budget str (bounded constraint_violations);
    build ~path:"" ~strategy:(str strategy) ~candidate ~check
      ~constraint_violations:(Json.Array (List.map str constraint_violations))
      ~generation_error:(option_json str generation_error)
  let of_json ?(path="") raw =
    let fields = record ~path ["schema_version";"strategy";"candidate";"constraint_violations";"check";
      "generation_error";"gate_count";"status"] "SyntheticAlternative" raw in
    let get key = get path key fields in
    Diagnostic.require ~path (get "schema_version"=str schema_version) "unsupported_schema" "Unsupported alternative schema.";
    let candidate = optional (C.of_json ~path:(path^"/candidate")) (get "candidate") in
    let check = optional (E.Check_result.of_json ~path:(path^"/check")) (get "check") in
    let result = build ~path ~strategy:(get "strategy") ~candidate ~check
      ~constraint_violations:(get "constraint_violations") ~generation_error:(get "generation_error") in
    require ~path (get "gate_count"=option_json Json.int result.gate_count && get "status"=str result.status)
      "Alternative summary disagrees with its artifacts."; result
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let strategy value = value.strategy
  let candidate value = value.candidate
  let constraint_violations value = value.constraint_violations
  let check value = value.check
  let generation_error value = value.generation_error
  let gate_count value = value.gate_count
  let status value = value.status
end

module Result = struct
  type t = {json:Json.t;fingerprint:string;size:int;request_fingerprint:string;history_fingerprint:string;
    until:N.t option;config:A.Config.t;minimize:string;alternatives:Alternative.t list;
    selected_strategy:string option;candidate:C.t option;outcome:string;checked_candidates:int;rejected_candidates:int}
  let schema_version = "biocompiler.synthetic_selection_result.v0.1"
  let build ~path ~request_fingerprint ~history_fingerprint ~until ~config ~minimize alternatives =
    let request_fingerprint = identity ~path "Realization request" request_fingerprint in
    let history_fingerprint = identity ~path "Input history" history_fingerprint in
    let until = horizon ~path until in
    require ~path (List.mem minimize [str "gate_count";str "none"]) "Unknown ranking policy.";
    let minimize = Json.string minimize in
    require ~path (List.map Alternative.strategy alternatives = strategies)
      "The complete bounded search contains native then de_morgan exactly once.";
    List.iter (fun item ->
      Option.iter (fun candidate ->
        let expected = A.Config.make ~profile_version:(A.Config.profile_version config)
          ~generator_version:(A.Config.generator_version config) ~catalog_fingerprint:(A.Config.catalog_fingerprint config)
          ~witness_selection:(A.Config.witness_selection config) ~conjunction_strategy:(Alternative.strategy item) () in
        require ~path (C.request_fingerprint candidate=request_fingerprint &&
          A.Config.fingerprint (C.generator_config candidate)=A.Config.fingerprint expected)
          "Alternative belongs to another request/configuration.") (Alternative.candidate item);
      Option.iter (fun check ->
        let recorded = Json.field "until" (Json.object_fields (dependency check "horizon")) in
        require ~path (dependency check "history"=str history_fingerprint &&
          horizon_equal (horizon ~path recorded) until && setting check "realization_request"=Some (str request_fingerprint))
          "Alternative check belongs to another history/horizon/request.") (Alternative.check item)) alternatives;
    let selected = List.fold_left (fun selected item ->
      match Alternative.check item with
      | Some check when E.Check_result.outcome check=E.Pass ->
          (match selected with None -> Some item | Some previous ->
            if minimize="gate_count" && Option.get (Alternative.gate_count item) < Option.get (Alternative.gate_count previous)
            then Some item else selected)
      | _ -> selected) None alternatives in
    let selected_strategy = Option.map Alternative.strategy selected in
    let candidate = Option.bind selected Alternative.candidate in
    let has outcome = List.exists (fun item -> match Alternative.check item with
      Some check -> E.Check_result.outcome check=outcome | None -> false) alternatives in
    let outcome = if candidate<>None then "selected" else if has E.Unknown then "unknown"
      else if has E.Unsupported || List.exists (fun item -> Alternative.generation_error item<>None) alternatives
      then "unsupported" else "exhausted" in
    let checked_candidates = List.fold_left (fun count item -> count + (if Alternative.check item<>None then 1 else 0)) 0 alternatives in
    let rejected_candidates = List.fold_left (fun count item -> count +
      (if Alternative.constraint_violations item<>[] ||
        (match Alternative.check item with Some check -> E.Check_result.outcome check=E.Fail | None -> false)
      then 1 else 0)) 0 alternatives in
    let skeleton = ["schema_version",str schema_version;"selection_version",str selection_version;"cost_version",str cost_version;
      "intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted";
      "request_fingerprint",str request_fingerprint;"history_fingerprint",str history_fingerprint;
      "until",option_json N.to_json until;"config",A.Config.to_json config;"minimize",str minimize;
      "alternatives",Json.Array [];"selected_strategy",option_json str selected_strategy;"outcome",str outcome;
      "checked_candidates",Json.int checked_candidates;"rejected_candidates",Json.int rejected_candidates;
      "search_scope",str "two_whole_program_conjunction_strategies"] in
    let budget = budget () in reserve budget (Json.Object skeleton); reserve_list budget Alternative.to_json alternatives;
    let json,fingerprint,size = finish (Json.Object (("alternatives",Json.Array (List.map Alternative.to_json alternatives)) ::
      List.remove_assoc "alternatives" skeleton)) in
    {json;fingerprint;size;request_fingerprint;history_fingerprint;until;config;minimize;alternatives;
      selected_strategy;candidate;outcome;checked_candidates;rejected_candidates}
  let make ~request_fingerprint ~history_fingerprint ?until ~config ~minimize alternatives =
    let alternatives = bounded alternatives in
    let budget = budget () in reserve_list budget Alternative.to_json alternatives;
    build ~path:"" ~request_fingerprint:(str request_fingerprint) ~history_fingerprint:(str history_fingerprint)
      ~until:(option_json raw_number until) ~config ~minimize:(str minimize) alternatives
  let of_json ?(path="") raw =
    let fields = record ~path ["schema_version";"selection_version";"cost_version";"intended_use";
      "human_therapeutic_admission";"request_fingerprint";"history_fingerprint";"until";"config";"minimize";
      "alternatives";"selected_strategy";"outcome";"checked_candidates";"rejected_candidates";"search_scope"]
      "SyntheticSelectionResult" raw in
    let get key = get path key fields in
    Diagnostic.require ~path (get "schema_version"=str schema_version && get "selection_version"=str selection_version &&
      get "cost_version"=str cost_version && get "intended_use"=str "software_test" &&
      get "human_therapeutic_admission"=str "not_admitted" && get "search_scope"=str "two_whole_program_conjunction_strategies")
      "unsupported_schema" "Unsupported selection schema/policy.";
    let raw_alternatives = match get "alternatives" with Json.Array values -> values | _ ->
      Diagnostic.fail ~path "synthetic_selection" "Expected alternatives array." in
    let config = A.Config.of_json ~path:(path^"/config") (get "config") in
    let alternatives = List.mapi (fun index -> Alternative.of_json ~path:(path^"/alternatives/"^string_of_int index)) raw_alternatives in
    let result = build ~path ~request_fingerprint:(get "request_fingerprint") ~history_fingerprint:(get "history_fingerprint")
      ~until:(get "until") ~config ~minimize:(get "minimize") alternatives in
    List.iter (fun (key,expected) -> require ~path (get key=expected)
      "Selection summary disagrees with checked alternatives.")
      ["selected_strategy",option_json str result.selected_strategy;"outcome",str result.outcome;
       "checked_candidates",Json.int result.checked_candidates;"rejected_candidates",Json.int result.rejected_candidates]; result
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let request_fingerprint value = value.request_fingerprint
  let history_fingerprint value = value.history_fingerprint
  let until value = value.until
  let config value = value.config
  let minimize value = value.minimize
  let alternatives value = value.alternatives
  let selected_strategy value = value.selected_strategy
  let candidate value = value.candidate
  let outcome value = value.outcome
  let checked_candidates value = value.checked_candidates
  let rejected_candidates value = value.rejected_candidates
end
