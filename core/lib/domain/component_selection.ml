open Bioc_wire
module P = Pinned_identity
module C = Component_contract
module Lock = Component_registry.Component_lock
module Keys = Map.Make (struct type t = string * string * string let compare = Stdlib.compare end)
module Names = Set.Make (String)
let resource_profile = "biocompiler.component_selection.resources.v1"
let require ?path condition message = Diagnostic.require ?path condition "component_selection" message
let limit ?path condition = Diagnostic.require ?path condition "component_selection_limit"
  "Component selection record exceeds its native resource boundary."
let str value = Json.String value
let optional encode = function None -> Json.Null | Some value -> encode value
let bounded values =
  let rec loop count = function [] -> values | _ :: rest -> limit (count < Limits.max_json_nodes); loop (count + 1) rest in
  loop 0 values

type visit = Enter of Json.t * int | Leave of Json.t
let measure ?(path = "") ?(maximum = Limits.max_response_bytes) value =
  limit ~path (maximum > 0 && maximum <= Limits.max_response_bytes);
  let bytes = ref 0 and nodes = ref 0 and queued = ref 1 in
  let add amount = limit ~path (amount <= maximum - !bytes); bytes := !bytes + amount in
  let quoted value =
    limit ~path (String.length value <= Limits.max_string_bytes); add (String.length value + 2);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | value when Char.code value < 32 -> add 5 | _ -> ()) value;
    Json.validate_utf8 value in
  let length maximum values =
    let rec loop count = function [] -> count | _ :: rest -> limit ~path (count < maximum); loop (count + 1) rest in
    loop 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let next = List.hd !pending in pending := List.tl !pending;
    match next with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes; limit ~path (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active))
            "component_selection_cycle" "Cyclic component selection record.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        (match value with
        | Json.Null -> add 4
        | Json.Bool value -> add (if value then 4 else 5)
        | Json.Int value ->
            limit ~path (Z.numbits value <= 4 * Limits.max_number_chars);
            let text = Z.to_string value in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
        | Json.Float value ->
            Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Selection records require finite JSON numbers.";
            add (String.length (Canonical.float_string value))
        | Json.String value -> quoted value
        | Json.Array values ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) values in
            add (2 + max 0 (count - 1)); enter values count
        | Json.Object fields ->
            let count = length ((Limits.max_json_nodes - !nodes - !queued) / 2) fields in
            nodes := !nodes + count;
            add (2 + count + max 0 (count - 1));
            let seen = Hashtbl.create 16 in
            List.iter (fun (key, _) -> quoted key;
              Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate component selection field.";
              Hashtbl.add seen key ()) fields;
            enter (List.map snd fields) count)
  done;
  !bytes, !nodes

type budget = { maximum : int; mutable bytes : int; mutable nodes : int }
let budget maximum = {maximum; bytes = 0; nodes = 0}
let reserve budget value =
  let bytes, nodes = measure ~maximum:budget.maximum value in
  limit (bytes <= budget.maximum - budget.bytes && nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + bytes; budget.nodes <- budget.nodes + nodes; value
let array budget encode values =
  let first = ref true in
  Json.Array (List.map (fun value ->
    if !first then first := false else (limit (budget.bytes < budget.maximum); budget.bytes <- budget.bytes + 1);
    reserve budget (encode value)) (bounded values))
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let record ~path ~maximum schema keys raw =
  ignore (measure ~path ~maximum raw);
  let fields = Json.object_fields ~path raw in Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (field path "schema_version" fields) = schema) "unsupported_schema" "Unsupported registry schema.";
  fields
let hash ~path ~label raw =
  let value = Json.string ~path raw in
  require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    (label ^ " must be a SHA-256 identity."); value
let names ~path ~label raw =
  let values = Json.array ~path raw |> List.map (Json.name ~path) in
  let seen = ref Names.empty in
  List.iter (fun value -> require ~path (not (Names.mem value !seen)) (label ^ " must be unique."); seen := Names.add value !seen) values;
  values
let identity_key value = P.kind_name value, P.id value, P.version value
let identities ~path values =
  let sorted = List.fold_left (fun result value ->
    let key = identity_key value in
    (match Keys.find_opt key result with None -> () | Some previous ->
      require ~path (P.content_fingerprint previous = P.content_fingerprint value)
        "Ambiguous dependency identity: one kind/ID/version has different hashes.");
    Keys.add key value result) Keys.empty values in
  List.map snd (Keys.bindings sorted)
let finish maximum raw = ignore (measure ~maximum raw); let canonical = Canonical.encode raw in Canonical.sha256 canonical, String.length canonical

module Request = struct
  type t = {json:Json.t; fingerprint:string; size:int; implementation_role:string; target:Build_request.Target.t;
    required_domain:C.Operating_domain.t; instance_id:string; classification:string option; required_guarantees:string list;
    component_id:string option; component_version:string option; required_identities:P.t list; preferred_component_ids:string list}
  let schema_version = "biocompiler.component_selection_request.v0.1"
  let encode ~implementation_role ~target ~required_domain ~instance_id ~classification ~required_guarantees
      ~component_id ~component_version ~required_identities ~preferred_component_ids =
    let budget = budget Limits.max_request_bytes in
    let skeleton = ["schema_version",str schema_version; "implementation_role",str implementation_role;
      "target",Build_request.Target.to_json target; "required_domain",C.Operating_domain.to_json required_domain;
      "instance_id",str instance_id; "classification",optional str classification;
      "component_id",optional str component_id; "component_version",optional str component_version;
      "required_guarantees",Json.Array []; "required_identities",Json.Array []; "preferred_component_ids",Json.Array []] in
    ignore (reserve budget (Json.Object skeleton));
    let guarantees = array budget str required_guarantees in
    let identities = array budget P.to_json required_identities in
    let preferred = array budget str preferred_component_ids in
    Json.Object (["required_guarantees",guarantees; "required_identities",identities; "preferred_component_ids",preferred] @
      List.filter (fun (key,_) -> not (List.mem key ["required_guarantees";"required_identities";"preferred_component_ids"])) skeleton)
  let of_json ?(path = "") raw =
    let fields = record ~path ~maximum:Limits.max_request_bytes schema_version
      ["implementation_role";"target";"required_domain";"instance_id";"classification";"required_guarantees";
       "component_id";"component_version";"required_identities";"preferred_component_ids"] raw in
    let get key = field path key fields in
    let target = Build_request.Target.of_json ~path:(path ^ "/target") (get "target") in
    let required_domain = C.Operating_domain.of_json ~path:(path ^ "/required_domain") (get "required_domain") in
    let pins = Json.array ~path:(path ^ "/required_identities") (get "required_identities") |> List.mapi
      (fun index -> P.of_json ~path:(path ^ "/required_identities/" ^ string_of_int index)) in
    let name key = Json.name ~path:(path ^ "/" ^ key) (get key) in
    let maybe key = match get key with Json.Null -> None | value -> Some (Json.name ~path:(path ^ "/" ^ key) value) in
    let implementation_role = name "implementation_role" in
    let instance_id = name "instance_id" in
    let classification = maybe "classification" in
    let component_id = maybe "component_id" in
    let component_version = maybe "component_version" in
    require ~path (component_version = None || component_id <> None) "A hard version pin requires a component ID.";
    let required_guarantees = names ~path:(path ^ "/required_guarantees") ~label:"required_guarantees" (get "required_guarantees") in
    let preferred_component_ids = names ~path:(path ^ "/preferred_component_ids") ~label:"preferred_component_ids" (get "preferred_component_ids") in
    let required_identities = identities ~path pins in
    let json = encode ~implementation_role ~target ~required_domain ~instance_id ~classification ~required_guarantees
      ~component_id ~component_version ~required_identities ~preferred_component_ids in
    let fingerprint,size = finish Limits.max_request_bytes json in
    {json;fingerprint;size;implementation_role;target;required_domain;instance_id;classification;required_guarantees;
     component_id;component_version;required_identities;preferred_component_ids}
  let make ~implementation_role ~target ~required_domain ?(instance_id = "selected") ?classification ?(required_guarantees = [])
      ?component_id ?component_version ?(required_identities = []) ?(preferred_component_ids = []) () =
    of_json (encode ~implementation_role ~target ~required_domain ~instance_id ~classification ~required_guarantees
      ~component_id ~component_version ~required_identities ~preferred_component_ids)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let implementation_role value = value.implementation_role
  let target value = value.target
  let required_domain value = value.required_domain
  let instance_id value = value.instance_id
  let classification value = value.classification
  let required_guarantees value = value.required_guarantees
  let component_id value = value.component_id
  let component_version value = value.component_version
  let required_identities value = value.required_identities
  let preferred_component_ids value = value.preferred_component_ids
end
module Alternative = struct
  type status = Eligible | Rejected | Unknown
  let status_name = function Eligible -> "eligible" | Rejected -> "rejected" | Unknown -> "unknown"
  type t = {json:Json.t;fingerprint:string;size:int;component_id:string;version:string;content_fingerprint:string;
    status:status;reasons:string list;preference_rank:Z.t option}
  let schema_version = "biocompiler.component_selection_alternative.v0.1"
  let encode ~component_id ~version ~content_fingerprint ~status ~reasons ~preference_rank =
    let budget = budget Limits.max_request_bytes in
    let skeleton = ["schema_version",str schema_version;"component_id",str component_id;"version",str version;
      "content_fingerprint",str content_fingerprint;"status",str (status_name status);"reasons",Json.Array [];
      "preference_rank",optional (fun value -> Json.Int value) preference_rank] in
    ignore (reserve budget (Json.Object skeleton));
    Json.Object (("reasons",array budget str reasons) :: List.remove_assoc "reasons" skeleton)
  let of_json ?(path = "") raw =
    let fields = record ~path ~maximum:Limits.max_request_bytes schema_version
      ["component_id";"version";"content_fingerprint";"status";"reasons";"preference_rank"] raw in
    let get key = field path key fields in
    let component_id = Json.name ~path:(path ^ "/component_id") (get "component_id") in
    let version = Json.name ~path:(path ^ "/version") (get "version") in
    let content_fingerprint = hash ~path:(path ^ "/content_fingerprint") ~label:"Component fingerprint" (get "content_fingerprint") in
    let status = match Json.string ~path:(path ^ "/status") (get "status") with
      | "eligible" -> Eligible | "rejected" -> Rejected | "unknown" -> Unknown
      | _ -> Diagnostic.fail ~path "component_selection" "Invalid alternative status." in
    let reasons = names ~path:(path ^ "/reasons") ~label:"Selection reasons" (get "reasons") in
    require ~path (reasons <> []) "Selection alternatives require rationale.";
    let preference_rank = match get "preference_rank" with Json.Null -> None | value -> Some (Json.integer ~path:(path ^ "/preference_rank") value) in
    require ~path (match status,preference_rank with Eligible,Some rank -> Z.sign rank >= 0 | (Rejected | Unknown),None -> true | _ -> false)
      "Preferences can rank only eligible alternatives.";
    let json = encode ~component_id ~version ~content_fingerprint ~status ~reasons ~preference_rank in
    let fingerprint,size = finish Limits.max_request_bytes json in
    {json;fingerprint;size;component_id;version;content_fingerprint;status;reasons;preference_rank}
  let make ~component_id ~version ~content_fingerprint ~status ~reasons ?preference_rank () =
    of_json (encode ~component_id ~version ~content_fingerprint ~status ~reasons ~preference_rank)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let component_id value = value.component_id
  let version value = value.version
  let content_fingerprint value = value.content_fingerprint
  let status value = value.status
  let reasons value = value.reasons
  let preference_rank value = value.preference_rank
  let key value = value.component_id,value.version,value.content_fingerprint
  let compare_rank left right = let rank = Option.compare Z.compare left.preference_rank right.preference_rank in
    if rank <> 0 then rank else Stdlib.compare (key left) (key right)
end
module Result = struct
  type outcome = Pass | Fail | Unknown | Unsupported
  let outcome_name = function Pass -> "pass" | Fail -> "fail" | Unknown -> "unknown" | Unsupported -> "unsupported"
  type t = {json:Json.t;fingerprint:string;size:int;registry_fingerprint:string;request_fingerprint:string;
    selected:Lock.t option;alternatives:Alternative.t list;admission:Admission.Assessment.t}
  let schema_version = "biocompiler.component_selection_result.v0.2"
  let encode ~registry_fingerprint ~request_fingerprint ~selected ~alternatives ~admission =
    let budget = budget Limits.max_response_bytes in
    let skeleton = ["schema_version",str schema_version;"registry_fingerprint",str registry_fingerprint;
      "request_fingerprint",str request_fingerprint;"selected",optional Lock.to_json selected;
      "alternatives",Json.Array [];"admission",Admission.Assessment.to_json admission] in
    ignore (reserve budget (Json.Object skeleton));
    Json.Object (("alternatives",array budget Alternative.to_json alternatives) :: List.remove_assoc "alternatives" skeleton)
  let decode ~path ~maximum raw =
    let fields = record ~path ~maximum schema_version ["registry_fingerprint";"request_fingerprint";"selected";"alternatives";"admission"] raw in
    let get key = field path key fields in
    let admission = Admission.Assessment.of_json ~path:(path ^ "/admission") (get "admission") in
    let selected = match get "selected" with Json.Null -> None | value -> Some (Lock.of_json ~path:(path ^ "/selected") value) in
    let alternatives = Json.array ~path:(path ^ "/alternatives") (get "alternatives") |> List.mapi
      (fun index -> Alternative.of_json ~path:(path ^ "/alternatives/" ^ string_of_int index)) in
    require ~path (selected = None || Admission.Assessment.decision admission = Admission.Software_only)
      "A non-admitted request cannot select a component.";
    let registry_fingerprint = hash ~path:(path ^ "/registry_fingerprint") ~label:"Registry fingerprint" (get "registry_fingerprint") in
    let request_fingerprint = hash ~path:(path ^ "/request_fingerprint") ~label:"Selection request fingerprint" (get "request_fingerprint") in
    let alternatives = List.sort (fun a b -> Stdlib.compare (Alternative.key a) (Alternative.key b)) alternatives in
    let previous = ref None and winner = ref None in
    List.iter (fun item ->
      let key = Alternative.component_id item,Alternative.version item in
      require ~path (!previous <> Some key) "Duplicate selection alternatives."; previous := Some key;
      if Alternative.status item = Alternative.Eligible then match !winner with
        | Some previous when Alternative.compare_rank previous item <= 0 -> ()
        | _ -> winner := Some item) alternatives;
    require ~path (match !winner,selected with None,None -> true | Some winner,Some selected ->
      Alternative.key winner = (Lock.component_id selected,Lock.version selected,Lock.content_fingerprint selected) | _ -> false)
      "Selection must choose the deterministically ranked eligible alternative.";
    let json = encode ~registry_fingerprint ~request_fingerprint ~selected ~alternatives ~admission in
    let fingerprint,size = finish Limits.max_response_bytes json in
    {json;fingerprint;size;registry_fingerprint;request_fingerprint;selected;alternatives;admission}
  let of_json ?(path = "") raw = decode ~path ~maximum:Limits.max_request_bytes raw
  let make ~registry_fingerprint ~request_fingerprint ~selected ~alternatives ~admission =
    decode ~path:"" ~maximum:Limits.max_response_bytes (encode ~registry_fingerprint ~request_fingerprint ~selected ~alternatives ~admission)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let registry_fingerprint value = value.registry_fingerprint
  let request_fingerprint value = value.request_fingerprint
  let selected value = value.selected
  let alternatives value = value.alternatives
  let admission value = value.admission
  let outcome value = if Admission.Assessment.decision value.admission <> Admission.Software_only then Unsupported
    else if value.selected <> None then Pass
    else if List.exists (fun item -> Alternative.status item = Alternative.Unknown) value.alternatives then Unknown else Fail
end
