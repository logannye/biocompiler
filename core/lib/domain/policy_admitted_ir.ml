open Bioc_wire
module D = Policy_document
module O = Policy_operational

module type Symbol = sig
  type t
  val name : t -> string
  val index : t -> int
end
module Make_symbol () = struct
  type t = { name : string; index : int }
  let make name index = { name; index }
  let name (value:t) = value.name
  let index (value:t) = value.index
end
module Role = Make_symbol ()
module Subject = Make_symbol ()
module Encounter = Make_symbol ()
module Clock = Make_symbol ()
module Observation = Make_symbol ()
module State = Make_symbol ()
module Effect = Make_symbol ()
module Rule = Make_symbol ()
module Machine = Make_symbol ()
module Transition = Make_symbol ()
module Parameter = Make_symbol ()
module Requirement = Make_symbol ()

type entity = Executor of Role.t | Target of Subject.t | Encounter_target of Encounter.t
type scope = Executor_scope of Role.t | Encounter_scope of Encounter.t
type read = Observation_read of Observation.t | State_read of State.t | Parameter_read of Parameter.t
type equality = Equal | Not_equal
type comparison = Eq | Ne | Lt | Le | Gt | Ge
type phase = Requested | Initiated | Completed | Failed | Timed_out
type truth_expression = { truth_term : truth_term; truth_source : Json.t }
and truth_term =
  | Truth_literal of O.truth | Truth_read of read
  | All of truth_expression list | Any of truth_expression list | Not of truth_expression
  | Truth_equal of equality * truth_expression * truth_expression
  | Text_equal of equality * text_expression * text_expression
  | Integer_compare of comparison * integer_expression * integer_expression
  | Quantity_compare of comparison * quantity_expression * quantity_expression
and integer_expression = { integer_term : integer_term; integer_source : Json.t }
and integer_term = Integer_literal of Z.t | Integer_read of read
and text_expression = { text_term : text_term; text_source : Json.t }
and text_term = Text_literal of string | Text_read of read
and quantity_expression = { quantity_term : quantity_term; quantity_source : Json.t; unit : Json.t }
and quantity_term = Quantity_literal of Q.t | Quantity_read of read
type scalar_expression = Truth of truth_expression | Integer of integer_expression
  | Text of text_expression | Quantity of quantity_expression
type event_expression = { event_term : event_term; event_source : Json.t }
and event_term = Updated of Observation.t | Rising of truth_expression | Effect_event of Effect.t * phase
type assignment = Truth_assignment of State.t * truth_expression
  | Integer_assignment of State.t * integer_expression | Text_assignment of State.t * text_expression
type arbitration_mode = Exclusive | Priority
type tie = Reject_tie | Declared_order
type conflict = Reject_conflict | Identical_only
type participant = Rule_participant of Rule.t | Transition_participant of Transition.t
type arbitration = { mode : arbitration_mode; tie : tie; conflict : conflict; order : participant list }
type authorization = At_initiation | Continuous
type unknown_response = Continue | Defer
type lifecycle = { authorization : authorization; on_unknown : unknown_response; timeout : Q.t option }
type termination = Explicit_event | Contact_loss
type clock_basis = Logical | Availability
type coverage = Sampled | Event

type declaration =
  | Role_declaration of Role.t
  | Subject_declaration of { id : Subject.t; executor : Role.t option; encounter : Encounter.t option }
  | Encounter_declaration of { id : Encounter.t; executor : Role.t; target : Subject.t; termination : termination }
  | Clock_declaration of { id : Clock.t; basis : clock_basis; resolution : Q.t }
  | Observation_declaration of { id : Observation.t; observer : Role.t; subject : entity;
      clock : Clock.t; value_type : O.value_type; coverage : coverage; coherence : string; freshness : Q.t }
  | State_declaration of { id : State.t; scope : scope; value_type : O.value_type;
      initial : O.value; capacity : int; reset : truth_expression option }
  | Effect_declaration of { id : Effect.t; executor : Role.t; subject : entity;
      lifecycle : lifecycle; parameters : (string * scalar_expression) list }
  | Rule_declaration of { id : Rule.t; executor : Role.t; on : event_expression;
      guard : truth_expression; effects : Effect.t list; assignments : assignment list; arbitration : arbitration }
  | Machine_declaration of { id : Machine.t; executor : Role.t; scope : scope; states : string list;
      initial : string; terminal : string list; arbitration : arbitration }
  | Transition_declaration of { id : Transition.t; machine : Machine.t; source : string; destination : string;
      on : event_expression; guard : truth_expression; effects : Effect.t list; assignments : assignment list }
  | Parameter_declaration of { id : Parameter.t; value_type : O.value_type; value : O.value }
  (* Requirements are obligations, not executable instructions. Their entire
     original body is retained, including unsupported monitoring expressions. *)
  | Retained_requirement of Requirement.t

type instruction = { declaration : declaration; original : D.declaration }
type t = { instructions : instruction list }
let instructions value = value.instructions
let declaration value = value.declaration
let source_path value = value.original.path
let original_declaration value = value.original.value
let truth_term value = value.truth_term
let integer_term value = value.integer_term
let text_term value = value.text_term
let quantity_term value = value.quantity_term
let event_term value = value.event_term
let truth_source value = value.truth_source
let integer_source value = value.integer_source
let text_source value = value.text_source
let quantity_source value = value.quantity_source
let event_source value = value.event_source
let quantity_unit value = value.unit
let name = function
  | Role_declaration id -> Role.name id
  | Subject_declaration d -> Subject.name d.id
  | Encounter_declaration d -> Encounter.name d.id
  | Clock_declaration d -> Clock.name d.id
  | Observation_declaration d -> Observation.name d.id
  | State_declaration d -> State.name d.id
  | Effect_declaration d -> Effect.name d.id
  | Rule_declaration d -> Rule.name d.id
  | Machine_declaration d -> Machine.name d.id
  | Transition_declaration d -> Transition.name d.id
  | Parameter_declaration d -> Parameter.name d.id
  | Retained_requirement id -> Requirement.name id
let kind = function
  | Role_declaration _ -> "Role" | Subject_declaration _ -> "Subject"
  | Encounter_declaration _ -> "Encounter" | Clock_declaration _ -> "Clock"
  | Observation_declaration _ -> "Observation" | State_declaration _ -> "StateStore"
  | Effect_declaration _ -> "Effect" | Rule_declaration _ -> "Rule"
  | Machine_declaration _ -> "Machine" | Transition_declaration _ -> "Transition"
  | Parameter_declaration _ -> "Parameter" | Retained_requirement _ -> "Requirement"

module Make (Charge : sig val charge : int -> unit end) = struct
let charge = Charge.charge
let fail path message = Diagnostic.fail ~path "policy_typed_ir" message
let require path condition message = if not condition then fail path message
let get key value =
  let fields=Json.object_fields value in
  charge (1 + String.length key);
  List.iter (fun (name,_) -> charge (1 + String.length name)) fields;
  Json.field key fields
let text key value = let value=Json.string (get key value) in charge (String.length value); value
let list key value = Json.array (get key value)
let map f values = List.map (fun value -> charge 1; f value) values
let option f = function Json.Null -> None | value -> Some (f value)
let ref_id value = text "id" value
module Names = Map.Make(struct type t=string let compare a b = charge (1 + String.length a + String.length b); String.compare a b end)
let string_equal a b = charge (1 + String.length a + String.length b);String.equal a b
let rec equal_json left right =
  charge 1;
  let rec paired_equal compare left right=match left,right with
    | [],[] -> true
    | left::ls,right::rs -> charge 1;compare left right && paired_equal compare ls rs
    | _ -> false in
  match left,right with
  | Json.Null,Json.Null -> true
  | Json.Bool a,Json.Bool b -> a=b
  | Json.Int a,Json.Int b -> charge (1+Z.numbits a);charge (1+Z.numbits b);Z.equal a b
  | Json.Float a,Json.Float b -> Int64.equal (Int64.bits_of_float a) (Int64.bits_of_float b)
  | Json.String a,Json.String b -> string_equal a b
  | Json.Array a,Json.Array b -> paired_equal equal_json a b
  | Json.Object a,Json.Object b ->
      let sort=List.sort (fun (a,_) (b,_) -> charge (1+String.length a+String.length b);String.compare a b) in
      let a=sort a and b=sort b in
      paired_equal (fun (ak,av) (bk,bv) -> string_equal ak bk && equal_json av bv) a b
  | _ -> false
let compatible expected actual = match expected,actual with
  | O.Truth_type,O.Truth_type | O.Integer_type,O.Integer_type | O.Text_type,O.Text_type -> true
  | O.Quantity_type expected,O.Quantity_type actual ->
      List.for_all (fun field -> charge 1;equal_json (get field expected) (get field actual)) ["dimension";"quantity_kind";"reference"]
  | _ -> false
let phase path = function
  | "requested" -> Requested | "initiated" -> Initiated | "completed" -> Completed
  | "failed" -> Failed | "timed_out" -> Timed_out | _ -> fail path "Unsupported effect lifecycle phase."
let comparison path = function
  | "eq" -> Eq | "ne" -> Ne | "lt" -> Lt | "le" -> Le | "gt" -> Gt | "ge" -> Ge
  | _ -> fail path "Unsupported comparison."
let equality path = function "eq" -> Equal | "ne" -> Not_equal | _ -> fail path "Only equality compares nonnumeric values."
let elaborate document =
  let declarations=D.declarations document in
  let index=List.fold_left (fun (next,index) (d:D.declaration) ->
    charge 1;
    require d.path (not (Names.mem d.id index)) "Duplicate resolved declaration identity.";
    next+1,Names.add d.id (next,d) index) (0,Names.empty) declarations |> snd in
  let resolve path expected value =
    let id=ref_id value in
    match Names.find_opt id index with
    | Some (position,(d:D.declaration)) when d.kind=expected ->
        require path (text "kind" value=text "$type" d.value) "Reference discriminator differs from its resolved declaration.";
        position,d
    | _ -> fail path "Reference does not resolve to the required declaration kind." in
  let symbol make expected path value = let position,d=resolve path expected value in make d.id position in
  let role=symbol Role.make D.Role and subject=symbol Subject.make D.Subject
  and encounter=symbol Encounter.make D.Encounter and clock=symbol Clock.make D.Clock
  and observation=symbol Observation.make D.Observation and state=symbol State.make D.State_store
  and effect_value=symbol Effect.make D.Effect and machine=symbol Machine.make D.Machine in
  let entity path value =
    match Names.find_opt (ref_id value) index with
    | Some (position,d) -> (match d.D.kind with
        | D.Role -> Executor (Role.make d.id position)
        | D.Subject -> Target (Subject.make d.id position)
        | D.Encounter -> Encounter_target (Encounter.make d.id position)
        | _ -> fail path "Executable entity must resolve to a role, subject or encounter.")
    | None -> fail path "Entity reference is unresolved." in
  let scope path value = match text "kind" value with
    | "executor" -> Executor_scope (role path (get "subject" value))
    | "encounter" -> Encounter_scope (encounter path (get "subject" value))
    | _ -> fail path "Unsupported executable scope." in
  let read path expected op value =
    let reference=get "ref" value in
    let kind=match op with "observe" -> D.Observation | "state" -> D.State_store | "parameter" -> D.Parameter
      | _ -> fail path "Expected a scalar read." in
    let position,target=resolve path kind reference in
    require path (compatible expected (O.value_type (get "value_type" target.value)))
      "Resolved read differs from its scalar expression type.";
    match kind with
    | D.Observation -> Observation_read (Observation.make target.id position)
    | D.State_store -> State_read (State.make target.id position)
    | D.Parameter -> Parameter_read (Parameter.make target.id position)
    | _ -> fail path "Invalid scalar reference kind." in
  let arity path count args = require path (List.length args=count) "Typed expression has wrong arity." in
  let rec scalar path value =
    charge 1;
    let kind=O.value_type (get "value_type" value) in
    let op=text "op" value and args=list "args" value in
    let leaf f = arity path 0 args; f () in
    match kind with
    | O.Truth_type ->
        let term=match op with
        | "literal" -> leaf (fun () -> match O.value_of_json kind (get "value" value) with
            O.Truth t -> Truth_literal t | _ -> fail path "Expected truth literal.")
        | "observe" | "state" | "parameter" -> leaf (fun () -> Truth_read (read path kind op value))
        | "all" | "any" ->
            require path (args<>[]) "Truth conjunction/disjunction requires operands.";
            let values=map (truth path) args in if op="all" then All values else Any values
        | "not" -> arity path 1 args; Not (truth path (List.hd args))
        | "eq" | "ne" | "lt" | "le" | "gt" | "ge" ->
            arity path 2 args;
            let a=List.hd args and b=List.nth args 1 in
            require path (compatible (O.value_type (get "value_type" a)) (O.value_type (get "value_type" b)))
              "Comparison operands have incompatible nominal scalar types.";
            (match scalar path a,scalar path b with
             | Truth a,Truth b -> Truth_equal (equality path op,a,b)
             | Text a,Text b -> Text_equal (equality path op,a,b)
             | Integer a,Integer b -> Integer_compare (comparison path op,a,b)
             | Quantity a,Quantity b -> Quantity_compare (comparison path op,a,b)
             | _ -> fail path "Comparison operands have different scalar categories.")
        | _ -> fail path "Unsupported truth expression operation." in
        Truth {truth_term=term;truth_source=value}
    | O.Integer_type ->
        let term=leaf (fun () -> match op with
          | "literal" -> Integer_literal (Json.integer (get "value" value))
          | "observe" | "state" | "parameter" -> Integer_read (read path kind op value)
          | _ -> fail path "Unsupported integer expression operation.") in
        Integer {integer_term=term;integer_source=value}
    | O.Text_type ->
        let term=leaf (fun () -> match op with
          | "literal" -> Text_literal (Json.string (get "value" value))
          | "observe" | "state" | "parameter" -> Text_read (read path kind op value)
          | _ -> fail path "Unsupported text expression operation.") in
        Text {text_term=term;text_source=value}
    | O.Quantity_type unit ->
        let term=leaf (fun () -> match op with
          | "literal" -> (match O.value_of_json kind (get "value" value) with
              O.Quantity (amount,_) -> Quantity_literal amount | _ -> fail path "Expected quantity literal.")
          | "observe" | "state" | "parameter" -> Quantity_read (read path kind op value)
          | _ -> fail path "Unsupported quantity expression operation.") in
        Quantity {quantity_term=term;quantity_source=value;unit}
  and truth path value = match scalar path value with
    | Truth value -> value | _ -> fail path "Executable predicate must be truth-valued." in
  let event path value =
    charge 1;
    require path (text "kind" (get "value_type" value)="event") "Executable trigger must be event-valued.";
    let args=list "args" value in
    let term=match text "op" value with
      | "updated" -> arity path 0 args; Updated (observation path (get "ref" value))
      | "rising" -> arity path 1 args; Rising (truth path (List.hd args))
      | "effect_event" -> arity path 0 args; Effect_event (effect_value path (get "ref" value),phase path (text "value" value))
      | _ -> fail path "Unsupported executable event operation." in
    {event_term=term;event_source=value} in
  let assignments path value = map (fun value ->
    let reference=get "state" value in
    let id=state path reference in
    let _,target=resolve path D.State_store reference in
    let source=get "value" value in
    require path (compatible (O.value_type (get "value_type" target.value)) (O.value_type (get "value_type" source)))
      "Assignment differs from its resolved state type.";
    match scalar path source with
      | Truth value -> Truth_assignment (id,value)
      | Integer value -> Integer_assignment (id,value)
      | Text value -> Text_assignment (id,value)
      | Quantity _ -> fail path "Quantity state is outside the admitted finite-storage profile.") (list "assignments" value) in
  let arbitration path value =
    let mode=match text "mode" value with "exclusive" -> Exclusive | "priority" -> Priority | _ -> fail path "Unsupported arbitration mode." in
    let tie=match text "tie" value with "reject" -> Reject_tie | "declared_order" -> Declared_order | _ -> fail path "Unsupported arbitration tie." in
    let conflict=match text "write_conflict" value with "reject" -> Reject_conflict | "identical_only" -> Identical_only | _ -> fail path "Unsupported write conflict." in
    let order=map (fun raw -> let id=Json.string raw in match Names.find_opt id index with
      | Some (position,d) -> (match d.D.kind with
          | D.Rule -> Rule_participant (Rule.make id position)
          | D.Transition -> Transition_participant (Transition.make id position)
          | _ -> fail path "Arbitration participant is not a rule or transition.")
      | None -> fail path "Arbitration participant is unresolved.") (list "order" value) in
    {mode;tie;conflict;order} in
  let values key value=map Json.string (list key value) in
  let instructions=List.mapi (fun position (d:D.declaration) ->
    charge 1;
    let p=d.path and v=d.value in
    let declaration=match d.kind with
    | D.Role -> Role_declaration (Role.make d.id position)
    | D.Subject -> Subject_declaration {id=Subject.make d.id position;
        executor=option (role p) (get "executor" v);encounter=option (encounter p) (get "encounter" v)}
    | D.Encounter -> Encounter_declaration {id=Encounter.make d.id position;executor=role p (get "executor" v);
        target=subject p (get "target" v);termination=(match text "termination" v with
          "explicit_event" -> Explicit_event | "contact_loss" -> Contact_loss | _ -> fail p "Unsupported encounter termination.")}
    | D.Clock -> Clock_declaration {id=Clock.make d.id position;basis=(match text "basis" v with
        "logical" -> Logical | "availability" -> Availability | _ -> fail p "Unsupported clock basis.");resolution=O.duration (get "resolution" v)}
    | D.Observation -> Observation_declaration {id=Observation.make d.id position;observer=role p (get "observer" v);
        subject=entity p (get "subject" v);clock=clock p (get "clock" v);value_type=O.value_type (get "value_type" v);
        coverage=(match text "coverage" v with "sampled" -> Sampled | "event" -> Event | _ -> fail p "Unsupported coverage.");
        coherence=text "coherence" v;freshness=O.duration (get "freshness" v)}
    | D.State_store ->
        let value_type=O.value_type (get "value_type" v) in
        let capacity=Json.integer (get "capacity" v) in
        require p (Z.fits_int capacity) "State capacity exceeds typed representation.";
        State_declaration {id=State.make d.id position;scope=scope p (get "scope" v);value_type;
          initial=O.value_of_json value_type (get "initial" v);capacity=Z.to_int capacity;reset=option (truth p) (get "reset" v)}
    | D.Effect ->
        let lc=get "lifecycle" v in
        let lifecycle={authorization=(match text "authorization" lc with "initiation" -> At_initiation
          | "continuous" -> Continuous | _ -> fail p "Unsupported authorization.");
          on_unknown=(match text "on_unknown" lc with "continue" -> Continue | "defer" -> Defer | _ -> fail p "Unsupported unknown response.");
          timeout=option O.duration (get "timeout" lc)} in
        Effect_declaration {id=Effect.make d.id position;executor=role p (get "executor" v);subject=entity p (get "subject" v);lifecycle;
          parameters=map (fun value -> text "name" value,scalar p (get "value" value)) (list "parameters" v)}
    | D.Rule -> Rule_declaration {id=Rule.make d.id position;executor=role p (get "executor" v);
        on=event p (get "on" v);guard=truth p (get "when" v);effects=map (effect_value p) (list "effects" v);
        assignments=assignments p v;arbitration=arbitration p (get "arbitration" v)}
    | D.Machine -> Machine_declaration {id=Machine.make d.id position;executor=role p (get "executor" v);scope=scope p (get "scope" v);
        states=values "states" v;initial=text "initial" v;terminal=values "terminal" v;arbitration=arbitration p (get "arbitration" v)}
    | D.Transition -> Transition_declaration {id=Transition.make d.id position;machine=machine p (get "machine" v);
        source=text "source" v;destination=text "destination" v;on=event p (get "on" v);guard=truth p (get "when" v);
        effects=map (effect_value p) (list "effects" v);assignments=assignments p v}
    | D.Parameter -> let value_type=O.value_type (get "value_type" v) in
        Parameter_declaration {id=Parameter.make d.id position;value_type;value=O.value_of_json value_type (get "value" v)}
    | D.Requirement -> Retained_requirement (Requirement.make d.id position)
    | D.Spatial_scope | D.Channel | D.Message -> fail p "Declaration is outside the executable typed profile." in
    {declaration;original=d}) declarations in
  {instructions}

let set value fields =
  let rec find key = function
    | [] -> None
    | (name,value)::rest -> charge 1;if string_equal key name then Some value else find key rest in
  Json.Object (map (fun (key,original) ->
  charge (String.length key);
  key,(match find key fields with Some value -> value | None -> original)) (Json.object_fields value))
let str value=Json.String value
let reference original name = set original ["id",str name]
let entity_name = function Executor id -> Role.name id | Target id -> Subject.name id | Encounter_target id -> Encounter.name id
let scope_wire original = function
  | Executor_scope id -> set original ["kind",str "executor";"subject",reference (get "subject" original) (Role.name id)]
  | Encounter_scope id -> set original ["kind",str "encounter";"subject",reference (get "subject" original) (Encounter.name id)]
let read_fields original = function
  | Observation_read id -> ["op",str "observe";"ref",reference (get "ref" original) (Observation.name id)]
  | State_read id -> ["op",str "state";"ref",reference (get "ref" original) (State.name id)]
  | Parameter_read id -> ["op",str "parameter";"ref",reference (get "ref" original) (Parameter.name id)]
let eq = function Equal -> "eq" | Not_equal -> "ne"
let cmp = function Eq -> "eq" | Ne -> "ne" | Lt -> "lt" | Le -> "le" | Gt -> "gt" | Ge -> "ge"
let phase_name = function Requested -> "requested" | Initiated -> "initiated" | Completed -> "completed" | Failed -> "failed" | Timed_out -> "timed_out"
let literal original value = set original ["op",str "literal";"value",value;"args",Json.Array []]
let rec truth_wire value =
  charge 1;
  let original=value.truth_source in
  let operation op args=set original ["op",str op;"args",Json.Array args] in
  match value.truth_term with
  | Truth_literal value -> literal original (O.value_to_json (O.Truth value))
  | Truth_read read -> set original (read_fields original read)
  | All values -> operation "all" (map truth_wire values)
  | Any values -> operation "any" (map truth_wire values)
  | Not value -> operation "not" [truth_wire value]
  | Truth_equal (op,a,b) -> operation (eq op) [truth_wire a;truth_wire b]
  | Text_equal (op,a,b) -> operation (eq op) [text_wire a;text_wire b]
  | Integer_compare (op,a,b) -> operation (cmp op) [integer_wire a;integer_wire b]
  | Quantity_compare (op,a,b) -> operation (cmp op) [quantity_wire a;quantity_wire b]
and integer_wire value =
  charge 1;
  match value.integer_term with Integer_literal n -> literal value.integer_source (Json.Int n)
  | Integer_read read -> set value.integer_source (read_fields value.integer_source read)
and text_wire value =
  charge 1;
  match value.text_term with Text_literal text -> literal value.text_source (str text)
  | Text_read read -> set value.text_source (read_fields value.text_source read)
and quantity_wire value =
  charge 1;
  match value.quantity_term with
  | Quantity_literal _ -> literal value.quantity_source (get "value" value.quantity_source)
  | Quantity_read read -> set value.quantity_source (read_fields value.quantity_source read)
let scalar_wire = function Truth value -> truth_wire value | Integer value -> integer_wire value
  | Text value -> text_wire value | Quantity value -> quantity_wire value
let event_wire value =
  charge 1;
  let original=value.event_source in
  match value.event_term with
  | Updated id -> set original ["op",str "updated";"ref",reference (get "ref" original) (Observation.name id)]
  | Rising value -> set original ["op",str "rising";"args",Json.Array [truth_wire value]]
  | Effect_event (id,phase) -> set original ["op",str "effect_event";
      "ref",reference (get "ref" original) (Effect.name id);"value",str (phase_name phase)]
let assignment_wire original = function
  | Truth_assignment (id,value) -> set original ["state",reference (get "state" original) (State.name id);"value",truth_wire value]
  | Integer_assignment (id,value) -> set original ["state",reference (get "state" original) (State.name id);"value",integer_wire value]
  | Text_assignment (id,value) -> set original ["state",reference (get "state" original) (State.name id);"value",text_wire value]
let paired f originals values = List.map2 (fun original value -> charge 1;f original value) originals values
let arbitration_wire original value = set original [
  "mode",str (match value.mode with Exclusive -> "exclusive" | Priority -> "priority");
  "tie",str (match value.tie with Reject_tie -> "reject" | Declared_order -> "declared_order");
  "write_conflict",str (match value.conflict with Reject_conflict -> "reject" | Identical_only -> "identical_only");
  "order",Json.Array (map (fun value -> str (match value with Rule_participant id -> Rule.name id
    | Transition_participant id -> Transition.name id)) value.order)]
let wire_declaration instruction =
  charge 1;
  let v=instruction.original.value in
  let ref_field key name=key,reference (get key v) name in
  let optional_ref key name value=key,(match value with None -> Json.Null | Some id -> reference (get key v) (name id)) in
  let effects values="effects",Json.Array (paired (fun original id -> reference original (Effect.name id)) (list "effects" v) values) in
  let assignments values="assignments",Json.Array (paired assignment_wire (list "assignments" v) values) in
  let fields=match instruction.declaration with
  | Role_declaration _ | Retained_requirement _ -> []
  | Subject_declaration d -> [optional_ref "executor" Role.name d.executor;optional_ref "encounter" Encounter.name d.encounter]
  | Encounter_declaration d -> [ref_field "executor" (Role.name d.executor);ref_field "target" (Subject.name d.target);
      "termination",str (match d.termination with Explicit_event -> "explicit_event" | Contact_loss -> "contact_loss")]
  | Clock_declaration d -> ["basis",str (match d.basis with Logical -> "logical" | Availability -> "availability")]
  | Observation_declaration d -> [ref_field "observer" (Role.name d.observer);ref_field "subject" (entity_name d.subject);
      ref_field "clock" (Clock.name d.clock);"coverage",str (match d.coverage with Sampled -> "sampled" | Event -> "event");"coherence",str d.coherence]
  | State_declaration d -> ["scope",scope_wire (get "scope" v) d.scope;"capacity",Json.int d.capacity;
      "initial",O.value_to_json d.initial;"reset",(match d.reset with None -> Json.Null | Some value -> truth_wire value)]
  | Effect_declaration d ->
      let lifecycle=set (get "lifecycle" v) ["authorization",str (match d.lifecycle.authorization with At_initiation -> "initiation" | Continuous -> "continuous");
        "on_unknown",str (match d.lifecycle.on_unknown with Continue -> "continue" | Defer -> "defer")] in
      [ref_field "executor" (Role.name d.executor);ref_field "subject" (entity_name d.subject);"lifecycle",lifecycle;
       "parameters",Json.Array (paired (fun original (name,value) -> set original ["name",str name;"value",scalar_wire value]) (list "parameters" v) d.parameters)]
  | Rule_declaration d -> [ref_field "executor" (Role.name d.executor);"on",event_wire d.on;"when",truth_wire d.guard;
      effects d.effects;assignments d.assignments;"arbitration",arbitration_wire (get "arbitration" v) d.arbitration]
  | Machine_declaration d -> [ref_field "executor" (Role.name d.executor);"scope",scope_wire (get "scope" v) d.scope;
      "states",Json.Array (map str d.states);"initial",str d.initial;"terminal",Json.Array (map str d.terminal);
      "arbitration",arbitration_wire (get "arbitration" v) d.arbitration]
  | Transition_declaration d -> [ref_field "machine" (Machine.name d.machine);"source",str d.source;"destination",str d.destination;
      "on",event_wire d.on;"when",truth_wire d.guard;effects d.effects;assignments d.assignments]
  | Parameter_declaration d -> ["value",(match d.value with O.Quantity _ -> get "value" v | value -> O.value_to_json value)] in
  set v (("$type",str (kind instruction.declaration))::("id",str (name instruction.declaration))::fields)
end
let elaborate ~charge document = let module M=Make(struct let charge=charge end) in M.elaborate document
let wire_declaration ~charge instruction = let module M=Make(struct let charge=charge end) in M.wire_declaration instruction
