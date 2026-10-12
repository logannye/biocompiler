open Bioc_wire
module Original = Policy_controlled_composition_request
module Domain = Policy_controlled_domain
let schema_version = "biocompiler.policy_controlled_behavior_request.v0.1"
let profile = Original.profile
let resource_profile = Original.resource_profile
type t = { body:Json.t; authority:Original.t; identity:string; work:int;
  evidence:Domain.effective_evidence array }
let get key raw = Json.field key (Json.object_fields raw)
let exact keys raw = Json.exact_fields keys (Json.object_fields raw)
let require value message = Diagnostic.require value "controlled_behavior_request" message
let integer maximum raw =
  let value = Json.integer raw in
  require (Z.sign value >= 0 && Z.leq value (Z.of_int maximum))
    "Readout tick/freshness exceeds the closed domain bound.";
  Z.to_int value
let of_json ?(charge=fun _ -> ()) body =
  let work = ref 0 in
  let spend n = charge n; work := !work + n in
  let bytes = Policy_material_request.preflight ~charge:spend body in
  exact ["schema_version";"original";"readout_evidence"] body;
  require (get "schema_version" body = Json.String schema_version)
    "Unsupported behavioral authority schema.";
  let authority = Original.of_json ~charge:spend (get "original" body) in
  let horizon = integer 64 (get "horizon_tick" (get "operating_domain" (Original.raw authority))) in
  let readout = get "readout_evidence" body in
  exact ["freshness_ticks";"samples"] readout;
  let freshness = integer 64 (get "freshness_ticks" readout) in
  require (freshness > 0) "Readout freshness must be positive.";
  let samples = Json.array (get "samples" readout) in
  require (List.length samples = horizon + 1)
    "Original readout evidence must explicitly cover every tick including the horizon.";
  let evidence = Array.of_list (List.mapi (fun tick raw ->
    spend 1;
    exact ["tick";"status";"observed_tick"] raw;
    require (integer 64 (get "tick" raw) = tick)
      "Readout samples must be complete, ordered and unique.";
    let status = match Json.string (get "status" raw) with
      | "valid" -> Domain.Valid | "missing" -> Domain.Missing
      | "invalid" -> Domain.Invalid | "conflicting" -> Domain.Conflicting
      | _ -> Diagnostic.fail "controlled_behavior_request" "Unknown readout evidence status." in
    match status,get "observed_tick" raw with
    | Domain.Missing,Json.Null -> Domain.Fresh Domain.Missing
    | Domain.Missing,_ | _,Json.Null ->
        Diagnostic.fail "controlled_behavior_request" "Readout evidence timestamp contradicts status."
    | _,raw -> let observed = integer 64 raw in
        require (observed <= tick) "Readout evidence cannot be future dated.";
        if tick - observed > freshness then Domain.Stale else Domain.Fresh status) samples) in
  spend bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:Molecular_record.max_json_bytes body in
  require (String.length encoded = bytes) "Behavior request canonical byte accounting disagrees.";
  spend bytes;
  require (!work <= (Original.budgets authority).max_work)
    "Complete behavioral authority decoding exceeds the original work ceiling.";
  {body;authority;identity=Canonical.sha256 encoded;work= !work;evidence}
let raw value = value.body
let to_json = raw
let original value = value.authority
let fingerprint value = value.identity
let decoding_work value = value.work
let budgets value = Original.budgets value.authority
let readout value tick =
  require (tick >= 0 && tick < Array.length value.evidence) "Readout lookup is outside original authority.";
  value.evidence.(tick)
