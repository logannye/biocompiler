open Bioc_wire
module B=Archive_budget
let limit condition=Diagnostic.require condition "archive_json_limit" "Archive JSON exceeds its native resource budget."
let encode budget ?(newline=true) ~max_bytes value=
  B.guard budget;
  let controls=B.limits budget in
  limit(max_bytes>=0 && max_bytes<=controls.max_archive_bytes);
  let nodes=ref 0 and bytes=ref(if newline then 1 else 0) in
  let add amount=limit(amount>=0 && amount<=max_bytes- !bytes);bytes:= !bytes+amount in
  let node()=B.charge budget 1;limit(!nodes<controls.max_json_nodes);incr nodes in
  let text_size text=
    B.product budget (String.length text+1) 4;
    limit(String.length text<=Limits.max_string_bytes);
    (try Json.validate_utf8 text with Diagnostic.Error error when error.code="invalid_utf8"->
      Diagnostic.fail "archive_container" "Archive metadata is not valid UTF-8.");
    let size=ref 2 in
    String.iter(fun character->size:= !size+(match character with
      |'"'|'\\'|'\b'|'\012'|'\n'|'\r'|'\t'->2 |c when Char.code c<32->6 |_->1))text;
    !size in
  let rec length count=function
    |[]->count |_::tail->B.charge budget 1;limit(count<controls.max_json_nodes);length(count+1)tail in
  let sorted fields=
    let count=length 0 fields in
    let key_bytes=List.fold_left(fun count(key,_)->B.charge budget 1;count+String.length key)0 fields in
    let rec levels n cost=if n<=1 then cost else levels(n/2)(cost+1) in
    B.product budget (count+key_bytes+1)(4*levels count 1);B.reserve budget(128*count+1024);
    List.sort(fun(left,_)(right,_)->String.compare left right)fields in
  let scalar=function
    |Json.Int value->B.charge budget(Z.numbits value+1);limit(Z.numbits value<=4*Limits.max_number_chars);
      B.reserve budget(Limits.max_number_chars+32);
      let text=Z.to_string value in limit(String.length text<=Limits.max_number_chars);text
    |Json.Float value->B.charge budget 4096;B.reserve budget 4096;
      Diagnostic.require(Float.is_finite value)"archive_container"
        ("Out of range float values are not JSON compliant: "^
         (if Float.is_nan value then "nan" else if value<0. then "-inf" else "inf"));
      Canonical.float_string value
    |Json.Null->"null"|Json.Bool true->"true"|Json.Bool false->"false"
    |_->assert false in
  let rec inspect active depth value=
    node();limit(depth<=controls.max_json_depth);B.charge budget(depth+1);
    Diagnostic.require(not(List.exists(fun previous->previous==value)active))
      "archive_json_cycle" "Cyclic archive JSON value.";
    let members count object_value=
      add(2+max 0(count-1)+(if object_value then 2*count else 0));
      if count>0 then add(count*(1+2*(depth+1))+1+2*depth) in
    match value with
    |Json.String text->add(text_size text)
    |Json.Array values->let count=length 0 values in members count false;
      B.reserve budget 32;List.iter(inspect(value::active)(depth+1))values
    |Json.Object fields->let count=length 0 fields in members count true;
      List.iter(fun(key,_)->node();add(text_size key))fields;
      let fields=sorted fields in
      let previous=ref None in
      List.iter(fun(key,_)->Diagnostic.require(!previous<>Some key)"duplicate_key" "Duplicate archive JSON key.";previous:=Some key)fields;
      B.reserve budget 32;List.iter(fun(_,child)->inspect(value::active)(depth+1)child)fields
    |scalar_value->add(String.length(scalar scalar_value)) in
  inspect [] 0 value;limit(!bytes<=max_bytes);
  B.product budget(!bytes+ !nodes)4;B.reserve budget(!bytes+128);
  let output=Bytes.create !bytes and position=ref 0 in
  let put character=limit(!position<Bytes.length output);Bytes.set output !position character;incr position in
  let append text=limit(String.length text<=Bytes.length output- !position);
    Bytes.blit_string text 0 output !position(String.length text);position:= !position+String.length text in
  let quoted text=
    put '"';String.iter(fun character->match character with
      |'"'->append "\\\""|'\\'->append "\\\\"|'\b'->append "\\b"|'\012'->append "\\f"
      |'\n'->append "\\n"|'\r'->append "\\r"|'\t'->append "\\t"
      |c when Char.code c<32->append "\\u00";let hex="0123456789abcdef" in
        put hex.[Char.code c lsr 4];put hex.[Char.code c land 15]
      |c->put c)text;put '"' in
  let indent depth=put '\n';for _=1 to 2*depth do put ' ' done in
  let rec write depth=function
    |Json.Array values->put '[';sequence depth(write(depth+1))values;put ']'
    |Json.Object fields->put '{';sequence depth(fun(key,value)->quoted key;append ": ";write(depth+1)value)(sorted fields);put '}'
    |Json.String text->quoted text
    |value->append(scalar value)
  and sequence:'a. int->('a->unit)->'a list->unit=fun depth emit values->match values with
    |[]->() |first::tail->indent(depth+1);emit first;
      List.iter(fun item->put ',';indent(depth+1);emit item)tail;indent depth in
  write 0 value;if newline then put '\n';
  Diagnostic.require(!position= !bytes)"archive_json_encoding" "Archive JSON byte preflight differs.";
  Bytes.unsafe_to_string output
