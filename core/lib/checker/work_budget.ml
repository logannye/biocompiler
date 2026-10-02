open Bioc_wire
type counter = { profile : string; error_code : string; mutable remaining : int;
  mutable exhaustion : Diagnostic.t option }
type t = counter list
let max_scopes = 16
let counter ~profile ~error_code ~maximum =
  Diagnostic.require (maximum >= 0) "invalid_work_budget" "A work allowance cannot be negative.";
  Diagnostic.require (String.length profile > 0 && String.length profile <= 256 &&
                      String.length error_code > 0 && String.length error_code <= 128)
    "invalid_work_budget" "A work scope requires bounded profile and error identities.";
  Json.validate_utf8 profile; Json.validate_utf8 error_code;
  {profile;error_code;remaining=maximum;exhaustion=None}
let create ~profile ~error_code ~maximum () = [counter ~profile ~error_code ~maximum]
let nested ~parent ~profile ~error_code ~maximum () =
  Diagnostic.require (List.length parent < max_scopes) "invalid_work_budget" "Nested work scope limit exceeded.";
  counter ~profile ~error_code ~maximum :: parent
let charge budget amount =
  Diagnostic.require (amount >= 0) "invalid_work_budget" "Work charges cannot be negative.";
  List.iter (fun scope -> if amount > scope.remaining then (
      let diagnostic = { Diagnostic.code=scope.error_code;
        message="Independent checker work limit exceeded under " ^ scope.profile ^ "."; path=None } in
      (* Retain the actual exception identity on every participating scope. This
         lets outer callers recognize descendant exhaustion without interpreting
         user-selected diagnostic strings or swallowing it as semantic failure. *)
      List.iter (fun scope -> scope.exhaustion <- Some diagnostic) budget;
      raise (Diagnostic.Error diagnostic))) budget;
  List.iter (fun scope -> scope.remaining <- scope.remaining - amount) budget
let is_exhaustion budget diagnostic = List.exists (fun scope ->
    match scope.exhaustion with Some previous -> previous == diagnostic | None -> false) budget
let remaining budget = List.fold_left (fun available scope -> min available scope.remaining) max_int budget
type output = { bytes : t; nodes : t; error_code : string; maximum_bytes : int }
let create_output ~profile ~error_code ~max_bytes ~max_nodes () =
  {bytes=create ~profile ~error_code ~maximum:max_bytes ();nodes=create ~profile ~error_code ~maximum:max_nodes ();
   error_code;maximum_bytes=max_bytes}
type frame = Value of Json.t * int | Array_tail of Json.t list * int * bool
  | Object_tail of (string * Json.t) list * int * bool
let reserve_json output raw =
  let bytes amount = charge output.bytes amount and node () = charge output.nodes 1 in
  let string value =
    bytes (String.length value); bytes 2;
    Json.validate_utf8 value;
    String.iter (function '"' | '\\' -> bytes 1 | '\b' | '\012' | '\n' | '\r' | '\t' -> bytes 1
      | value when Char.code value < 32 -> bytes 5 | _ -> ()) value in
  let rec visit = function
    | [] -> ()
    | Value (value,depth) :: rest ->
        Diagnostic.require (depth <= 128) output.error_code "Checker output nesting exceeds its fixed bound.";
        node ();
        (match value with
         | Json.String value -> string value; visit rest
         | Json.Array values -> bytes 2; visit (Array_tail (values,depth + 1,true) :: rest)
         | Json.Object fields -> bytes 2; visit (Object_tail (fields,depth + 1,true) :: rest)
         | Json.Int value ->
             Diagnostic.require (Z.numbits value / 4 <= output.maximum_bytes) output.error_code "Checker output number exceeds its publication budget.";
             bytes (String.length (Canonical.encode (Json.Int value))); visit rest
         | value -> bytes (String.length (Canonical.encode value)); visit rest)
    | Array_tail ([],_,_) :: rest | Object_tail ([],_,_) :: rest -> visit rest
    | Array_tail (value :: values,depth,first) :: rest ->
        if not first then bytes 1;
        visit (Value (value,depth) :: Array_tail (values,depth,false) :: rest)
    | Object_tail ((key,value) :: values,depth,first) :: rest ->
        if not first then bytes 1;
        node (); string key; bytes 1;
        visit (Value (value,depth) :: Object_tail (values,depth,false) :: rest) in
  visit [Value (raw,0)]
