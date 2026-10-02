open Bioc_wire
module M = Molecular_record
module A = Architecture_contract.Constraints
module L = Architecture_refinement.Library
type t = {id:string; circuit:Circuit_request.t; library:L.t; constraints:A.t; source:Human_request.t}
let schema_version = "biocompiler.payload_architecture_request.v0.1"
let str value = Json.String value
let to_json (value : t) = Json.Object ["schema_version",str schema_version;"id",str value.id;
    "circuit",Circuit_request.to_json value.circuit;"library",L.to_json value.library;"constraints",A.to_json value.constraints]
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version ["id";"circuit";"library";"constraints"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let id = M.text ~path:(path ^ "/id") (get "id") in
  let circuit = match Circuit_request.of_json (get "circuit") with
    | Circuit_request.Decoded value -> value
    | Circuit_request.Unsupported _ -> Diagnostic.fail ~path "unsupported_architecture_authority" "Architecture requires complete supported circuit authority." in
  let profile = Circuit_request.profile circuit in
  let source = match Circuit_request.Profile.source_request profile with
    | Some value -> value
    | None -> Diagnostic.fail ~path "invalid_architecture_request" "Architecture compilation requires complete original source authority." in
  let target = Circuit_request.Profile.target profile in
  Diagnostic.require ~path (Circuit_request.Profile.purpose profile = "human_immune_payload"
    && (match target with Some target -> Build_request.Target.kind target = Build_request.Human_target && Build_request.Target.payload_format target = "RNA" | None -> false)
    && Json.field "molecular_form" (Json.object_fields (Circuit_request.Profile.to_json profile)) = str "RNA")
    "invalid_architecture_request" "Architecture compilation targets human in-vivo immune-cell RNA only.";
  let library = L.of_json ~path:(path ^ "/library") (get "library")
  and constraints = A.of_json ~path:(path ^ "/constraints") (get "constraints") in
  let value = {id;circuit;library;constraints;source} in
  M.check_resources ~path (to_json value); value
let default_constraints () = A.make ~exact_count:None ~max_count:None ~max_member_bases:None ~max_total_bases:None
    ~delivery_groups:[] ~control_requirements:[] ~preferred_refinement_ids:[] ~max_combinations:256 ~require_complete:false
    ~max_match_states:100_000 ~max_match_instances:256 ~deployment_requirements:[]
let make ?constraints ~id ~circuit ~library () =
  let constraints = match constraints with Some value -> value | None -> default_constraints () in
  let circuit_json = Circuit_request.to_json circuit and library_json = L.to_json library and constraints_json = A.to_json constraints in
  (* Each child is abstract and checked; reject their cumulative representation
     before publishing an expanded parent. The parent applies its full budget. *)
  let bytes = ref 0 and nodes = ref 1 in
  List.iter (fun raw ->
      bytes := !bytes + M.pretty_size raw;
      Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Architecture request exceeds aggregate child budget.";
      let pending = ref [raw] in
      while !pending <> [] do
        let raw = List.hd !pending in pending := List.tl !pending; incr nodes;
        Diagnostic.require (!nodes <= M.max_items) "molecular_resource_limit" "Architecture request exceeds aggregate item budget.";
        match raw with
        | Json.Object fields -> nodes := !nodes + List.length fields; pending := List.rev_append (List.map snd fields) !pending
        | Json.Array values -> pending := List.rev_append values !pending
        | _ -> ()
      done) [circuit_json;library_json;constraints_json];
  of_json (Json.Object ["schema_version",str schema_version;"id",str id;"circuit",circuit_json;"library",library_json;"constraints",constraints_json])
let fingerprint value = Canonical.fingerprint (to_json value)
let id (value : t) = value.id
let circuit (value : t) = value.circuit
let library (value : t) = value.library
let constraints (value : t) = value.constraints
let source (value : t) = value.source
