open Bioc_wire
module C = Bioc_domain.Pipeline_contract
let require condition message = if not condition then failwith message
let get key raw = Json.field key (Json.object_fields raw)
let read path = let channel = open_in_bin path in
  let raw = really_input_string channel (in_channel_length channel) in
  close_in channel; Json.parse raw
module type Record = sig
  type t
  val of_json : ?limits:C.Codec.limits -> ?path:string -> Json.t -> t
  val to_json : t -> Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
end
let codec = function
  | "Source_link" -> (module C.Source_link : Record)
  | "Producer_obligation" -> (module C.Producer_obligation : Record)
  | "Scoped_obligation" -> (module C.Scoped_obligation : Record)
  | "Check_spec" -> (module C.Check_spec : Record)
  | "Check_decision" -> (module C.Check_decision : Record)
  | "Pass_contract" -> (module C.Pass_contract : Record)
  | "Pass_context" -> (module C.Pass_context : Record)
  | "Component_input_contract" -> (module C.Component_input_contract : Record)
  | "Completion_profile" -> (module C.Completion_profile : Record)
  | "Stage_record" -> (module C.Stage_record : Record)
  | "Pipeline_result" -> (module C.Pipeline_result : Record)
  | "Pass_result" -> (module C.Pass_result : Record)
  | _ -> failwith "Unreviewed pipeline record kind"
let rejected action = match action () with
  | _ -> failwith "Malformed or exhausted pipeline codec accepted"
  | exception Diagnostic.Error _ -> ()
let () =
  require (Array.length Sys.argv=2) "Expected independent pipeline literal fixture path";
  let fixture = read Sys.argv.(1) in
  require (get "assertion_status" fixture=Json.String "passed") "Original assertion did not pass";
  let literals = Json.array (get "literals" fixture) in
  require (List.length literals=13) "Complete pipeline literal inventory changed";
  List.iter (fun literal ->
    let kind=Json.string (get "kind" literal) and raw=get "document" literal in
    let module R = (val codec kind : Record) in
    let parsed=R.of_json raw in
    require (Canonical.encode (R.to_json parsed)=Canonical.encode raw) (kind^": complete original fields differ");
    require (R.fingerprint parsed=Json.string (get "fingerprint" literal)) (kind^": original identity differs");
    require (R.canonical_size parsed=Z.to_int (Json.integer (get "canonical_bytes" literal)))
      (kind^": canonical byte census differs");
    require (R.fingerprint (R.of_json (R.to_json parsed))=R.fingerprint parsed) (kind^": roundtrip changed identity");
    rejected (fun ()->R.of_json (Json.Object (("extra",Json.Null)::Json.object_fields raw)))) literals;
  let rejections=Json.array (get "rejections" fixture) in
  require (List.length rejections=19) "Original constructor rejection inventory changed";
  List.iter (fun literal ->
    let kind=Json.string (get "kind" literal) in
    let module R = (val codec kind : Record) in
    match R.of_json (get "document" literal) with
    | _ -> failwith (kind^": original constructor rejection was accepted")
    | exception Diagnostic.Error error ->
      require (error.message=Json.string (get "message" (get "error" literal)))
        (Json.string (get "id" literal)^": original rejection differs: "^error.message)) rejections;
  let unicode=List.find (fun literal->get "id" literal=Json.String "unicode-numeric-kinds") literals |> get "document" in
  let size=C.Codec.measure unicode in
  let exact=C.Codec.make_limits ~max_bytes:size.bytes ~max_nodes:size.nodes () in
  ignore(C.Check_decision.of_json ~limits:exact unicode);
  rejected(fun ()->C.Check_decision.of_json ~limits:(C.Codec.make_limits ~max_bytes:(size.bytes-1) ()) unicode);
  rejected(fun ()->C.Check_decision.of_json ~limits:(C.Codec.make_limits ~max_nodes:(size.nodes-1) ()) unicode);
  let rec cyclic=Json.Array[cyclic] in rejected(fun ()->C.Codec.measure cyclic);
  let rec spine=Json.Null::spine in rejected(fun ()->C.Codec.measure(Json.Array spine));
  rejected(fun ()->C.Codec.measure(Json.String "\255"));
  let unknown=C.Pass_result.make ~output:None ~obligations:[] ~source_links:[]
      ~observation_map:Json.Null ~search_status:"future" () in
  require(C.Pass_result.search_status unknown="future" && C.Pass_result.observation_map unknown=Json.Null)
    "Structural records prematurely claimed manager acceptance";
  let baseline=get "manager_baseline" fixture |> get "records" |> get "mechanism" in
  let historical=C.Stage_record.of_json baseline in
  require(C.Stage_record.accepted historical) "Historical inspection erased original claimed acceptance";
  let obligation=C.Scoped_obligation.make ~id:"retained_obligation" ~scope:"historical_view"
    ~evidence_kind:Bioc_domain.Realization_evidence.Unresolved
    ~description:"A retained object is not independent acceptance." () in
  let unresolved=[obligation] in
  let result=C.Pipeline_result.make ~status:C.Partial ~artifact:historical
    ~scope:"historical_view" ~unresolved () in
  require(C.Pipeline_result.artifact result==historical)
    "Typed result construction replaced its actual record capability";
  require(C.Pipeline_result.unresolved result==unresolved &&
    List.hd(C.Pipeline_result.unresolved result)==obligation)
    "Typed result construction replaced its unresolved obligation origins";
  let restored=C.Pipeline_result.of_json(C.Pipeline_result.to_json result) in
  require(C.Pipeline_result.artifact restored!=historical &&
    List.hd(C.Pipeline_result.unresolved restored)!=obligation)
    "Structural import reused externally supplied typed result origins";
  require(C.Pipeline_result.fingerprint restored=C.Pipeline_result.fingerprint result &&
    Canonical.encode(C.Pipeline_result.to_json restored)=Canonical.encode(C.Pipeline_result.to_json result))
    "Retaining typed result origins changed complete content or identity";
  print_endline "Pipeline contracts: 13 complete original records, 19 constructor rejections, bounded codecs and historical-only claims passed"
