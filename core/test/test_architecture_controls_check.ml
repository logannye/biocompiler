open Bioc_wire
module C = Bioc_checker.Architecture_controls_check
module W = Bioc_checker.Work_budget
module H = Bioc_domain.Human_request
module A = Bioc_domain.Architecture_contract
let checks = ref 0
let require yes message = incr checks; if not yes then failwith message
let str v = Json.String v
let arr v = Json.Array v
let obj v = Json.Object v
let field k v = Json.field k (Json.object_fields v)
let rejected label code run = incr checks;match run () with _ -> failwith (label ^ ": accepted")
  | exception Diagnostic.Error e -> if e.code <> code then failwith (label ^ ": " ^ e.code)
let literal_source () =
  let typ kind name = obj ["kind",str kind;"name",str name;"dimensions",obj [];"arguments",arr []] in
  let condition = typ "condition" "Condition" in
  let node id kind inputs attributes dtype = obj ["id",str id;"kind",str kind;"inputs",arr (List.map str inputs);
      "attributes",obj attributes;"data_type",dtype;"role",(if kind="role" then Json.Null else str "cell");"source",Json.Null] in
  let nodes = [node "cell" "role" [] ["name",str "cell";"engineering",str "in_vivo";"cell_type",str "declared"] Json.Null;
    node "scope" "scope" ["cell"] ["scope",str "environment";"name",str "environment"] Json.Null;
    node "signal" "signal" ["scope"] ["scope",str "environment";"name",str "control";"observation",str "signal"] (typ "scalar" "Level");
    node "gate" "qualitative" ["signal"] ["band",str "present"] condition;
    node "inverse" "not" ["gate"] [] condition;
    node "action" "action.rest" ["cell"] ["ongoing",Json.Bool true] Json.Null;
    node "rule" "rule" ["cell";"gate";"action"] ["trigger",str "condition";"execution",str "concurrent";"priority",str "unspecified"] Json.Null;
    node "memory" "memory" ["cell";"inverse";"gate"] ["name",str "store";"input_names",arr [str "owner";str "set_when";str "reset_when"];
      "initial",Json.Bool false;"initial_true_is_onset",Json.Bool true;"reset_priority",Json.Bool true;"setting",str "onset";"expiry",str "until_reset"] condition] in
  H.of_json (obj ["schema_version",str "biocompiler.build_request.v0.1";
    "intent",obj ["schema_version",str "biocompiler.intent.v0.1";"name",str "independent literal";"nodes",arr nodes;"roots",arr [str "cell";str "rule";str "memory"]];
    "artifact_scope",str "abstract_behavior";"behavior_profile",str "biocompiler.behavior.v0.1";"target",Json.Null;
    "explicit_overrides",obj [];"resolved_defaults",obj [];"resolved_bindings",obj [];"implementation_constraints",obj [];
    "preferences",obj [];"parameter_metadata",obj [];"provenance",obj ["schema_version",str "biocompiler.elaboration_provenance.v0.1";
      "source_identities",obj [];"dependency_identities",obj [];"external_inputs",obj [];"locations",obj [];"recorded_at",Json.Null]])
let literals () =
  let source = literal_source () in
  let prove target kind = C.prove_source ~source ~target ~controlling_node_ids:["gate"] ~kind () in
  let active = prove "action" A.Activation in
  require (C.reason active=None && active.targets=["action"] && List.length active.witnesses=2) "Independent activation theorem differs";
  require (C.reason (prove "action" A.Shutdown)=Some "assertion_does_not_veto") "Independent shutdown counterexample differs";
  require (C.reason (prove "action" A.Activity_control)=None) "Independent activity theorem differs";
  require (C.reason (prove "memory" A.Memory_reset)=None) "Independent reset-priority memory theorem differs";
  require (C.reason (prove "action" A.Physical_separation)=Some "kind_not_implemented") "Physical material relation was promoted to source theorem";
  let input = C.Input.make ~source ~target:"action" ~controlling_node_ids:["gate"] ~kind:A.Activation ~bindings:(C.Input.Frozen (obj [])) in
  require (Canonical.encode (C.Input.to_json (C.Input.of_json (C.Input.to_json input)))=Canonical.encode (C.Input.to_json input)) "Input replay changed authority";
  rejected "cannot enlarge local ceiling" "architecture_control_limit" (fun () -> C.make_budget ~maximum:(C.max_work+1) ());
  let tiny = C.make_budget ~maximum:1 () in
  rejected "standalone work bound" "architecture_control_limit" (fun () -> C.prove ~budget:tiny input);
  let parent = W.create ~profile:"independent test" ~error_code:"architecture_resource_limit" ~maximum:1 () in
  rejected "parent work bound" "architecture_resource_limit" (fun () -> C.prove ~budget:(C.make_budget ~parent ()) input);
  let parent = W.create ~profile:"cumulative test" ~error_code:"architecture_resource_limit" ~maximum:active.work () in
  ignore (C.prove ~budget:(C.make_budget ~parent ()) input);
  rejected "cumulative parent cannot reset across calls" "architecture_resource_limit" (fun () -> C.prove ~budget:(C.make_budget ~parent ()) input);
  let exact_controllers = List.init 4096 (fun _ -> "gate") in
  let exact_input=C.Input.make ~source ~target:"action" ~controlling_node_ids:exact_controllers ~kind:A.Activation ~bindings:C.Input.Defaults in
  require (C.reason (C.prove exact_input)=Some "requires_one_boolean_condition") "Exact controller transport ceiling was tightened";
  rejected "one-over controller inventory" "architecture_control_limit" (fun () ->
    C.Input.make ~source ~target:"action" ~controlling_node_ids:("gate"::exact_controllers) ~kind:A.Activation ~bindings:C.Input.Defaults);
  let set key value raw=obj ((key,value)::List.remove_assoc key (Json.object_fields raw)) in
  let original=H.to_json source in let intent=field "intent" original in
  let nodes=Json.array (field "nodes" intent) in let role=List.hd nodes in
  let padded count = let extras=List.init (count-List.length nodes) (fun index -> set "id" (str ("padding_role_" ^ string_of_int index)) role) in
    H.of_json (set "intent" (set "nodes" (arr (nodes @ extras)) intent) original) in
  let exact_source=padded 4096 in
  require (C.extended_targets ~source:exact_source ~target:"cell" ~kind:A.Physical_separation ()=["cell"])
    "Exact source-node transport ceiling was tightened";
  let over_source=padded 4097 in
  rejected "one-over source-node inventory" "architecture_control_limit" (fun () ->
    C.extended_targets ~source:over_source ~target:"cell" ~kind:A.Physical_separation ());
  let rec controllers = "gate"::controllers in
  rejected "cyclic controller list" "architecture_control_limit" (fun () -> C.Input.make ~source ~target:"action" ~controlling_node_ids:controllers ~kind:A.Activation ~bindings:C.Input.Defaults);
  rejected "duplicate frozen parameter key" "duplicate_key" (fun () -> C.Input.make ~source ~target:"action" ~controlling_node_ids:["gate"] ~kind:A.Activation ~bindings:(C.Input.Frozen (obj ["x",Json.Null;"x",Json.Null])));
  let rec raw = Json.Array [raw] in rejected "raw cyclic input" "source_manifest_limit" (fun () -> C.Input.of_json raw);
  Printf.printf "architecture controls: %d independent literal and runtime-boundary checks passed\n" !checks
let inventory corpus = Canonical.fingerprint (obj (List.map (fun k -> k,field k corpus) ["cases";"coverage";"native_boundary"]))
let retained path =
  require (not (Filename.is_relative path)) "Control corpus path must be absolute";
  let ch = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr ch) (fun () -> let size=in_channel_length ch in
      require (size <= Limits.max_request_bytes) "Control corpus read bound";Json.parse (really_input_string ch size)) in
  require (field "schema_version" corpus = str "biocompiler.architecture_proofs_conformance.v1" && field "kind" corpus = str "controls") "Wrong control corpus";
  let digest="3281755936e663372e4091d3b7f9212ca886e66d69b37d3a1b42afeea42412c4" in
  require (inventory corpus=digest && field "inventory_sha256" corpus=str digest) "Control whole-input/result inventory changed";
  let docs=Json.object_fields (field "documents" corpus) and cases=Json.array (field "cases" corpus) in
  require (List.length docs=89 && List.length cases=112) "Truncated control corpus";
  List.iter (fun (sha,raw)->require (Canonical.fingerprint raw=sha) "Changed original source document") docs;
  let used=Hashtbl.create 128 and ids=Hashtbl.create 128 in
  List.iter (fun case ->
      let id=Json.string (field "id" case) in require (not (Hashtbl.mem ids id)) "Duplicate control case";Hashtbl.add ids id ();
      let sha=Json.string (field "source" case) in Hashtbl.replace used sha ();
      let raw=Json.field sha docs in
      let input=C.Input.of_json (obj ["source",raw;"target",field "target" case;"controlling_node_ids",field "controlling_node_ids" case;
        "kind",field "kind" case;"parameter_bindings",field "parameter_bindings" case]) in
      let result=C.prove input and expected=field "expected" case in
      let actual=obj ["reason",(match C.reason result with None->Json.Null | Some reason->str reason);"targets",arr (List.map str result.targets)] in
      require (Json.equal actual expected) (id ^ ": theorem differs: " ^ Canonical.encode actual);
      let source=H.of_json raw in
      let kind=match Json.string (field "kind" case) with "activation"->A.Activation | "shutdown"->A.Shutdown
        | "memory_reset"->A.Memory_reset | "production_adjustment"->A.Production_adjustment | "activity_control"->A.Activity_control
        | "physical_separation"->A.Physical_separation | "dependency_disjointness"->A.Dependency_disjointness | _->failwith "Unknown theorem kind" in
      let target=Json.string (field "target" case) and controllers=Json.array (field "controlling_node_ids" case) |> List.map Json.string in
      require (C.extended_targets ~source ~target ~kind ()=result.targets) (id ^ ": public target resolution differs");
      let resolved=Bioc_domain.Build_request.resolved_bindings (H.build_request source) |> obj in
      if Json.equal (field "parameter_bindings" case) resolved || (field "parameter_bindings" case=Json.Null && resolved=obj []) then (
        let authoritative=C.prove_source ~source ~target ~controlling_node_ids:controllers ~kind () in
        require (C.reason authoritative=C.reason result && authoritative.targets=result.targets) (id ^ ": full-source binding entry point differs"));
      require (Canonical.fingerprint raw=sha) "Control checking mutated original source";
      let again=C.prove input in require (Json.equal (arr result.witnesses) (arr again.witnesses) && result.work=again.work) (id ^ ": proof witnesses nondeterministic");
      if C.reason result=None && List.mem (Json.string (field "kind" case)) ["activation";"shutdown";"memory_reset";"production_adjustment";"activity_control"] then
        require (result.witnesses<>[]) (id ^ ": theorem lacks exhaustive-row witnesses")) cases;
  require (Hashtbl.length used=List.length docs) "Unreferenced control source document";
  Printf.printf "architecture controls: %d complete source/binding theorems with exact targets/reasons and deterministic witnesses passed\n" (List.length cases)
let () = match Array.to_list Sys.argv with [_]->literals () | [_;path]->literals ();retained path
  | _ -> failwith "Usage: test_architecture_controls_check.exe [<absolute-corpus.json>]"
