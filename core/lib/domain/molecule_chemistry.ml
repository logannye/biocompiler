open Bioc_wire
module M = Molecular_record
module C = Molecule_coordinates
module P = M.Provenance

type status = Declared | Unknown | Inapplicable | Absent
type sequence_extent = Complete | Exact_core
let status_name = function Declared -> "declared" | Unknown -> "unknown" | Inapplicable -> "inapplicable" | Absent -> "absent"
let status_of_json ~path value = match Json.string ~path value with
  | "declared" -> Declared | "unknown" -> Unknown | "inapplicable" -> Inapplicable | "absent" -> Absent
  | _ -> Diagnostic.fail ~path "invalid_chemistry" "Unknown chemical declaration status."
let check ?path condition message = Diagnostic.require ?path condition "invalid_chemistry" message
let option decoder = function Json.Null -> None | value -> Some (decoder value)
let optional encoder = function None -> Json.Null | Some value -> encoder value
let string value = Json.String value
let finish ?path json value = M.check_resources ?path json; value

module Chemical_identity = struct
  type t = { namespace : string; accession : string; version : string }
  let schema_version = "biocompiler.chemical_identity.v0.1"
  let to_json (value : t) = Json.Object ["schema_version", string schema_version;
      "namespace", string value.namespace; "accession", string value.accession; "version", string value.version]
  let nominal_json = to_json
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["namespace"; "accession"; "version"] value in
    let text key = M.text ~path:(path ^ "/" ^ key) (Json.field ~path key fields) in
    let result = {namespace = text "namespace"; accession = text "accession"; version = text "version"} in
    finish ~path (to_json result) result
  let make ~namespace ~accession ~version = of_json (to_json {namespace; accession; version})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let namespace (value : t) = value.namespace
  let accession (value : t) = value.accession
  let version (value : t) = value.version
  let declared_nominal_complete value = List.for_all ((<>) "unknown") [value.namespace; value.accession; value.version]
end

module Claim = struct
  type t = { status : status; identity : Chemical_identity.t option; provenance : P.t }
  let schema_version = "biocompiler.chemistry_claim.v0.1"
  let nominal_json (value : t) = Json.Object ["schema_version", string schema_version;
      "status", string (status_name value.status); "identity", optional Chemical_identity.nominal_json value.identity]
  let to_json (value : t) = match nominal_json value with
    | Json.Object fields -> Json.Object (fields @ ["provenance", P.to_json value.provenance])
    | _ -> assert false
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["status"; "identity"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let status = status_of_json ~path:(path ^ "/status") (get "status") in
    let identity = option (Chemical_identity.of_json ~path:(path ^ "/identity")) (get "identity") in
    check ~path ((status = Declared) = Option.is_some identity) "Only declared chemistry claims carry an identity.";
    let result = {status; identity; provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~status ~identity ~provenance = of_json (to_json {status; identity; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let status (value : t) = value.status
  let identity (value : t) = value.identity
  let provenance (value : t) = value.provenance
  let declared_nominal_complete value = value.status <> Unknown && Option.fold ~none:true ~some:Chemical_identity.declared_nominal_complete value.identity
end

module Modification = struct
  type scope = Positions | All_matching_bases
  type t = { id : string; identity : Chemical_identity.t; canonical_base : char; scope : scope; positions : int list; provenance : P.t }
  let schema_version = "biocompiler.base_modification.v0.1"
  let nominal_json (value : t) = Json.Object ["schema_version", string schema_version;
      "identity", Chemical_identity.nominal_json value.identity;
      "canonical_base", string (String.make 1 value.canonical_base);
      "scope", string (match value.scope with Positions -> "positions" | All_matching_bases -> "all_matching_bases");
      "positions", Json.Array (List.map Json.int value.positions)]
  let to_json (value : t) = match nominal_json value with
    | Json.Object fields -> Json.Object (fields @ ["id", string value.id; "provenance", P.to_json value.provenance])
    | _ -> assert false
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "identity"; "canonical_base"; "scope"; "positions"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let id = M.text ~path:(path ^ "/id") (get "id") in
    let identity = Chemical_identity.of_json ~path:(path ^ "/identity") (get "identity") in
    let base = Json.string ~path (get "canonical_base") in
    check ~path (String.length base = 1 && String.contains "ACGTU" base.[0]) "Unknown canonical modification parent base.";
    let canonical_base = base.[0] in
    let scope = match Json.string ~path (get "scope") with
      | "positions" -> Positions | "all_matching_bases" -> All_matching_bases
      | _ -> Diagnostic.fail ~path "invalid_chemistry" "Unknown modification scope." in
    let positions = M.array ~path:(path ^ "/positions") ~maximum:4096 (get "positions")
      |> List.map (M.index ~path:(path ^ "/positions") ~maximum:(M.max_residues - 1)) in
    check ~path (List.length positions = List.length (List.sort_uniq Int.compare positions)) "Duplicate modification positions.";
    let positions = List.sort Int.compare positions in
    check ~path (match scope with Positions -> positions <> [] | All_matching_bases -> positions = []) "Modification scope and site inventory disagree.";
    if Chemical_identity.namespace identity = "biocompiler.chemical" && Chemical_identity.version identity = "1" then (
      let expected = List.assoc_opt (Chemical_identity.accession identity)
          ["inosine", 'A'; "pseudouridine", 'U'; "n1_methylpseudouridine", 'U'] in
      check ~path (Option.fold ~none:true ~some:((=) canonical_base) expected) "Built-in modification has the wrong canonical parent base.");
    let result = {id; identity; canonical_base; scope; positions; provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~id ~identity ~canonical_base ~scope ~positions ~provenance =
    ignore (M.bounded_length ~maximum:4096 positions);
    of_json (to_json {id; identity; canonical_base; scope; positions; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let identity (value : t) = value.identity
  let canonical_base (value : t) = value.canonical_base
  let scope (value : t) = value.scope
  let positions (value : t) = value.positions
  let provenance (value : t) = value.provenance
end

module Tail_length = struct
  type mode = Exact of int | Bounded of int * int | Unknown_length
  type t = mode
  let schema_version = "biocompiler.tail_length.v0.1"
  let to_json value =
    let mode, exact, lower, upper = match value with
      | Exact exact -> "exact", Json.int exact, Json.Null, Json.Null
      | Bounded (lower, upper) -> "bounded", Json.Null, Json.int lower, Json.int upper
      | Unknown_length -> "unknown", Json.Null, Json.Null, Json.Null in
    Json.Object ["schema_version", string schema_version; "mode", string mode; "exact", exact; "lower", lower; "upper", upper]
  let nominal_json = to_json
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["mode"; "exact"; "lower"; "upper"] value in
    let get key = Json.field ~path key fields in
    let result = match Json.string ~path (get "mode") with
      | "exact" ->
          let exact = M.index ~path:(path ^ "/exact") (get "exact") in
          check ~path (get "lower" = Json.Null && get "upper" = Json.Null) "Exact tails cannot carry bounds.";
          Exact exact
      | "bounded" ->
          check ~path (get "exact" = Json.Null) "Bounded tails cannot invent an exact length.";
          let lower = M.index ~path:(path ^ "/lower") (get "lower") and upper = M.index ~path:(path ^ "/upper") (get "upper") in
          check ~path (lower < upper) "Tail bounds must be strictly ordered."; Bounded (lower, upper)
      | "unknown" ->
          check ~path (List.for_all (fun key -> get key = Json.Null) ["exact"; "lower"; "upper"]) "Unknown tail length cannot invent numbers.";
          Unknown_length
      | _ -> Diagnostic.fail ~path "invalid_chemistry" "Unknown tail length mode." in
    finish ~path (to_json result) result
  let make value = of_json (to_json value)
  let fingerprint value = Canonical.fingerprint (to_json value)
  let mode value = value
end

module Tail = struct
  type placement = Represented_terminal | Appended_terminal | Absent_tail
  type t = { status : status; placement : placement option; length : Tail_length.t option; path : C.Path.t option; provenance : P.t }
  let schema_version = "biocompiler.tail_declaration.v0.1"
  let placement_name = function Represented_terminal -> "represented_terminal" | Appended_terminal -> "appended_terminal" | Absent_tail -> "absent"
  let fields (value : t) = ["schema_version", string schema_version; "status", string (status_name value.status);
      "placement", optional (fun value -> string (placement_name value)) value.placement;
      "length", optional Tail_length.to_json value.length]
  let to_json (value : t) = Json.Object (fields value @ ["path", optional C.Path.to_json value.path; "provenance", P.to_json value.provenance])
  let nominal_json (value : t) =
    let path = optional (fun value -> Json.Object (List.remove_assoc "space_id" (Json.object_fields (C.Path.to_json value)))) value.path in
    Json.Object (fields value @ ["path", path])
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["status"; "placement"; "length"; "path"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let status = status_of_json ~path:(path ^ "/status") (get "status") in
    check ~path (status <> Absent) "Tail status must be declared, unknown or inapplicable.";
    let placement = option (fun value -> match Json.string ~path value with
      | "represented_terminal" -> Represented_terminal | "appended_terminal" -> Appended_terminal | "absent" -> Absent_tail
      | _ -> Diagnostic.fail ~path "invalid_chemistry" "Unknown tail placement.") (get "placement") in
    let length = option (Tail_length.of_json ~path:(path ^ "/length")) (get "length") in
    let coordinate_path = option (C.Path.of_json ~path:(path ^ "/path")) (get "path") in
    let valid = match status, placement, Option.map Tail_length.mode length, coordinate_path with
      | Declared, Some Represented_terminal, Some (Tail_length.Exact length), Some _ -> length > 0
      | Declared, Some Appended_terminal, Some (Tail_length.Bounded _ | Tail_length.Unknown_length), None -> true
      | Declared, Some Absent_tail, Some (Tail_length.Exact 0), None -> true
      | (Unknown | Inapplicable), None, None, None -> true
      | _ -> false in
    check ~path valid "Tail status, placement, length and coordinates disagree.";
    let result = {status; placement; length; path = coordinate_path; provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~status ~placement ~length ~path ~provenance = of_json (to_json {status; placement; length; path; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let status (value : t) = value.status
  let placement (value : t) = value.placement
  let length (value : t) = value.length
  let path (value : t) = value.path
  let provenance (value : t) = value.provenance
  let declared_nominal_complete value = value.status = Inapplicable ||
      (value.status = Declared && match Option.map Tail_length.mode value.length with Some (Tail_length.Exact _) -> true | _ -> false)
end

type t = { cap : Claim.t; start_end : Claim.t; finish_end : Claim.t; modifications : Modification.t list;
           modification_inventory_status : status; modification_inventory_provenance : P.t; terminal_tail : Tail.t }
let schema_version = "biocompiler.molecule_chemistry.v0.1"
let to_json (value : t) = Json.Object ["schema_version", string schema_version;
    "cap", Claim.to_json value.cap; "start_end", Claim.to_json value.start_end; "finish_end", Claim.to_json value.finish_end;
    "modifications", Json.Array (List.map Modification.to_json value.modifications);
    "modification_inventory_status", string (status_name value.modification_inventory_status);
    "modification_inventory_provenance", P.to_json value.modification_inventory_provenance;
    "terminal_tail", Tail.to_json value.terminal_tail]
let of_json ?(path = "") value =
  let fields = M.record ~path schema_version ["cap"; "start_end"; "finish_end"; "modifications";
      "modification_inventory_status"; "modification_inventory_provenance"; "terminal_tail"] value in
  let get key = Json.field ~path key fields in
  let modifications = M.array ~path:(path ^ "/modifications") ~maximum:128 (get "modifications")
    |> List.mapi (fun index -> Modification.of_json ~path:(path ^ "/modifications/" ^ string_of_int index)) in
  let ids = List.map Modification.id modifications in
  check ~path (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate modification occurrence IDs.";
  let modifications = List.sort (fun left right -> String.compare (Modification.id left) (Modification.id right)) modifications in
  let modification_inventory_status = status_of_json ~path:(path ^ "/modification_inventory_status") (get "modification_inventory_status") in
  check ~path (modification_inventory_status <> Absent && (modification_inventory_status <> Inapplicable || modifications = []))
    "Invalid modification inventory status or inapplicable nonempty inventory.";
  let result = {cap = Claim.of_json ~path:(path ^ "/cap") (get "cap");
    start_end = Claim.of_json ~path:(path ^ "/start_end") (get "start_end");
    finish_end = Claim.of_json ~path:(path ^ "/finish_end") (get "finish_end"); modifications; modification_inventory_status;
    modification_inventory_provenance = P.of_json ~path:(path ^ "/modification_inventory_provenance") (get "modification_inventory_provenance");
    terminal_tail = Tail.of_json ~path:(path ^ "/terminal_tail") (get "terminal_tail")} in
  finish ~path (to_json result) result
let make ~cap ~start_end ~finish_end ~modifications ~modification_inventory_status ~modification_inventory_provenance ~terminal_tail =
  ignore (M.bounded_length ~maximum:128 modifications);
  of_json (to_json {cap; start_end; finish_end; modifications; modification_inventory_status; modification_inventory_provenance; terminal_tail})
let fingerprint value = Canonical.fingerprint (to_json value)
let nominal_json (value : t) =
  let modifications = List.map Modification.nominal_json value.modifications
      |> List.map (fun item -> Canonical.fingerprint item, item)
      |> List.stable_sort (fun (left, _) (right, _) -> String.compare left right) |> List.map snd in
  Json.Object ["schema_version", string schema_version; "cap", Claim.nominal_json value.cap;
    "start_end", Claim.nominal_json value.start_end; "finish_end", Claim.nominal_json value.finish_end;
    "modifications", Json.Array modifications; "modification_inventory_status", string (status_name value.modification_inventory_status);
    "terminal_tail", Tail.nominal_json value.terminal_tail]
let cap (value : t) = value.cap
let start_end (value : t) = value.start_end
let finish_end (value : t) = value.finish_end
let modifications (value : t) = value.modifications
let modification_inventory_status (value : t) = value.modification_inventory_status
let modification_inventory_provenance (value : t) = value.modification_inventory_provenance
let terminal_tail (value : t) = value.terminal_tail
let declared_nominal_complete value =
  List.for_all Claim.declared_nominal_complete [value.cap; value.start_end; value.finish_end]
  && value.modification_inventory_status <> Unknown
  && List.for_all (fun item -> Chemical_identity.declared_nominal_complete (Modification.identity item)) value.modifications
  && Tail.declared_nominal_complete value.terminal_tail

let validate_for value space ~sequence ~sequence_extent =
  let alphabet = C.Space.alphabet space and topology = C.Space.topology space in
  check (String.length sequence = C.Space.length space && M.valid_sequence alphabet sequence) "Sequence and coordinate alphabet or length disagree.";
  if topology = C.Circular then
    check (List.for_all (fun item -> Claim.status item = Inapplicable) [value.cap; value.start_end; value.finish_end]
           && Tail.status value.terminal_tail = Inapplicable) "Circular molecules have no free ends, cap or terminal tail."
  else check (List.for_all (fun item -> List.mem (Claim.status item) [Declared; Unknown]) [value.start_end; value.finish_end])
      "Linear ends must be declared or unknown.";
  if alphabet <> C.Rna then
    check (Claim.status value.cap = Inapplicable && Tail.status value.terminal_tail = Inapplicable) "DNA and protein RNA caps/tails are inapplicable."
  else if topology = C.Linear then (
    check (List.mem (Claim.status value.cap) [Declared; Unknown; Absent]) "Linear RNA cap is declared, unknown or absent.";
    check (List.mem (Tail.status value.terminal_tail) [Declared; Unknown]) "Linear RNA tail is declared or unknown.");
  if alphabet = C.Protein then check (value.modifications = []) "Proteins cannot carry nucleotide modifications."
  else check (value.modification_inventory_status <> Inapplicable) "Nucleotide modification inventories cannot be inapplicable.";
  let used = Hashtbl.create 64 and all_matching = Hashtbl.create 5 and explicit = Hashtbl.create 5 in
  List.iter (fun modification ->
      let base = Modification.canonical_base modification in
      check (String.contains (M.alphabet_symbols alphabet) base) "Modification parent and alphabet disagree.";
      match Modification.scope modification with
      | Modification.Positions ->
          let positions = Modification.positions modification in
          check (List.for_all (fun position -> position < String.length sequence) positions) "Modification position is outside the sequence.";
          check (List.for_all (fun position -> sequence.[position] = base) positions) "Modification site has the wrong canonical parent.";
          check (not (Hashtbl.mem all_matching base)) "Explicit modifications overlap an all-matching policy.";
          check (List.for_all (fun position -> not (Hashtbl.mem used position)) positions) "Modification positions overlap.";
          List.iter (fun position -> Hashtbl.add used position ()) positions; Hashtbl.replace explicit base ()
      | Modification.All_matching_bases ->
          check (not (Hashtbl.mem all_matching base || Hashtbl.mem explicit base)) "All-matching modifications overlap another declaration.";
          Hashtbl.add all_matching base ()) value.modifications;
  let tail = value.terminal_tail in
  if Tail.status tail = Declared && Tail.placement tail = Some Tail.Represented_terminal then (
    let path = Option.get (Tail.path tail) in
    C.Path.validate_for path space;
    let exact = match Tail_length.mode (Option.get (Tail.length tail)) with Tail_length.Exact value -> value | _ -> assert false in
    check (C.Path.strand path = C.Forward && List.length (C.Path.spans path) = 1
           && C.Span.stop (List.hd (C.Path.spans path)) = String.length sequence && C.Path.length path = exact)
      "Represented tail requires one forward terminal interval with the exact length.";
    let span = List.hd (C.Path.spans path) in
    for position = C.Span.start span to C.Span.stop span - 1 do
      check (sequence.[position] = 'A') "Represented poly(A) tail contains a non-adenine base."
    done);
  let appended = Tail.status tail = Declared && Tail.placement tail = Some Tail.Appended_terminal in
  if appended then check (alphabet = C.Rna && topology = C.Linear && sequence_extent = Exact_core) "An uncertain appended tail requires an exact linear RNA core.";
  if sequence_extent = Exact_core then check appended "An exact core requires an explicit uncertain appended tail."
