open Bioc_wire
open Bioc_domain
module C = Construction
module B = Construction_build
module A = Construction_artifact
module E = Construction_assessment
let build ?parent original =
  let request = C.Request.of_json (C.Request.to_json original) in
  let candidate = Construction_producer.construct ?parent request in
  let assessment = Bioc_checker.Construction_check.check ?parent ~expected_request:request candidate in
  B.make ~request ~candidate ~assessment
let rec python_equal left right =
  let numeric = function Json.Bool value -> Some (Json.int (if value then 1 else 0))
    | (Json.Int _ | Json.Float _) as value -> Some value | _ -> None in
  match left,right with
  | Json.Array a,Json.Array b -> List.length a=List.length b && List.for_all2 python_equal a b
  | Json.Object a,Json.Object b ->
      let order = List.sort (fun (a,_) (b,_) -> String.compare a b) in
      List.length a=List.length b && List.for_all2 (fun (key,value) (other_key,other) ->
          key=other_key && python_equal value other) (order a) (order b)
  | _ -> (match numeric left,numeric right with Some a,Some b -> Json.number_compare a b=0 | _ -> Json.equal left right)
let verify ?parent ~expected_request original =
  let build = B.of_json (B.to_json original) in
  let expected = C.Request.of_json (C.Request.to_json expected_request) in
  Diagnostic.require (python_equal (C.Request.to_json (B.request build)) (C.Request.to_json expected))
    "construction_build_authority" "Construction build differs from independent complete authority.";
  Bioc_checker.Construction_check.replay ?parent ~expected_request:expected ~candidate:(B.candidate build) (B.assessment build)
let verified_molecules ?parent ~expected_request build =
  let assessment = verify ?parent ~expected_request build in
  Diagnostic.require (C.Request.mode expected_request=C.Request.Strict) "construction_handoff_mode"
    "Diagnostic construction cannot produce a complete-set handoff.";
  Diagnostic.require (E.passed assessment && E.complete assessment) "construction_handoff_incomplete"
    "Complete-set handoff requires fresh successful construction and payload checks.";
  let candidate = B.candidate build in
  Diagnostic.require (A.bundle candidate<>None && A.missing_members candidate=[]) "construction_handoff_inventory"
    "Complete-set handoff cannot omit a required member.";
  Molecule_set.Artifact.make ~bundle:(Option.get (A.bundle candidate)) ~experimental_amounts:(A.experimental_amounts candidate) ~run_metadata:[]
