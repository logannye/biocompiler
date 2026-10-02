open Bioc_wire
open Bioc_domain
module C = Composition
module E = Composition_evidence
module R = Component
module K = Component_contract
module P = K.Port
module N = Runtime_number
module S = Set.Make (String)
module M = Map.Make (String)
module Pair = struct type t = string * string let compare = Stdlib.compare end
module PM = Map.Make (Pair)
let checker_version = "biocompiler.component_linker.v0.3"
let implementation_version = "biocompiler.ocaml.composition_check.v0.1"
let resource_profile = "biocompiler.composition_check.resources.v1"
let diagnostic_order_profile = "pair_sorted_unknown_dependency_binding_and_unknown_resource_binding_only.v1"
type limits = { max_work : int; max_items : int; max_input_bytes : int;
  max_report_bytes : int; max_report_nodes : int; max_rational_bits : int }
let make_limits ?(max_work = 50_000_000) ?(max_items = 100_000)
    ?(max_input_bytes = Limits.max_request_bytes) ?(max_report_bytes = Limits.max_response_bytes)
    ?(max_report_nodes = Limits.max_json_nodes) ?(max_rational_bits = 8192) () =
  List.iter (fun (value, maximum) -> Diagnostic.require (value > 0 && value <= maximum)
      "composition_limits" "Composition checker limits must be positive reductions of the fixed native profile.")
    [max_work,50_000_000;max_items,100_000;max_input_bytes,Limits.max_request_bytes;
     max_report_bytes,Limits.max_response_bytes;max_report_nodes,Limits.max_json_nodes;max_rational_bits,8192];
  {max_work;max_items;max_input_bytes;max_report_bytes;max_report_nodes;max_rational_bits}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile",Json.String resource_profile;
  "max_work",Json.int limits.max_work;"max_retained_intermediate_items",Json.int limits.max_items;
  "max_input_bytes",Json.int limits.max_input_bytes;"max_input_nodes",Json.int Limits.max_json_nodes;
  "max_report_bytes",Json.int limits.max_report_bytes;"max_report_nodes",Json.int limits.max_report_nodes;
  "max_rational_bits",Json.int limits.max_rational_bits;
  "rational_arithmetic",Json.String "exact_Fraction_of_Python_decimal_spelling";
  "intermediate_accounting",Json.String "cumulative_no_refunds";
  "diagnostic_order",Json.String diagnostic_order_profile]
type usage = { work : int; retained_items : int }
type budget = { limits : limits; work : Work_budget.t; initial : int; output : Work_budget.output;
  mutable retained : int }
let create ?parent limits =
  let work = match parent with None -> Work_budget.create ~profile:resource_profile ~error_code:"composition_work_limit" ~maximum:limits.max_work ()
    | Some parent -> Work_budget.nested ~parent ~profile:resource_profile ~error_code:"composition_work_limit" ~maximum:limits.max_work () in
  {limits;work;initial=Work_budget.remaining work;retained=0;
   output=Work_budget.create_output ~profile:resource_profile ~error_code:"composition_report_limit"
     ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes ()}
let charge (budget : budget) amount = Work_budget.charge budget.work amount
let keep (budget : budget) count =
  Diagnostic.require (count >= 0 && count <= budget.limits.max_items - budget.retained)
    "composition_item_limit" "Composition intermediate inventory exceeds the native cumulative item limit.";
  charge budget count; budget.retained <- budget.retained + count
let node_work budget raw =
  let pending = ref [raw] in
  while !pending <> [] do
    let value = List.hd !pending in pending := List.tl !pending; charge budget 1;
    match value with
    | Json.String text -> charge budget (String.length text)
    | Json.Int value -> charge budget (1 + Z.numbits value / 3)
    | Json.Array values -> List.iter (fun value -> pending := value :: !pending) values
    | Json.Object fields -> List.iter (fun (key,value) -> charge budget (1 + String.length key); pending := value :: !pending) fields
    | _ -> ()
  done
let reserve budget raw =
  Work_budget.reserve_json budget.output (Json.Array [raw]); node_work budget raw
let prepare budget request registry =
  (* Cached immutable sizes are charged before any full authority traversal, so
     retrying against an exhausted parent cannot rescan a large request. *)
  charge budget (C.canonical_size request + Component_registry.canonical_size registry + 1);
  let output = Work_budget.create_output ~profile:resource_profile ~error_code:"composition_input_limit"
      ~max_bytes:budget.limits.max_input_bytes ~max_nodes:Limits.max_json_nodes () in
  let raw = Json.Object ["request",C.to_json request;"registry",Component_registry.to_json registry] in
  Work_budget.reserve_json output raw; node_work budget raw
let dependencies ?parent ?(limits=default_limits) ~request ~registry () =
  let budget = create ?parent limits in prepare budget request registry;
  let value = E.dependencies ~request ~registry in reserve budget (E.Dependencies.to_json value); value
let add_set budget value values =
  charge budget (1 + String.length value);
  if S.mem value values then values else (keep budget 1; S.add value values)
let set budget values = List.fold_left (fun result value -> add_set budget value result) S.empty values
let status assessment = match K.status assessment with K.Pass -> E.Pass | K.Fail -> E.Fail | K.Unknown -> E.Unknown
let priority values = if List.mem E.Fail values then E.Fail else if List.mem E.Unsupported values then E.Unsupported
  else if List.mem E.Unknown values then E.Unknown else E.Pass
let severity = function E.Fail -> E.Link_diagnostic.Fail | E.Unknown -> E.Link_diagnostic.Unknown
  | E.Unsupported -> E.Link_diagnostic.Unsupported | E.Pass -> assert false
let bits value = Z.numbits (Q.num value) + Z.numbits (Q.den value)
let bound_q budget value =
  Diagnostic.require (bits value <= budget.limits.max_rational_bits) "composition_rational_limit"
    "Exact decimal resource arithmetic exceeds its native rational-size boundary."; value
let rational_charge budget left right =
  let limbs = 1 + (bits left + bits right) / 64 in charge budget (limbs * limbs)
let decimal budget = function
  | N.Integer value -> charge budget (1 + Z.numbits value); bound_q budget (Q.of_bigint value)
  | N.Real value ->
      let text = Canonical.float_string value in charge budget (String.length text);
      let mantissa,exponent = match String.split_on_char 'e' text with
        | [mantissa] -> mantissa,0 | [mantissa;exponent] -> mantissa,int_of_string exponent | _ -> assert false in
      let digits,scale = match String.split_on_char '.' mantissa with
        | [whole] -> whole,0 | [whole;fraction] -> whole ^ fraction,String.length fraction | _ -> assert false in
      let numerator = Z.of_string digits and power = exponent - scale in
      bound_q budget (if power >= 0 then Q.of_bigint (Z.mul numerator (Z.pow (Z.of_int 10) power))
        else Q.make numerator (Z.pow (Z.of_int 10) (-power)))
let compare_q budget left right = rational_charge budget left right; Q.compare left right
let add_q budget left right = rational_charge budget left right; bound_q budget (Q.add left right)
let numeric_type_equal left right = Json.equal (Type_spec.to_json left) (Type_spec.to_json right)
let find_values key map = Option.value ~default:[] (PM.find_opt key map)
let add_values budget key value map = keep budget 1; PM.add key (value :: find_values key map) map
let fixed_point budget nodes invalid =
  let grounded = ref S.empty and changed = ref true in
  while !changed do
    changed := false;
    let ready = List.fold_left (fun values (key,requirements) ->
      charge budget (1 + String.length key);
      if not (S.mem key !grounded) && not (S.mem key invalid)
         && S.for_all (fun key -> charge budget (1 + String.length key); S.mem key !grounded) requirements
      then add_set budget key values else values) S.empty nodes in
    if not (S.is_empty ready) then (
      S.iter (fun key -> grounded := add_set budget key !grounded) ready; changed := true)
  done; !grounded
exception Finished of E.Result.t
let check_in (budget : budget) ~request ~registry =
  let limits = budget.limits in prepare budget request registry;
  let dependencies = E.dependencies ~request ~registry in
  let diagnostics = ref [] and statuses = ref [] and resolved = ref [] and usage = ref [] in
  let instances = List.fold_left (fun map item -> keep budget 1; M.add (C.Instance.id item) item map) M.empty (C.instances request) in
  let covered = List.fold_left (fun ids item -> List.fold_left (fun ids id -> add_set budget id ids) ids (C.Instance.requirement_ids item)) S.empty (C.instances request) |> S.elements in
  reserve budget (E.Result.to_json (E.Result.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:covered ()));
  let diagnostic outcome code message instance_id =
    let requirement_ids = match Option.bind instance_id (fun id -> M.find_opt id instances) with
      | Some instance -> C.Instance.requirement_ids instance | None -> C.requirement_ids request in
    let value = E.Link_diagnostic.make ~status:(severity outcome) ~code ~message ?instance_id ~requirement_ids () in
    reserve budget (E.Link_diagnostic.to_json value); keep budget 1;
    diagnostics := value :: !diagnostics; statuses := outcome :: !statuses in
  let finish () =
    let value = E.Result.make ~outcome:(priority !statuses) ~dependencies ~checked_requirement_ids:covered
        ~diagnostics:(List.rev !diagnostics) ~resolved_dependencies:!resolved ~resource_usage:(List.rev !usage) () in
    let output = Work_budget.create_output ~profile:resource_profile ~error_code:"composition_report_limit"
        ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
    let raw = E.Result.to_json value in Work_budget.reserve_json output raw; node_work budget raw; value in
  let stop () = raise (Finished (finish ())) in
  let execute () =
    if not (S.equal (set budget covered) (set budget (C.requirement_ids request))) then
      diagnostic E.Unknown "uncovered_requirement" "Every requested requirement must correspond to at least one selected instance." None;
    let registry_records = List.fold_left (fun map record -> keep budget 1;
        PM.add (R.id record,R.version record) record map) PM.empty (Component_registry.components registry) in
    List.iter (fun locked -> charge budget 1;
      match PM.find_opt (Component_registry.Component_lock.component_id locked,
          Component_registry.Component_lock.version locked) registry_records with
      | None -> () | Some record -> node_work budget (R.to_json record))
      (Component_registry.Lock.components (C.registry_lock request));
    let records = try Component_registry.resolve registry (C.registry_lock request) with
      | Diagnostic.Error error when error.code = "component_registry" ->
          diagnostic E.Fail "stale_registry_lock" error.message None; stop () in
    let locks = List.fold_left (fun map value -> keep budget 1; M.add (Component_registry.Component_lock.node_id value) value map)
        M.empty (Component_registry.Lock.components (C.registry_lock request)) in
    if not (S.equal (set budget (List.map fst records)) (set budget (List.map C.Instance.id (C.instances request))))
       || List.exists (fun instance -> charge budget 1;
         match M.find_opt (C.Instance.id instance) locks with None -> true | Some locked ->
           not (Json.equal (Component_registry.Component_lock.to_json locked)
             (Component_registry.Component_lock.to_json (C.Instance.component instance)))) (C.instances request)
    then (diagnostic E.Fail "instance_lock_mismatch" "Instances must exactly match the locked selections." None; stop ());
    let admission = Admission_check.for_target ~target:(C.target request) ~boundary:Admission.Verification ~components:(List.map snd records) in
    if Admission.Assessment.decision admission <> Admission.Software_only then
      diagnostic E.Unsupported "human_profile_not_admitted" (String.concat "; " (Admission.Assessment.diagnostics admission)) None;
    let target = Build_request.Target.payload_format (C.target request) in
    let target_compartments = set budget (Build_request.Target.compartments (C.target request)) in
    let invalid = ref S.empty in
    let invalidate id = invalid := add_set budget id !invalid in
    List.iter (fun (id,record) ->
      charge budget 1;
      (match R.synthetic_model record with Some model ->
        if List.exists (fun check -> charge budget 1; K.status check = K.Unknown)
            (R.Synthetic_operator.domain_checks model ~ports:(R.ports record) ~supported_domain:(R.supported_domain record)) then
          diagnostic E.Unknown "unknown_executable_domain" "Executable output guarantees cannot be established from unknown domains." (Some id)
      | None -> ());
      if R.synthetic_model record = None && List.exists (fun port -> charge budget 1;
          match P.timing port with P.Temporal_level | P.Temporal_event -> true | _ -> false) (R.ports record) then
        diagnostic E.Unknown "missing_transition_model" "Discrete-event interfaces require an explicit executable transition model." (Some id);
      if not (List.mem target (R.supported_targets record)) then (
        diagnostic E.Fail "unsupported_target" "Selected component does not support this payload target." (Some id); invalidate id);
      let required_domain = C.Instance.required_domain (M.find id instances) in
      let required_coordinates = K.Operating_domain.constraints required_domain
      and supported_coordinates = K.Operating_domain.constraints (R.supported_domain record) in
      let coordinate_count = List.length required_coordinates + List.length supported_coordinates in
      let coordinate_bytes = List.fold_left (fun count (key,_) -> count + String.length key) 0 required_coordinates
        + List.fold_left (fun count (key,_) -> count + String.length key) 0 supported_coordinates in
      (* The shared algebra scans both association lists for every union key.
         Include supported-only coordinates and string comparison work before
         invoking it; input size alone cannot bound this quadratic traversal. *)
      charge budget ((coordinate_count + 1) * (coordinate_bytes + coordinate_count + 1));
      let domain = K.operating_domain_subset ~required:(C.Instance.required_domain (M.find id instances)) ~supported:(R.supported_domain record) in
      if not (K.passed domain) then (
        diagnostic (status domain) "operating_domain" (String.concat " " (K.reasons domain)) (Some id); invalidate id);
      let compartments = List.map P.compartment (R.ports record) @ List.map R.Capability.compartment (R.capabilities record)
        @ List.map R.Dependency.compartment (R.dependencies record) @ List.map R.Resource.compartment (R.resources record) in
      if List.exists (fun compartment -> charge budget 1; not (S.mem compartment target_compartments)) compartments then (
        diagnostic E.Fail "target_compartment" "A selected interface or dependency uses a compartment absent from the target." (Some id); invalidate id)) records;
    let ports = List.concat_map (fun (id,record) -> List.map (fun port -> keep budget 1; (id,P.id port),port) (R.ports record)) records in
    let port_map = List.fold_left (fun map (key,port) -> PM.add key port map) PM.empty ports in
    let connected = ref PM.empty in
    List.iter (fun connection -> charge budget 1;
      let consumer = C.Connection.consumer_instance connection,C.Connection.consumer_port connection in
      let count = Option.value ~default:0 (PM.find_opt consumer !connected) in keep budget 1; connected := PM.add consumer (count+1) !connected;
      match PM.find_opt (C.Connection.producer_instance connection,C.Connection.producer_port connection) port_map, PM.find_opt consumer port_map with
      | Some producer,Some consumer_port ->
          node_work budget (P.to_json producer); node_work budget (P.to_json consumer_port);
          let checked = K.ports_compatible ~producer ~consumer:consumer_port in
          if not (K.passed checked) then diagnostic (status checked) "incompatible_ports" (String.concat " " (K.reasons checked)) (Some (fst consumer))
      | _ -> diagnostic E.Fail "missing_port" "A connection references an unknown instance or port." (Some (fst consumer))) (C.connections request);
    List.iter (fun ((id,port_id),port) -> charge budget 1;
      let count = Option.value ~default:0 (PM.find_opt (id,port_id) !connected) in
      if P.direction port = P.Input && count <> 1 then diagnostic (if count > 1 then E.Fail else E.Unknown)
        "input_connection_count" "Every input port requires exactly one producer." (Some id)) ports;
    let upstream = ref (M.map (fun _ -> S.empty) instances) in
    List.iter (fun connection -> charge budget 1;
      let producer = C.Connection.producer_instance connection and consumer = C.Connection.consumer_instance connection in
      if M.mem producer instances && M.mem consumer instances then upstream := M.add consumer
          (add_set budget producer (M.find consumer !upstream)) !upstream) (C.connections request);
    if S.cardinal (fixed_point budget (M.bindings !upstream) S.empty) <> M.cardinal instances then
      diagnostic E.Unsupported "cyclic_port_connections" "The stateless interface profile cannot establish a solution for cyclic wiring." None;
    let capabilities = ref M.empty and kinds = ref M.empty and prerequisites = ref M.empty in
    List.iter (fun (id,record) -> keep budget 3;
      capabilities := M.add id (R.capabilities record) !capabilities;
      kinds := M.add id (match C.Instance.placement (M.find id instances) with C.Instance.Encoded_here -> E.Resolved_dependency.Encoded_here | C.Instance.Co_payload -> E.Resolved_dependency.Co_payload) !kinds;
      prerequisites := M.add id S.empty !prerequisites) records;
    List.iter (fun provider -> charge budget 1;
      let id = C.Provider.id provider in keep budget 3;
      capabilities := M.add id (C.Provider.capabilities provider) !capabilities;
      kinds := M.add id (match C.Provider.kind provider with C.Provider.Host -> E.Resolved_dependency.Host | C.Provider.External -> E.Resolved_dependency.External | C.Provider.Unresolved -> E.Resolved_dependency.Unresolved) !kinds;
      prerequisites := M.add id (set budget (C.Provider.depends_on provider)) !prerequisites;
      if C.Provider.kind provider = C.Provider.Unresolved then invalidate id;
      if not (List.mem target (C.Provider.supported_targets provider)) then (
        invalidate id; diagnostic E.Fail "provider_target" ("Provider " ^ Diagnostic_text.repr id ^ " does not support the target.") None);
      if List.exists (fun cap -> charge budget 1; not (S.mem (R.Capability.compartment cap) target_compartments)) (C.Provider.capabilities provider) then (
        invalidate id; diagnostic E.Fail "provider_compartment" ("Provider " ^ Diagnostic_text.repr id ^ " uses an undeclared compartment.") None);
      if C.Provider.kind provider = C.Provider.Host && not (S.subset (set budget (List.map R.Capability.id (C.Provider.capabilities provider)))
          (set budget (Build_request.Target.capabilities (C.target request)))) then (
        invalidate id; diagnostic E.Fail "host_capability" ("Provider " ^ Diagnostic_text.repr id ^ " claims a capability absent from the target.") None)) (C.providers request);
    let bindings = List.fold_left (fun map item -> add_values budget (C.Dependency_binding.instance_id item,C.Dependency_binding.requirement_id item) (C.Dependency_binding.provider_id item) map)
        PM.empty (C.dependency_bindings request) in
    let requirements = List.concat_map (fun (id,record) -> List.map (fun requirement -> keep budget 1; (id,R.Dependency.id requirement),requirement) (R.dependencies record)) records in
    let requirement_map = List.fold_left (fun map (key,value) -> PM.add key value map) PM.empty requirements in
    (* Only these two historical set-difference groups have native deterministic
       pair order; every other diagnostic retains original declaration order. *)
    PM.iter (fun (id,requirement) _ -> charge budget 1;
      if not (PM.mem (id,requirement) requirement_map) then diagnostic E.Fail "unknown_dependency_binding"
          ("Binding names undeclared dependency " ^ Diagnostic_text.repr requirement ^ ".") (Some id)) bindings;
    let selected = ref PM.empty and provisional = ref [] in
    List.iter (fun ((id,requirement_id),requirement) -> charge budget 1;
      let compatible cap = charge budget 1; R.Capability.id cap = R.Dependency.capability requirement && R.Capability.role cap = R.Dependency.role requirement
        && R.Capability.scope cap = R.Dependency.scope requirement && R.Capability.compartment cap = R.Dependency.compartment requirement in
      let candidates = M.bindings !capabilities |> List.filter_map (fun (key,caps) -> charge budget 1;
          if List.exists compatible caps then (keep budget 1; Some key) else None) in
      let explicit = find_values (id,requirement_id) bindings in
      let chosen,status = match explicit with
        | _ :: _ :: _ -> diagnostic E.Fail "duplicate_dependency_binding" "A dependency has multiple explicit bindings." (Some id); None,E.Fail
        | [provider] when List.mem provider candidates -> Some provider,E.Unknown
        | [_] -> diagnostic E.Fail "incompatible_provider" "The bound provider is absent or differs in capability meaning, role, scope or compartment." (Some id); None,E.Fail
        | [] -> (match candidates with [provider] -> Some provider,E.Unknown | _ ->
            if R.Dependency.required requirement then diagnostic E.Unknown (if candidates=[] then "missing_provider" else "ambiguous_provider")
              "A required dependency needs exactly one compatible provider or an explicit binding." (Some id); None,E.Unknown) in
      (match chosen with Some provider -> keep budget 1; selected := PM.add (id,requirement_id) provider !selected;
          if R.Dependency.required requirement then prerequisites := M.add id (add_set budget provider (M.find id !prerequisites)) !prerequisites
        | None -> if R.Dependency.required requirement then invalidate id);
      keep budget 1; provisional := ((id,requirement_id),chosen,status) :: !provisional) requirements;
    let pools = List.fold_left (fun map pool -> keep budget 1; M.add (C.Resource_pool.id pool) pool map) M.empty (C.resource_pools request) in
    let resource_bindings = List.fold_left (fun map binding -> add_values budget (C.Resource_binding.instance_id binding,C.Resource_binding.reservation_id binding)
        (C.Resource_binding.pool_id binding) map) PM.empty (C.resource_bindings request) in
    let reservations = List.concat_map (fun (id,record) -> List.map (fun resource -> keep budget 1; (id,R.Resource.id resource),resource) (R.resources record)) records in
    let reservation_map = List.fold_left (fun map (key,value) -> PM.add key value map) PM.empty reservations in
    List.iter (fun ((id,reservation),resource) -> charge budget 1;
      match find_values (id,reservation) resource_bindings with
      | [pool] when M.mem pool pools -> let pool = M.find pool pools in
          prerequisites := M.add id (add_set budget (C.Resource_pool.provider_id pool) (M.find id !prerequisites)) !prerequisites;
          if R.Resource.amount resource = None || C.Resource_pool.capacity pool = None then invalidate id
      | _ -> invalidate id) reservations;
    let provider_lifetime provider id consumed =
      charge budget 1;
      match M.find_opt provider instances with None -> () | Some provider ->
        let provider = C.Instance.lifetime provider and consumer = C.Instance.lifetime (M.find id instances) in
        if C.Lifecycle.unit provider <> "s" || C.Lifecycle.unit consumer <> "s" then (
          diagnostic E.Unsupported "provider_lifecycle" "Provider availability requires lifecycle intervals in seconds." (Some id); invalidate id)
        else if N.compare (C.Lifecycle.start provider) (C.Lifecycle.start consumer) > 0 ||
          (match C.Lifecycle.end_time provider with None -> false | Some stop ->
            if consumed then N.compare stop (C.Lifecycle.start consumer) <= 0
            else match C.Lifecycle.end_time consumer with None -> true | Some ending -> N.compare stop ending < 0)
        then (diagnostic E.Fail "provider_lifecycle" "The provider does not cover the required consumer lifetime." (Some id); invalidate id) in
    List.iter (fun (key,chosen,_) -> match chosen with None -> () | Some provider -> provider_lifetime provider (fst key) false) (List.rev !provisional);
    List.iter (fun ((id,reservation),resource) -> charge budget 1;
      match find_values (id,reservation) resource_bindings with [pool] when M.mem pool pools ->
        provider_lifetime (C.Resource_pool.provider_id (M.find pool pools)) id (not (R.Resource.reusable resource)) | _ -> ()) reservations;
    let grounded = fixed_point budget (M.bindings !prerequisites) !invalid in
    resolved := List.rev !provisional |> List.map (fun ((id,requirement_id),chosen,initial_status) -> charge budget 1;
      let grounded_provider = match chosen with Some provider -> S.mem provider grounded | None -> false in
      if chosen <> None && not grounded_provider && R.Dependency.required (PM.find (id,requirement_id) requirement_map) then
        diagnostic E.Unknown "ungrounded_provider" "Provider prerequisites are missing, invalid, or circular; assumptions cannot establish their own guarantees." (Some id);
      let provider_kind = match chosen with None -> E.Resolved_dependency.Unresolved | Some provider -> M.find provider !kinds in
      let value = E.Resolved_dependency.make ~instance_id:id ~requirement_id ~provider_id:chosen ~provider_kind
          ~status:(if grounded_provider then E.Pass else initial_status) in reserve budget (E.Resolved_dependency.to_json value); value);
    let physical = ref PM.empty and physical_order = ref [] in
    List.iter (fun pool -> charge budget 1;
      let provider = C.Resource_pool.provider_id pool in
      let physical_provider = if M.find_opt provider !kinds = Some E.Resolved_dependency.Host then "@target_host" else provider in
      let key = physical_provider,C.Resource_pool.resource pool in
      if not (PM.mem key !physical) then (keep budget 1; physical_order := key :: !physical_order);
      physical := add_values budget key (C.Resource_pool.id pool) !physical) (C.resource_pools request);
    List.iter (fun key -> charge budget 1; if List.length (PM.find key !physical) > 1 then
      diagnostic E.Unsupported "aliased_resource_pool" "Multiple pool IDs alias one provider resource; explicit partitioning is unsupported." None) (List.rev !physical_order);
    PM.iter (fun (id,reservation) _ -> charge budget 1;
      if not (PM.mem (id,reservation) reservation_map) then diagnostic E.Fail "unknown_resource_binding"
        "Resource binding names no declared reservation." (Some id)) resource_bindings;
    let events = ref M.empty and pool_statuses = ref M.empty and used = ref S.empty in
    let pool_status id status = keep budget 1; pool_statuses := M.add id (status :: Option.value ~default:[] (M.find_opt id !pool_statuses)) !pool_statuses in
    let event id time change = keep budget 1; events := M.add id ((time,change) :: Option.value ~default:[] (M.find_opt id !events)) !events in
    List.iter (fun ((id,reservation_id),reservation) -> charge budget 1;
      let bound = find_values (id,reservation_id) resource_bindings in
      match bound with
      | [pool] when M.mem pool pools ->
          used := add_set budget pool !used;
          let pool_record = M.find pool pools in
          if R.Resource.resource reservation <> C.Resource_pool.resource pool_record || R.Resource.unit reservation <> C.Resource_pool.unit pool_record
             || not (numeric_type_equal (R.Resource.dtype reservation) (C.Resource_pool.dtype pool_record)) then (
            pool_status pool E.Fail; diagnostic E.Fail "resource_unit_or_type" "Reservation and pool must match resource meaning, type and explicit units." (Some id))
          else if not (List.exists (fun cap -> charge budget 1; R.Capability.id cap = R.Resource.resource reservation && R.Capability.role cap = R.Resource.role reservation
              && R.Capability.scope cap = R.Resource.scope reservation && R.Capability.compartment cap = R.Resource.compartment reservation)
              (Option.value ~default:[] (M.find_opt (C.Resource_pool.provider_id pool_record) !capabilities))) then (
            pool_status pool E.Fail; diagnostic E.Fail "resource_provider_context" "A resource provider must match the reservation's exact role, contact scope and compartment." (Some id))
          else (match R.Resource.amount reservation with None -> pool_status pool E.Unknown;
            diagnostic E.Unknown "unknown_reservation" "A resource reservation amount is unknown." (Some id)
          | Some amount -> let lifetime = C.Instance.lifetime (M.find id instances) in
              if C.Lifecycle.unit lifetime <> "s" then (pool_status pool E.Unsupported;
                diagnostic E.Unsupported "unsupported_lifecycle" "Only explicit half-open lifecycle intervals in seconds are supported." (Some id))
              else (let amount = decimal budget amount in event pool (decimal budget (C.Lifecycle.start lifetime)) amount;
                match R.Resource.reusable reservation,C.Lifecycle.end_time lifetime with
                | true,Some ending -> event pool (decimal budget ending) (Q.neg amount) | _ -> ()))
      | _ -> diagnostic (if List.length bound > 1 then E.Fail else E.Unknown) "missing_resource_pool"
          "Every reservation requires exactly one declared resource pool." (Some id)) reservations;
    S.iter (fun id -> charge budget 1;
      let pool = M.find id pools in
      let add status code message = pool_status id status; diagnostic status code message None in
      let provider = C.Resource_pool.provider_id pool in
      if not (S.mem provider grounded) then add E.Unknown "resource_provider_unresolved" ("Pool " ^ Diagnostic_text.repr id ^ " has no grounded provider.");
      if not (List.exists (fun cap -> charge budget 1; R.Capability.id cap = C.Resource_pool.resource pool)
          (Option.value ~default:[] (M.find_opt provider !capabilities))) then
        add E.Fail "resource_provider_capability" ("Pool " ^ Diagnostic_text.repr id ^ " is not supplied by the named provider capability.");
      if C.Resource_pool.capacity pool = None then add E.Unknown "unknown_capacity"
          ("Pool " ^ Diagnostic_text.repr id ^ " capacity is unknown; missing measurement is not unlimited capacity.");
      if M.find_opt provider !kinds = Some E.Resolved_dependency.Host then (
        match List.assoc_opt (C.Resource_pool.resource pool) (Build_request.Target.resources (C.target request)) with
        | None -> add E.Unknown "unknown_host_capacity" ("Target does not declare capacity for host resource " ^ Diagnostic_text.repr (C.Resource_pool.resource pool) ^ ".")
        | Some capacity ->
            if not (numeric_type_equal (Measurement_contract.Scalar.dtype capacity) (C.Resource_pool.dtype pool))
               || Json.string (Json.field "unit" (Json.object_fields (Measurement_contract.Scalar.to_json capacity))) <> C.Resource_pool.unit pool
               || (match C.Resource_pool.capacity pool with None -> false | Some value -> N.compare value (N.of_json (Json.field "value" (Json.object_fields (Measurement_contract.Scalar.to_json capacity)))) > 0)
            then add E.Fail "host_capacity_mismatch" ("Pool " ^ Diagnostic_text.repr id ^ " exceeds or differs from the target host resource declaration."));
      let sorted = List.sort (fun (time,a) (other,b) -> let order = compare_q budget time other in if order=0 then compare_q budget a b else order)
          (Option.value ~default:[] (M.find_opt id !events)) in
      let current = ref Q.zero and peak = ref Q.zero in
      List.iter (fun (_,change) -> charge budget 1; current := add_q budget !current change;
        if compare_q budget !current !peak > 0 then peak := !current) sorted;
      (match C.Resource_pool.capacity pool with Some capacity when compare_q budget !peak (decimal budget capacity) > 0 ->
          add E.Fail "resource_overallocation" ("Pool " ^ Diagnostic_text.repr id ^ " exceeds its declared shared capacity.") | _ -> ());
      let peak_value = if Z.equal (Q.den !peak) Z.one then (
          let value = Q.num !peak in if Float.is_finite (Z.to_float value) then Some (N.Integer value) else None)
        else (let value = Q.to_float !peak in if Float.is_finite value then Some (N.Real value) else None) in
      if peak_value = None then add E.Unknown "resource_total_unrepresentable"
          ("Pool " ^ Diagnostic_text.repr id ^ " total exceeds finite artifact reporting; exact capacity comparison was retained.");
      let statuses = Option.value ~default:[] (M.find_opt id !pool_statuses) in
      let value = E.Resource_usage.make ~pool_id:id ~peak_reservation:(if List.mem E.Unknown statuses || List.mem E.Unsupported statuses then None else peak_value)
          ~capacity:(C.Resource_pool.capacity pool) ~unit:(C.Resource_pool.unit pool) ~status:(priority statuses) in
      reserve budget (E.Resource_usage.to_json value); keep budget 1; usage := value :: !usage) !used;
    finish () in
  try execute () with Finished result -> result
let check_with_usage ?parent ?(limits=default_limits) ~request ~registry () =
  let budget = create ?parent limits in
  let result = check_in budget ~request ~registry in
  result,{work=budget.initial - Work_budget.remaining budget.work;retained_items=budget.retained}
let check ?parent ?limits ~request ~registry () = fst (check_with_usage ?parent ?limits ~request ~registry ())
let replay ?parent ?(limits=default_limits) ~expected_request ~registry expected () =
  let budget = create ?parent limits in
  charge budget (E.Result.canonical_size expected + 1);
  let supplied = E.Result.to_json expected in
  let input = Work_budget.create_output ~profile:resource_profile ~error_code:"composition_report_limit"
      ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  Work_budget.reserve_json input supplied; node_work budget supplied;
  let actual = check_in budget ~request:expected_request ~registry in
  let actual = E.Result.to_json actual in node_work budget actual;
  Json.equal actual supplied
