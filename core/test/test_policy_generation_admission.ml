open Bioc_wire
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module F = Bioc_domain.Policy_operating_domain
module Source = Bioc_checker.Policy_check
module A = Bioc_checker.Policy_admission
module C = Bioc_checker.Policy_correspondence
module RA = Bioc_checker.Policy_realization_admission
module L = Bioc_compiler.Policy_lowering
let require condition message = if not condition then failwith message
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let replace key replacement value = Json.Object (List.map (fun (name,item) ->
  name,if name=key then replacement else item) (Json.object_fields value))
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000
      (really_input_string channel (in_channel_length channel)))
let capture action =
  let reversed = ref [] in
  let result = action (fun amount ->
    require (amount >= 0) "Generation charged a negative count";
    reversed := amount :: !reversed) in
  result,List.rev !reversed
let fail_at label action count =
  let marker = {Diagnostic.code="generation_admission_stop";message=label;path=None} in
  let calls = ref 0 in
  match action (fun _ -> incr calls; if !calls=count then raise (Diagnostic.Error marker)) with
  | _ -> failwith (label ^ ": injected exhaustion returned an admission/result")
  | exception Diagnostic.Error actual ->
      require (actual == marker && !calls=count)
        (label ^ ": callback failure was replaced, swallowed or followed by further work")
let compare label expected action =
  let result,charges = capture action in
  require (Canonical.encode result = Canonical.encode expected)
    (label ^ ": count-only callback changed the old result bytes");
  let count = List.length charges in
  require (count>2 && List.exists (fun amount -> amount>1) charges)
    (label ^ ": dynamic scalar/collection work was not charged");
  List.iter (fail_at label action) [1;max 2 (count/2);count];
  charges
let diagnostic action =
  match action () with
  | _ -> failwith "Invalid independent authority unexpectedly admitted"
  | exception Diagnostic.Error value -> value
let equality_controls () =
  let first=String.make 129 'a' and second=String.make 257 'b' in
  let left=Json.Object [second,Json.String "second";first,Json.String "first"]
  and right=Json.Object [first,Json.String "first";second,Json.String "second"] in
  let action charge =
    let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge=charge end) in
    Json.Bool (Meter.Json.equal left right) in
  let charges=compare "object equality" (Json.Bool true) action in
  (* Each key occurs only twice in these inputs. Sorting both objects and
     comparing their aligned keys must charge more than an input-size scan. *)
  List.iter (fun size -> require (List.length (List.filter ((=) size) charges)>=4)
    "Object equality did not charge repeated sorting and key comparisons") [129;257];
  let marker={Diagnostic.code="generation_equality_stop";message="key comparison";path=None} in
  let keys=ref 0 and stopped=ref false in
  (match action (fun amount ->
      require (not !stopped) "Object equality continued after comparator exhaustion";
      if amount=129 then (incr keys; if !keys=3 then (stopped:=true;raise (Diagnostic.Error marker)))) with
   | _ -> failwith "Object equality omitted comparator exhaustion"
   | exception Diagnostic.Error actual ->
       require (actual==marker && !keys=3) "Object equality replaced comparator exhaustion");
  let module Legacy=Bioc_checker.Policy_generation_meter.Make(struct
    let charge=Bioc_checker.Policy_generation_meter.no_charge end) in
  List.iter (fun (left,right) ->
    require (Legacy.Json.equal left right=Json.equal left right) "Legacy JSON equality changed";
    let module Meter=Bioc_checker.Policy_generation_meter.Make(struct let charge _=() end) in
    require (Meter.Json.equal left right=Json.equal left right) "Metered JSON equality changed")
    [left,right;Json.Float (-0.),Json.Float 0.;Json.Int Z.one,Json.Float 1.;
      Json.Array [left;Json.Null],Json.Array [right;Json.Null];
      Json.Array [left],Json.Array [right;Json.Null]]
let () =
  require (Array.length Sys.argv=2) "Supply the original policy implementation-binding fixture";
  equality_controls ();
  let cases = Json.array (get "cases" (read Sys.argv.(1))) in
  let original = List.hd cases in
  let request = R.of_json (get "request" original) in
  let document = R.document request and descriptors = R.definitions request in
  let assessment = Source.check document in
  require (text "status" assessment="valid") "Original source is not independently source-valid";
  ignore (compare "source assessment" assessment (fun charge -> Source.check ~charge document));
  let admitted = A.admit ~document ~descriptors in
  let admission_charges = compare "operational admission" (A.report admitted)
    (fun charge -> A.report (A.admit_metered ~charge ~document ~descriptors)) in
  let behavior = L.lower admitted in
  ignore (compare "source correspondence" (C.check ~expected_document:document ~descriptors behavior)
    (fun charge -> C.check ~charge ~expected_document:document ~descriptors behavior));
  let realization = RA.admit ~request ~behavior in
  let realization_charges = compare "realization admission" (RA.report realization)
    (fun charge -> RA.report (RA.admit_metered ~charge ~request ~behavior)) in
  (* These are literal control-flow obligations: realization first admits the
     original, then correspondence independently admits it again. The earlier
     explicit producer admission is the third admission; none is cached away. *)
  let rec consume expected actual = match expected,actual with
    | [],rest -> rest
    | left::ls,right::rs when left=right -> consume ls rs
    | _ -> failwith "Repeated operational admission lost its complete callback stream" in
  let remaining = consume admission_charges realization_charges in
  ignore (consume admission_charges remaining);
  let meter_calls = ref 0 in
  let charged = RA.admit_metered ~charge:(fun _ -> incr meter_calls) ~request ~behavior in
  let before = !meter_calls in
  let bridge = List.hd (R.catalog_bindings request) in
  RA.require_model charged ~entry_id:bridge.entry_id (List.hd bridge.models);
  require (!meter_calls>before) "Model membership escaped its retained invocation meter";
  let domain = R.operating_domain request in
  let identity validated = Json.String (F.cursor_digest (F.initial validated)) in
  ignore (compare "domain compatibility" (identity (F.validate_for ~behavior domain))
    (fun charge -> identity (F.validate_for ~charge ~behavior domain)));
  (* A syntactically valid, stale external descriptor remains the same semantic
     rejection under a nonexhausting callback; metering cannot relabel it. *)
  let raw = O.descriptors_to_json descriptors in
  let rows = Json.array (get "definitions" raw) in
  let first = List.hd rows in
  let pin = get "definition" first in
  let old = text "digest" pin in
  let changed = (if old.[0]='0' then "1" else "0") ^ String.sub old 1 63 in
  let first = replace "definition" (replace "digest" (Json.String changed) pin) first in
  let stale = O.descriptors_of_json (replace "definitions" (Json.Array (first::List.tl rows)) raw) in
  let old_error = diagnostic (fun () -> A.admit ~document ~descriptors:stale) in
  let new_error = diagnostic (fun () -> A.admit_metered ~charge:(fun _ -> ()) ~document ~descriptors:stale) in
  require (old_error=new_error && old_error.code="policy_operational_unsupported")
    "Metered admission changed the old descriptor diagnostic";
  Printf.printf "Generation admissions retain original bytes, three admission passes, model membership and terminal callback failures\n"
