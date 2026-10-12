open Bioc_wire
module D = Bioc_domain.Policy_document

type symbol = { id : string; path : string; index : int; original : Json.t }
type definition = { identity : string; path : string; reference : Json.t; body : Json.t }
type input_scope = Executor | Encounter
type observation = { symbol : symbol; scope : input_scope; contract : definition; freshness_ticks : int }
type product = { symbol : symbol; product_identity : string }
type obligation_kind = No_unauthorized_activation | Initial_activation
  | Controller_cessation | Antigen_cessation | Component_cessation | Reactivation
type obligation = { symbol : symbol; kind : obligation_kind; contract : definition; deadline_ticks : int option }
type deadlines = { onset_ticks : int; controller_off_ticks : int; antigen_off_ticks : int;
  component_off_ticks : int; reactivation_ticks : int }
type source = {
  executor : symbol; target : symbol; encounter : symbol; clock : symbol;
  tick_resolution : Q.t; tick_unit : Json.t; resolution : Json.t; horizon_ticks : int;
  antigen : observation; controller : observation; products : product * product;
  activity : symbol; operation : definition; readout : definition;
  obligations : obligation list; deadlines : deadlines; selected_implementation : Json.t;
}
type t = { document_value : D.controlled; source_value : source;
  report_value : Json.t; correspondence_value : Json.t }
let schema_version = "biocompiler.policy_controlled_composition_source_admission.v0.1"
let document (value:t) = value.document_value
let typed (value:t) = value.source_value
let report (value:t) = value.report_value
let correspondence (value:t) = value.correspondence_value
let obligation_tag = function
  | No_unauthorized_activation -> "no_unauthorized_activation"
  | Initial_activation -> "initial_activation"
  | Controller_cessation -> "controller_cessation"
  | Antigen_cessation -> "antigen_cessation"
  | Component_cessation -> "component_cessation"
  | Reactivation -> "reactivation"

module Make (Charge : sig val charge : int -> unit end) = struct
module Meter = Policy_generation_meter.Make(Charge)
module List = Meter.List
module String = Meter.String
module Json = Meter.Json
module D = Meter.Document
module Names = Meter.Names
module Seen = Meter.Seen
let ( ^ ) = Meter.append_string
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let fail path message = Diagnostic.fail ~path "policy_controlled_source" message
let require path condition message = if not condition then fail path message
let get path key value = Json.field ~path:(path ^ "/" ^ key) key (Json.object_fields ~path value)
let text path key value = Json.string ~path:(path ^ "/" ^ key) (get path key value)
let list path key value = Json.array ~path:(path ^ "/" ^ key) (get path key value)
let exact path actual expected message = require path (Json.equal actual expected) message
let nulls path keys value = List.iter (fun key -> exact (path ^ "/" ^ key) (get path key value) Json.Null
  "This source field requires an explicit later interpretation; it cannot be ignored.") keys
let empty path keys value = List.iter (fun key -> exact (path ^ "/" ^ key) (get path key value) (arr [])
  "Additional source constraints or evidence require a separately admitted interpretation.") keys
let identifier path value =
  let letter char = (char >= 'a' && char <= 'z') || (char >= 'A' && char <= 'Z') in
  require path (String.length value > 0 && letter value.[0] &&
    String.for_all (fun char -> letter char || (char >= '0' && char <= '9') || String.contains "_.:/-" char) value)
    "Source identities require the closed namespaced identifier grammar."
let nonblank path value = require path (D.nonblank_text value) "Source text must be nonblank."
let scalar kind = obj ["$type",str "TypeSpec";"kind",str kind;"unit",Json.Null;"entity_kind",Json.Null]
let reference kind identity = obj ["$type",str "Ref";"kind",str kind;"id",str identity]
let expr op kind ?(args=[]) ?(reference=Json.Null) ?(scope=Json.Null) ?(value=Json.Null) () =
  obj ["$type",str "Expr";"op",str op;"value_type",scalar kind;"args",arr args;
    "ref",reference;"scope",scope;"value",value;"contract",Json.Null;"duration",Json.Null;
    "clock",Json.Null;"coverage",Json.Null;"binding",Json.Null]
let marker semantic = expr "literal" "text" ~value:(str ("biocompiler.controlled_source." ^ semantic ^ ".v0.1")) ()

let admit ~(document:D.controlled) : t =
  let raw = D.controlled_to_json document in
  Meter.preflight raw;
  (* The decoder measures/canonicalizes the full original twice, fingerprints
     its metadata projection, then records full artifact bytes. Reserve each
     bounded serialization pass before the opaque decoder allocation. *)
  List.iter (fun _ -> Meter.serialization raw) [();();();()];
  let document = D.of_controlled_json ~path:"/document" raw in
  let root = "/document" and pp = "/document/program" in
  let program = get root "program" raw in
  identifier (pp ^ "/id") (text pp "id" program);
  let declarations = list pp "declarations" program in
  require (pp ^ "/declarations") (List.length declarations = 15)
    "Controlled source requires precisely its fifteen declarations, including all six obligations.";
  let symbols : symbol list = List.mapi (fun index original ->
    let path = pp ^ "/declarations/" ^ string_of_int index in
    let id = text path "id" original in identifier (path ^ "/id") id;
    ({id;path;index;original} : symbol)) declarations in
  let index : symbol Names.t = List.fold_left (fun table (symbol:symbol) ->
    require symbol.path (not (Names.mem symbol.id table)) "Duplicate controlled source declaration.";
    Names.add symbol.id symbol table) Names.empty symbols in
  let of_kind kind : symbol list = List.filter (fun (symbol:symbol) -> text symbol.path "$type" symbol.original = kind) symbols in
  let one kind : symbol = match of_kind kind with
    | [symbol] -> symbol | _ -> fail (pp ^ "/declarations") ("Expected exactly one " ^ kind ^ " declaration.") in
  let resolve path kind value : symbol =
    require path (text path "kind" value = kind) "Reference names the wrong declaration kind.";
    let identity = text path "id" value in
    match Names.find_opt identity index with
    | Some (symbol:symbol) when text symbol.path "$type" symbol.original = kind -> symbol
    | _ -> fail path "Reference does not resolve to its original declaration." in
  let bind path kind (symbol:symbol) value =
    let resolved : symbol = resolve path kind value in
    require path (resolved.id = symbol.id) "Source reference resolves to another executor, encounter or endpoint." in
  let executor : symbol = one "Role" and target : symbol = one "Subject" and encounter : symbol = one "Encounter"
  and clock : symbol = one "Clock" and activity : symbol = one "ControlledActivity" in
  require (pp ^ "/declarations") (List.length (of_kind "Observation") = 2 &&
    List.length (of_kind "Parameter") = 2 && List.length (of_kind "Requirement") = 6)
    "Extra observations, products, requirements or executable features are unsupported.";
  let sp = pp ^ "/semantics" in
  let semantics = get pp "semantics" program in
  identifier (sp ^ "/id") (text sp "id" semantics);
  nonblank (sp ^ "/version") (text sp "version" semantics);
  let definitions = list sp "definitions" semantics in
  require (sp ^ "/definitions") (List.length definitions <= 128)
    "Controlled source definition census exceeds its closed bound.";
  let definition_index : definition Names.t = List.mapi (fun position body ->
    let path = sp ^ "/definitions/" ^ string_of_int position in
    let identity = text path "id" body in
    identifier (path ^ "/id") identity; nonblank (path ^ "/version") (text path "version" body);
    nonblank (path ^ "/meaning") (text path "meaning" body);
    empty path ["assumptions"] body;
    nulls path ["executor_kind";"subject_kind"] body;
    let reference = obj ["$type",str "DefinitionRef";"id",str identity;"version",get path "version" body;
      "digest",str (D.document_digest body)] in
    ({identity;path;reference;body} : definition)) definitions
    |> List.fold_left (fun table (definition:definition) ->
      require definition.path (not (Names.mem definition.identity table)) "Duplicate semantic definition identity.";
      Names.add definition.identity definition table) Names.empty in
  let used = ref Seen.empty in
  let definition path value : definition =
    let identity = text path "id" value in
    let original : definition = match Names.find_opt identity definition_index with
      | Some original -> original | None -> fail path "Complete original semantic definition body is absent." in
    exact path value original.reference "Definition reference differs from the full original body/version/digest.";
    used := Seen.add identity !used; original in
  (* Resolve every pin in all original source fields, including deployment and
     catalog dependencies. These original bodies remain independent of the
     selected mechanism and are retained even where later context admission owns
     their interpretation. No source-map/provenance exclusion is used here. *)
  let rec references path = function
    | Json.Object fields as value ->
        if List.assoc_opt "$type" fields = Some (str "DefinitionRef") then ignore (definition path value)
        else List.iter (fun (key,value) -> references (path ^ "/" ^ key) value) fields
    | Json.Array values -> List.iteri (fun i value -> references (path ^ "/" ^ string_of_int i) value) values
    | _ -> () in
  references root raw;
  require (sp ^ "/definitions") (Seen.cardinal !used = Names.cardinal definition_index)
    "Unused semantic definitions are outside this closed source family.";
  let interpreted = ref Seen.empty in
  let semantic path value ~category ~meaning ~result : definition =
    let original : definition = definition path value in
    empty original.path ["parameters"] original.body;
    require path (text original.path "category" original.body = category) "Semantic category differs from this source use.";
    exact (original.path ^ "/result") (get original.path "result" original.body) result "Semantic result type differs from the fixed operation/readout.";
    (match list original.path "clauses" original.body with
     | [clause] ->
         let cp = original.path ^ "/clauses/0" in
         require (cp ^ "/kind") (text cp "kind" clause = "postcondition") "Unsupported semantic clause interpretation.";
         nonblank (cp ^ "/description") (text cp "description" clause);
         exact (cp ^ "/expression") (get cp "expression" clause) (marker meaning)
           "Semantic clause does not supply the exact controlled source interpretation."
     | _ -> fail (original.path ^ "/clauses") "Exactly one interpreted clause is required; extra clauses cannot be discarded.");
    interpreted := Seen.add original.identity !interpreted; original in
  let definition_use (symbol:symbol) key category meaning result : definition =
    semantic (symbol.path ^ "/" ^ key) (get symbol.path key symbol.original) ~category ~meaning ~result in
  nulls executor.path ["population"] executor.original;
  exact (executor.path ^ "/lineage_role") (get executor.path "lineage_role" executor.original) (Json.Bool false)
    "Population/lineage execution is outside the one-executor profile.";
  let capability : definition = match list executor.path "requires" executor.original with
    | [pin] -> semantic (executor.path ^ "/requires/0") pin ~category:"capability" ~meaning:"human_t_cell" ~result:Json.Null
    | _ -> fail (executor.path ^ "/requires") "Exactly the interpreted human T-cell capability is required." in
  require target.path (text target.path "entity_kind" target.original = "cell" &&
    text target.path "identity" target.original = "encounter") "The activity target must be one encounter-owned cell subject.";
  bind (target.path ^ "/executor") "Role" executor (get target.path "executor" target.original);
  bind (target.path ^ "/encounter") "Encounter" encounter (get target.path "encounter" target.original);
  nulls target.path ["domain"] target.original;
  bind (encounter.path ^ "/executor") "Role" executor (get encounter.path "executor" encounter.original);
  bind (encounter.path ^ "/target") "Subject" target (get encounter.path "target" encounter.original);
  require encounter.path (text encounter.path "termination" encounter.original = "explicit_event")
    "Controlled encounters require the explicit bounded start/end/reset lifecycle.";
  ignore (definition_use encounter "contract" "encounter" "encounter" Json.Null);
  require clock.path (text clock.path "basis" clock.original = "logical" &&
    text clock.path "simultaneous" clock.original = "atomic_batch") "Controlled activity requires one atomic sampled logical clock.";
  let duration path value =
    let unit = get path "unit" value in
    require (path ^ "/unit") (text path "dimension" unit = "time" && text path "quantity_kind" unit = "duration" &&
      get path "reference" unit = Json.Null) "Time values require an unreferenced duration unit.";
    let scale = D.exact_decimal ~path:(path ^ "/unit/scale") (text path "scale" unit) in
    let amount = D.exact_decimal ~path:(path ^ "/amount") (text path "amount" value) in
    require path (Q.sign scale > 0 && Q.sign amount > 0) "Time quantities and unit scales must be positive.";
    Q.mul amount scale in
  let resolution = get clock.path "resolution" clock.original in
  let tick_resolution = duration (clock.path ^ "/resolution") resolution in
  let tick_unit = get (clock.path ^ "/resolution") "unit" resolution in
  let ticks path value =
    let amount = Q.div (duration path value) tick_resolution in
    require path (Z.equal (Q.den amount) Z.one && Z.compare (Q.num amount) (Z.of_int 10_000) <= 0)
      "Source times must be positive integral ticks within the admitted 10,000-tick ceiling.";
    Z.to_int (Q.num amount) in
  let assurance = get root "assurance" raw and ap = root ^ "/assurance" in
  empty ap ["assumptions";"tolerances"] assurance;
  let horizon = get ap "horizon" assurance in
  let horizon_ticks = ticks (ap ^ "/horizon") horizon in
  let observed : observation list = List.map (fun (symbol:symbol) ->
    bind (symbol.path ^ "/observer") "Role" executor (get symbol.path "observer" symbol.original);
    bind (symbol.path ^ "/clock") "Clock" clock (get symbol.path "clock" symbol.original);
    exact (symbol.path ^ "/value_type") (get symbol.path "value_type" symbol.original) (scalar "truth") "Gate observations must be truth-valued.";
    require symbol.path (text symbol.path "access" symbol.original = "cell" &&
      text symbol.path "coverage" symbol.original = "sampled" && text symbol.path "coherence" symbol.original = "atomic_frame")
      "The cellular gate requires sampled coherent inputs; an evaluator is not an actuator.";
    nulls symbol.path ["spatial_scope"] symbol.original;
    exact (symbol.path ^ "/invalidity") (get symbol.path "invalidity" symbol.original)
      (arr (List.map str ["missing";"stale";"invalid";"conflicting"])) "All unresolved evidence states must remain distinct.";
    let subject = get symbol.path "subject" symbol.original in
    let scope, meaning = if Json.equal subject (reference "Role" executor.id) then Executor,"controller"
      else if Json.equal subject (reference "Subject" target.id) then Encounter,"antigen"
      else fail (symbol.path ^ "/subject") "Observation uses the wrong executor/encounter scope." in
    let contract : definition = definition_use symbol "contract" "observation" meaning (scalar "truth") in
    let freshness_ticks = ticks (symbol.path ^ "/freshness") (get symbol.path "freshness" symbol.original) in
    ({symbol;scope;contract;freshness_ticks} : observation)) (of_kind "Observation") in
  let observation scope : observation = match List.filter (fun (value:observation) -> value.scope = scope) observed with
    | [value] -> value | _ -> fail (pp ^ "/declarations") "Exactly one antigen and one executor-local controller observation are required." in
  let antigen : observation = observation Encounter and controller : observation = observation Executor in
  bind (activity.path ^ "/executor") "Role" executor (get activity.path "executor" activity.original);
  bind (activity.path ^ "/subject") "Subject" target (get activity.path "subject" activity.original);
  bind (activity.path ^ "/clock") "Clock" clock (get activity.path "clock" activity.original);
  let operation : definition = definition_use activity "contract" "operation" "activity" Json.Null in
  let readout : definition = definition_use activity "readout" "observation" "readout" (scalar "text") in
  let antigen_expr = expr "observe" "truth" ~reference:(reference "Observation" antigen.symbol.id) ~scope:(reference "Subject" target.id) () in
  let controller_expr = expr "observe" "truth" ~reference:(reference "Observation" controller.symbol.id) ~scope:(reference "Role" executor.id) () in
  let gate = get activity.path "gate" activity.original in
  require (activity.path ^ "/gate") (Json.equal gate (expr "all" "truth" ~args:[antigen_expr;controller_expr] ()) ||
    Json.equal gate (expr "all" "truth" ~args:[controller_expr;antigen_expr] ()))
    "Activity gate must be exactly antigen AND executor-local controller, with no ignored expression fields.";
  let products : product list = list activity.path "products" activity.original |> List.mapi (fun position value ->
    let path = activity.path ^ "/products/" ^ string_of_int position in
    let symbol : symbol = resolve path "Parameter" value in
    exact (symbol.path ^ "/value_type") (get symbol.path "value_type" symbol.original) (scalar "text") "Product identity must be a text parameter.";
    require symbol.path (text symbol.path "selection" symbol.original = "fixed") "Product selection must retain the fixed original identity.";
    nulls symbol.path ["lower";"upper"] symbol.original;
    let product_identity = text symbol.path "value" symbol.original in
    nonblank (symbol.path ^ "/value") product_identity; ({symbol;product_identity} : product)) in
  let products : product * product = match products with
    | [(a:product);(b:product)] when a.symbol.id <> b.symbol.id && a.product_identity <> b.product_identity -> a,b
    | _ -> fail (activity.path ^ "/products") "Exactly two distinct original product parameters are required." in
  let band value = expr "eq" "truth" ~args:[expr "activity_band" "text"
    ~reference:(reference "ControlledActivity" activity.id) ~scope:(reference "Subject" target.id) ();
    expr "literal" "text" ~value:(str value) ()] () in
  let all_kinds = [No_unauthorized_activation;Initial_activation;Controller_cessation;
    Antigen_cessation;Component_cessation;Reactivation] in
  let obligations : obligation list = List.map (fun (symbol:symbol) ->
    nonblank (symbol.path ^ "/description") (text symbol.path "description" symbol.original);
    exact (symbol.path ^ "/scope") (get symbol.path "scope" symbol.original)
      (obj ["$type",str "Scope";"kind",str "executor";"subject",reference "Role" executor.id]) "Every activity obligation requires the sole executor scope.";
    bind (symbol.path ^ "/clock") "Clock" clock (get symbol.path "clock" symbol.original);
    exact (symbol.path ^ "/applies_to") (get symbol.path "applies_to" symbol.original)
      (arr [reference "ControlledActivity" activity.id]) "Obligation does not bind exactly the original activity endpoint.";
    nulls symbol.path ["condition";"trigger";"lower";"upper"] symbol.original;
    empty symbol.path ["assumptions"] symbol.original;
    require (symbol.path ^ "/horizon") (ticks (symbol.path ^ "/horizon") (get symbol.path "horizon" symbol.original) = horizon_ticks)
      "Each source obligation must preserve the complete original assurance horizon.";
    let raw_definition : definition = definition (symbol.path ^ "/contract") (get symbol.path "contract" symbol.original) in
    let clause = match list raw_definition.path "clauses" raw_definition.body with
      | [clause] -> clause | _ -> fail raw_definition.path "Requirement needs one explicit interpreted clause." in
    let kind = match List.filter (fun kind -> Json.equal (get raw_definition.path "expression" clause) (marker (obligation_tag kind))) all_kinds with
      | [kind] -> kind | _ -> fail raw_definition.path "Unsupported requirement clause; no source obligation may be dropped." in
    let contract : definition = definition_use symbol "contract" "requirement" (obligation_tag kind) Json.Null in
    let deadline_ticks = if kind = No_unauthorized_activation then (
      require symbol.path (text symbol.path "kind" symbol.original = "safety") "Unauthorized activation is a safety obligation.";
      nulls symbol.path ["response";"deadline"] symbol.original; None)
    else (
      require symbol.path (text symbol.path "kind" symbol.original = "progress") "Timed activity responses require progress obligations.";
      exact (symbol.path ^ "/response") (get symbol.path "response" symbol.original)
        (band (if kind = Initial_activation || kind = Reactivation then "active" else "background"))
        "Response must read the exact modeled activity band, not product generation or effect completion.";
      Some (ticks (symbol.path ^ "/deadline") (get symbol.path "deadline" symbol.original))) in
    ({symbol;kind;contract;deadline_ticks} : obligation)) (of_kind "Requirement") in
  List.iter (fun kind -> require (pp ^ "/declarations")
    (List.length (List.filter (fun (item:obligation) -> item.kind = kind) obligations) = 1)
    "Every one of the six source obligations must appear exactly once.") all_kinds;
  let claimed = list ap "requirements" assurance |> List.map (Json.string ~path:(ap ^ "/requirements")) in
  require (ap ^ "/requirements") (List.sort String.compare claimed = List.sort String.compare
    (List.map (fun (item:obligation) -> item.symbol.id) obligations)) "Assurance requirements must preserve the exact complete source obligation set.";
  let bound kind = match (List.find (fun (item:obligation) -> item.kind = kind) obligations).deadline_ticks with
    | Some value -> value | None -> fail ap "Missing timed source obligation." in
  let deadlines : deadlines = {onset_ticks=bound Initial_activation;controller_off_ticks=bound Controller_cessation;
    antigen_off_ticks=bound Antigen_cessation;component_off_ticks=bound Component_cessation;
    reactivation_ticks=bound Reactivation} in
  let dp = root ^ "/deployment" in
  let deployment = get root "deployment" raw in
  require (dp ^ "/route") (text dp "route" deployment = "in_vivo") "Only the original human in-vivo deployment is in scope.";
  empty dp ["environment"] deployment;
  let binding = match list dp "bindings" deployment with [value] -> value
    | _ -> fail (dp ^ "/bindings") "Exactly one original recipient binding is required." in
  bind (dp ^ "/bindings/0/role") "Role" executor (get dp "role" binding);
  let chassis = get dp "chassis" binding in
  require (dp ^ "/bindings/0/chassis") (text dp "species" chassis = "human" &&
    text dp "recipient_class" chassis = "immune" && text dp "lineage" chassis = "T_cell")
    "The sole source executor must bind an explicitly declared human immune T cell.";
  exact dp (get dp "capabilities" chassis) (arr [capability.reference]) "Recipient capability differs from the original role contract.";
  empty dp ["environment";"interfaces"] chassis;
  let delivery = get dp "delivery" deployment in
  require (dp ^ "/delivery/co_delivery") (text dp "co_delivery" delivery = "same_recipient") "Two products require the explicit same-recipient delivery premise.";
  exact dp (get dp "intended_recipients" delivery) (arr [reference "Role" executor.id]) "Delivery recipients differ from the sole executor.";
  empty (dp ^ "/delivery") ["assumptions"] delivery;
  let payload = get dp "payload" deployment in
  List.iter (fun (key,value) -> exact (dp ^ "/payload/" ^ key) (get dp key payload) (Json.int value)
    "Source RNA/product census differs from the closed two-product profile.")
    ["design_count",1;"member_count",2;"helper_count",0;"orf_count",2;"product_count",2];
  nulls (dp ^ "/payload") ["copy_number";"dose";"payload_persistence";"effector_persistence"] payload;
  let ip = root ^ "/implementations" in
  let catalog = get root "implementations" raw in
  let selected_implementation = match list ip "implementations" catalog with [value] -> value
    | _ -> fail ip "Exactly one complete supplied implementation is required; selection search is not admitted." in
  exact ip (get ip "operation" selected_implementation) operation.reference "Selected catalog entry names another activity operation.";
  exact ip (get ip "chassis" selected_implementation) (arr [get dp "id" chassis]) "Selected implementation has a different recipient scope.";
  exact ip (get ip "payload_formats" selected_implementation) (arr [str "RNA"]) "Selected implementation must preserve the RNA-only payload.";
  empty ip ["evidence"] selected_implementation;
  let supplied_products = ref Seen.empty in
  Names.iter (fun _ (definition:definition) ->
    if not (Seen.mem definition.identity !interpreted) then (
      empty definition.path ["clauses"] definition.body;
      nulls definition.path ["result"] definition.body;
      match list definition.path "parameters" definition.body with
      | [] -> ()
      | parameters ->
          require definition.path (text definition.path "category" definition.body = "model")
            "Only exact supplied product descriptors admit inert semantic parameters.";
          require (definition.path ^ "/parameters") (List.length parameters = 3)
            "A product descriptor must retain identity, version and content digest.";
          let values = List.map2 (fun (index,key) parameter ->
            let path = definition.path ^ "/parameters/" ^ string_of_int index in
            require path (text path "id" parameter = key && text path "selection" parameter = "fixed")
              "Supplied product descriptor fields are fixed and ordered.";
            exact (path ^ "/value_type") (get path "value_type" parameter) (scalar "text")
              "Product descriptor values require text types.";
            nulls path ["lower";"upper"] parameter;
            let value = text path "value" parameter in nonblank path value; value)
            [0,"product_identity";1,"product_version";2,"product_sha256"] parameters in
          (match values with
           | [identity;_version;digest] ->
               let (a:product),(b:product) = products in
               require definition.path (identity = a.product_identity || identity = b.product_identity)
                 "Supplied product descriptor does not name either original source product.";
               require definition.path (not (Seen.mem identity !supplied_products))
                 "A source product has more than one supplied descriptor.";
               require definition.path (String.length digest = 64 && String.for_all
                 (function '0'..'9' | 'a'..'f' -> true | _ -> false) digest)
                 "Supplied product descriptors require lowercase SHA-256 content pins.";
               supplied_products := Seen.add identity !supplied_products
           | _ -> assert false))) definition_index;
  require (sp ^ "/definitions") (Seen.cardinal !supplied_products = 2)
    "Both original source products require complete supplied identity/version/digest descriptors.";
  List.iteri (fun i span ->
    let path = pp ^ "/source_map/" ^ string_of_int i in
    require path (Names.mem (text path "declaration_id" span) index) "Source map refers to an absent declaration.";
    nonblank (path ^ "/file") (text path "file" span)) (list pp "source_map" program);
  let source_value : source = {executor;target;encounter;clock;tick_resolution;tick_unit;resolution;horizon_ticks;
    antigen;controller;products;activity;operation;readout;obligations;deadlines;selected_implementation} in
  let symbol_json (symbol:symbol) = obj ["id",str symbol.id;"source_path",str symbol.path;
    "source_index",Json.int symbol.index;"kind",get symbol.path "$type" symbol.original;"original",symbol.original] in
  let definition_json (definition:definition) = obj ["reference",definition.reference;"source_path",str definition.path;"original",definition.body] in
  let correspondence_value = obj ["declarations",arr (List.map symbol_json symbols);
    "definitions",arr (List.map definition_json (Names.bindings definition_index |> List.map snd));
    "source_map",get pp "source_map" program] in
  let report_value = obj ["schema_version",str schema_version;"status",str "source_admitted";
    "profile",str D.controlled_source_profile;
    "document_fingerprint",str (D.controlled_fingerprint document);
    "artifact_digest",str (D.controlled_artifact_digest document);"document",raw;
    "horizon_ticks",Json.int horizon_ticks;
    "requirements",arr (List.map (fun (item:obligation) -> obj ["id",str item.symbol.id;
      "kind",str (obligation_tag item.kind);"source_path",str item.symbol.path;
      "deadline_ticks",(match item.deadline_ticks with None -> Json.Null | Some value -> Json.int value)]) obligations);
    "correspondence",correspondence_value;"execution",str "not_performed";"material",str "not_performed";
    "empirical_status",str "unassessed";"context_status",str "supplied_not_realized"] in
  Meter.preflight report_value;
  {document_value=document;source_value;report_value;correspondence_value}
end

let admit ~charge ~(document:D.controlled) : t =
  let module Admission = Make(struct let charge = charge end) in
  Admission.admit ~document
