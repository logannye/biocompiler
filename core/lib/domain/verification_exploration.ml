open Bioc_wire
module N = Runtime_number
module D = Execution_data
module E = Realization_evidence
module Strings = Set.Make(String)
module String_map = Map.Make(String)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let option_json encode = function None -> Json.Null | Some value -> encode value
let require ?path condition message = Diagnostic.require ?path condition "verification_exploration" message
let limit ?path condition = Diagnostic.require ?path condition "verification_exploration_limit"
    "Verification workflow exceeds its native resource boundary."
module Codec = struct
  type limits = { max_bytes:int; max_nodes:int; charge_work:int -> unit }
  type size = { bytes:int; nodes:int }
  let make_limits ?(max_bytes=67_108_864) ?(max_nodes=1_000_000) ?(charge=(fun _ -> ())) () =
    Diagnostic.require (max_bytes > 0 && max_bytes <= 67_108_864 && max_nodes > 0 && max_nodes <= 1_000_000)
      "verification_exploration_limits" "Workflow codec limits must be positive reductions.";
    {max_bytes;max_nodes;charge_work=charge}
  let default_limits = make_limits ()
  let limits_json value = obj ["profile",str "biocompiler.verification_workflow.records.v1";
    "max_bytes",Json.int value.max_bytes;"max_nodes",Json.int value.max_nodes;
    "node_accounting",str "values_and_object_keys";"max_depth",Json.int Limits.max_depth;
    "max_string_bytes",Json.int Limits.max_string_bytes;"max_number_chars",Json.int Limits.max_number_chars]
  let charge value amount = limit (amount >= 0); value.charge_work amount
  let maximum_nodes value = value.max_nodes
  let maximum_bytes value = value.max_bytes
  let length limits values =
    let rec loop count = function [] -> count | _ :: rest ->
      charge limits 1; limit (count < limits.max_nodes); loop (count+1) rest in loop 0 values
  let sort_work count key_bytes =
    let rec height n result = if n <= 1 then result else height (n/2) (result+1) in
    (count+key_bytes+1) * (4 * height count 1)
  let sort_cost limits count key_bytes = charge limits (sort_work count key_bytes)
  let utf8 text = try Json.validate_utf8 text with Diagnostic.Error error when error.code="invalid_utf8" ->
    Diagnostic.fail "verification_exploration" "Exploration text must be valid UTF-8."
  let quoted_size limits text =
    charge limits (4*(String.length text+1));
    limit (String.length text <= Limits.max_string_bytes); utf8 text;
    let bytes = ref 2 in
    String.iter (fun value -> bytes := !bytes + match value with
      | '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> 2
      | value when Char.code value < 32 -> 6 | _ -> 1) text;
    !bytes
  type visit = Enter of Json.t * int | Leave of Json.t
  type inspection = {size:size;measure_work:int;writer_work:int}
  (* The pass charges itself before visiting data and accumulates only the
     additional writer cost. Scalar types and per-object key volumes determine
     that cost; nonnumeric nodes no longer pay for two binary64 conversions. *)
  let inspect ?(limits=default_limits) ?(path="") value =
    let measure_work=ref 0 and writer_work=ref 0 in
    let original=limits in
    let limits={limits with charge_work=(fun amount->charge original amount; measure_work:= !measure_work+amount)} in
    let bytes = ref 0 and nodes = ref 0 and queued = ref 1 and pending = ref [Enter(value,0)] and active = ref [] in
    let add amount = limit ~path (amount >= 0 && amount <= limits.max_bytes - !bytes); bytes := !bytes+amount in
    let writer amount=writer_work:= !writer_work+amount in
    let node () = charge limits 1; limit ~path (!nodes < limits.max_nodes); incr nodes; writer 1 in
    let quoted text=writer(4*(String.length text+1)); quoted_size limits text in
    while !pending <> [] do
      charge limits (Limits.max_depth+1);
      let next = List.hd !pending in pending := List.tl !pending;
      match next with
      | Leave value -> active := List.filter (fun other -> other != value) !active
      | Enter(value,depth) ->
          decr queued; node (); limit ~path (depth <= Limits.max_depth);
          let enter count children =
            limit ~path (count <= limits.max_nodes - !nodes - !queued);
            queued := !queued + count;
            Diagnostic.require ~path (not (List.exists (fun other -> other == value) !active))
              "verification_exploration_cycle" "Cyclic workflow JSON value.";
            active := value :: !active; pending := Leave value :: !pending;
            List.iter (fun child -> pending := Enter(child,depth+1) :: !pending) children in
          (match value with
          | Json.Null -> add 4 | Json.Bool value -> add (if value then 4 else 5)
          | Json.String text -> add (quoted text)
          | Json.Int value ->
              let cost=Z.numbits value+1 in charge limits cost; writer cost;
              limit ~path (Z.numbits value <= 4*Limits.max_number_chars);
              let text = Z.to_string value in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
          | Json.Float value -> charge limits 4096; writer 4096; add (String.length (Canonical.float_string value))
          | Json.Array values ->
              let count = length limits values in limit ~path (count <= limits.max_nodes - !nodes - !queued);
              writer count; add (2+max 0 (count-1)); enter count values
          | Json.Object fields ->
              let count = length limits fields in limit ~path (count <= (limits.max_nodes - !nodes - !queued)/2);
              add (2+max 0 (count-1)+count);
              let key_bytes = List.fold_left (fun total (key,_) -> node (); let size = quoted key in
                add size; total+String.length key) 0 fields in
              let sorting=sort_work count key_bytes in charge limits sorting; writer(sorting+4*count);
              let sorted = List.sort (fun (a,_) (b,_) -> String.compare a b) fields in
              let previous = ref None in
              List.iter (fun (key,_) -> Diagnostic.require ~path (!previous<>Some key) "duplicate_key"
                "Duplicate workflow JSON object key."; previous:=Some key) sorted;
              enter count (List.rev_map snd fields))
    done; {size={bytes = !bytes; nodes = !nodes};measure_work= !measure_work;writer_work= !writer_work}
  let measure ?limits ?path raw=(inspect ?limits ?path raw).size
  let preflight ?limits ?path raw = ignore (measure ?limits ?path raw)
  let encode ?(limits=default_limits) raw =
    let inspected=inspect ~limits raw in
    charge limits(inspected.writer_work+3*inspected.size.bytes);
    let encoded = Canonical.encode_bounded ~max_bytes:limits.max_bytes raw in
    limit (String.length encoded=inspected.size.bytes); encoded
  let fingerprint ?(limits=default_limits) raw =
    let encoded=encode ~limits raw in charge limits(String.length encoded); Canonical.sha256 encoded
  type work_bounds={measure:int;encode:int;fingerprint:int}
  let work_bounds (size:size) =
    limit(size.bytes>=0 && size.bytes<=67_108_864 && size.nodes>=0 && size.nodes<=1_000_000);
    (* At most 20 merge-sort levels and 129 active-ancestor comparisons.
       Number conversion uses at most four units per decimal character for
       integers, or 4096 per binary64. See the public plan for the pass census. *)
    {measure=88*size.bytes+4608*size.nodes+1;
     encode=180*size.bytes+9216*size.nodes+2;
     fingerprint=181*size.bytes+9216*size.nodes+3}

end
type number = N.t
type frame = D.Input_frame.t
type check = E.Check_result.t
let exploration_version = "biocompiler.boolean_exploration.v0.1"
let input_exploration_version = "biocompiler.boolean_input_exploration.v0.1"
let claim_scope = "Only the declared Boolean contact states on the variable time lattice with the exact fixed suffix and finite horizon are enumerated. Completion means enumeration coverage, not whole-profile, temporal or biological refinement."
let input_claim_scope = "Only the declared Boolean cell and contact states on the variable time lattice with the exact fixed suffix and finite horizon are enumerated. Completion means enumeration coverage, not whole-profile, temporal or biological refinement."
type packed = {json:Json.t;fingerprint:string;size:int}
let pack limits json = let canonical = Codec.encode ~limits json in
  Codec.charge limits(String.length canonical);
  {json;fingerprint=Canonical.sha256 canonical;size=String.length canonical}
let bounded limits values = ignore (Codec.length limits values); values
let records_size limits encode values =
  limit(Codec.maximum_bytes limits>=2);
  let remaining_bytes = ref (Codec.maximum_bytes limits-2) and remaining_nodes = ref (Codec.maximum_nodes limits-1) and separator=ref 0 in
  List.iter (fun value -> let size = Codec.measure ~limits (encode value) in
    limit (size.bytes + !separator <= !remaining_bytes && size.nodes <= !remaining_nodes);
    remaining_bytes:= !remaining_bytes-size.bytes - !separator; separator:=1; remaining_nodes:= !remaining_nodes-size.nodes) (bounded limits values);
  {Codec.bytes=Codec.maximum_bytes limits - !remaining_bytes;nodes=Codec.maximum_nodes limits - !remaining_nodes}
let reserve_records limits encode values=ignore(records_size limits encode values)

let record_inspected limits path label keys raw =
  let inspected=Codec.inspect ~limits ~path raw in
  match raw with Json.Object values ->
    Codec.sort_cost limits (List.length values) (List.fold_left (fun n (key,_) -> n+String.length key) 0 values);
    require ~path (List.sort String.compare (List.map fst values)=List.sort String.compare keys) ("Invalid fields in "^label^"."); values,inspected
  | _ -> Diagnostic.fail ~path "verification_exploration" ("Invalid fields in "^label^".")
let record limits path label keys raw=fst(record_inspected limits path label keys raw)
let get path fields key = Json.field ~path:(path^"/"^key) key fields
let optional parse = function Json.Null -> None | value -> Some(parse value)
let text limits label raw = match raw with
  | Json.String value -> Codec.charge limits (String.length value+1); Codec.utf8 value;
      (try ignore(Json.name (str value)) with Diagnostic.Error error when error.code="invalid_name" ->
        Diagnostic.fail "verification_exploration" (label^" must be a nonempty string.")); value
  | _ -> Diagnostic.fail "verification_exploration" (label^" must be a nonempty string.")
let name limits label value = text limits label (str value)
let names limits label values =
  let seen = ref Strings.empty in
  let values=List.map (name limits label) (bounded limits values) in
  List.iter(fun value->Codec.charge limits(64*(String.length value+1));
    require(not(Strings.mem value !seen))(label^" must be unique."); seen:=Strings.add value !seen)values; values
let raw_names limits label = function Json.Array values -> names limits label (List.map (text limits label) values)
  | _ -> Diagnostic.fail "verification_exploration" (label^" must be an array.")
let integer label lower upper = function Json.Int value when Z.compare value (Z.of_int lower)>=0 && Z.compare value (Z.of_int upper)<=0 -> Z.to_int value
  | _ -> Diagnostic.fail "verification_exploration" ("Invalid "^label^".")
let time value =
  let valid = match value with N.Integer value -> Z.sign value>=0 && Float.is_finite(Z.to_float value)
    | N.Real value -> Float.is_finite value && value>=0. in
  require valid "Exploration times must be finite nonnegative numbers."; value
let raw_time = function Json.Int value -> time(N.Integer value) | Json.Float value -> time(N.Real value)
  | _ -> Diagnostic.fail "verification_exploration" "Exploration times must be finite nonnegative numbers."
let history_json values = arr (List.map D.Input_frame.to_json values)
let frames_of_json ?(limits=Codec.default_limits) ?(path="") raw =
  Codec.preflight ~limits ~path raw;
  let frames = match raw with Json.Array values -> values | _ ->
    Diagnostic.fail ~path "verification_exploration" "History must be an array." in
  List.mapi (fun index raw ->
    let path = path^"/"^string_of_int index in
    let fields,inspected = record_inspected limits path "InputFrame" ["time";"signals";"contacts"] raw in
    let samples raw = match raw with Json.Object fields ->
      List.iter (fun (_,raw) -> ignore(record limits path "SignalSample" ["value";"present";"high";"low"] raw)) fields
      | _ -> Diagnostic.fail ~path "verification_exploration" "Samples must be a mapping." in
    let contacts=match get path fields "contacts" with Json.Object contacts->contacts
      |_->Diagnostic.fail ~path "verification_exploration" "Contacts must be a mapping." in
    samples (get path fields "signals");
    List.iter(fun(_,values)->samples values)contacts;
    (* Existing typed leaf decoders have fixed nested preflights, but no charge
       callback. Pay their complete bounded pass envelope before invoking them. *)
    Codec.charge limits(8*inspected.measure_work+64*inspected.size.bytes+64*inspected.size.nodes);
    D.Input_frame.of_json ~path raw) frames
let check_of_json ?(limits=Codec.default_limits) ?(path="") raw =
  let inspected=Codec.inspect ~limits ~path raw in
  (* CheckResult -> dependency/horizon, diagnostic/source, counterexample/
     expected/interval/source, and coverage. Each layer measures on entry and
     packing; twelve complete-volume traversals cover every nested path. *)
  Codec.charge limits(12*inspected.measure_work+64*inspected.size.bytes+64*inspected.size.nodes);
  E.Check_result.of_json ~path raw
let history_fingerprint ?(limits=Codec.default_limits) values =
  ignore(bounded limits values); limit(Codec.maximum_bytes limits>=2);
  let remaining_bytes=ref(Codec.maximum_bytes limits-2) and remaining_nodes=ref(Codec.maximum_nodes limits-1) in
  (* The ASCII history identity is streamed one frame at a time. Its complete
     UTF-8 inventory is checked incrementally; no growing prefix is rescanned.
     Before the inherited two-pass ASCII encoder, pay the measured traversal
     and writer costs plus the at-most-sixfold escaped scalar expansion. *)
  let hash = ref Digestif.SHA256.empty in
  let feed text = Codec.charge limits (String.length text+1); hash:=Digestif.SHA256.feed_string !hash text in
  feed "["; let separator=ref 0 in
  List.iter(fun frame ->
    let raw=D.Input_frame.to_json frame in let inspected=Codec.inspect ~limits raw in
    let size=inspected.size in
    limit(size.bytes + !separator <= !remaining_bytes && size.nodes <= !remaining_nodes);
    remaining_bytes:= !remaining_bytes-size.bytes - !separator; remaining_nodes:= !remaining_nodes-size.nodes;
    Codec.charge limits(inspected.measure_work+inspected.writer_work+42*size.bytes+8*size.nodes+1);
    if !separator=1 then feed "," else separator:=1;
    feed(Legacy_ascii.encode raw))values;
  feed "]"; Digestif.SHA256.to_hex(Digestif.SHA256.get !hash)

let validate_history ?(limits=Codec.default_limits) ?(initial=true) values until =
  reserve_records limits D.Input_frame.to_json values; ignore(time until);
  require (not initial || (match values with first::_ -> N.equal (D.Input_frame.time first) N.zero | [] -> false))
    "History must start at time zero.";
  let previous=ref None in List.iter(fun frame -> Codec.charge limits 1; let current=D.Input_frame.time frame in
    require ((match !previous with None->true|Some before->N.compare before current<0) && N.compare current until<=0)
      "History times must increase within the fixed horizon."; previous:=Some current) values
let stable_dependencies result =
  obj (List.remove_assoc "history" (Json.object_fields(E.Dependency_snapshot.to_json(E.Check_result.dependencies result))))
let validate_result ?(limits=Codec.default_limits) ?stable result history until =
  Codec.preflight ~limits (E.Check_result.to_json result);
  let dependencies=Json.object_fields(E.Dependency_snapshot.to_json(E.Check_result.dependencies result)) in
  require (Json.field "history" dependencies=str(history_fingerprint ~limits history))
    "Evaluator returned stale or unrelated history evidence.";
  let horizon=Json.object_fields(Json.field "horizon" dependencies) in
  let same raw = match raw with Json.Int value -> N.equal (N.Integer value) until | Json.Float value -> N.equal(N.Real value) until | _->false in
  require (same(Json.field "until" horizon) && same(Json.field "effective" horizon))
    "Evaluator changed the explicit finite horizon.";
  Option.iter(fun expected -> require (Codec.fingerprint ~limits(stable_dependencies result)=Codec.fingerprint ~limits expected)
    "Evaluator changed model, request, contract, domain, target or tool dependencies.") stable
module Observation = struct
  type t = {packed:packed;signal_id:string;field:string}
  let schema_version="biocompiler.boolean_observation.v0.1"
  let make ?(limits=Codec.default_limits) ~signal_id ?(field="present") () =
    let signal_id=name limits "Signal ID" signal_id in
    require (List.mem field ["present";"high";"low"]) "Exploration requires a Boolean observation field.";
    let packed=pack limits(obj["schema_version",str schema_version;"signal_id",str signal_id;"field",str field]) in
    {packed;signal_id;field}
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits path "BooleanObservation" ["schema_version";"signal_id";"field"] raw in
    let get=get path fields in
    Diagnostic.require ~path (get "schema_version"=str schema_version) "unsupported_schema" "Unsupported exploration schema.";
    let signal_id=text limits "Signal ID" (get "signal_id") in
    let field=match get "field" with Json.String value->value|_->"" in make ~limits ~signal_id ~field ()
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let signal_id value=value.signal_id
  let field value=value.field
end
module Bounds = struct
  type kind = Contact | Mixed
  type t = {packed:packed;kind:kind;contact_ids:string list;observations:Observation.t list;
    cell_observations:Observation.t list;variable_times:number list;until:number;fixed_suffix:frame list;
    max_histories:int;state_count:Z.t;possible_histories:Z.t;fixed_suffix_size:Codec.size}
  let schema = function Contact->"biocompiler.boolean_contact_config.v0.1"|Mixed->"biocompiler.boolean_input_config.v0.1"
  let observations_unique limits message values =
    let seen=ref Strings.empty in List.iter(fun item ->
      let key=Codec.encode ~limits(arr[str(Observation.signal_id item);str(Observation.field item)]) in
      Codec.charge limits(64*(String.length key+1)); require(not(Strings.mem key !seen)) message;
      seen:=Strings.add key !seen) values
  let complete_samples limits samples observations =
    Codec.charge limits(256*(List.fold_left(fun n item->n+Observation.canonical_size item)0 observations+
      List.fold_left(fun n (id,_)->n+String.length id)0 samples+1));
    let expected=List.fold_left(fun result item -> Strings.add(Observation.signal_id item) result) Strings.empty observations in
    let actual=List.fold_left(fun result (key,_) -> Codec.charge limits(64*(String.length key+1)); Strings.add key result) Strings.empty samples in
    require(Strings.equal expected actual) "Snapshots require the complete declared signal inventory.";
    List.iter(fun(signal_id,sample) ->
      List.iter(fun(key,value) -> Codec.charge limits 32;
        let declared=List.exists(fun item -> Observation.signal_id item=signal_id && Observation.field item=key) observations in
        require (if declared then match value with Json.Bool _->true|_->false else value=Json.Null)
          "Snapshot observations differ from the declared Boolean bounds.") (Json.object_fields(D.Sample.to_json sample))) samples
  let complete_snapshot limits contact_ids observations cell_observations frame =
    List.iter(fun(key,_)->Codec.charge limits(64*(String.length key+1)))(D.Input_frame.contacts frame);
    require(List.for_all(fun(key,_)->List.mem key contact_ids)(D.Input_frame.contacts frame))
      "Snapshot contains contacts outside the Boolean bounds.";
    complete_samples limits (D.Input_frame.signals frame) cell_observations;
    List.iter(fun(_,samples)->complete_samples limits samples observations)(D.Input_frame.contacts frame)
  let make ?(limits=Codec.default_limits) ~kind ~contact_ids ~observations ~variable_times ~until
      ?(fixed_suffix=[]) ?(max_histories=10000) ?(cell_observations=[]) () =
    ignore(bounded limits contact_ids); reserve_records limits Observation.to_json observations;
    reserve_records limits Observation.to_json cell_observations; ignore(bounded limits variable_times);
    let fixed_suffix_size=records_size limits D.Input_frame.to_json fixed_suffix in
    (* Python's mixed subclass validates cell declarations before its base. *)
    if kind=Mixed then (
      require(List.length cell_observations<=8) "Mixed exploration supports at most eight Boolean cell observations.";
      observations_unique limits "Duplicate Boolean cell observation." cell_observations;
      require(cell_observations<>[] || observations<>[]) "Mixed bounds need an observation.";
      Codec.charge limits(64*(List.fold_left(fun n item->n+Observation.canonical_size item)0 observations+
        List.fold_left(fun n item->n+Observation.canonical_size item)0 cell_observations+1));
      require(not(List.exists(fun a -> List.exists(fun b -> Observation.signal_id a=Observation.signal_id b) observations) cell_observations))
        "A signal cannot be both cell-local and contact-local.")
    else require(cell_observations=[]) "Contact-only bounds cannot contain cell observations.";
    let contact_ids=names limits "Contact IDs" contact_ids in
    let lower=if kind=Mixed then 0 else 1 in
    require(List.length contact_ids>=lower && List.length contact_ids<=8)
      "Exploration supports at most eight fixed contact IDs; contact-only bounds require one.";
    require(List.length observations>=lower && List.length observations<=8)
      "Exploration supports one to eight Boolean observations.";
    require((contact_ids<>[])=(observations<>[]))
      "Contact observations and contact IDs must either both be present or both be empty.";
    observations_unique limits "Duplicate Boolean observation." observations;
    require(List.length variable_times>=1 && List.length variable_times<=16)
      "Exploration needs one to sixteen variable times.";
    let variable_times=List.map time variable_times in
    let rec increasing=function first::(second::_ as rest)->N.compare first second<0 && increasing rest|_->true in
    require(N.equal(List.hd variable_times)N.zero && increasing variable_times)
      "Variable lattice must start at zero and strictly increase.";
    let until=time until in
    let last=List.fold_left(fun _ value->value)N.zero variable_times in
    require(N.compare last until<=0) "Variable lattice exceeds the horizon.";
    validate_history ~limits ~initial:false fixed_suffix until;
    require(match fixed_suffix with []->true|first::_->N.compare(D.Input_frame.time first)last>0)
      "Fixed suffix must follow all variable times.";
    List.iter(complete_snapshot limits contact_ids observations cell_observations)fixed_suffix;
    require(max_histories>=1 && max_histories<=100000) "Invalid history evaluation cap.";
    Codec.charge limits 8192;
    let radix=Z.succ(Z.shift_left Z.one(List.length observations)) in
    let state_count=Z.mul(Z.shift_left Z.one(List.length cell_observations))(Z.pow radix(List.length contact_ids)) in
    let possible_histories=Z.pow state_count(List.length variable_times) in
    let fields=["schema_version",str(schema kind);"contact_ids",arr(List.map str contact_ids);
      "observations",arr(List.map Observation.to_json observations);"variable_times",arr(List.map N.to_json variable_times);
      "until",N.to_json until;"fixed_suffix",history_json fixed_suffix;"max_histories",Json.int max_histories] in
    let fields=if kind=Mixed then fields@["cell_observations",arr(List.map Observation.to_json cell_observations)] else fields in
    let packed=pack limits(obj fields) in
    {packed;kind;contact_ids;observations;cell_observations;variable_times;until;fixed_suffix;max_histories;state_count;possible_histories;
      fixed_suffix_size}
  let decode ?(limits=Codec.default_limits) ?(path="") kind raw =
    let label=if kind=Contact then "BooleanContactConfig" else "BooleanInputConfig" in
    let keys=["schema_version";"contact_ids";"observations";"variable_times";"until";"fixed_suffix";"max_histories"] in
    let keys=if kind=Mixed then keys@["cell_observations"] else keys in
    let fields=record limits path label keys raw in let get=get path fields in
    Diagnostic.require ~path (get "schema_version"=str(schema kind)) "unsupported_schema" "Unsupported exploration schema.";
    let observations key=match get key with Json.Array values->List.mapi(fun i->Observation.of_json ~limits ~path:(path^"/"^key^"/"^string_of_int i))values
      |_->Diagnostic.fail ~path "verification_exploration" "Exploration records must be an array." in
    let observations=observations "observations" in
    let fixed_suffix=frames_of_json ~limits ~path:(path^"/fixed_suffix")(get "fixed_suffix") in
    let cell_observations=if kind=Mixed then match get "cell_observations" with
      Json.Array values->List.mapi(fun i->Observation.of_json ~limits ~path:(path^"/cell_observations/"^string_of_int i))values
      |_->Diagnostic.fail ~path "verification_exploration" "Exploration records must be an array." else [] in
    (* Import first decodes every nested artifact, then follows constructor order. *)
    if kind=Mixed then (
      require(List.length cell_observations<=8) "Mixed exploration supports at most eight Boolean cell observations.";
      observations_unique limits "Duplicate Boolean cell observation." cell_observations;
      require(cell_observations<>[] || observations<>[]) "Mixed bounds need an observation.";
      Codec.charge limits(64*(List.fold_left(fun n item->n+Observation.canonical_size item)0 observations+
        List.fold_left(fun n item->n+Observation.canonical_size item)0 cell_observations+1));
      require(not(List.exists(fun a->List.exists(fun b->Observation.signal_id a=Observation.signal_id b)observations)cell_observations))
        "A signal cannot be both cell-local and contact-local.");
    let contact_ids=raw_names limits "Contact IDs" (get "contact_ids") in
    let lower=if kind=Mixed then 0 else 1 in
    require(List.length contact_ids>=lower && List.length contact_ids<=8)
      "Exploration supports at most eight fixed contact IDs; contact-only bounds require one.";
    require(List.length observations>=lower && List.length observations<=8) "Exploration supports one to eight Boolean observations.";
    require((contact_ids<>[])=(observations<>[])) "Contact observations and contact IDs must either both be present or both be empty.";
    observations_unique limits "Duplicate Boolean observation." observations;
    let raw_times=match get "variable_times" with Json.Array values when List.length values>=1 && List.length values<=16->values
      |_->Diagnostic.fail ~path "verification_exploration" "Exploration needs one to sixteen variable times." in
    let variable_times=List.map raw_time raw_times in
    let rec increasing=function first::(second::_ as tail)->N.compare first second<0 && increasing tail|_->true in
    require(N.equal(List.hd variable_times)N.zero && increasing variable_times) "Variable lattice must start at zero and strictly increase.";
    let until=raw_time(get "until") in
    let last=List.fold_left(fun _ current->current)N.zero variable_times in
    require(N.compare last until<=0) "Variable lattice exceeds the horizon.";
    validate_history ~limits ~initial:false fixed_suffix until;
    require(match fixed_suffix with []->true|first::_->N.compare(D.Input_frame.time first)last>0) "Fixed suffix must follow all variable times.";
    List.iter(complete_snapshot limits contact_ids observations cell_observations)fixed_suffix;
    let max_histories=integer "history evaluation cap" 1 100000 (get "max_histories") in
    make ~limits ~kind ~contact_ids ~observations ~variable_times ~until ~fixed_suffix ~max_histories ~cell_observations ()
  let contact_of_json ?limits ?path raw=decode ?limits ?path Contact raw
  let input_of_json ?limits ?path raw=decode ?limits ?path Mixed raw
  let of_json ?(limits=Codec.default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    let fields=match raw with Json.Object fields->fields|_->Diagnostic.fail ~path "verification_exploration" "Boolean bounds must be an object." in
    let schema_value=List.assoc_opt "schema_version" fields in
    require ~path (match schema_value with Some(Json.String _)->true|_->false) "Boolean bounds schema must be text.";
    if schema_value=Some(str(schema Contact)) then contact_of_json ~limits ~path raw
    else if schema_value=Some(str(schema Mixed)) then input_of_json ~limits ~path raw
    else Diagnostic.fail ~path "unsupported_schema" "Unsupported Boolean bounds schema."
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let kind value=value.kind
  let contact_ids value=value.contact_ids
  let observations value=value.observations
  let cell_observations value=value.cell_observations
  let variable_times value=value.variable_times
  let until value=value.until
  let fixed_suffix value=value.fixed_suffix
  let max_histories value=value.max_histories
  let state_count value=value.state_count
  let possible_histories value=value.possible_histories
  let boolean_samples limits observations code =
    let samples=List.mapi(fun index observation ->
      Codec.charge limits(64*(String.length(Observation.signal_id observation)+String.length(Observation.field observation)+1));
      Observation.signal_id observation,Observation.field observation,Z.testbit code index)observations in
    let values=List.fold_left(fun result (signal,field,value) ->
      let previous=match List.assoc_opt signal result with None->[]|Some value->value in
      (signal,(field,value)::previous)::List.remove_assoc signal result)[] samples in
    List.map(fun(signal,fields) -> signal,D.Sample.make ?present:(List.assoc_opt "present" fields)
      ?high:(List.assoc_opt "high" fields) ?low:(List.assoc_opt "low" fields)())values
  let snapshot_raw limits value ~time:at ~code =
    Codec.charge limits (Z.numbits code+4096);
    require(Z.sign code>=0 && Z.compare code value.state_count<0) "Boolean snapshot index exceeds its declared state space.";
    let remaining,cell=Z.ediv_rem code(Z.shift_left Z.one(List.length value.cell_observations)) in
    let signals=boolean_samples limits value.cell_observations cell in
    let radix=Z.succ(Z.shift_left Z.one(List.length value.observations)) in
    let _,contacts=List.fold_left(fun(code,result)identity ->
      let remaining,state=Z.ediv_rem code radix in
      if Z.equal state Z.zero then remaining,result else
        remaining,(identity,boolean_samples limits value.observations(Z.pred state))::result)
      (remaining,[])value.contact_ids in
    let samples values=obj(List.map(fun(id,sample)->id,D.Sample.to_json sample)values) in
    obj["time",N.to_json at;"signals",samples signals;"contacts",obj(List.map(fun(id,values)->id,samples values)(List.rev contacts))]
  let snapshot ?(limits=Codec.default_limits) value ~time ~code =
    let raw=snapshot_raw limits value ~time ~code in let size=Codec.measure ~limits raw in
    Codec.charge limits(64*size.bytes+64*size.nodes+1); D.Input_frame.of_json raw
  let history_at ?(limits=Codec.default_limits) value index =
    Codec.charge limits (Z.numbits index+8192);
    require(Z.sign index>=0 && Z.compare index value.possible_histories<0) "Boolean history index exceeds its declared lattice.";
    let _,codes=List.fold_left(fun(index,values)_ -> let next,code=Z.ediv_rem index value.state_count in next,code::values)
      (index,[])value.variable_times in
    let raw_prefix=List.map2(fun at code->snapshot_raw limits value ~time:at ~code)value.variable_times codes in
    let remaining_bytes=ref(Codec.maximum_bytes limits-2) and remaining_nodes=ref(Codec.maximum_nodes limits-1) and separator=ref 0 in
    let reserve raw=let size=Codec.measure ~limits raw in
      limit(size.bytes + !separator <= !remaining_bytes && size.nodes <= !remaining_nodes);
      remaining_bytes:= !remaining_bytes-size.bytes - !separator; separator:=1; remaining_nodes:= !remaining_nodes-size.nodes;
      Codec.charge limits(64*size.bytes+64*size.nodes+1) in
    List.iter reserve raw_prefix;
    (* Bounds constructors validated and froze the suffix. Reuse its exact
       occurrence census instead of traversing that immutable suffix twice per
       lattice point. The only new list spine is the <=16-frame prefix. *)
    let suffix=value.fixed_suffix_size in
    if suffix.nodes>1 then (
      limit(suffix.bytes-2 + !separator <= !remaining_bytes && suffix.nodes-1 <= !remaining_nodes));
    let prefix=List.map D.Input_frame.of_json raw_prefix in
    Codec.charge limits(List.length prefix); prefix@value.fixed_suffix
end

let decode_array parse = function Json.Array values -> List.mapi parse values
  | _ -> Diagnostic.fail "verification_exploration" "Exploration records must be an array."
let schema_check path expected actual = Diagnostic.require ~path (actual=str expected)
    "unsupported_schema" "Unsupported exploration schema."
let string_or_empty = function Json.String value -> value | _ -> ""
let outcome_name = function E.Pass->"pass"|E.Fail->"fail"|E.Unknown->"unknown"|E.Unsupported->"unsupported"
module Report = struct
  type t = {packed:packed;kind:Bounds.kind;config:Bounds.t;results:check list;
    explorer_version:string;claim_scope:string;outcome_counts:(E.outcome*int)list;
    coverage_totals:E.Requirement_coverage.t list;shared_dependencies:Json.t;
    evaluated_histories:int;complete:bool;all_passed:bool}
  let schema = function Bounds.Contact->"biocompiler.boolean_exploration_report.v0.1"
    |Bounds.Mixed->"biocompiler.boolean_input_exploration_report.v0.1"
  let derived=["state_count";"possible_histories";"evaluated_histories";"complete";"all_passed";
    "outcome_counts";"coverage_totals";"shared_dependencies"]
  let make ?(limits=Codec.default_limits) ~kind ~config ~results ?explorer_version:version ?claim_scope:scope () =
    reserve_records limits E.Check_result.to_json results;
    let evaluated_histories=List.length results in
    require(evaluated_histories>0 && evaluated_histories<=Bounds.max_histories config &&
      Z.compare(Z.of_int evaluated_histories)(Bounds.possible_histories config)<=0) "Invalid evaluated history count.";
    let expected_version,expected_scope=match kind with Bounds.Contact->exploration_version,claim_scope
      |Bounds.Mixed->input_exploration_version,input_claim_scope in
    let explorer_version=Option.value version ~default:expected_version and claim_scope=Option.value scope ~default:expected_scope in
    require(kind=Bounds.kind config && explorer_version=expected_version && claim_scope=expected_scope)
      "Invalid exploration version or claim scope.";
    let stable=ref None and requirements=ref None in
    List.iteri(fun index result ->
      validate_result ~limits ?stable:!stable result (Bounds.history_at ~limits config(Z.of_int index)) (Bounds.until config);
      stable:=Some(stable_dependencies result);
      let ids=E.Check_result.checked_requirement_ids result in
      Codec.charge limits(E.Check_result.canonical_size result+1);
      require(match !requirements with None->true|Some expected->expected=ids) "Evaluator changed checked requirement inventory.";
      requirements:=Some ids)results;
    let complete=Z.equal(Z.of_int evaluated_histories)(Bounds.possible_histories config) in
    Codec.charge limits(5*evaluated_histories+1);
    let all_passed=complete && List.for_all(fun item->E.Check_result.outcome item=E.Pass)results in
    let outcome_counts=List.map(fun outcome->outcome,List.fold_left(fun n item->if E.Check_result.outcome item=outcome then n+1 else n)0 results)
      [E.Pass;E.Fail;E.Unknown;E.Unsupported] in
    let totals=ref String_map.empty in
    List.iter(fun result->List.iter(fun coverage ->
      let id=E.Requirement_coverage.requirement_id coverage in
      Codec.charge limits(64*(String.length id+1)+8*E.Requirement_coverage.canonical_size coverage);
      let a,b,c,d=match String_map.find_opt id !totals with None->Z.zero,Z.zero,Z.zero,Z.zero|Some value->value in
      totals:=String_map.add id (Z.add a(E.Requirement_coverage.activation_deadlines_checked coverage),
        Z.add b(E.Requirement_coverage.inactive_deadlines_checked coverage),
        Z.add c(E.Requirement_coverage.incomplete_episode_count coverage),
        Z.add d(E.Requirement_coverage.cancelled_episode_count coverage)) !totals)(E.Check_result.coverage result))results;
    Codec.charge limits(1+List.fold_left(fun n result->n+E.Check_result.canonical_size result)0 results);
    let coverage_totals=List.map(fun(id,(a,b,c,d))->E.Requirement_coverage.make ~requirement_id:id
      ~activation_deadlines_checked:a ~inactive_deadlines_checked:b ~incomplete_episode_count:c ~cancelled_episode_count:d ())
      (String_map.bindings !totals) in
    let shared_dependencies=stable_dependencies(List.hd results) in
    let packed=pack limits(obj["schema_version",str(schema kind);"config",Bounds.to_json config;
      "results",arr(List.map E.Check_result.to_json results);"explorer_version",str explorer_version;"claim_scope",str claim_scope;
      "state_count",Json.Int(Bounds.state_count config);"possible_histories",Json.Int(Bounds.possible_histories config);
      "evaluated_histories",Json.int evaluated_histories;"complete",Json.Bool complete;"all_passed",Json.Bool all_passed;
      "outcome_counts",obj(List.map(fun(outcome,count)->outcome_name outcome,Json.int count)outcome_counts);
      "coverage_totals",arr(List.map E.Requirement_coverage.to_json coverage_totals);"shared_dependencies",shared_dependencies]) in
    {packed;kind;config;results;explorer_version;claim_scope;outcome_counts;coverage_totals;shared_dependencies;
      evaluated_histories;complete;all_passed}
  let decode ?(limits=Codec.default_limits) ?(path="") kind raw =
    let label=match kind with Bounds.Contact->"ExplorationReport"|Bounds.Mixed->"BooleanInputExplorationReport" in
    let fields=record limits path label (["schema_version";"config";"results";"explorer_version";"claim_scope"]@derived) raw in
    let get=get path fields in schema_check path (schema kind)(get "schema_version");
    let config=(match kind with Bounds.Contact->Bounds.contact_of_json|Bounds.Mixed->Bounds.input_of_json)
      ~limits ~path:(path^"/config")(get "config") in
    let results=decode_array(fun index raw->check_of_json ~limits ~path:(path^"/results/"^string_of_int index)raw)(get "results") in
    let result=make ~limits ~kind ~config ~results ~explorer_version:(string_or_empty(get "explorer_version"))
      ~claim_scope:(string_or_empty(get "claim_scope")) () in
    let actual=Json.object_fields result.packed.json in
    List.iter(fun key->require ~path (Codec.fingerprint ~limits(get key)=Codec.fingerprint ~limits(List.assoc key actual))
      ("Inconsistent exploration "^key^"."))derived; result
  let contact_of_json ?limits ?path raw=decode ?limits ?path Bounds.Contact raw
  let input_of_json ?limits ?path raw=decode ?limits ?path Bounds.Mixed raw
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    Codec.preflight ~limits ~path raw;
    let fields=match raw with Json.Object value->value|_->Diagnostic.fail ~path "verification_exploration" "Verification result must be an object." in
    match List.assoc_opt "schema_version" fields with
    |Some(Json.String value) when value=schema Bounds.Contact->contact_of_json ~limits ~path raw
    |Some(Json.String value) when value=schema Bounds.Mixed->input_of_json ~limits ~path raw
    |Some(Json.String _)->Diagnostic.fail ~path "unsupported_schema" "Unsupported verification result schema."
    |_->Diagnostic.fail ~path "verification_exploration" "Verification result schema must be text."
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let kind value=value.kind
  let config value=value.config
  let results value=value.results
  let explorer_version value=value.explorer_version
  let claim_scope value=value.claim_scope
  let state_count value=Bounds.state_count value.config
  let possible_histories value=Bounds.possible_histories value.config
  let evaluated_histories value=value.evaluated_histories
  let complete value=value.complete
  let all_passed value=value.all_passed
  let outcome_counts value=value.outcome_counts
  let coverage_totals value=value.coverage_totals
  let shared_dependencies value=value.shared_dependencies
end
module Failure_signature = struct
  type kind=Response|Diagnostic
  type t={packed:packed;kind:kind;requirement_id:string option;code:string option;rule_id:string option;
    specification_id:string option;contact_id:string option;state:string option;node_id:string option}
  let schema_version="biocompiler.failure_signature.v0.1"
  let kind_name=function Response->"response"|Diagnostic->"diagnostic"
  let make ?(limits=Codec.default_limits) ~kind ?requirement_id ?code ?rule_id ?specification_id ?contact_id ?state ?node_id () =
    List.iter(fun(label,value)->Option.iter(fun value->ignore(name limits label value))value)
      ["requirement_id",requirement_id;"code",code;"rule_id",rule_id;"specification_id",specification_id;
        "contact_id",contact_id;"state",state;"node_id",node_id];
    (match kind with Response->require(requirement_id<>None && rule_id<>None && specification_id<>None &&
      (state=Some "active" || state=Some "inactive") && code=None && node_id=None) "Invalid response failure signature."
    |Diagnostic->require(code<>None && rule_id=None && specification_id=None && contact_id=None && state=None)
      "Invalid diagnostic failure signature.");
    let packed=pack limits(obj["schema_version",str schema_version;"kind",str(kind_name kind);
      "requirement_id",option_json str requirement_id;"code",option_json str code;"rule_id",option_json str rule_id;
      "specification_id",option_json str specification_id;"contact_id",option_json str contact_id;
      "state",option_json str state;"node_id",option_json str node_id]) in
    {packed;kind;requirement_id;code;rule_id;specification_id;contact_id;state;node_id}
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits path "FailureSignature" ["schema_version";"kind";"requirement_id";"code";"rule_id";
      "specification_id";"contact_id";"state";"node_id"] raw in
    let get=get path fields in schema_check path schema_version(get "schema_version");
    let kind=match get "kind" with Json.String "response"->Response|Json.String "diagnostic"->Diagnostic
      |_->Diagnostic.fail ~path "verification_exploration" "Invalid failure signature kind." in
    let value key=optional(text limits key)(get key) in
    let requirement_id=value "requirement_id" in let code=value "code" in let rule_id=value "rule_id" in
    let specification_id=value "specification_id" in let contact_id=value "contact_id" in let state=value "state" in let node_id=value "node_id" in
    make ~limits ~kind ?requirement_id ?code ?rule_id ?specification_id ?contact_id ?state ?node_id ()
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let kind value=value.kind
  let requirement_id value=value.requirement_id
  let code value=value.code
  let rule_id value=value.rule_id
  let specification_id value=value.specification_id
  let contact_id value=value.contact_id
  let state value=value.state
  let node_id value=value.node_id
  let from_counterexample ?(limits=Codec.default_limits) item =
    Codec.charge limits(E.Counterexample.canonical_size item+1);
    make ~limits ~kind:Response ~requirement_id:(E.Counterexample.requirement_id item)
      ~rule_id:(E.Counterexample.rule_id item) ~specification_id:(E.Counterexample.specification_id item)
      ?contact_id:(E.Counterexample.contact_id item)
      ~state:(match E.Counterexample.state item with E.Active->"active"|E.Inactive->"inactive") ()
  let from_diagnostic ?(limits=Codec.default_limits) item =
    Codec.charge limits(E.Check_diagnostic.canonical_size item+1);
    make ~limits ~kind:Diagnostic ?requirement_id:(E.Check_diagnostic.requirement_id item)
      ~code:(E.Check_diagnostic.code item) ?node_id:(E.Check_diagnostic.node_id item) ()
  let matches ?(limits=Codec.default_limits) value result =
    Codec.charge limits(E.Check_result.canonical_size result+value.packed.size+1);
    E.Check_result.outcome result=E.Fail && match value.kind with
    |Response->List.exists(fun item->(from_counterexample ~limits item).packed.fingerprint=value.packed.fingerprint)(E.Check_result.counterexamples result)
    |Diagnostic->List.exists(fun item->(from_diagnostic ~limits item).packed.fingerprint=value.packed.fingerprint)(E.Check_result.diagnostics result)
end

(* Python frame dictionaries compare numbers by numeric value, unlike canonical
   identity. Both arguments are already bounded and have normalized map order. *)
let rec frame_json_equal left right = match left,right with
  |Json.Int a,Json.Float b|Json.Float b,Json.Int a->N.equal(N.Integer a)(N.Real b)
  |Json.Float a,Json.Float b->a=b
  |Json.Array a,Json.Array b->List.length a=List.length b && List.for_all2 frame_json_equal a b
  |Json.Object a,Json.Object b->List.length a=List.length b &&
    List.for_all2(fun(ak,av)(bk,bv)->ak=bk && frame_json_equal av bv)a b
  |_->Json.equal left right
module Reduction = struct
  type t={packed:packed;original_history:frame list;history:frame list;until:number;signature:Failure_signature.t;
    original_result:check;result:check;evaluations:int;one_minimal:bool;reducer_version:string}
  let schema_version="biocompiler.history_reduction.v0.1"
  let make ?(limits=Codec.default_limits) ~original_history ~history ~until ~signature ~original_result ~result
      ~evaluations ~one_minimal ?(reducer_version=exploration_version) () =
    validate_history ~limits original_history until; validate_history ~limits history until;
    require(evaluations>=1 && evaluations<=100000) "Invalid reduction evaluation count.";
    require(reducer_version=exploration_version) "Unsupported reduction policy version.";
    validate_result ~limits original_result original_history until;
    validate_result ~limits ~stable:(stable_dependencies original_result) result history until;
    Codec.charge limits(E.Check_result.canonical_size original_result+E.Check_result.canonical_size result+1);
    require(E.Check_result.checked_requirement_ids original_result=E.Check_result.checked_requirement_ids result)
      "Reduction changed checked requirement inventory.";
    require(Failure_signature.matches ~limits signature original_result && Failure_signature.matches ~limits signature result)
      "Reduction changed its selected explicit failure.";
    let frame_equal a b=let a=D.Input_frame.to_json a and b=D.Input_frame.to_json b in
      let sa=Codec.measure ~limits a and sb=Codec.measure ~limits b in Codec.charge limits(sa.bytes+sb.bytes+sa.nodes+sb.nodes);
      frame_json_equal a b in
    let rec subset originals current = match current with []->true|item::rest ->
      (match originals with []->false|original::tail ->
        Codec.charge limits 1;
        let order=N.compare(D.Input_frame.time original)(D.Input_frame.time item) in
        if order<0 then subset tail current else order=0 && frame_equal original item && subset tail rest) in
    require(frame_equal(List.hd history)(List.hd original_history) && subset original_history history)
      "Reduction may delete snapshots only; initial state and horizon stay fixed.";
    reserve_records limits D.Input_frame.to_json original_history; reserve_records limits D.Input_frame.to_json history;
    let packed=pack limits(obj["schema_version",str schema_version;"original_history",history_json original_history;
      "history",history_json history;"until",N.to_json until;"signature",Failure_signature.to_json signature;
      "original_result",E.Check_result.to_json original_result;"result",E.Check_result.to_json result;
      "evaluations",Json.int evaluations;"one_minimal",Json.Bool one_minimal;"reducer_version",str reducer_version]) in
    {packed;original_history;history;until;signature;original_result;result;evaluations;one_minimal;reducer_version}
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits path "ReductionResult" ["schema_version";"original_history";"history";"until";"signature";
      "original_result";"result";"evaluations";"one_minimal";"reducer_version"] raw in
    let get=get path fields in schema_check path schema_version(get "schema_version");
    let original_history=frames_of_json ~limits ~path:(path^"/original_history")(get "original_history") in
    let history=frames_of_json ~limits ~path:(path^"/history")(get "history") in
    let signature=Failure_signature.of_json ~limits ~path:(path^"/signature")(get "signature") in
    let original_result=check_of_json ~limits ~path:(path^"/original_result")(get "original_result") in
    let result=check_of_json ~limits ~path:(path^"/result")(get "result") in
    let until=raw_time(get "until") in validate_history ~limits original_history until; validate_history ~limits history until;
    let evaluations=integer "reduction evaluation count" 1 100000 (get "evaluations") in
    let one_minimal=match get "one_minimal" with Json.Bool value->value|_->Diagnostic.fail ~path "verification_exploration" "Minimality marker must be Boolean." in
    make ~limits ~original_history ~history ~until ~signature ~original_result ~result ~evaluations ~one_minimal
      ~reducer_version:(string_or_empty(get "reducer_version")) ()
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let original_history value=value.original_history
  let history value=value.history
  let until value=value.until
  let signature value=value.signature
  let original_result value=value.original_result
  let result value=value.result
  let evaluations value=value.evaluations
  let one_minimal value=value.one_minimal
  let reducer_version value=value.reducer_version
end
module Adversarial_config = struct
  type t={packed:packed;bounds:Bounds.t;seed:Z.t;random_cases:int}
  let schema_version="biocompiler.adversarial_history_config.v0.1"
  let make ?(limits=Codec.default_limits) ~bounds ~seed ?(random_cases=16) () =
    require(Bounds.kind bounds=Bounds.Contact && List.length(Bounds.variable_times bounds)>=3)
      "Adversarial transition cases need at least three variable times.";
    Codec.charge limits(Z.numbits seed+1);
    require(Z.sign seed>=0 && Z.numbits seed<=64) "Invalid history seed.";
    require(random_cases>=0 && random_cases<=1000) "Invalid random case count.";
    let packed=pack limits(obj["schema_version",str schema_version;"bounds",Bounds.to_json bounds;
      "seed",Json.Int seed;"random_cases",Json.int random_cases]) in {packed;bounds;seed;random_cases}
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits path "AdversarialConfig" ["schema_version";"bounds";"seed";"random_cases"] raw in
    let get=get path fields in schema_check path schema_version(get "schema_version");
    let bounds=Bounds.contact_of_json ~limits ~path:(path^"/bounds")(get "bounds") in
    require(List.length(Bounds.variable_times bounds)>=3) "Adversarial transition cases need at least three variable times.";
    let seed=match get "seed" with Json.Int value when Z.sign value>=0 && Z.numbits value<=64->value
      |_->Diagnostic.fail ~path "verification_exploration" "Invalid history seed." in
    let random_cases=integer "random case count" 0 1000 (get "random_cases") in make ~limits ~bounds ~seed ~random_cases ()
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let bounds value=value.bounds
  let seed value=value.seed
  let random_cases value=value.random_cases
end
module History_case = struct
  type t={packed:packed;id:string;kind:string;history:frame list;until:number;config_fingerprint:string;intentionally_incomplete:bool}
  let schema_version="biocompiler.adversarial_history.v0.1"
  let identity value=String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value
  let make ?(limits=Codec.default_limits) ~id ~kind ~history ~until ~config_fingerprint ?(intentionally_incomplete=false) () =
    ignore(name limits "History case ID" id); ignore(name limits "History case kind" kind);
    validate_history ~limits history until; require(identity config_fingerprint) "Invalid generator configuration identity.";
    let packed=pack limits(obj["schema_version",str schema_version;"id",str id;"kind",str kind;
      "history",history_json history;"until",N.to_json until;"config_fingerprint",str config_fingerprint;
      "intentionally_incomplete",Json.Bool intentionally_incomplete]) in
    {packed;id;kind;history;until;config_fingerprint;intentionally_incomplete}
  let of_json ?(limits=Codec.default_limits) ?(path="") raw =
    let fields=record limits path "HistoryCase" ["schema_version";"id";"kind";"history";"until";"config_fingerprint";"intentionally_incomplete"] raw in
    let get=get path fields in schema_check path schema_version(get "schema_version");
    let history=frames_of_json ~limits ~path:(path^"/history")(get "history") in
    let id=text limits "History case ID" (get "id") in let kind=text limits "History case kind" (get "kind") in
    let until=raw_time(get "until") in validate_history ~limits history until;
    let config_fingerprint=string_or_empty(get "config_fingerprint") in require(identity config_fingerprint) "Invalid generator configuration identity.";
    let intentionally_incomplete=match get "intentionally_incomplete" with Json.Bool value->value
      |_->Diagnostic.fail ~path "verification_exploration" "Incomplete-observation marker must be Boolean." in
    make ~limits ~id ~kind ~history ~until ~config_fingerprint ~intentionally_incomplete ()
  let to_json value=value.packed.json
  let fingerprint value=value.packed.fingerprint
  let canonical_size value=value.packed.size
  let id value=value.id
  let kind value=value.kind
  let history value=value.history
  let until value=value.until
  let config_fingerprint value=value.config_fingerprint
  let intentionally_incomplete value=value.intentionally_incomplete
end
