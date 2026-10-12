open Bioc_wire
module D = Bioc_domain.Policy_document
module S = Bioc_checker.Policy_controlled_source
let require condition message = if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let set key replacement value = obj (List.map (fun (name,item) -> name,if name=key then replacement else item) (Json.object_fields value))
let update key f value = set key (f (get key value)) value
let declaration identity f = update "program" (update "declarations" (fun values ->
  Json.Array (List.map (fun value -> if text "id" value=identity then f value else value) (Json.array values))))
let source_definition identity f = update "program" (update "semantics" (update "definitions" (fun values ->
  Json.Array (List.map (fun value -> if text "id" value=identity then f value else value) (Json.array values)))))
let admit json = S.admit ~charge:(fun _ -> ()) ~document:(D.of_controlled_json json)
let rejected label f = match f () with
  | _ -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error _ -> ()
let rejected_source label json = match admit json with
  | _ -> failwith (label ^ ": intended source rejection accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code="policy_controlled_source") (label ^ ": incorrect rejection stage " ^ diagnostic.code);
      require (Option.is_some diagnostic.path) (label ^ ": source diagnostic lost its original path")
let repin_definitions json =
  let definitions = Json.array (get "definitions" (get "semantics" (get "program" json))) in
  let rec visit = function
    | Json.Object fields as value when List.assoc_opt "$type" fields=Some(str "DefinitionRef") ->
        let original=List.find (fun body -> text "id" body=text "id" value) definitions in
        set "version" (get "version" original) (set "digest" (str(D.document_digest original)) value)
    | Json.Object fields -> obj(List.map(fun (key,value)->key,visit value)fields)
    | Json.Array values -> Json.Array(List.map visit values)
    | value -> value in
  visit json

let positive json =
  let admitted : S.t = admit json in
  let source : S.source = S.typed admitted in
  require(source.executor.id="tcell" && source.target.id="target" && source.encounter.id="contact") "Resolved source owner identities differ";
  require(source.antigen.scope=S.Encounter && source.controller.scope=S.Executor) "Mixed observation ownership collapsed";
  require(source.antigen.symbol.id="antigen" && source.controller.symbol.id="controller") "Observation bindings changed";
  let (a:S.product),(b:S.product)=source.products in
  require(a.symbol.id="product-a" && b.symbol.id="product-b") "Original product member order changed";
  require(source.deadlines.onset_ticks=2 && source.deadlines.controller_off_ticks=2 &&
    source.deadlines.antigen_off_ticks=2 && source.deadlines.component_off_ticks=2 && source.deadlines.reactivation_ticks=2)
    "Source requirement deadlines were not independently elaborated";
  require(source.horizon_ticks=10 && Q.equal source.tick_resolution Q.one) "Exact source clock or horizon changed";
  require(List.length source.obligations=6) "Source obligation dropped";
  require(Json.equal(D.controlled_to_json(S.document admitted))json) "Complete source authority changed";
  let report=S.report admitted in
  require(text "status" report="source_admitted" && text "execution" report="not_performed" &&
    text "material" report="not_performed" && text "empirical_status" report="unassessed") "Source token was promoted to execution or material acceptance";
  let mapping=S.correspondence admitted in
  require(List.length(Json.array(get "declarations" mapping))=15) "Incomplete source declaration correspondence";
  require(Json.equal(get "source_map" mapping)(get "source_map"(get "program" json))) "Authored source paths were erased";
  List.iter(fun (item:S.obligation)->require(String.starts_with ~prefix:"/document/program/declarations/" item.symbol.path)
    "Requirement occurrence lost its canonical source path")source.obligations;
  let bytes=Canonical.encode report in
  require(bytes=Canonical.encode(S.report(admit json))) "Repeated source admission is not canonical";
  let changed=declaration "controller-off" (update "deadline" (set "amount" (str "3"))) json
    |> declaration "antigen-off" (update "deadline" (set "amount" (str "1")))
    |> declaration "component-off" (update "deadline" (set "amount" (str "4"))) in
  let independent : S.source = S.typed(admit changed) in
  require(independent.deadlines.controller_off_ticks=3 && independent.deadlines.antigen_off_ticks=1 &&
    independent.deadlines.component_off_ticks=4 && independent.deadlines.onset_ticks=2) "Independent source off deadlines were conflated";
  let mapped=update "program" (update "source_map" (fun values->Json.Array(List.map(set "line"(Json.int 2))(Json.array values)))) json in
  let modified : S.t = admit mapped in
  require(D.controlled_fingerprint(S.document admitted)=D.controlled_fingerprint(S.document modified)) "Source-map exclusion changed legacy digest meaning";
  require(D.controlled_artifact_digest(S.document admitted)<>D.controlled_artifact_digest(S.document modified)) "Full source authority discarded source-map changes"

let negatives json =
  rejected "legacy document route" (fun()->D.of_json json);
  rejected "static expression route" (fun()->D.of_expression_json json);
  rejected "standalone controlled program" (fun()->D.of_controlled_json(get "program" json));
  rejected "legacy nested program" (fun()->D.of_controlled_json(update "program" (set "profile"(str D.profile))json));
  rejected "unknown field" (fun()->D.of_controlled_json(obj(("native_accepted",Json.Bool true)::Json.object_fields json)));
  let controller=List.find(fun value->text "id" value="controller")(Json.array(get "declarations"(get "program" json))) in
  let antigen=List.find(fun value->text "id" value="antigen")(Json.array(get "declarations"(get "program" json))) in
  let cases=[
    "controller encounter scope",declaration "controller" (set "subject"(get "subject" antigen))json;
    "antigen executor scope",declaration "antigen" (set "subject"(get "subject" controller))json;
    "evaluator-as-actuator",declaration "controller" (set "access"(str "external_evaluator"))json;
    "unresolved evidence erased",declaration "controller" (set "invalidity"(Json.Array[]))json;
    "continuous observation",declaration "antigen" (set "coverage"(str "continuous"))json;
    "wrong controller contract",declaration "controller" (set "contract"(get "contract" antigen))json;
    "gate hidden value",declaration "activity" (update "gate"(set "value"(Json.Bool true)))json;
    "OR gate",declaration "activity" (update "gate"(set "op"(str "any")))json;
    "lost source requirement",update "assurance"(set "requirements"(Json.Array[]))json;
    "extra requirement",update "program"(update "declarations"(fun values->let values=Json.array values in Json.Array(values@[List.hd(List.rev values)])))json;
    "duplicate product",declaration "activity"(update "products"(fun values->let first=List.hd(Json.array values)in Json.Array[first;first]))json;
    "unfixed product",declaration "product-a"(set "selection"(str "design"))json;
    "fractional source deadline",declaration "onset"(update "deadline"(set "amount"(str "0.5")))json;
    "zero source deadline",declaration "controller-off"(update "deadline"(set "amount"(str "0")))json;
    "deadline exceeds ceiling",declaration "reactivation"(update "deadline"(set "amount"(str "10001")))json;
    "unmapped source constraint",declaration "onset"(set "condition"(get "response"(List.find(fun value->text "id" value="onset")(Json.array(get "declarations"(get "program" json))))))json;
    "definition body substitution",source_definition "contract.activity"(set "meaning"(str "Foreign unchanged-pin meaning"))json;
    "repinned wrong activity semantics",repin_definitions(source_definition "contract.activity"(update "clauses"(fun values->Json.Array(List.map(update "expression"(set "value"(str "biocompiler.controlled_source.secretion.v0.1")))(Json.array values))))json);
    "repinned extra clause",repin_definitions(source_definition "contract.activity"(update "clauses"(fun values->let values=Json.array values in Json.Array(values@values)))json);
    "dropped supplied product descriptor",repin_definitions(source_definition "artificial.product-a"(set "parameters"(Json.Array[]))json);
    "repinned foreign product descriptor",repin_definitions(source_definition "artificial.product-a"(update "parameters"(fun values->Json.Array(List.mapi(fun i parameter->if i=0 then set "value"(str "foreign-product")parameter else parameter)(Json.array values))))json);
    "repinned designed product descriptor",repin_definitions(source_definition "artificial.product-a"(update "parameters"(fun values->Json.Array(List.mapi(fun i parameter->if i=0 then set "selection"(str "design")parameter else parameter)(Json.array values))))json);
    "wrong physical recipient",update "deployment"(update "bindings"(fun values->Json.Array(List.map(update "chassis"(set "lineage"(str "B_cell")))(Json.array values))))json;
    "population co-delivery",update "deployment"(update "delivery"(set "co_delivery"(str "same_population")))json;
    "extra source RNA",update "deployment"(update "payload"(set "member_count"(Json.int 3)))json;
  ] in
  List.iter(fun(label,value)->rejected_source label value)cases;
  let charged=ref 0 in
  (match S.admit ~charge:(fun amount->charged:= !charged+amount;if !charged>64 then Diagnostic.fail "fixture_budget" "Stop source work.")
      ~document:(D.of_controlled_json json) with
   | _->failwith "Exhausted source admission returned a token"
   | exception Diagnostic.Error diagnostic->require(diagnostic.code="fixture_budget") "Source admission replaced original meter failure");
  require(!charged>64) "Source admission did not charge the original invocation"

let () =
  require(Array.length Sys.argv=2) "Expected complete original controlled-source fixture path";
  let channel=open_in_bin Sys.argv.(1) in
  let source=Fun.protect ~finally:(fun()->close_in channel)(fun()->really_input_string channel(in_channel_length channel)) in
  let json=Json.parse source in
  positive json;negatives json;
  print_endline "controlled source admission: source-only typed resolution and independent obligation controls passed"
