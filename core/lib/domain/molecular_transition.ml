open Bioc_wire
module M = Molecular_record
module P = M.Provenance
module F = Molecule.Feature
let max_dispositions = 4096
let max_component_destinations = 256
let max_feature_outputs = 256
let str value = Json.String value
let obj value = Json.Object value
let array encode values = Json.Array (List.map encode values)
let optional encode = function None -> Json.Null | Some value -> encode value
let option decode = function Json.Null -> None | value -> Some (decode value)
let finish ~path json value = M.check_resources ~path json; value
let records ~path ~maximum (decode : ?path:string -> Json.t -> 'a) value =
  M.array ~path ~maximum value |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index))
(* Native callers can reuse large checked children. Reserve their cumulative
   representation before retaining every expanded child in a parent record. *)
let bounded_jsons ~maximum encode values =
  ignore (M.bounded_length ~maximum values);
  let nodes = ref 0 and bytes = ref 0 in
  let reserve json =
    bytes := !bytes + M.pretty_size json;
    Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Transition children exceed the aggregate publication budget.";
    let pending = ref [json] in
    while !pending <> [] do
      let value = List.hd !pending in pending := List.tl !pending; incr nodes;
      Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Transition children exceed the aggregate value budget.";
      match value with
      | Json.Array values -> pending := List.rev_append values !pending
      | Json.Object fields -> nodes := !nodes + List.length fields; pending := List.rev_append (List.map snd fields) !pending
      | _ -> ()
    done;
    Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Transition children exceed the aggregate value budget.";
    json in
  List.map (fun value -> reserve (encode value)) values
let unique ~path ~code compare values =
  let sorted = List.sort compare values in
  let rec check = function
    | first :: (second :: _ as rest) -> Diagnostic.require ~path (compare first second <> 0) code "Duplicate transition inventory key."; check rest
    | _ -> () in
  check sorted; sorted
module Component = struct
  type t = Cap | Start_end | Finish_end | Terminal_tail | Modification_inventory | Modification of string
  let to_string = function Cap -> "cap" | Start_end -> "start_end" | Finish_end -> "finish_end"
    | Terminal_tail -> "terminal_tail" | Modification_inventory -> "modification_inventory" | Modification id -> "modification:" ^ id
  let of_string ?(path = "") value =
    ignore (M.text ~path ~maximum:(M.max_text_bytes + 13) (str value));
    match value with "cap" -> Cap | "start_end" -> Start_end | "finish_end" -> Finish_end
    | "terminal_tail" -> Terminal_tail | "modification_inventory" -> Modification_inventory
    | value when String.starts_with ~prefix:"modification:" value ->
        Modification (M.text ~path (str (String.sub value 13 (String.length value - 13))))
    | _ -> Diagnostic.fail ~path "invalid_chemistry_disposition" "Unknown chemistry component selector."
  let of_json ~path value = of_string ~path (Json.string ~path value)
end
module Chemistry_disposition = struct
  type decision = Mapped_copy | Declared_replacement | Not_carried | Unknown
  type t = {source_id:string; component:Component.t; decision:decision; destination_components:Component.t list; provenance:P.t}
  let schema_version = "biocompiler.chemistry_disposition.v0.1"
  let decision_name = function Mapped_copy -> "mapped_copy" | Declared_replacement -> "declared_replacement" | Not_carried -> "not_carried" | Unknown -> "unknown"
  let to_json (value : t) = obj ["schema_version",str schema_version; "source_id",str value.source_id;
      "component",str (Component.to_string value.component); "decision",str (decision_name value.decision);
      "destination_components",array (fun value -> str (Component.to_string value)) value.destination_components; "provenance",P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["source_id";"component";"decision";"destination_components";"provenance"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let decision = match Json.string (get "decision") with "mapped_copy" -> Mapped_copy | "declared_replacement" -> Declared_replacement
      | "not_carried" -> Not_carried | "unknown" -> Unknown | _ -> Diagnostic.fail ~path "invalid_chemistry_disposition" "Unknown chemistry disposition." in
    let destination_components = M.array ~path ~maximum:max_component_destinations (get "destination_components")
      |> List.map (Component.of_json ~path) |> unique ~path ~code:"invalid_chemistry_disposition" (fun left right -> String.compare (Component.to_string left) (Component.to_string right)) in
    Diagnostic.require ~path (match decision with Not_carried -> destination_components = [] | Mapped_copy | Declared_replacement -> destination_components <> [] | Unknown -> true)
      "invalid_chemistry_disposition" "Disposition and destination chemistry count disagree.";
    let result = {source_id = M.text ~path (get "source_id"); component = Component.of_json ~path (get "component"); decision; destination_components;
                  provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~source_id ~component ~decision ~destination_components ~provenance =
    ignore (M.bounded_length ~maximum:max_component_destinations destination_components);
    of_json (to_json {source_id;component;decision;destination_components;provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let source_id (value : t) = value.source_id
  let component (value : t) = value.component
  let decision (value : t) = value.decision
  let destination_components (value : t) = value.destination_components
  let provenance (value : t) = value.provenance
end
module Chemistry = struct
  module D = Chemistry_disposition
  type mode = Exact_inheritance | Explicit_output
  type t = {mode:mode; output:Molecule_chemistry.t option; dispositions:D.t list; provenance:P.t}
  let schema_version = "biocompiler.chemistry_transition.v0.1"
  let mode_name = function Exact_inheritance -> "exact_inheritance" | Explicit_output -> "explicit_output"
  let to_json (value : t) = obj ["schema_version",str schema_version; "mode",str (mode_name value.mode);
      "output",optional Molecule_chemistry.to_json value.output; "dispositions",array D.to_json value.dispositions; "provenance",P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["mode";"output";"dispositions";"provenance"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let mode = match Json.string (get "mode") with "exact_inheritance" -> Exact_inheritance | "explicit_output" -> Explicit_output
      | _ -> Diagnostic.fail ~path "invalid_chemistry_transition" "Unknown chemistry transition mode." in
    let output = option (Molecule_chemistry.of_json ~path:(path ^ "/output")) (get "output") in
    let dispositions = records ~path:(path ^ "/dispositions") ~maximum:max_dispositions D.of_json (get "dispositions")
      |> unique ~path ~code:"invalid_chemistry_transition" (fun left right -> Stdlib.compare (D.source_id left,Component.to_string (D.component left)) (D.source_id right,Component.to_string (D.component right))) in
    Diagnostic.require ~path (match mode with Exact_inheritance -> output = None && dispositions = [] | Explicit_output -> Option.is_some output)
      "invalid_chemistry_transition" "Exact inheritance cannot override authority; explicit output requires full chemistry.";
    let result = {mode;output;dispositions;provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~mode ~output ~dispositions ~provenance =
    let dispositions = bounded_jsons ~maximum:max_dispositions D.to_json dispositions in
    of_json (obj ["schema_version",str schema_version; "mode",str (mode_name mode); "output",optional Molecule_chemistry.to_json output;
      "dispositions",Json.Array dispositions; "provenance",P.to_json provenance])
  let fingerprint value = Canonical.fingerprint (to_json value)
  let mode (value : t) = value.mode
  let output (value : t) = value.output
  let dispositions (value : t) = value.dispositions
  let provenance (value : t) = value.provenance
end
let features ~path value = records ~path ~maximum:max_feature_outputs F.of_json value
  |> unique ~path ~code:"invalid_feature_transition" (fun left right -> String.compare (F.id left) (F.id right))
module Feature_disposition = struct
  type decision = Exact | Partial | Split | Not_carried | Outside_selection | Unknown
  type t = {source_id:string; feature_id:string; decision:decision; outputs:F.t list; provenance:P.t}
  let schema_version = "biocompiler.feature_disposition.v0.1"
  let decision_name = function Exact -> "exact" | Partial -> "partial" | Split -> "split" | Not_carried -> "not_carried" | Outside_selection -> "outside_selection" | Unknown -> "unknown"
  let to_json (value : t) = obj ["schema_version",str schema_version; "source_id",str value.source_id; "feature_id",str value.feature_id;
      "decision",str (decision_name value.decision); "outputs",array F.to_json value.outputs; "provenance",P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["source_id";"feature_id";"decision";"outputs";"provenance"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let decision = match Json.string (get "decision") with "exact" -> Exact | "partial" -> Partial | "split" -> Split
      | "not_carried" -> Not_carried | "outside_selection" -> Outside_selection | "unknown" -> Unknown
      | _ -> Diagnostic.fail ~path "invalid_feature_disposition" "Unknown feature disposition." in
    let outputs = features ~path:(path ^ "/outputs") (get "outputs") in
    let count = List.length outputs in
    Diagnostic.require ~path (match decision with Exact | Partial -> count = 1 | Split -> count >= 2 | Not_carried | Outside_selection -> count = 0 | Unknown -> true)
      "invalid_feature_disposition" "Feature disposition and output count disagree.";
    let result = {source_id = M.text ~path (get "source_id"); feature_id = M.text ~path (get "feature_id"); decision; outputs;
                  provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~source_id ~feature_id ~decision ~outputs ~provenance =
    let outputs = bounded_jsons ~maximum:max_feature_outputs F.to_json outputs in
    of_json (obj ["schema_version",str schema_version; "source_id",str source_id; "feature_id",str feature_id;
      "decision",str (decision_name decision); "outputs",Json.Array outputs; "provenance",P.to_json provenance])
  let fingerprint value = Canonical.fingerprint (to_json value)
  let source_id (value : t) = value.source_id
  let feature_id (value : t) = value.feature_id
  let decision (value : t) = value.decision
  let outputs (value : t) = value.outputs
  let provenance (value : t) = value.provenance
end
module Feature = struct
  module D = Feature_disposition
  type t = {dispositions:D.t list; added:F.t list; provenance:P.t}
  let schema_version = "biocompiler.feature_transition.v0.1"
  let to_json (value : t) = obj ["schema_version",str schema_version; "dispositions",array D.to_json value.dispositions;
      "added",array F.to_json value.added; "provenance",P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["dispositions";"added";"provenance"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let dispositions = records ~path:(path ^ "/dispositions") ~maximum:max_dispositions D.of_json (get "dispositions")
      |> unique ~path ~code:"invalid_feature_transition" (fun left right -> Stdlib.compare (D.source_id left,D.feature_id left) (D.source_id right,D.feature_id right)) in
    let added = features ~path:(path ^ "/added") (get "added") in
    let count = List.fold_left (fun count disposition ->
        let count = count + List.length (D.outputs disposition) in
        Diagnostic.require ~path (count <= max_feature_outputs) "invalid_feature_transition" "Total output feature limit exceeded."; count) (List.length added) dispositions in
    ignore count;
    let outputs = List.rev_append added (List.concat_map D.outputs dispositions) in
    ignore (unique ~path ~code:"invalid_feature_transition" (fun left right -> String.compare (F.id left) (F.id right)) outputs);
    let result = {dispositions;added;provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~dispositions ~added ~provenance =
    ignore (M.bounded_length ~maximum:max_dispositions dispositions); ignore (M.bounded_length ~maximum:max_feature_outputs added);
    ignore (List.fold_left (fun count item -> let count = count + List.length (D.outputs item) in
        Diagnostic.require (count <= max_feature_outputs) "invalid_feature_transition" "Total output feature limit exceeded."; count) (List.length added) dispositions);
    let dispositions = bounded_jsons ~maximum:max_dispositions D.to_json dispositions
    and added = bounded_jsons ~maximum:max_feature_outputs F.to_json added in
    of_json (obj ["schema_version",str schema_version; "dispositions",Json.Array dispositions; "added",Json.Array added; "provenance",P.to_json provenance])
  let fingerprint value = Canonical.fingerprint (to_json value)
  let dispositions (value : t) = value.dispositions
  let added (value : t) = value.added
  let provenance (value : t) = value.provenance
end
