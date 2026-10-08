open Bioc_wire
let checker_version = "biocompiler.ocaml.policy_check.v0.1"
module Make (Charge : sig val charge : int -> unit end) = struct
module Meter = Policy_generation_meter.Make(Charge)
module List = Meter.List
module String = Meter.String
module Json = Meter.Json
module D = Meter.Document
module Names = Meter.Names
module Seen = Meter.Seen
let ( ^ ) = Meter.append_string
let ( @ ) = List.append
let str x = Json.String x
let obj x = Json.Object x
let arr x = Json.Array x
let strings xs = arr (List.map str xs)
let get key = function Json.Object xs -> Option.value ~default:Json.Null (List.assoc_opt key xs) | _ -> Json.Null
let text key value = match get key value with Json.String s -> s | _ -> ""
let list key value = match get key value with Json.Array xs -> xs | _ -> []
let tag value = text "$type" value
let present value = value <> Json.Null
let equal = Json.equal
let names values = List.map (fun x -> match x with Json.String s -> s | _ -> "") values
let set values = List.fold_left (fun s x -> Seen.add x s) Seen.empty values
let unique values = List.length values = Seen.cardinal (set values)
let ref_id value = text "id" value
let type_kind value = text "kind" value
let quantity value = Q.mul (D.exact_decimal (text "amount" value)) (D.exact_decimal (text "scale" (get "unit" value)))
let compatible a b =
  type_kind a = type_kind b && equal (get "entity_kind" a) (get "entity_kind" b) &&
  (if type_kind a = "quantity" then
     let u = get "unit" a and v = get "unit" b in
     present u && present v && List.for_all (fun key -> equal (get key u) (get key v)) ["dimension";"quantity_kind";"reference"]
   else not (present (get "unit" a)) && not (present (get "unit" b)))
let typed kind = obj ["$type",str "TypeSpec";"kind",str kind;"unit",Json.Null;"entity_kind",Json.Null]
let quantity_type unit = obj ["$type",str "TypeSpec";"kind",str "quantity";"unit",unit;"entity_kind",Json.Null]
let literal_type expected = function
  | Json.Bool _ -> typed "truth"
  | Json.Int _ -> typed "integer"
  | Json.String "unknown" when type_kind expected = "truth" -> typed "truth"
  | Json.String _ -> typed "text"
  | value when tag value = "Quantity" -> quantity_type (get "unit" value)
  | _ -> Json.Null
let identifier value =
  let letter c = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') in
  String.length value > 0 && letter value.[0] && String.for_all (fun c -> letter c || (c >= '0' && c <= '9') || String.contains "_.:/-" c) value
let quantifiers = ["exists";"forall";"count"]
let reference_ops = ["observe";"state";"parameter";"updated";"effect_event";"message_event"]
let temporal_ops = ["holds";"recently";"followed_by";"within";"after";"until";"integrate"]
let deferred = ["policy_execution_and_lowering";"temporal_and_uncertainty_semantics";
  "safety_and_progress_satisfaction";"realizability_and_target_suitability"]

type state = {
  index : Json.t Names.t; definitions : (Json.t * string) Names.t;
  mutable diagnostics : Json.t list; mutable features : Seen.t;
  mutable assumptions : Seen.t; mutable obligations : Seen.t;
  mutable dependencies : Json.t Names.t; mutable work : int;
}
let spend state =
  Charge.charge 1;
  state.work <- state.work + 1;
  Diagnostic.require (state.work <= 8_000_000) "policy_check_limit" "Policy source analysis exceeds its deterministic work budget."
let document_path path = if path = "/document" || String.starts_with ~prefix:"/document/" path then path else "/document" ^ path
let issue state path code message = state.diagnostics <- obj ["code",str code;"message",str message;"path",str (document_path path)] :: state.diagnostics
let require state path condition code message = if not condition then issue state path code message
let feature state value = state.features <- Seen.add value state.features
let obligation state value = state.obligations <- Seen.add value state.obligations
let lookup state formals reference =
  let identity = ref_id reference in
  match (if text "kind" reference = "Parameter" then Names.find_opt identity formals else None) with
  | Some value -> value
  | None -> Option.value ~default:Json.Null (Names.find_opt identity state.index)
let resolve state formals path reference kinds =
  spend state;
  let value = lookup state formals reference in
  require state path (present value) "missing_reference" "Reference is absent from its lexical source scope.";
  if present value then require state path (text "kind" reference = tag value && (kinds = [] || List.mem (tag value) kinds))
      "reference_kind" "Reference has the wrong nominal declaration kind.";
  if present value && text "kind" reference = tag value && (kinds = [] || List.mem (tag value) kinds) then value else Json.Null
let definition state path reference categories =
  if not (present reference) then (issue state path "missing_definition" "A pinned semantic definition is required."; Json.Null)
  else match Names.find_opt (ref_id reference) state.definitions with
    | None -> issue state path "missing_definition" "Pinned semantic definition body is absent."; Json.Null
    | Some (value,digest) ->
        require state path (text "version" reference = text "version" value && text "digest" reference = digest)
          "definition_identity" "Semantic definition version/digest differs from its complete source body.";
        require state path (categories = [] || List.mem (text "category" value) categories)
          "definition_category" "Semantic definition category is incompatible with this use.";
        value
let duration state path ?(required=true) ?(positive=true) value =
  if not (present value) then require state path (not required) "missing_duration" "An explicit duration is required."
  else (
    let unit = get "unit" value in
    require state path (text "dimension" unit = "time" && text "quantity_kind" unit = "duration") "duration_dimension" "Duration requires time dimension and duration quantity kind.";
    let comparison = Q.compare (quantity value) Q.zero in
    require state path (if positive then comparison > 0 else comparison >= 0) "duration_bound" "Duration violates its positive/nonnegative bound.")
let rec subjects state expression =
  spend state;
  if List.mem (text "op" expression) ("call" :: quantifiers) then Seen.empty
  else
    let scope = get "scope" expression in
    let own = if text "kind" scope = "Subject" then Seen.singleton (ref_id scope) else Seen.empty in
    List.fold_left (fun acc item -> Seen.union acc (subjects state item)) own (list "args" expression)
let rec mentions state binding expression =
  spend state;
  if List.mem (text "op" expression) quantifiers && ref_id (get "binding" expression) = binding then false
  else ref_id (get "scope" expression) = binding || ref_id (get "ref" expression) = binding || List.exists (mentions state binding) (list "args" expression)
let scope_owner state scope =
  let subject = lookup state Names.empty (get "subject" scope) in
  match tag subject with
  | "Role" -> get "subject" scope
  | "Encounter" -> get "executor" subject
  | "Subject" -> if present (get "executor" subject) then get "executor" subject
      else get "executor" (lookup state Names.empty (get "encounter" subject))
  | _ -> Json.Null
let state_access state path executor store =
  let owner = scope_owner state (get "scope" store) in
  require state path (not (present owner) || equal owner executor) "executor_ownership" "State access crosses its declared executor scope.";
  let channel = lookup state Names.empty (get "coordination" store) in
  if tag channel = "Channel" then require state path (equal executor (get "sender" channel) || List.exists (equal executor) (list "recipients" channel))
      "executor_ownership" "Shared state access is outside its coordination participants."
let rec access state path executor expression =
  spend state;
  let target = lookup state Names.empty (get "ref" expression) in
  (match tag target with
  | "Observation" ->
      require state path (text "access" target = "cell") "observation_access" "Evaluator-only observations cannot control cellular behavior.";
      require state path (equal executor (get "observer" target)) "executor_ownership" "Observation interface belongs to another executor."
  | "Effect" -> require state path (equal executor (get "executor" target)) "executor_ownership" "Effect feedback belongs to another executor."
  | "StateStore" -> state_access state path executor target
  | "Message" ->
      let allowed = if text "value" expression = "received" then
          List.exists (equal executor) (list "recipients" (lookup state Names.empty (get "channel" target)))
        else equal executor (get "sender" target) in
      require state path allowed "executor_ownership" "Message phase is outside the executor's sender/recipient interface."
  | _ -> ());
  List.iteri (fun i arg -> access state (path ^ "/args/" ^ string_of_int i) executor arg) (list "args" expression)

let expression state formals bound path value =
  let op = text "op" value and args = list "args" value and result = get "value_type" value in
  let kind = type_kind result in
  let req ok code message = require state path ok code message in
  let signature count input output =
    req (if count < 0 then args <> [] else List.length args = count) "expression_arity" "Operation argument count differs from its signature.";
    req (input = "" || List.for_all (fun a -> type_kind (get "value_type" a) = input) args) "expression_input_type" "Operand types differ from the operation signature.";
    req (kind = output) "expression_result_type" "Result type differs from the operation signature." in
  feature state ("expression:" ^ op);
  if kind = "truth" then feature state "truth:three_valued";
  List.iter (fun reference -> let subject = lookup state formals reference in
    if tag subject = "Subject" && text "identity" subject = "bound" then
      req (Seen.mem (ref_id reference) bound) "unbound_subject" "Bound subject escaped its lexical quantifier.") [get "scope" value;get "ref" value];
  (match op with
  | "observe" | "state" | "parameter" | "updated" | "effect_event" | "message_event" ->
      req (args = [] && present (get "ref" value)) "expression_reference" "Reference operations require one nominal reference and no operands.";
      let kinds = match op with "observe"|"updated" -> ["Observation"] | "state" -> ["StateStore"] | "parameter" -> ["Parameter"] | "effect_event" -> ["Effect"] | _ -> ["Message"] in
      let target = resolve state formals (path ^ "/ref") (get "ref" value) kinds in
      if present target then (
        req (if List.mem op ["observe";"state";"parameter"] then compatible result (get "value_type" target) else kind = "event") "reference_value_type" "Reference expression type differs from its declaration.";
        let scope = match tag target with "Observation"|"Effect"|"Message" -> get "subject" target | "StateStore" -> get "subject" (get "scope" target) | _ -> Json.Null in
        req (equal scope (get "scope" value)) "expression_scope" "Reference expression scope differs from its declaration.")
  | "literal" ->
      req (args = []) "expression_arity" "Literals cannot carry operands.";
      if kind = "entity" then (
        let target = resolve state formals (path ^ "/ref") (get "ref" value) ["Role";"Subject";"Encounter"] in
        req (not (present (get "value" value)) && equal (get "scope" value) (get "ref" value)) "entity_literal" "Entity literal requires its exact nominal reference and scope.";
        if tag target = "Subject" then req (equal (get "entity_kind" result) (get "entity_kind" target)) "entity_type" "Entity literal differs from the subject's nominal type.")
      else req (not (present (get "ref" value)) && compatible result (literal_type result (get "value" value))) "literal_type" "Literal value differs from its declared type."
  | "all"|"any" -> signature (-1) "truth" "truth"
  | "not" -> signature 1 "truth" "truth"
  | "eq"|"ne"|"lt"|"le"|"gt"|"ge" ->
      signature 2 "" "truth";
      (match args with [a;b] ->
        req (compatible (get "value_type" a) (get "value_type" b)) "incompatible_operands" "Comparison requires compatible nominal types and units.";
        if not (List.mem op ["eq";"ne"]) then req (List.mem (type_kind (get "value_type" a)) ["integer";"quantity"]) "ordered_comparison" "Ordering requires numeric operands." | _ -> ())
  | "add"|"subtract"|"multiply"|"divide" ->
      req (List.length args = 2) "expression_arity" "Arithmetic requires two operands.";
      req (List.mem kind ["integer";"quantity"] && List.for_all (fun a -> List.mem (type_kind (get "value_type" a)) ["integer";"quantity"]) args) "expression_input_type" "Arithmetic requires explicit numeric operand/result types.";
      (match args with [a;b] when List.mem op ["add";"subtract"] -> req (compatible result (get "value_type" a) && compatible result (get "value_type" b)) "incompatible_operands" "Addition/subtraction requires compatible types and units." | _ -> ());
      if List.mem op ["multiply";"divide"] then obligation state "derived_quantity_operation_semantics"
  | "exists"|"forall"|"count" ->
      signature 1 "truth" (if op = "count" then "integer" else "truth");
      let domain = resolve state formals (path ^ "/scope") (get "scope" value) ["Subject"] in
      req (List.mem (text "entity_kind" domain) ["population";"region"]) "quantifier_domain" "Quantifier domain must be a population or region.";
      let binding = get "binding" value in
      let subject = resolve state formals (path ^ "/binding") binding ["Subject"] in
      req (text "identity" subject = "bound" && equal (get "domain" subject) (get "scope" value)) "quantifier_binding" "Bound subject must belong to the quantifier's exact domain.";
      req (not (Seen.mem (ref_id binding) bound)) "quantifier_shadowing" "Nested quantifiers require distinct bound identities.";
      req (List.length args = 1 && List.exists (mentions state (ref_id binding)) args) "unused_quantifier_binding" "Predicate must use the quantifier's own bound subject.";
      List.iter (fun arg -> req (Seen.subset (subjects state arg) (Seen.add (ref_id binding) bound)) "quantifier_free_subject" "Quantifier predicate contains unrelated free subjects.") args;
      obligation state "quantifier_membership_and_coverage"
  | "distinct" -> signature (-1) "entity" "truth"; req (List.length args >= 2) "expression_arity" "Distinct requires at least two entities."
  | "holds"|"recently" -> signature 1 "truth" "truth"
  | "followed_by"|"within"|"after" -> signature 2 "event" (if op = "within" then "truth" else "event")
  | "until" -> signature 2 "truth" "truth"
  | "rising" -> signature 1 "truth" "event"
  | "integrate" -> signature 1 "quantity" "quantity"; obligation state "integration_and_derived_unit_semantics"
  | "call" ->
      let body = definition state (path ^ "/contract") (get "contract" value) ["operation"] in
      if present body then (
        let parameters = list "parameters" body in
        req (List.length args = List.length parameters) "call_arity" "Call arguments must cover the formal signature.";
        if List.length args = List.length parameters then List.iter2 (fun arg parameter -> req (compatible (get "value_type" arg) (get "value_type" parameter)) "call_argument_type" "Call argument differs from its formal type.") args parameters;
        req (present (get "result" body) && compatible result (get "result" body)) "call_result_type" "Call result differs from its pinned signature.")
  | _ -> req false "unsupported_expression" "Operation is outside the native policy frontend profile.");
  if List.mem op temporal_ops then (
    ignore (resolve state formals (path ^ "/clock") (get "clock" value) ["Clock"]);
    if List.mem op ["holds";"recently";"followed_by";"within";"integrate"] then duration state (path ^ "/duration") (get "duration" value)
    else req (not (present (get "duration" value))) "unexpected_expression_field" "This temporal operation does not carry a duration.";
    let coverage = text "coverage" value in
    req (if List.mem op ["holds";"recently"] then List.mem coverage ["continuous";"sampled"] else if op = "integrate" then coverage = "sampled" else if op = "until" then coverage = "" else coverage = "event") "temporal_coverage" "Temporal coverage differs from the operation's required profile.")
  else req (List.for_all (fun key -> not (present (get key value))) ["duration";"clock";"coverage"]) "unexpected_expression_field" "Non-temporal operation carries temporal fields.";
  if present (get "coverage" value) then feature state ("coverage:" ^ text "coverage" value);
  req (not (present (get "contract" value)) || op = "call") "unexpected_expression_field" "Only calls carry operation contracts.";
  req (not (present (get "ref" value)) || List.mem op ("literal" :: reference_ops)) "unexpected_expression_field" "Unexpected reference field.";
  req (not (present (get "binding" value)) || List.mem op quantifiers) "unexpected_expression_field" "Only quantifiers carry bound identities.";
  req (not (present (get "scope" value)) || List.mem op (quantifiers @ reference_ops) || (op = "literal" && kind = "entity")) "unexpected_expression_field" "Unexpected scope field.";
  req (not (present (get "value" value)) || List.mem op ["literal";"effect_event";"message_event"]) "unexpected_expression_field" "Unexpected literal/event field.";
  if op = "effect_event" then req (List.mem (text "value" value) ["requested";"initiated";"completed";"outcome";"failed";"timed_out";"cancel_requested";"cancel_acknowledged";"ceased"]) "effect_event" "Unknown effect phase.";
  if op = "message_event" then req (List.mem (text "value" value) ["sent";"received";"acknowledged";"expired"]) "message_event" "Unknown message phase.";
  if not (List.mem op ("call" :: "distinct" :: quantifiers)) then
    req (Seen.cardinal (List.fold_left (fun acc arg -> Seen.union acc (subjects state arg)) Seen.empty args) <= 1) "mixed_subject_scope" "Cross-subject operands require explicit quantification or a relationship operation."

let parameter state path formal value =
  let value_type = get "value_type" value and supplied = get "value" value in
  require state path (formal || text "selection" value <> "fixed" || present supplied) "fixed_parameter_value" "Fixed parameters require a value.";
  if present supplied then require state path (compatible value_type (literal_type value_type supplied)) "parameter_type" "Parameter value differs from its declared type.";
  List.iter (fun name -> let bound = get name value in if present bound then (
    let unit = get "unit" bound in
    let count = type_kind value_type = "integer" && text "dimension" unit = "count" && text "quantity_kind" unit = "count" && not (present (get "reference" unit)) && Q.equal (D.exact_decimal (text "scale" unit)) Q.one in
    let valid = compatible value_type (quantity_type unit) || count in
    require state (path ^ "/" ^ name) valid "parameter_bound_type" "Parameter bounds require compatible quantity units or unscaled integer counts.";
    let amount = if tag supplied = "Quantity" && valid then Some (quantity supplied) else match supplied with Json.Int n when count -> Some (Q.of_bigint n) | _ -> None in
    Option.iter (fun amount -> require state (path ^ "/" ^ name) (if name = "lower" then Q.compare amount (quantity bound) >= 0 else Q.compare amount (quantity bound) <= 0) "parameter_bound_value" "Parameter value is outside its exact supplied bound.") amount)) ["lower";"upper"]

let scope state path value =
  let kind = text "kind" value and subject = get "subject" value in
  feature state ("scope:" ^ kind);
  if kind = "program" then require state path (not (present subject)) "scope_subject" "Program scope has no subject."
  else (
    let kinds = if kind = "executor" then ["Role"] else if kind = "encounter" then ["Encounter"] else ["Subject"] in
    let target = resolve state Names.empty (path ^ "/subject") subject kinds in
    if tag target = "Subject" then (
      require state path (text "identity" target <> "bound") "bound_subject_escape" "Bound quantifier subjects cannot be persistent declaration scopes.";
      if List.mem kind ["population";"lineage";"region"] then require state path (text "entity_kind" target = kind) "scope_entity" "Scope differs from its nominal subject kind."))

let rec walk state formals bound in_definition path value =
  spend state;
  match value with
  | Json.Array values -> List.iteri (fun i item -> walk state formals bound in_definition (path ^ "/" ^ string_of_int i) item) values
  | Json.Object fields ->
      let kind = tag value in
      let formals = if kind = "SemanticDefinition" then List.fold_left (fun acc p -> Names.add (ref_id p) p acc) Names.empty (list "parameters" value) else formals in
      let in_definition = in_definition || kind = "SemanticDefinition" in
      List.iter (fun key -> match get key value with Json.String s -> require state (path ^ "/" ^ key) (D.nonblank_text s) "empty_name" "Required name or meaning is empty." | _ -> ()) ["id";"name";"version";"description";"meaning";"expected";"question"];
      if List.mem kind ["PolicyProgram";"SemanticDefinition";"Parameter"] then require state (path ^ "/id") (identifier (ref_id value)) "invalid_identifier" "Identity is outside the ASCII namespaced identifier grammar.";
      List.iter (fun x -> match x with Json.String s -> state.assumptions <- Seen.add s state.assumptions | _ -> ()) (list "assumptions" value);
      (match kind with
      | "Ref" -> ignore (resolve state formals path value [])
      | "DefinitionRef" ->
          ignore (definition state path value []);
          state.dependencies <- Names.add (text "id" value ^ "\000" ^ text "version" value ^ "\000" ^ text "digest" value) value state.dependencies
      | "SemanticDefinition" ->
          require state path (unique (List.map ref_id (list "parameters" value))) "duplicate_parameter" "Formal parameter identities are duplicated.";
          obligation state ("semantic_definition:" ^ ref_id value)
      | "TypeSpec" ->
          require state path ((type_kind value = "quantity") = present (get "unit" value)) "type_unit" "Exactly quantity types carry units.";
          require state path ((type_kind value = "entity") = present (get "entity_kind" value)) "type_entity" "Exactly entity types carry nominal entity kinds."
      | "Unit" ->
          require state path (Q.sign (D.exact_decimal (text "scale" value)) > 0) "unit_scale" "Unit scale must be positive.";
          require state path (D.nonblank_text (text "dimension" value) && D.nonblank_text (text "quantity_kind" value)) "unit_dimension" "Unit dimension and quantity kind are required."
      | "Expr" -> expression state formals bound path value
      | "Scope" -> scope state path value
      | "Parameter" -> parameter state path in_definition value
      | "EffectLifecycle" ->
          ignore (definition state (path ^ "/contract") (get "contract" value) ["lifecycle"]);
          duration state (path ^ "/timeout") ~required:false (get "timeout" value);
          require state path (not (List.exists (fun key -> text key value = "request_cancel") ["on_loss";"on_unknown"]) || text "cancellation" value <> "unsupported") "cancellation_contract" "Requested cancellation is unsupported by the declared lifecycle."
      | "Arbitration" ->
          let order = names (list "order" value) in
          require state path (unique order) "arbitration_order" "Arbitration order repeats a participant.";
          require state path ((text "mode" value <> "priority" && text "tie" value <> "declared_order") || order <> []) "arbitration_order" "Priority/tie ordering requires explicit participants.";
          require state path ((text "write_conflict" value <> "contract" && text "preemption" value <> "contract") || present (get "contract" value)) "arbitration_contract" "Contract-defined arbitration requires a pinned interpretation.";
          obligation state "arbitration_fairness_and_conflict_resolution"
      | "SourceSpan" ->
          let nonnegative = function Json.Int n -> Z.sign n >= 0 | _ -> false in
          let positive = function Json.Int n -> Z.sign n > 0 | _ -> false in
          require state path (Names.mem (text "declaration_id" value) state.index && positive (get "line" value) && nonnegative (get "column" value)) "source_map" "Source correspondence requires a declared identity and valid line/column."
      | _ -> ());
      let lower = get "lower" value and upper = get "upper" value in
      if present lower && present upper then (
        let valid = compatible (quantity_type (get "unit" lower)) (quantity_type (get "unit" upper)) in
        require state path valid "bound_units" "Interval bounds have incompatible units.";
        if valid then require state path (Q.compare (quantity lower) (quantity upper) <= 0) "bound_order" "Lower bound exceeds upper bound under exact supplied scales.");
      List.iter (fun (key,item) ->
        let child_bound = if kind = "Expr" && key = "args" && List.mem (text "op" value) quantifiers then Seen.add (ref_id (get "binding" value)) bound else bound in
        walk state formals child_bound in_definition (path ^ "/" ^ key) item) fields
  | _ -> ()

let behavior state path executor value =
  let req condition code message = require state path condition code message in
  req (unique (List.map (fun assignment -> ref_id (get "state" assignment)) (list "assignments" value))) "duplicate_assignment" "An atomic behavior cannot assign the same state through indistinguishable write occurrences.";
  req (type_kind (get "value_type" (get "on" value)) = "event") "trigger_type" "Behavior trigger must be an event.";
  req (type_kind (get "value_type" (get "when" value)) = "truth") "guard_type" "Behavior guard must be truth-valued.";
  List.iter (fun key -> access state (path ^ "/" ^ key) executor (get key value)) ["on";"when"];
  req ((text "unknown" value = "transition") = present (get "unknown_target" value)) "unknown_target" "Only unknown-to-state transitions carry a target.";
  if tag value = "Rule" then req (text "unknown" value <> "transition") "unknown_transition_context" "Unknown-to-state behavior requires a machine transition.";
  let evidence = Seen.union (subjects state (get "on" value)) (subjects state (get "when" value)) in
  List.iteri (fun i reference ->
    let location = path ^ "/effects/" ^ string_of_int i in
    let requested_effect = resolve state Names.empty location reference ["Effect"] in
    if present requested_effect then (
      require state location (equal (get "executor" requested_effect) executor) "executor_ownership" "Requested effect belongs to another executor.";
      require state location (Seen.for_all (fun subject -> subject = ref_id (get "subject" requested_effect)) evidence || present (get "relationship" requested_effect)) "effect_relationship" "Redirected subject evidence requires an explicit relationship contract.")) (list "effects" value);
  List.iteri (fun i assignment ->
    let location = path ^ "/assignments/" ^ string_of_int i in
    let store = resolve state Names.empty (location ^ "/state") (get "state" assignment) ["StateStore"] in
    access state (location ^ "/value") executor (get "value" assignment);
    if present store then (
      require state location (compatible (get "value_type" store) (get "value_type" (get "value" assignment))) "assignment_type" "Assigned expression differs from the state type.";
      state_access state location executor store)) (list "assignments" value);
  List.iteri (fun i reference -> let location = path ^ "/emissions/" ^ string_of_int i in
    let message = resolve state Names.empty location reference ["Message"] in
    if present message then require state location (equal executor (get "sender" message)) "executor_ownership" "Message emission belongs to another sender.") (list "emissions" value)

let declaration state path value =
  let kind = tag value in
  let req condition code message = require state path condition code message in
  let reference key kinds = resolve state Names.empty (path ^ "/" ^ key) (get key value) kinds in
  let def key kinds = definition state (path ^ "/" ^ key) (get key value) kinds in
  feature state ("declaration:" ^ kind);
  if List.mem kind ["Observation";"Effect";"Channel"] && present (get "spatial_scope" value) then ignore (reference "spatial_scope" ["SpatialScope"]);
  if List.mem kind ["Effect";"Message";"Encounter";"SpatialScope";"Role"] then List.iter (fun key ->
    let target = lookup state Names.empty (get key value) in
    req (tag target <> "Subject" || text "identity" target <> "bound") "bound_subject_escape" "Quantifier-bound subject escapes into an unbound declaration.") ["subject";"target";"anchor";"population";"correlation"];
  if List.mem kind ["StateStore";"Machine"] && text "lifetime" value = "persistent" then (
    let target = lookup state Names.empty (get "subject" (get "scope" value)) in
    if tag target = "Encounter" || (tag target = "Subject" && text "identity" target = "encounter") then obligation state "persistent_encounter_identity_lifetime");
  match kind with
  | "Role" ->
      List.iteri (fun i pin -> ignore (definition state (path ^ "/requires/" ^ string_of_int i) pin ["capability";"interface"])) (list "requires" value);
      if present (get "population" value) then let target = reference "population" ["Subject"] in req (text "entity_kind" target = "population") "population_kind" "Role population is not a nominal population."
  | "Subject" ->
      if present (get "executor" value) then ignore (reference "executor" ["Role"]);
      req ((text "identity" value = "encounter") = present (get "encounter" value)) "subject_encounter" "Exactly encounter-local subjects carry an encounter.";
      if present (get "encounter" value) then (
        let encounter = reference "encounter" ["Encounter"] in
        req (ref_id (get "target" encounter) = ref_id value && (not (present (get "executor" value)) || equal (get "executor" value) (get "executor" encounter))) "subject_encounter" "Encounter-local subject differs from its encounter target/executor.");
      req ((text "identity" value = "bound") = present (get "domain" value)) "subject_domain" "Exactly bound subjects carry domains.";
      if present (get "domain" value) then let domain = reference "domain" ["Subject"] in
        req (List.mem (text "entity_kind" domain) ["population";"region"] && ref_id domain <> ref_id value) "subject_domain" "Bound subject requires a distinct population/region domain."
  | "Encounter" -> ignore (reference "executor" ["Role"]); ignore (reference "target" ["Subject"]); ignore (def "contract" ["encounter"])
  | "SpatialScope" ->
      ignore (reference "anchor" ["Role";"Subject";"Encounter"]); ignore (def "contract" ["spatial"]);
      if present (get "radius" value) then req (text "dimension" (get "unit" (get "radius" value)) = "length" && Q.sign (quantity (get "radius" value)) >= 0) "spatial_radius" "Spatial radius must be a nonnegative length."
  | "Clock" -> duration state (path ^ "/resolution") (get "resolution" value)
  | "Observation" ->
      ignore (reference "observer" ["Role"]); ignore (reference "subject" ["Role";"Subject"]); ignore (reference "clock" ["Clock"]);
      let contract = def "contract" ["observation"] in
      if present contract then req (present (get "result" contract) && compatible (get "value_type" value) (get "result" contract)) "observation_signature" "Observation type differs from its contract result.";
      duration state (path ^ "/freshness") ~positive:false (get "freshness" value);
      req (D.nonblank_text (text "coherence" value)) "observation_coherence" "Observation requires a coherent-frame identity.";
      req (unique (names (list "invalidity" value))) "duplicate_invalidity" "Observation invalidity reasons repeat."
  | "StateStore" ->
      let value_type = get "value_type" value in
      req (compatible value_type (literal_type value_type (get "initial" value))) "state_initial_type" "Initial state differs from its declared type.";
      (match get "capacity" value with
      | Json.Int n -> req (Z.sign n > 0) "state_capacity" "State capacity must be positive."
      | Json.String _ -> obligation state "unbounded_state_capacity"
      | capacity -> let p = resolve state Names.empty (path ^ "/capacity") capacity ["Parameter"] in
          req (type_kind (get "value_type" p) = "integer") "state_capacity" "State capacity parameter must be integer-valued.";
          if text "selection" p = "fixed" then (match get "value" p with Json.Int n -> req (Z.sign n > 0) "state_capacity" "Fixed capacity must be positive." | _ -> ()));
      req ((text "lifetime" value = "duration") = present (get "duration" value)) "state_lifetime" "Exactly duration-lived state carries a duration.";
      duration state (path ^ "/duration") ~required:false (get "duration" value);
      if present (get "reset" value) then (
        req (type_kind (get "value_type" (get "reset" value)) = "truth") "state_reset_type" "State reset must be truth-valued.";
        let owner = scope_owner state (get "scope" value) in if present owner then access state (path ^ "/reset") owner (get "reset" value));
      req (text "kind" (get "scope" value) <> "population" || present (get "coordination" value)) "population_coordination" "Population state requires an explicit coordination channel.";
      if present (get "coordination" value) then ignore (reference "coordination" ["Channel"]);
      req ((text "overflow" value <> "contract" && text "inheritance" value <> "contract") || present (get "contract" value)) "state_contract" "Contract-defined storage requires a definition.";
      obligation state "state_lifetime_capacity_and_inheritance"
  | "Effect" ->
      feature state "effects:lifecycle";
      ignore (reference "executor" ["Role"]);
      let subject = reference "subject" ["Role";"Subject"] and contract = def "contract" ["operation";"capability"] in
      List.iteri (fun i pin -> ignore (definition state (path ^ "/resources/" ^ string_of_int i) pin ["resource"])) (list "resources" value);
      if present contract then (
        let parameters = list "parameters" contract and arguments = list "parameters" value in
        let supplied = List.map (text "name") arguments in
        req (unique supplied && Seen.equal (set supplied) (set (List.map ref_id parameters))) "effect_arguments" "Effect arguments must cover the pinned signature exactly once.";
        List.iter (fun arg ->
          (match List.find_opt (fun p -> ref_id p = text "name" arg) parameters with
          | Some p -> req (compatible (get "value_type" p) (get "value_type" (get "value" arg))) "effect_argument_type" "Effect argument differs from its formal type."
          | None -> ()); access state (path ^ "/parameters") (get "executor" value) (get "value" arg)) arguments;
        if tag subject = "Subject" && present (get "subject_kind" contract) then req (equal (get "entity_kind" subject) (get "subject_kind" contract)) "effect_subject_type" "Affected entity kind differs from the contract signature.");
      obligation state "effect_authorization_feedback_and_cancellation"
  | "Rule" -> ignore (reference "executor" ["Role"]); behavior state path (get "executor" value) value
  | "Machine" ->
      ignore (reference "executor" ["Role"]);
      let owner = scope_owner state (get "scope" value) in
      req (not (present owner) || equal owner (get "executor" value)) "executor_ownership" "Machine executor differs from its scope owner.";
      let states = names (list "states" value) and terminal = names (list "terminal" value) in
      req (states <> [] && unique states && List.for_all D.nonblank_text states) "machine_states" "Machine states must be nonempty and unique.";
      req (List.mem (text "initial" value) states && unique terminal && Seen.subset (set terminal) (set states)) "machine_membership" "Initial/terminal state is absent from the machine.";
      obligation state "machine_reachability_termination_and_progress"
  | "Transition" ->
      let machine = reference "machine" ["Machine"] in
      if present machine then (
        let states = names (list "states" machine) in
        req (List.mem (text "source" value) states && List.mem (text "destination" value) states && (not (present (get "unknown_target" value)) || List.mem (text "unknown_target" value) states)) "transition_membership" "Transition endpoint is absent from its machine.";
        behavior state path (get "executor" machine) value)
  | "Channel" ->
      feature state "coordination:declared_transport";
      ignore (reference "sender" ["Role"]);
      let recipients = list "recipients" value in
      req (recipients <> [] && unique (List.map ref_id recipients)) "channel_recipients" "Channel requires unique recipients.";
      List.iteri (fun i r -> ignore (resolve state Names.empty (path ^ "/recipients/" ^ string_of_int i) r ["Role"])) recipients;
      ignore (def "contract" ["transport"]);
      req ((text "retry" value = "bounded") = present (get "max_attempts" value)) "retry_bound" "Exactly bounded retry carries an attempt limit.";
      (match get "max_attempts" value with Json.Int n -> req (Z.sign n > 0) "retry_bound" "Retry bound must be positive." | _ -> ());
      duration state (path ^ "/latency") ~required:false ~positive:false (get "latency" value);
      obligation state "delivery_ordering_loss_duplicates_and_retry"
  | "Message" ->
      let channel = reference "channel" ["Channel"] in
      ignore (reference "sender" ["Role"]); ignore (reference "subject" ["Role";"Subject"]);
      let correlation = reference "correlation" ["Role";"Subject";"Encounter";"StateStore";"Parameter"] in
      if tag correlation = "StateStore" then state_access state (path ^ "/correlation") (get "sender" value) correlation;
      if present channel then req (equal (get "sender" value) (get "sender" channel) && compatible (get "value_type" (get "payload" value)) (get "message_type" channel)) "message_signature" "Message sender/payload differs from the channel interface.";
      access state (path ^ "/payload") (get "sender" value) (get "payload" value);
      obligation state "message_emission_retry_and_feedback_identity"
  | "Requirement" ->
      if present (get "condition" value) then req (List.mem (type_kind (get "value_type" (get "condition" value))) ["truth";"event"]) "requirement_condition" "Requirement condition must be truth/event-valued.";
      if present (get "trigger" value) then req (type_kind (get "value_type" (get "trigger" value)) = "event") "requirement_trigger" "Requirement trigger must be an event.";
      if present (get "clock" value) then ignore (reference "clock" ["Clock"]);
      req (not (present (get "deadline" value)) || (present (get "trigger" value) && present (get "clock" value))) "requirement_deadline_anchor" "Timed requirement requires an explicit anchor and clock.";
      if text "kind" value = "progress" then (
        req (List.exists (fun key -> present (get key value)) ["condition";"trigger";"contract"]) "progress_enabling" "Progress requires an enabling condition, trigger or interpretation contract.";
        req (present (get "response" value)) "progress_response" "Progress must retain its required response.");
      duration state (path ^ "/deadline") ~required:false (get "deadline" value);
      if tag (get "horizon" value) = "Quantity" then duration state (path ^ "/horizon") (get "horizon" value);
      if get "horizon" value = str "unbounded_requested" then obligation state "unbounded_requirement_horizon";
      if text "kind" value = "assumption" then state.assumptions <- Seen.add (text "description" value) state.assumptions;
      obligation state ("requirement_satisfaction:" ^ ref_id value)
  | "Parameter" -> ()
  | _ -> issue state path "unsupported_declaration" "Declaration is outside the native policy frontend profile."

type participant = { node : Json.t; path : string; executor : Json.t; arbitration : Json.t }
let conflicts state declarations =
  let participants = List.filter_map (fun (d : D.declaration) ->
    match tag d.value with
    | "Rule" -> Some {node=d.value;path=d.path;executor=get "executor" d.value;arbitration=get "arbitration" d.value}
    | "Transition" -> let machine = lookup state Names.empty (get "machine" d.value) in
        if tag machine = "Machine" then Some {node=d.value;path=d.path;executor=get "executor" machine;arbitration=get "arbitration" machine} else None
    | _ -> None) declarations in
  let writers = List.fold_left (fun found p ->
    let keys = List.map (fun a -> "state:" ^ ref_id (get "state" a)) (list "assignments" p.node) @ List.map (fun r -> "effect:" ^ ref_id r) (list "effects" p.node) |> set in
    Seen.fold (fun key acc -> Names.add key (p :: Option.value ~default:[] (Names.find_opt key acc)) acc) keys found) Names.empty participants in
  Names.iter (fun _ reversed -> let group = List.rev reversed in match group with
    | [] | [_] -> ()
    | first :: _ ->
        require state first.path (List.for_all (fun p -> present p.arbitration) group) "missing_arbitration" "Multiple source writers require explicit arbitration regardless of guard satisfiability.";
        let policies = List.filter_map (fun p -> if present p.arbitration then Some p.arbitration else None) group in
        (match policies with [] -> () | first_policy :: rest -> require state first.path (List.for_all (equal first_policy) rest) "inconsistent_arbitration" "Participants sharing an output have inconsistent arbitration.");
        List.iter (fun policy -> if text "mode" policy = "priority" || text "tie" policy = "declared_order" then
          require state first.path (Seen.subset (set (List.map (fun p -> ref_id p.node) group)) (set (names (list "order" policy)))) "arbitration_order_coverage" "Explicit order omits a participant sharing an output.") policies) writers;
  let by_executor = List.fold_left (fun acc p -> let identity = ref_id p.executor in
      let before = Option.value ~default:Seen.empty (Names.find_opt identity acc) in
      Names.add identity (Seen.add (ref_id p.node) before) acc) Names.empty participants in
  List.iter (fun (d : D.declaration) ->
    if List.mem (tag d.value) ["Rule";"Machine"] && present (get "arbitration" d.value) then (
      let policy = get "arbitration" d.value in
      let allowed = Option.value ~default:Seen.empty (Names.find_opt (ref_id (get "executor" d.value)) by_executor) in
      let order = set (names (list "order" policy)) in
      require state d.path (Seen.subset order allowed) "arbitration_participant" "Arbitration order names a participant outside its executor.";
      let required = if tag d.value = "Rule" then Seen.singleton d.id else
          set (List.filter_map (fun p -> if tag p.node = "Transition" && ref_id (get "machine" p.node) = d.id then Some (ref_id p.node) else None) participants) in
      if text "mode" policy = "priority" || text "tie" policy = "declared_order" then require state d.path (Seen.subset required order) "arbitration_order_coverage" "Explicit order omits a governed rule or machine transition.")) declarations

let request state path value =
  feature state "request:deployment_catalog_assurance";
  List.iter (obligation state) ["chassis_capability_and_delivery_suitability";"implementation_catalog_applicability";"requested_assurance_not_established"];
  let deployment = get "deployment" value in
  let roles = Names.fold (fun id d acc -> if tag d = "Role" then Seen.add id acc else acc) state.index Seen.empty in
  let bindings = list "bindings" deployment in
  let supplied = List.map (fun b -> ref_id (get "role" b)) bindings in
  require state (path ^ "/deployment/bindings") (unique supplied && Seen.equal roles (set supplied)) "deployment_role_coverage" "Deployment must bind each declared role exactly once.";
  List.iteri (fun i binding ->
    let location = path ^ "/deployment/bindings/" ^ string_of_int i in
    let role = resolve state Names.empty (location ^ "/role") (get "role" binding) ["Role"] in
    let chassis = get "chassis" binding in
    List.iter (fun key -> List.iteri (fun j pin -> ignore (definition state (location ^ "/chassis/" ^ key ^ "/" ^ string_of_int j) pin (if key = "environment" then ["environment"] else ["capability";"interface"]))) (list key chassis)) ["capabilities";"interfaces";"environment"];
    ignore (definition state (location ^ "/chassis/operational_model") (get "operational_model" chassis) ["model"]);
    let available = list "capabilities" chassis @ list "interfaces" chassis in
    List.iter (fun pin -> require state location (List.exists (equal pin) available) "role_capability_binding" "A role requirement is absent from its supplied chassis interfaces/capabilities.") (list "requires" role)) bindings;
  List.iteri (fun i pin -> ignore (definition state (path ^ "/deployment/environment/" ^ string_of_int i) pin ["environment"])) (list "environment" deployment);
  let delivery = get "delivery" deployment in
  let recipients = list "intended_recipients" delivery in
  require state (path ^ "/deployment/delivery") (recipients <> [] && unique (List.map ref_id recipients)) "delivery_recipients" "Delivery needs unique intended recipients.";
  List.iteri (fun i r -> ignore (resolve state Names.empty (path ^ "/deployment/delivery/intended_recipients/" ^ string_of_int i) r ["Role";"Subject"])) recipients;
  List.iter (fun key -> ignore (definition state (path ^ "/deployment/delivery/" ^ key) (get key delivery) ["delivery"])) ["arrival";"expression";"activation";"contract"];
  let payload = get "payload" deployment in
  List.iter (fun key -> match get key payload with Json.Int n -> require state (path ^ "/deployment/payload/" ^ key) (Z.sign n >= 0) "payload_count" "Payload counts cannot be negative." | _ -> ()) ["design_count";"member_count";"helper_count";"orf_count";"product_count"];
  List.iter (fun key -> duration state (path ^ "/deployment/payload/" ^ key) ~required:false (get key payload)) ["payload_persistence";"effector_persistence"];
  let implementations = list "implementations" (get "implementations" value) in
  require state (path ^ "/implementations") (unique (List.map ref_id implementations)) "implementation_identity" "Catalog implementation IDs must be unique.";
  List.iteri (fun i implementation -> let location = path ^ "/implementations/implementations/" ^ string_of_int i in
    ignore (definition state (location ^ "/operation") (get "operation" implementation) ["operation";"capability"]);
    ignore (definition state (location ^ "/realization") (get "realization" implementation) []);
    obligation state ("implementation_applicability:" ^ ref_id implementation)) implementations;
  let assurance = get "assurance" value in
  let requested = names (list "requirements" assurance) in
  let known = Names.fold (fun id d acc -> if tag d = "Requirement" then Seen.add id acc else acc) state.index Seen.empty in
  require state (path ^ "/assurance/requirements") (unique requested && Seen.subset (set requested) known) "assurance_requirements" "Assurance references duplicate or unknown requirements.";
  if tag (get "horizon" assurance) = "Quantity" then duration state (path ^ "/assurance/horizon") (get "horizon" assurance)

let check document =
  let program = D.program document and declarations = D.declarations document in
  let raw = D.to_json document in
  let prefix = match D.kind document with D.Program -> "" | D.Request -> "/program" | D.Submission -> "/request/program" in
  let definitions = list "definitions" (get "semantics" program) in
  let index = List.fold_left (fun acc (d : D.declaration) -> if Names.mem d.id acc then acc else Names.add d.id d.value acc) Names.empty declarations in
  let definition_index = List.fold_left (fun acc d -> if Names.mem (ref_id d) acc then acc else Names.add (ref_id d) (d,D.document_digest d) acc) Names.empty definitions in
  let state = {index;definitions=definition_index;diagnostics=[];features=Seen.singleton "profile:biocompiler.policy.v0.1";assumptions=Seen.empty;obligations=set deferred;dependencies=Names.empty;work=0} in
  require state (prefix ^ "/declarations") (unique (List.map (fun (d : D.declaration) -> d.id) declarations)) "duplicate_declaration" "Declaration identities must be unique.";
  require state (prefix ^ "/semantics/definitions") (unique (List.map ref_id definitions)) "duplicate_definition" "Semantic definition identities must be unique.";
  List.iter (fun (d : D.declaration) -> require state (d.path ^ "/id") (identifier d.id) "invalid_identifier" "Declaration identity is outside the ASCII namespace grammar.") declarations;
  (* Never traverse untrusted submission summary claims as source authority. *)
  let authority = match D.request document with Some value -> value | None -> program in
  let authority_path = if D.kind document = D.Submission then "/request" else "" in
  walk state Names.empty Seen.empty false authority_path authority;
  List.iter (fun (d : D.declaration) -> declaration state d.path d.value) declarations;
  conflicts state declarations;
  Option.iter (request state authority_path) (D.request document);
  let dependencies = Names.bindings state.dependencies |> List.map snd in
  let features = Seen.elements state.features and assumptions = Seen.elements state.assumptions in
  if D.kind document = D.Submission then (
    require state "/required_features" (equal (get "required_features" raw) (strings features)) "submission_features" "Submission feature inventory differs from independently analyzed source.";
    require state "/assumptions" (equal (get "assumptions" raw) (strings assumptions)) "submission_assumptions" "Submission assumptions differ from independently analyzed source.";
    require state "/dependencies" (equal (get "dependencies" raw) (arr dependencies)) "submission_dependencies" "Submission dependencies differ from complete source references.");
  let source_index = List.fold_left (fun acc source -> let id = text "declaration_id" source in
      Names.add id (source :: Option.value ~default:[] (Names.find_opt id acc)) acc) Names.empty (list "source_map" program) in
  let ledger (d : D.declaration) = obj ["id",str d.id;"kind",str (tag d.value);"path",str (document_path d.path);"value",d.value;
      "sources",arr (List.rev (Option.value ~default:[] (Names.find_opt d.id source_index)))] in
  let result = obj ["schema_version",str "biocompiler.policy_assessment.v0.1";
    "status",str (if state.diagnostics = [] then "valid" else "invalid");
    "document_digest",str (D.fingerprint document);"program_digest",str (D.document_digest program);"artifact_digest",str (D.artifact_digest document);
    "declarations",arr (List.map ledger declarations);
    "requirements",arr (List.filter_map (fun (d : D.declaration) -> if tag d.value = "Requirement" then Some (ledger d) else None) declarations);
    "required_features",strings features;"dependencies",arr dependencies;"assumptions",strings assumptions;
    "unresolved_obligations",strings (Seen.elements state.obligations);"diagnostics",arr (List.rev state.diagnostics);
    "semantic_status",str "unresolved";"target_status",str "unassessed";"lowering",str "unsupported";"artifact",str "withheld"] in
  Meter.preflight result;
  result
end

let check ?(charge = Policy_generation_meter.no_charge) document =
  let module Checked = Make(struct let charge = charge end) in
  Checked.check document
