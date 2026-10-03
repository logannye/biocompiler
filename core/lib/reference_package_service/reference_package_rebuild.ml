open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module D=Bioc_reference_artifact.Reference_package_manifest
module A=Bioc_reference_artifact.Reference_package_container
module I=Bioc_reference_input.Reference_inputs
module S=Reference_package_workflow
module Codec=Verification_exploration.Codec
let require value message=Diagnostic.require value "reference_package" message
let equal budget left right=
  let limits=Codec.make_limits ~max_bytes:(B.limits budget).max_member_bytes
    ~max_nodes:(B.limits budget).max_json_nodes ~charge:(B.charge budget)() in
  let l=Codec.measure ~limits left and r=Codec.measure ~limits right in
  B.product budget(l.bytes+r.bytes+l.nodes+r.nodes+1)128;
  (* Structural dataclass/mapping equality in the historical request permits
     Python numeric equality. The later manifest fingerprint still binds exact
     canonical spelling; this comparison never grants standalone acceptance. *)
  let number=function Json.Bool value->Some(Json.int(if value then 1 else 0))
    |(Json.Int _|Json.Float _)as value->Some value|_->None in
  let rec lookup key = function
    | [] -> None
    | (other,value)::rest ->
        (* Mapping equality is order independent. Meter each actual lookup before
           comparing keys; a linear tree preflight does not cover quadratic
           nested-map searches or long common string prefixes. *)
        B.charge budget(String.length key+String.length other+1);
        if String.equal key other then Some value else lookup key rest in
  let rec same left right=match number left,number right,left,right with
    |Some left,Some right,_,_->Json.number_compare left right=0
    |_,_,Json.Null,Json.Null->true
    |_,_,Json.String left,Json.String right->String.equal left right
    |_,_,Json.Array left,Json.Array right->List.length left=List.length right && List.for_all2 same left right
    |_,_,Json.Object left,Json.Object right->List.length left=List.length right &&
      List.for_all(fun(key,value)->match lookup key right with Some other->same value other|None->false)left
    |_->false in same left right
let verify ?runtime budget ~callbacks ?expected_request ?expected_build_fingerprint data=
  B.charge budget 1;
  require(Option.is_some expected_request || Option.is_some expected_build_fingerprint)
    "Fresh verification requires an independently trusted request or build fingerprint.";
  require(B.owns_retention budget)"Package reconstruction requires one configured persistent-data owner.";
  let imported=A.read ?runtime budget data in
  let manifest=A.manifest imported and files=A.files imported in
  let raw=match List.assoc_opt "request.json" files with Some value->value|None->
    Diagnostic.fail "reference_package" "Package has no frozen request." in
  (try Json.validate_utf8 raw with Diagnostic.Error error when error.code="invalid_utf8"->
    Diagnostic.fail "reference_package" "Packaged request must be UTF-8 JSON.");
  let request=D.Request.of_json_text budget raw in
  Option.iter(fun expected->require(equal budget(D.Request.to_json request)(D.Request.to_json expected))
    "Packaged request differs from independent authority.")expected_request;
  Option.iter(fun expected->B.charge budget(String.length expected+65);
    require(String.equal(D.Manifest.fingerprint manifest)expected)
      "Packaged build differs from independently trusted identity.")expected_build_fingerprint;
  require(D.Manifest.request_fingerprint manifest=D.Request.fingerprint request)"Packaged request fingerprint mismatch.";
  let target=Reference_construct.Request.target(D.Request.construct request) in
  let size=Codec.measure ~limits:(Codec.make_limits ~charge:(B.charge budget)())(Build_request.Target.to_json target) in
  B.product budget(size.bytes+size.nodes+1)128;B.reserve budget(16*size.bytes+128*size.nodes+8192);
  ignore(Bioc_checker.Admission_check.require_software_use ~target ~boundary:Admission.Verification ~components:[]);
  let prefix="references/"^Pinned_identity.id I.manifest_pin^"/" in
  B.reserve budget(128*List.length files+128);
  let retained=List.filter_map(fun(name,bytes)->B.charge budget(String.length name+1);
    if String.starts_with ~prefix name then begin
      let count=String.length name-String.length prefix in B.reserve budget(count+64);
      Some(String.sub name(String.length prefix)count,bytes)
    end else None)files in
  let rebuilt=S.build budget ~callbacks:(callbacks retained) ~request ?run_metadata:(A.run_metadata imported)() in
  B.charge budget(D.Manifest.canonical_size manifest+D.Manifest.canonical_size(S.manifest rebuilt)+1);
  require(equal budget(D.Manifest.to_json(S.manifest rebuilt))(D.Manifest.to_json manifest))
    "Package identities or evidence are stale, altered or unsupported by current tools.";
  B.charge budget(String.length(S.data rebuilt)+String.length data+1);
  require(String.equal(S.data rebuilt)data)"Package content differs from current independent offline reconstruction.";
  rebuilt
