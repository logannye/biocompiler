open Bioc_wire
module W=Bioc_checker.Work_budget
let require value message=if not value then failwith message
let root ?retain_bytes()=W.create ?retain_bytes ~profile:"retention.test" ~error_code:"retention_test_work" ~maximum:100()
let child parent=W.nested ~parent ~profile:"retention.child" ~error_code:"retention_child_work" ~maximum:50()
let expect code call=try call();failwith("Expected "^code)with Diagnostic.Error error->
  require(error.code=code)("Wrong retention diagnostic: "^error.code)
let shared()=
  let calls=ref [] and used=ref 0 in
  let retain_bytes bytes=Diagnostic.require(bytes<=10- !used)"retention_test_limit" "Retained bytes exhausted.";
    used:= !used+bytes;calls:= !calls@[bytes] in
  let root=root ~retain_bytes() in let left=child root and right=child root in let nested=child left in
  W.retain nested 3;W.retain right 7;
  require(!used=10 && !calls=[3;7])"Nested reservation did not reach one shared owner exactly once";
  require(W.remaining root=100 && W.remaining nested=50)"Retained bytes were silently treated as work units";
  let original=try W.retain left 1;failwith "One-short retention accepted" with Diagnostic.Error error->error in
  require(W.is_exhaustion root original && W.is_exhaustion left original && W.exhausted right)
    "Actual retention failure did not latch shared siblings/ancestors";
  (try W.charge right 1;failwith "Caught retention failure permitted sibling work"
   with Diagnostic.Error error->require(error==original)"Resource exception identity changed");
  (try W.retain nested 0;failwith "Caught retention failure permitted descendant retention"
   with Diagnostic.Error error->require(error==original)"Retained failure was replaced");
  require(!used=10 && !calls=[3;7])"Failed reservation called sink again or refunded ownership"
let unchanged()=
  let owner=root() in let nested=child owner in
  W.retain nested max_int;require(W.remaining owner=100 && W.remaining nested=50)
    "Unconfigured historical profile changed work semantics";
  W.charge nested 12;require(W.remaining owner=88 && W.remaining nested=38)"Original shared work charges changed";
  expect "invalid_work_budget"(fun()->W.retain nested(-1))
let ownership()=
  let outer=root() and used=ref 0 in
  let package=W.nested ~parent:outer ~retain_bytes:(fun amount->used:= !used+amount)
    ~profile:"new.package.owner" ~error_code:"package_work" ~maximum:80() in
  let leaf=child package in W.retain leaf 9;W.charge leaf 3;
  require(!used=9 && W.remaining outer=97 && W.remaining package=77)"New package owner lost supplied work ancestry";
  expect "invalid_work_budget"(fun()->ignore(W.nested ~parent:leaf ~retain_bytes:(fun _->())
    ~profile:"replacement" ~error_code:"replacement_work" ~maximum:10()));
  W.retain package 1;require(!used=10)"Rejected owner replacement mutated existing sink"
let callback_failure()=
  let marker=Failure "actual retention callback" and calls=ref 0 in
  let owner=root ~retain_bytes:(fun _->incr calls;raise marker)() in
  (try W.retain(child owner)1;failwith "Callback did not raise"with error->require(error==marker)"Callback error replaced");
  require(W.exhausted owner)"Opaque callback failure did not close owner";
  (try ignore(child owner);failwith "Closed owner created a usable descendant"with error->require(error==marker)"Nested creation error replaced");
  require(!calls=1)"Opaque failure retried sink"
let reentrant()=
  let captured=ref None in
  let owner=root ~retain_bytes:(fun _->W.retain(Option.get !captured)1)() in captured:=Some owner;
  expect "invalid_work_budget"(fun()->W.retain owner 1);
  require(W.exhausted owner)"Recursive reservation did not latch owner";
  let captured=ref None in
  let owner=root ~retain_bytes:(fun _->try W.retain(Option.get !captured)1 with Diagnostic.Error _->())() in
  captured:=Some owner;
  expect "invalid_work_budget"(fun()->W.retain owner 1);
  require(W.exhausted owner)"Swallowed recursive reservation permitted publication"
let caught_work()=
  let captured=ref None and original=ref None and calls=ref 0 in
  let owner=root ~retain_bytes:(fun _->incr calls;
    try W.charge(Option.get !captured)101 with Diagnostic.Error error->original:=Some error)() in
  captured:=Some owner;
  (try W.retain owner 1;failwith "Swallowed sink work exhaustion permitted publication"
   with Diagnostic.Error error->require(error==Option.get !original)"Sink work failure identity changed");
  require(W.exhausted owner && !calls=1 && W.remaining owner=100)
    "Sink work failure did not remain atomic and sticky";
  (try W.retain owner 0;failwith "Caught work failure retried sink"
   with Diagnostic.Error error->require(error==Option.get !original)"Caught work failure was replaced");
  require(!calls=1)"Caught work failure called the sink again";
  let prior=root() in
  let original=try W.charge prior 101;failwith "Expected prior work exhaustion"with Diagnostic.Error error->error in
  (try ignore(W.nested ~parent:prior ~retain_bytes:(fun _->()) ~profile:"late.package"
      ~error_code:"late_work" ~maximum:10());failwith "Exhausted work acquired a new retention owner"
   with Diagnostic.Error error->require(error==original)"Prior work failure changed during owner creation");
  W.charge prior 1;
  require(W.remaining prior=99)"Unconfigured historical work behavior changed after failure"
let ()=shared();unchanged();ownership();callback_failure();reentrant();caught_work();
  print_endline "Optional retention owner: exact shared ancestry, cumulative reservations and sticky exception identity passed."
