open Bioc_wire
open Bioc_domain
module B=Bioc_compiler.Reference_producer_budget
module P=Bioc_compiler.Reference_construct_producer
module E=Bioc_compiler.Reference_sequence_emitter
module W=Bioc_checker.Work_budget
module Check=Bioc_checker.Reference_construct_check
module Codec=Verification_exploration.Codec
module C=Reference_construct
module M=Reference_manifest
module A=Reference_components
module N=Reference_molecular
let require condition message=if not condition then failwith message
let resource run=
  try ignore(run());failwith "Expected producer resource rejection" with
  | Diagnostic.Error error->
      require (List.mem error.code ["reference_producer_resource_limit";"verification_exploration_limit";
        "verification_exploration_cycle";"reference_check_work_limit";"reference_check_item_limit";
        "reference_check_report_limit";"composition_work_limit";"composition_input_limit";
        "composition_report_limit";"composition_item_limit"])
        ("Resource exhaustion was remapped: "^error.code^": "^error.message);error
let expect code message run=
  try ignore(run());failwith "Expected exact diagnostic" with Diagnostic.Error error->
    require (error.code=code && error.message=message) ("Unexpected diagnostic: "^error.code^": "^error.message)
let field key value=Json.field key (Json.object_fields value)
let number key value=Z.to_int (Json.integer (field key value))
let parent maximum=W.create ~profile:"reference.producer.test" ~error_code:"reference_test_parent_limit" ~maximum ()
let load directory identity=
  let channel=open_in_bin (Filename.concat directory (identity^".json")) in
  let raw=Fun.protect ~finally:(fun()->close_in_noerr channel) (fun()->
    let length=in_channel_length channel in require (length>0 && length<=Limits.max_request_bytes) "Unbounded fixture";
    really_input_string channel length) in
  let value=Json.parse_artifact ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes raw in
  require (Canonical.fingerprint value=identity) "Original producer authority changed";value
let one=function [value]->value|_->failwith "Expected one original fixture member"
let atomic_work_tests ()=
  let ancestor=parent 7 in
  let budget=B.create ~parent:ancestor (B.make_limits ~max_work:10 ()) in
  B.charge_product budget 2 3;
  require (W.remaining ancestor=1 && W.remaining (B.work budget)=1) "Product charge missed an ancestor";
  (try B.charge_product budget max_int max_int;failwith "Overflowing product accepted" with
   | Diagnostic.Error error->require (error.code="reference_test_parent_limit" && W.is_exhaustion ancestor error)
       "Overflow was not rejected by the actual limiting ancestor");
  require (W.remaining ancestor=1 && W.exhausted ancestor) "Failed work charge was not atomic and sticky";
  let budget=B.create (B.make_limits ~max_work:6 ()) in
  B.charge_product budget 2 3;require (W.remaining (B.work budget)=0) "Exact product budget changed";
  ignore(resource(fun()->B.charge budget 1));
  let budget=B.create (B.make_limits ()) in
  expect "reference_producer_limits" "Reference producer work factors must be nonnegative."
    (fun()->B.charge_product budget (-1) 1);
  expect "reference_producer_limits" "Reference producer limits exceed the fixed resource profile."
    (fun()->B.make_limits ~max_work:max_int ())
let reservation_tests ()=
  let value=Json.Array [Json.int 10] in
  let size=Codec.measure value in
  require (size.bytes=4 && size.nodes=2) "Reservation fixture identity changed";
  List.iter (fun reserve->
    let make bytes nodes=B.create (B.make_limits ~max_input_bytes:bytes ~max_output_bytes:bytes
      ~max_input_nodes:nodes ~max_output_nodes:nodes ()) in
    let exact=make (2*size.bytes) (2*size.nodes) in
    reserve exact value;reserve exact value;ignore(resource(fun()->reserve exact Json.Null));
    let byte_short=make (2*size.bytes-1) (2*size.nodes) in
    reserve byte_short value;ignore(resource(fun()->reserve byte_short value));
    let node_short=make (2*size.bytes) (2*size.nodes-1) in
    reserve node_short value;ignore(resource(fun()->reserve node_short value));
    let rec cyclic=Json.Array [cyclic] in
    let cycle=resource(fun()->reserve (B.create B.default_limits) cyclic) in
    require (cycle.code="verification_exploration_cycle") "Cyclic reservation bypassed bounded codec") [B.input;B.output];
  let exact_work=parent 10_000_000 in
  let budget=B.create ~parent:exact_work B.default_limits in
  B.input budget value;B.output budget value;
  let consumed=10_000_000-W.remaining exact_work in
  let run allowance=
    let budget=B.create (B.make_limits ~max_work:allowance ()) in
    B.input budget value;B.output budget value;budget in
  require (W.remaining (B.work (run consumed))=0) "Reservation work is not deterministic";
  ignore(resource(fun()->run (consumed-1)))
let checker_reduction_tests ()=
  let inherited=Check.limits_json (B.checker_limits B.default_limits) in
  let original=Check.limits_json Check.default_limits in
  let expected=Json.Object (List.map (fun (key,value)->key,
    if key="max_report_bytes" then Json.int 16_777_216 else value) (Json.object_fields original)) in
  require (Canonical.encode inherited=Canonical.encode expected)
    "Default checker mapping relaxed a ceiling or dropped the producer output-byte bound";
  let inherited=Check.limits_json (B.checker_limits (B.make_limits ~max_work:7 ~max_input_bytes:2048
    ~max_input_nodes:11 ~max_output_bytes:1024 ~max_output_nodes:9 ())) in
  List.iter (fun (key,expected)->require (number key inherited=expected) ("Checker reduction was dropped: "^key))
    ["max_work",7;"max_input_bytes",2048;"max_report_bytes",1024;"max_report_nodes",9;
     "max_retained_intermediate_items",9;"max_input_nodes",Limits.max_json_nodes]
let actual_work label encode run=
  let maximum=256_000_000 in
  let ancestor=parent maximum in
  let expected=encode (run B.default_limits (Some ancestor)) in
  let used=maximum-W.remaining ancestor in
  require (used>1) (label^" did not charge actual production work");
  let exact=parent used in
  let actual=encode (run B.default_limits (Some exact)) in
  require (W.remaining exact=0 && Canonical.encode actual=Canonical.encode expected) (label^" exact ancestor changed result/work");
  let short=parent (used-1) in
  (try ignore(run B.default_limits (Some short));failwith (label^" accepted one-short ancestor") with
   | Diagnostic.Error error->require (error.code="reference_test_parent_limit" && W.is_exhaustion short error)
       (label^" swallowed actual ancestor exhaustion"));
  require (W.exhausted short) (label^" lost sticky ancestor exhaustion");
  require (Canonical.encode (encode (run (B.make_limits ~max_work:used ()) None))=Canonical.encode expected)
    (label^" exact local work budget changed output");
  ignore(resource(fun()->run (B.make_limits ~max_work:(used-1) ()) None));
  ignore(resource(fun()->run (B.make_limits ~max_work:0 ()) None));
  used
let ()=
  require (Array.length Sys.argv=2) "Expected original reference document directory";
  let load=load Sys.argv.(1) in
  (* These are complete caller inputs. Every output exercised below is produced
     by current native code; no accepted output or report is imported. *)
  let original=C.Request.of_json (load "6260b3a9fac1f1df4a7941ee60bfe9672fd73e1be66ded1c0f46d9ddd9880f1f") in
  let registry=Component_registry.of_json (load "15d4a9b57ec16b43ddc5297802ea974662ef5af54a4be17fd4f393fe008c49d9") in
  let manifests=Json.object_fields (load "f6119eba928e760f8201011028e007d9d46bdda0b599e946b0ea4f068663562b")
    |> List.map (fun (key,value)->key,M.of_json value) in
  let selection=C.Reference.selection (one (C.Request.references original)) in
  let manifest=List.assoc (Pinned_identity.id (A.Selection.manifest selection)) manifests in
  let composition=C.Request.composition original in
  let molecule_id=C.Molecule.id (one (C.Request.molecules original)) in
  let prepare ?(molecule_id=molecule_id) limits parent=P.prepare ~limits ?parent ~molecule_id ~manifest ~selection ~composition ~registry () in
  let request=prepare B.default_limits None in
  require (C.Request.fingerprint request=C.Request.fingerprint original) "Native preparation changed original supplied layout authority";
  let construct=P.generate request in
  let emit limits parent=E.emit ~limits ?parent ~request ~construct ~registry ~manifests () in
  let artifact=emit B.default_limits None in
  require (N.Artifact.construct_fingerprint artifact=C.Candidate.fingerprint construct) "Emitter lost actual generated construct";
  List.iter (fun molecule_id->expect "reference_construct_producer" "Molecule ID must be a nonempty string."
    (fun()->prepare ~molecule_id B.default_limits None)) ["";" \t\n";"\194\160";"\226\128\135\227\128\128";"\028"];
  let preserved="\194\160payload\226\128\135" in
  require (C.Molecule.id (one (C.Request.molecules (prepare ~molecule_id:preserved B.default_limits None)))=preserved)
    "Unicode name validation rewrote a valid identifier";
  atomic_work_tests();reservation_tests();checker_reduction_tests();
  ignore(actual_work "prepare" C.Request.to_json (fun limits parent->prepare limits parent));
  ignore(actual_work "generate" C.Candidate.to_json (fun limits parent->P.generate ~limits ?parent request));
  ignore(actual_work "emit" N.Artifact.to_json emit);
  List.iter (fun run->
    ignore(resource(fun()->run (B.make_limits ~max_input_bytes:1 ()) None));
    ignore(resource(fun()->run (B.make_limits ~max_input_nodes:1 ()) None));
    ignore(resource(fun()->run (B.make_limits ~max_output_bytes:1 ()) None));
    ignore(resource(fun()->run (B.make_limits ~max_output_nodes:1 ()) None)))
    [(fun limits parent->ignore(prepare limits parent));
     (fun limits parent->ignore(P.generate ~limits ?parent request));
     (fun limits parent->ignore(emit limits parent))];
  (* These reductions must fail inside the independent checker's allocation
     limits, rather than constructing a full artifact and failing only at the
     producer's final output reservation. *)
  List.iter (fun limits->let error=resource(fun()->emit limits None) in
    require (error.code<>"reference_producer_resource_limit") "Emitter dropped nested report reduction")
    [B.make_limits ~max_output_bytes:1 ();B.make_limits ~max_output_nodes:1 ()];
  let inputs=C.Request.to_json request::C.Candidate.to_json construct::Component_registry.to_json registry::
    List.map (fun (id,value)->Json.Object [id,M.to_json value]) manifests in
  let total_nodes=List.fold_left (fun total value->total+(Codec.measure value).nodes) 0 inputs in
  let largest=List.fold_left (fun total value->max total (Codec.measure value).nodes) 0 inputs in
  require (largest<total_nodes-1) "Cumulative input fixture does not distinguish per-document bounds";
  let error=resource(fun()->emit (B.make_limits ~max_input_nodes:(total_nodes-1) ()) None) in
  require (error.code="reference_producer_resource_limit") "Actual aggregate input-node bound was not enforced before checker entry";
  let rec repeated=("cycle",manifest)::repeated in
  expect "reference_sequence_emitter" "Reference manifest keys must be unique."
    (fun()->E.emit ~request ~construct ~registry ~manifests:repeated ());
  print_endline "Reference producers: actual generation/emission, inherited reductions, exact lifetime work and bounded inventories passed."
