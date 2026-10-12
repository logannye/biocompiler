open Bioc_wire
module Check = Bioc_checker.Policy_controlled_material_check
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
module Input = Bioc_domain.Policy_material_request
let str value = Json.String value
let obj fields = Json.Object fields
let get key value = Json.field key (Json.object_fields value)
let measure ~charge raw = Input.preflight ~max_bytes:8_323_072
  ~max_nodes:249_968 ~max_depth:128 ~charge raw
let fingerprint ~charge raw =
  let size = measure ~charge raw in
  charge size;
  let encoded = Canonical.encode_bounded ~max_bytes:8_323_072 raw in
  charge size;
  Diagnostic.require (String.length encoded = size) "controlled_material_format_accounting"
    "Exact publication size disagrees with the reserved original body.";
  Canonical.sha256 encoded
let render ~charge checked =
  let request = Check.request checked and candidate = Check.candidate checked in
  let raw_candidate = C.to_json candidate and report = Check.evidence checked in
  let content = get "construction" raw_candidate in
  (* These immutable original subtrees were freshly decoded and independently
     reconstructed before the private capability was created. No producer is
     called here, and no behavioral capability is fabricated. *)
  let molecules = Json.array (get "molecules" (get "inventory" content)) in
  charge 128;
  Diagnostic.require (List.length molecules = 2) "controlled_material_format_inventory"
    "Structural publication requires exactly two independently checked members.";
  let fasta = Buffer.create 128 in
  let members = List.mapi (fun index molecule ->
    ignore (measure ~charge molecule);
    let id = Json.string (get "id" molecule) in
    let sequence = Json.string (get "sequence" molecule) in
    let size = String.length sequence in
    let fasta_id = Printf.sprintf "rna_%04d" (index + 1) in
    let header = ">" ^ fasta_id ^ " alphabet=RNA\n" in
    charge (String.length header + size + (size + 79) / 80);
    Buffer.add_string fasta header;
    let rec lines offset = if offset < size then (
      let count = min 80 (size - offset) in
      Buffer.add_substring fasta sequence offset count;
      Buffer.add_char fasta '\n'; lines (offset + count)) in
    lines 0;
    charge size;
    obj ["fasta_id",str fasta_id; "member_id",str id; "molecule",molecule;
      "sequence_sha256",str (Canonical.sha256 sequence)]) molecules in
  charge (Buffer.length fasta);
  let fasta = Buffer.contents fasta in
  let manifest = obj [
    "schema_version",str "biocompiler.policy_controlled_composition_material_manifest.v0.1";
    "stage",str "material"; "request",R.raw request; "candidate",raw_candidate; "report",report;
    "request_fingerprint",str (R.fingerprint request);
    "candidate_fingerprint",str (C.fingerprint candidate);
    "invocation_fingerprint",get "invocation_fingerprint" report;
    "report_fingerprint",str (fingerprint ~charge report); "members",Json.Array members;
    "behavior_status",str "not_performed"; "empirical_status",str "unassessed";
    "human_use",str "unassessed"; "therapeutic_export",str "withheld"] in
  let manifest_sha256 = fingerprint ~charge manifest in
  charge (String.length fasta);
  obj ["fasta",str fasta; "fasta_sha256",str (Canonical.sha256 fasta);
    "manifest",manifest; "manifest_sha256",str manifest_sha256]
