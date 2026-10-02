open Bioc_wire
open Bioc_domain
module S = Bioc_candidate_runtime.Synthetic
module M = Mechanism
module D = Model_execution_data
module N = Runtime_number
module O = Measurement_contract.Observable
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let jn value = N.to_json value
let n = N.of_int
let b value = D.Boolean value
let dtype scalar = obj ["kind",str (if scalar then "scalar" else "condition");
    "name",str (if scalar then "Level" else "Condition");"dimensions",obj [];"arguments",arr []]
let scalar ?(duration=false) value =
  let ty = if duration then obj ["kind",str "scalar";"name",str "Duration";
      "dimensions",obj ["time",Json.int 1];"arguments",arr []] else dtype true in
  Measurement_contract.Scalar.of_json (obj ["kind",str "scalar";"value",jn value;
      "canonical_value",jn value;"unit",str (if duration then "s" else "1");"type",ty])
let duration value = scalar ~duration:true (n value)
let node ?(scope=O.Cell) ?(scalar=false) id operation inputs =
  let output = O.of_json (obj ["schema_version",str O.schema_version;"id",str ("meaning:" ^ id);
      "dtype",dtype scalar;"role",str "role";"scope",str (if scope = O.Cell then "cell" else "contact");
      "compartment",str "abstract"]) in
  M.Node.make ~id ~operation ~output ~inputs ()
let program nodes outputs = M.make ~name:"Independent literal mechanism" ~nodes ~outputs ()
let input ?(contacts=[]) time values = D.Input_frame.make ~time:(n time) ~values ~contacts ()
let fields values = obj (List.map (fun (key,value) -> key,D.value_to_json value) values)
let frame ?(contacts=[]) time values = obj ["time",jn time;"values",fields values;
    "contacts",obj (List.map (fun (id,values) -> id,fields values) contacts)]
let bool_frame time value = frame (n time) ["output",b value]
let exact_trace label model horizon frames actual =
  let expected = obj ["schema_version",str D.Trace.schema_version;"model_version",str S.runner_version;
      "program_fingerprint",str (M.fingerprint model);"horizon",jn horizon;"frames",arr frames] in
  require (Canonical.encode expected = Canonical.encode (D.Trace.to_json actual)) (label ^ ": complete trace differs")
let check ?until label model history horizon frames =
  let actual = S.run ?until model history in exact_trace label model horizon frames actual
let rejected ?message label code call = match call () with
  | () -> failwith (label ^ ": unexpected success")
  | exception Diagnostic.Error error ->
      require (error.code = code) (label ^ ": expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message);
      Option.iter (fun expected -> require (error.message = expected) (label ^ ": wrong diagnostic text")) message
let delayed ?(scope=O.Cell) () = program [node ~scope "input" M.Input [];
    node ~scope "delay" (M.Delay {duration=duration 2;initial=M.Boolean false}) ["input"];
    node ~scope "output" M.Output ["delay"]] ["output"]
let history values = List.map (fun (time,value) -> input time ["input",b value]) values
let held () = program [node "input" M.Input [];node "held" (M.Held_for (duration 2)) ["input"];
    node "output" M.Output ["held"]] ["output"]
let pulse ?(scope=O.Cell) () = program [node ~scope "input" M.Input [];
    node ~scope "event" M.Onset ["input"];node ~scope "pulse" (M.Pulse (duration 2)) ["event"];
    node ~scope "output" M.Output ["pulse"]] ["output"]
let memory permanence = program [node "input" M.Input [];node "reset" M.Input [];
    node "event" M.Onset ["input"];node "memory" (M.Memory (if permanence then None else Some (duration 2))) ["event";"reset"];
    node "output" M.Output ["memory"]] ["output"]
let memory_history values = List.map (fun (time,set,reset) -> input time ["input",b set;"reset",b reset]) values

let combinational () =
  let model = program [node "flag" M.Input [];node ~scalar:true "amount" M.Input [];
      node "negated" M.Not ["flag"];node "either" M.Or ["flag";"negated"];
      node "both" M.And ["flag";"either"];
      node ~scalar:true "constant" (M.Constant (M.Scalar (scalar (n 2)))) [];
      node "larger" (M.Compare M.Gt) ["amount";"constant"];
      node ~scalar:true "choice" M.Select ["both";"amount";"constant"];
      node "output" M.Output ["larger"];node ~scalar:true "quantity" M.Output ["choice"]]
      ["output";"quantity"] in
  let frames = [input 0 ["flag",b false;"amount",D.Number (n 1)];
      input 1 ["flag",b true;"amount",D.Number (N.Real 3.5)]] in
  check "all combinational variants" model frames (n 1)
    [frame (n 0) ["output",b false;"quantity",D.Number (n 2)];
     frame (n 1) ["output",b true;"quantity",D.Number (N.Real 3.5)]];
  let huge = N.Integer (Z.of_string "9007199254740993") in
  List.iter (fun (operation,expected) ->
      let model = program [node ~scalar:true "a" M.Input [];node ~scalar:true "b" M.Input [];
          node "comparison" (M.Compare operation) ["a";"b"];node "output" M.Output ["comparison"]] ["output"] in
      check "exact mixed integer comparison" model [input 0 ["a",D.Number huge;"b",D.Number (N.Real 9007199254740992.)]] N.zero
        [bool_frame 0 expected]) [M.Lt,false;M.Le,false;M.Gt,true;M.Ge,true;M.Eq,false;M.Ne,true];
  let model = program [node ~scalar:true "input" M.Input [];
      node ~scalar:true "delay" (M.Delay {duration=duration 2;initial=M.Scalar (scalar N.zero)}) ["input"];
      node ~scalar:true "output" M.Output ["delay"]] ["output"] in
  check ~until:(n 3) "numeric equality retains initial representation" model
    [input 0 ["input",D.Number (N.Real (-0.))]] (n 3)
    [frame N.zero ["output",D.Number N.zero];frame (n 3) ["output",D.Number N.zero]]

let temporal () =
  let model = delayed () in
  let inputs = history [0,true;1,true;2,false;3,true] in
  let frames = List.map (fun (t,v) -> bool_frame t v) [0,false;1,false;2,false;3,false;5,true;6,true] in
  check ~until:(n 6) "inertial deadline cancellation/restart" model inputs (n 6) frames;
  check ~until:(n 6) "fresh independent repeat" model inputs (n 6) frames;
  check ~until:(n 1) "unvisited future snapshot inventory is not evaluated" model
    [input 0 ["input",b true];input 10 []] (n 1) [bool_frame 0 false;bool_frame 1 false];
  let cascade = program [node "input" M.Input [];
      node "first" (M.Delay {duration=duration 1;initial=M.Boolean false}) ["input"];
      node "second" (M.Delay {duration=duration 2;initial=M.Boolean false}) ["first"];
      node "output" M.Output ["second"]] ["output"] in
  check ~until:(n 5) "cascaded timers" cascade (history [0,true]) (n 5)
    [bool_frame 0 false;bool_frame 1 false;bool_frame 3 true;bool_frame 5 true];
  check ~until:(n 6) "held deadline interruption" (held ()) (history [0,true;2,false;3,true]) (n 6)
    [bool_frame 0 false;bool_frame 2 false;bool_frame 3 false;bool_frame 5 true;bool_frame 6 true];
  check ~until:(n 1) "truncated held interval" (held ()) (history [0,true;2,false]) (n 1)
    [bool_frame 0 false;bool_frame 1 false];
  check ~until:(n 4) "pulse expiry rearm" (pulse ()) (history [0,true;1,false;2,true]) (n 4)
    [bool_frame 0 true;bool_frame 1 true;bool_frame 2 true;bool_frame 4 false];
  check ~until:(n 3) "sustained onset does not refresh pulse" (pulse ()) (history [0,true;1,true]) (n 3)
    [bool_frame 0 true;bool_frame 1 true;bool_frame 2 false;bool_frame 3 false];
  check ~until:(n 8) "reset then set then expiry priority" (memory false)
    (memory_history [0,true,false;1,false,false;2,true,true;3,true,false;4,false,false;5,true,false]) (n 8)
    [bool_frame 0 true;bool_frame 1 true;bool_frame 2 false;bool_frame 3 false;bool_frame 4 false;
     bool_frame 5 true;bool_frame 7 false;bool_frame 8 false];
  check ~until:(n 8) "permanent memory" (memory true) (memory_history [0,true,false;4,false,false]) (n 8)
    [bool_frame 0 true;bool_frame 4 true;bool_frame 8 true];
  let ties = program [node "input" M.Input [];
      node "a-float" (M.Delay {duration=scalar ~duration:true (N.Real 2.);initial=M.Boolean false}) ["input"];
      node "z-integer" (M.Delay {duration=duration 2;initial=M.Boolean false}) ["input"];
      node "output" M.Output ["a-float"];node "other" M.Output ["z-integer"]] ["output";"other"] in
  let pair time value = frame time ["output",b value;"other",b value] in
  check ~until:(n 3) "equal deadline insertion representation" ties (history [0,true]) (n 3)
    [pair N.zero false;pair (N.Real 2.) true;pair (n 3) true];
  check ~until:(n 2) "horizon wins equal numeric deadline representation" ties (history [0,true]) (n 2)
    [pair N.zero false;pair (n 2) true]

let contacts () =
  let model = delayed ~scope:O.Contact () in
  let frame_contacts time contacts = input ~contacts time [] in
  let contact_values values = List.map (fun (id,v) -> id,["input",b v]) values in
  let output_contacts time values = frame ~contacts:(List.map (fun (id,v) -> id,["output",b v]) values) (n time) [] in
  check ~until:(n 5) "contact disappearance clears local timer" model
    [frame_contacts 0 (contact_values ["β",false;"a",true]);frame_contacts 1 [];
     frame_contacts 2 (contact_values ["a",true]);frame_contacts 4 (contact_values ["a",true])]
    (n 5) [output_contacts 0 ["a",false;"β",false];output_contacts 1 [];
           output_contacts 2 ["a",false];output_contacts 4 ["a",true];output_contacts 5 ["a",true]];
  let model = program [node ~scope:O.Contact "x" M.Input [];node ~scope:O.Contact "y" M.Input [];
      node ~scope:O.Contact "same" M.And ["x";"y"];node "exists" M.Any_contact ["same"];
      node "output" M.Output ["exists"]] ["output"] in
  let signal x y = ["x",b x;"y",b y] in
  check "same-contact conjunction before reduction" model
    [frame_contacts 0 ["b",signal false true;"a",signal true false];
     frame_contacts 1 ["a",signal true true]] (n 1)
    [frame ~contacts:["a",[];"b",[]] N.zero ["output",b false];
     frame ~contacts:["a",[]] (n 1) ["output",b true]];
  let model = program [node "input" M.Input [];node "event" M.Onset ["input"];
      node ~scope:O.Contact "pulse" (M.Pulse (duration 2)) ["event"];
      node ~scope:O.Contact "output" M.Output ["pulse"]] ["output"] in
  let snapshot time value contacts = input ~contacts time ["input",b value] in
  check ~until:(n 5) "cell events broadcast without late-contact replay" model
    [snapshot 0 true [];snapshot 1 true ["a",[]];snapshot 2 false ["a",[]];snapshot 3 true ["a",[]]] (n 5)
    [frame N.zero [];output_contacts 1 ["a",false];output_contacts 2 ["a",false];
     output_contacts 3 ["a",true];output_contacts 5 ["a",false]]

let histories_and_errors () =
  let model = delayed () in
  rejected ~message:"Model history requires ModelInputFrame records starting at zero." "empty history" "synthetic_history"
    (fun () -> ignore (S.run model []));
  List.iter (fun times -> rejected "invalid history" "synthetic_history" (fun () ->
      ignore (S.run model (history (List.map (fun time -> time,true) times))))) [[1];[0;0];[0;2;1]];
  let first = input 0 ["input",b true] in
  let rec cyclic = first :: cyclic in
  rejected "cyclic native list spine" "synthetic_history" (fun () -> ignore (S.run model cyclic));
  List.iter (fun until -> rejected "invalid horizon" "synthetic_horizon" (fun () ->
      ignore (S.run ~until model [first]))) [n (-1);N.Real Float.infinity;N.Real Float.nan];
  rejected ~message:"Input snapshot for contact None has missing ['input'] or unknown/wrong-scope [] ports."
    "missing cell input" "synthetic_input_inventory" (fun () -> ignore (S.run model [input 0 []]));
  rejected ~message:"Input 'input' requires a Boolean, not int."
    "strict Boolean input" "synthetic_input_type" (fun () -> ignore (S.run model [input 0 ["input",D.Number N.zero]]));
  List.iter (fun (model,values) -> rejected "nonadvancing temporal deadline" "synthetic_deadline" (fun () ->
      ignore (S.run model [D.Input_frame.make ~time:N.zero ~values:(List.map (fun (id,_) -> id,b false) values) ();
                           D.Input_frame.make ~time:(N.Real 1e20) ~values ()])))
    [held (),["input",b true];pulse (),["input",b true];memory false,["input",b true;"reset",b false]];
  let too_large = program [node "input" M.Input [];
      node "held" (M.Held_for (scalar ~duration:true (N.Real 1e308))) ["input"];
      node "output" M.Output ["held"]] ["output"] in
  rejected ~message:"held_for deadline must be finite." "overflow timer" "synthetic_deadline" (fun () ->
      ignore (S.run too_large [input 0 ["input",b false];D.Input_frame.make ~time:(N.Real 1e308) ~values:["input",b true] ()]));
  let model = program [node "unused" M.Input [];node "constant" (M.Constant (M.Boolean true)) [];
      node "selected" M.Output ["constant"];node "unselected" M.Output ["unused"]] ["selected"] in
  check "selected output subset" model [input 0 ["unused",b false]] N.zero [frame N.zero ["selected",b true]];
  rejected "all declared inputs remain required" "synthetic_input_inventory" (fun () -> ignore (S.run model [input 0 []]))

let rec items = function
  | Json.Object fields -> 1 + List.fold_left (fun sum (_,value) -> sum + 1 + items value) 0 fields
  | Json.Array values -> 1 + List.fold_left (fun sum value -> sum + items value) 0 values
  | _ -> 1
let resources () =
  let model = program [node "input" M.Input [];node "output" M.Output ["input"]] ["output"] in
  let history = history [0,true] in
  let trace,used = S.run_with_usage model history in
  require (used.frames = 1 && used.trace_items = items (D.Trace.to_json trace)) "Trace item receipt is not exact";
  require (used.trace_bytes = String.length (Canonical.encode (D.Trace.to_json trace))) "Trace byte receipt is not exact";
  let exact = S.make_limits ~max_work:used.work ~max_frames:used.frames ~max_trace_items:used.trace_items
      ~max_trace_bytes:used.trace_bytes ~max_state_items:3 () in
  require (D.Trace.fingerprint (S.run ~limits:exact model history) = D.Trace.fingerprint trace) "Exact resource boundary failed";
  List.iter (fun (code,limits) -> rejected "one below required resource" code (fun () -> ignore (S.run ~limits model history)))
    ["synthetic_work_limit",S.make_limits ~max_work:(used.work - 1) ();
     "synthetic_frame_limit",S.make_limits ~max_frames:0 ();
     "synthetic_trace_limit",S.make_limits ~max_trace_items:(used.trace_items - 1) ();
     "synthetic_trace_limit",S.make_limits ~max_trace_bytes:(used.trace_bytes - 1) ();
     "synthetic_state_limit",S.make_limits ~max_state_items:2 ()];
  rejected "caller cannot enlarge work profile" "synthetic_invalid_limits" (fun () -> ignore (S.make_limits ~max_work:50_000_001 ()));
  require (D.Trace.fingerprint (S.run model history) = D.Trace.fingerprint trace) "Failed run leaked state to a new session";
  let contacts = List.init 20 (fun index -> string_of_int index,["input",b true]) in
  rejected "snapshot state preflight" "synthetic_state_limit" (fun () ->
      ignore (S.run ~limits:(S.make_limits ~max_state_items:10 ()) (delayed ~scope:O.Contact ())
                [input ~contacts 0 []]));
  let chain = List.init 2000 (fun index ->
      let id = "n" ^ string_of_int index in
      if index = 0 then node id M.Input [] else node id M.Not ["n" ^ string_of_int (index - 1)]) in
  let model = program (chain @ [node "output" M.Output ["n1999"]]) ["output"] in
  check "flat deep DAG uses iterative execution" model [input 0 ["n0",b true]] N.zero [bool_frame 0 false]

let () =
  if Array.length Sys.argv <> 1 then failwith "test_synthetic_model takes no fixture arguments";
  combinational ();temporal ();contacts ();histories_and_errors ();resources ();
  print_endline "independent synthetic model: all14 operations, complete literal traces, exact deadlines and resource boundaries checked"
