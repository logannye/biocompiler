(* Literal callback envelopes exercise the real native capability adapter.
   They are protocol responses, never accepted manager records. *)
open Bioc_wire
module H = Bioc_pipeline_service.Host_bridge
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
let obj fields=Json.Object fields
let str value=Json.String value
let reference index=obj["handle",str("object/"^string_of_int index)]
let require condition message=if not condition then failwith message
let same left right=Canonical.encode left=Canonical.encode right
let budget ()=W.create ~profile:"host_bridge_test" ~error_code:"host_bridge_test_work" ~maximum:100_000_000 ()
let scripted steps =
  let pending=ref steps in
  let invoke ~action ~arguments=match !pending with
    | []->failwith ("Unexpected host action: "^action)
    | (name,expected,result)::tail->
      require (action=name && same arguments expected) ("Host action or exact arguments changed: "^action);
      pending:=tail;result in
  invoke,(fun ()->require (!pending=[]) "Host action sequence incomplete")
let failure action=
  try action ();failwith "Expected bridge rejection" with Diagnostic.Error _->()
exception Marker of string ref
let ()=
  let work=budget () in
  let invoke,finished=scripted [
    "document",obj["object",reference 0],reference 1;
    "is-instance",obj["object",reference 1;"type",str "Mapping"],Json.Bool true;
    "attr",obj["object",reference 1;"name",str "get"],reference 2;
    "literal",obj["kind",str "json";"value",str "schema_version"],reference 3;
    "call",obj["callable",reference 2;"args",Json.Array[reference 3];"kwargs",obj[]],reference 4;
    "is-instance",obj["object",reference 4;"type",str "str"],Json.Bool true;
    "attr",obj["object",reference 4;"name",str "strip"],reference 5;
    "call",obj["callable",reference 5;"args",Json.Array[];"kwargs",obj[]],reference 4;
    "truth",obj["object",reference 4],Json.Bool true;
    "freeze-json",obj["object",reference 1],reference 6;
    "json",obj["object",reference 6],obj["schema_version",str "test.v1"]] in
  let bridge=H.create ~budget:work ~invoke () in
  let value=H.of_reference bridge (reference 0) in
  require (value==H.of_reference bridge(reference 0)) "Host physical identity changed";
  require (same (H.reference bridge value) (reference 0)) "Host reference changed";
  let document=value.document work in
  require (document.is_instance work M.Mapping) "Mapping response changed";
  let schema=document.get work "schema_version" in
  require (schema.is_instance work M.String) "String response changed";
  require (((schema.attribute work "strip").call work []).truth work) "Schema truth changed";
  require (same(document.freeze work)(obj["schema_version",str "test.v1"])) "Document freeze changed";
  finished ();
  let invoke,finished=scripted [
    "literal",obj["kind",str "json";"value",str "default"],reference 7;
    "attr-default",obj["object",reference 0;"name",str "fingerprint";"default",reference 7],reference 8;
    "literal",obj["kind",str "set";"value",Json.Array[str "candidate";str "no_candidate_found"]],reference 9;
    "contains",obj["container",reference 9;"item",reference 8],Json.Bool true;
    "enum",obj["type",str "CheckOutcome";"value",str "pass"],reference 10;
    "compare",obj["left",reference 8;"right",reference 10;"operator",str "is"],Json.Bool false] in
  let bridge=H.create ~budget:work ~invoke () in
  let value=H.of_reference bridge(reference 0) in
  let identity=value.attribute_default work "fingerprint" (M.Json_value(str "default")) in
  require(identity.contains work (M.Json_set[str "candidate";str "no_candidate_found"])) "Set membership changed";
  require(not(identity.compare work M.Is (M.Check_outcome Bioc_domain.Realization_evidence.Pass))) "Enum identity changed";
  finished ();
  let invoke,finished=scripted [
    "tuple",obj["object",reference 0],reference 1;
    "iter",obj["object",reference 1],reference 2;
    "next",obj["object",reference 2],obj["exhausted",Json.Bool false;"object",reference 3];
    "next",obj["object",reference 2],obj["exhausted",Json.Bool false;"object",reference 3];
    "next",obj["object",reference 2],obj["exhausted",Json.Bool true;"object",Json.Null];
    "set-attribute-equal",obj["objects",Json.Array[reference 3;reference 3];"name",str "requirement_id";
      "values",Json.Array[str "r1"]],Json.Bool true;
    "lookup",obj["object",reference 3;"entries",Json.Array[Json.Array[str "r1";Json.int 7]]],reference 4;
    "json",obj["object",reference 4],Json.int 7] in
  let bridge=H.create ~budget:work ~invoke () in
  let value=H.of_reference bridge(reference 0) in
  let items=value.tuple work in
  (match items with [left;right]->require(left==right) "Tuple repeated reference lost identity"|_->failwith "Tuple inventory changed");
  require(value.attribute_set_equal work items ~attribute:"requirement_id" (M.Json_set[str "r1"])) "Attribute set changed";
  require(same((List.hd items).lookup work ["r1",Json.int 7])(Json.int 7)) "Lookup changed";
  finished ();
  let token=ref "original" in
  let cause=Marker token in
  let calls=ref 0 in
  let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->incr calls;raise cause) () in
  let value=H.of_reference bridge(reference 0) in
  (try ignore(value.document work);failwith "Original exception disappeared" with
   | Marker found as raised->require(found==token && raised==cause) "Host exception identity changed");
  require(same(H.reference bridge value)(reference 0)) "Logical host exception destroyed retained identity";
  require(!calls=1) "Host action was retried";
  let calls=ref 0 in
  let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->incr calls;Json.Bool true) () in
  let value=H.of_reference bridge(reference 0) in
  failure(fun ()->ignore(value.attribute_default (budget ()) "fingerprint" (M.Json_value(str "default"))));
  require(!calls=0) "Foreign budget executed a host action before rejection";
  failure(fun ()->ignore(value.truth work));
  let bridge=H.create ~budget:work ~max_handles:1 ~invoke:(fun ~action:_ ~arguments:_->reference 1) () in
  let value=H.of_reference bridge(reference 0) in
  failure(fun ()->ignore(value.attribute work "output"));
  failure(fun ()->ignore(H.reference bridge value));
  let bridge=H.create ~budget:work ~max_actions:1 ~invoke:(fun ~action:_ ~arguments:_->Json.Bool true) () in
  let value=H.of_reference bridge(reference 0) in
  require(value.truth work) "First bounded action failed";
  failure(fun ()->ignore(value.truth work));
  List.iter(fun invalid->
    let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->Json.Null) () in
    failure(fun ()->ignore(H.of_reference bridge invalid));
    failure(fun ()->ignore(H.of_reference bridge(reference 0))))
    [obj["handle",str "object/01"];obj["handle",str "object/-1"];obj["handle",str "object/"];
     obj["handle",str "provider/0"];obj["handle",str "object/0";"accepted",Json.Bool true]];
  let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->str "true") () in
  let value=H.of_reference bridge(reference 0) in
  failure(fun ()->ignore(value.truth work));
  failure(fun ()->ignore(H.counts bridge));
  let bridge=H.create ~budget:work ~max_retained_bytes:1 ~invoke:(fun ~action:_ ~arguments:_->Json.Null) () in
  failure(fun ()->ignore(H.of_reference bridge(reference 0)));
  let exhausted=budget () in
  let calls=ref 0 in
  let bridge=H.create ~budget:exhausted ~invoke:(fun ~action:_ ~arguments:_->incr calls;Json.Bool true) () in
  let value=H.of_reference bridge(reference 0) in
  failure(fun ()->W.charge exhausted (W.remaining exhausted+1));
  require(W.remaining exhausted>0) "Failed charge unexpectedly spent remaining allowance";
  failure(fun ()->ignore(value.truth exhausted));
  require(!calls=0) "Caught work exhaustion still invoked the host";
  let bridge=H.create ~budget:work ~invoke:(fun ~action:_ ~arguments:_->Json.Null) () in
  let value=H.of_reference bridge(reference 0) in H.close bridge;
  failure(fun ()->ignore(value.document work));
  print_endline "host bridge: deferred envelopes, physical identities, enum comparison, tuple order, original exceptions and cumulative limits checked"
