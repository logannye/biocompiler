open Bioc_wire
module M = Molecular_record
module C = Molecule_chemistry.Chemical_identity
let max_recodings = 4096
let standard_genetic_code = "ncbi_standard_v1"
(* Normative immutable table-1 data in UCAG order. No translation executor. *)
let standard_rna_codon_table =
  let bases = "UCAG" and residues = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG" in
  List.init 64 (fun index -> String.init 3 (function 0 -> bases.[index / 16] | 1 -> bases.[index / 4 mod 4] | _ -> bases.[index mod 4]), residues.[index])
let str value = Json.String value
let chr value = str (String.make 1 value)
let obj value = Json.Object value
let optional encode = function None -> Json.Null | Some value -> encode value
let option decode = function Json.Null -> None | value -> Some (decode value)
let finish ~path json value = M.check_resources ~path json; value
let symbol ~path ~code allowed value =
  let text = Json.string ~path value in
  Diagnostic.require ~path (String.length text = 1 && String.contains allowed text.[0]) code "Expected one exact canonical symbol.";
  text.[0]
module Canonical_edit = struct
  type t = {position:int; expected:char; replacement:char}
  let schema_version = "biocompiler.canonical_base_edit.v0.1"
  let to_json (value : t) = obj ["schema_version",str schema_version; "position",Json.int value.position;
      "expected",chr value.expected; "replacement",chr value.replacement]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["position";"expected";"replacement"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let position = M.index ~path ~maximum:(M.max_residues - 1) (get "position")
    and expected = symbol ~path ~code:"invalid_canonical_edit" "ACGU" (get "expected")
    and replacement = symbol ~path ~code:"invalid_canonical_edit" "ACGU" (get "replacement") in
    Diagnostic.require ~path (expected <> replacement) "invalid_canonical_edit" "Canonical edits must change the expected symbol.";
    let result = {position;expected;replacement} in finish ~path (to_json result) result
  let make ~position ~expected ~replacement = of_json (to_json {position;expected;replacement})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let position (value : t) = value.position
  let expected (value : t) = value.expected
  let replacement (value : t) = value.replacement
end
module Chemical_edit = struct
  type t = {position:int; parent:char; before:C.t option; after:C.t option}
  let schema_version = "biocompiler.chemical_base_edit.v0.1"
  let to_json (value : t) = obj ["schema_version",str schema_version; "position",Json.int value.position; "parent",chr value.parent;
      "before",optional C.to_json value.before; "after",optional C.to_json value.after]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["position";"parent";"before";"after"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let position = M.index ~path ~maximum:(M.max_residues - 1) (get "position")
    and parent = symbol ~path ~code:"invalid_chemical_edit" "ACGU" (get "parent") in
    let decode key = option (C.of_json ~path:(path ^ "/" ^ key)) (get key) in
    let before = decode "before" and after = decode "after" in
    List.iter (Option.iter (fun identity ->
      if C.namespace identity = "biocompiler.chemical" && C.version identity = "1" then
        let expected = List.assoc_opt (C.accession identity) ["inosine",'A';"pseudouridine",'U';"n1_methylpseudouridine",'U'] in
        Diagnostic.require ~path (Option.fold ~none:true ~some:((=) parent) expected)
          "invalid_chemical_edit" "Built-in chemical edit identity has the wrong canonical parent.")) [before;after];
    Diagnostic.require ~path (not (Json.equal (optional C.to_json before) (optional C.to_json after)))
      "invalid_chemical_edit" "Chemical edits must change declared site chemistry.";
    let result = {position;parent;before;after} in finish ~path (to_json result) result
  let make ~position ~parent ~before ~after = of_json (to_json {position;parent;before;after})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let position (value : t) = value.position
  let parent (value : t) = value.parent
  let before (value : t) = value.before
  let after (value : t) = value.after
end
module Codon_recoding = struct
  type t = {codon_index:int; expected_triplet:string; amino_acid:char; condition:string}
  let schema_version = "biocompiler.codon_recoding.v0.1"
  let to_json (value : t) = obj ["schema_version",str schema_version; "codon_index",Json.int value.codon_index;
      "expected_triplet",str value.expected_triplet; "amino_acid",chr value.amino_acid; "condition",str value.condition]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["codon_index";"expected_triplet";"amino_acid";"condition"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let codon_index = M.index ~path ~maximum:(M.max_residues / 3 - 1) (get "codon_index")
    and expected_triplet = M.text ~path ~maximum:3 (get "expected_triplet") in
    Diagnostic.require ~path (String.length expected_triplet = 3 && String.for_all (String.contains "ACGU") expected_triplet)
      "invalid_codon_recoding" "Recoding requires exactly three canonical RNA symbols.";
    let amino_acid = symbol ~path ~code:"invalid_codon_recoding" (M.alphabet_symbols Molecule_coordinates.Protein ^ "*") (get "amino_acid")
    and condition = M.text ~path (get "condition") in
    let result = {codon_index;expected_triplet;amino_acid;condition} in finish ~path (to_json result) result
  let make ~codon_index ~expected_triplet ~amino_acid ~condition = of_json (to_json {codon_index;expected_triplet;amino_acid;condition})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let codon_index (value : t) = value.codon_index
  let expected_triplet (value : t) = value.expected_triplet
  let amino_acid (value : t) = value.amino_acid
  let condition (value : t) = value.condition
end
module Translation_policy = struct
  module R = Codon_recoding
  type profile = Ordinary_cds | Conditional_cds
  type t = {profile:profile; genetic_code:string; recodings:R.t list}
  let schema_version = "biocompiler.translation_policy.v0.1"
  let profile_name = function Ordinary_cds -> "ordinary_cds" | Conditional_cds -> "conditional_cds"
  let recodings_json values =
    ignore (M.bounded_length ~maximum:max_recodings values);
    let bytes = ref 0 in
    (* Each fixed-shape recoding has 11 JSON items, so this collection's
       declared count already bounds its nodes below the molecular budget. *)
    Json.Array (List.map (fun value -> let json = R.to_json value in
        bytes := !bytes + M.pretty_size json;
        Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Recodings exceed the aggregate publication budget.";
        json) values)
  let to_json (value : t) = obj ["schema_version",str schema_version; "profile",str (profile_name value.profile);
      "genetic_code",str value.genetic_code; "recodings",recodings_json value.recodings]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["profile";"genetic_code";"recodings"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let profile = match Json.string (get "profile") with "ordinary_cds" -> Ordinary_cds | "conditional_cds" -> Conditional_cds
      | _ -> Diagnostic.fail ~path "invalid_translation_policy" "Unknown translation profile." in
    let genetic_code = Json.string (get "genetic_code") in
    Diagnostic.require ~path (genetic_code = standard_genetic_code) "invalid_translation_policy" "Unsupported declared genetic code.";
    let recodings = M.array ~path:(path ^ "/recodings") ~maximum:max_recodings (get "recodings")
      |> List.mapi (fun index -> R.of_json ~path:(path ^ "/recodings/" ^ string_of_int index))
      |> List.sort (fun left right -> Int.compare (R.codon_index left) (R.codon_index right)) in
    let rec unique = function first :: (second :: _ as rest) ->
        Diagnostic.require ~path (R.codon_index first <> R.codon_index second) "invalid_translation_policy" "Duplicate codon recoding site."; unique rest
      | _ -> () in unique recodings;
    Diagnostic.require ~path (match profile with Ordinary_cds -> recodings = [] | Conditional_cds -> recodings <> [])
      "invalid_translation_policy" "Conditional translation requires explicit recodings; ordinary translation cannot carry them.";
    let result = {profile;genetic_code;recodings} in finish ~path (to_json result) result
  let make ?(genetic_code = standard_genetic_code) ?(recodings = []) ~profile () =
    ignore (M.bounded_length ~maximum:max_recodings recodings);
    of_json (to_json {profile;genetic_code;recodings})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let profile (value : t) = value.profile
  let genetic_code (value : t) = value.genetic_code
  let recodings (value : t) = value.recodings
end
