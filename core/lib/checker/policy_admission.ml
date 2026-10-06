open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module Names = Map.Make(String)
module Seen = Set.Make(String)
type t = { document_value : D.t; descriptors_value : O.descriptor_bundle; assessment_value : Json.t; report_value : Json.t }
let document (value:t) = value.document_value
let descriptors (value:t) = value.descriptors_value
let source_assessment (value:t) = value.assessment_value
let report (value:t) = value.report_value
let get = O.get
let text = O.text
let list = O.list
let ref_id = O.ref_id
let present value = value <> Json.Null
let strings values = List.map Json.string values
let str value = Json.String value
let fail path message = Diagnostic.fail ~path "policy_operational_unsupported" message
let require path condition message = if not condition then fail path message
let supported_types = ["truth";"integer";"text";"quantity"]
let expr_ops = ["literal";"observe";"state";"parameter";"all";"any";"not";"eq";"ne";"lt";"le";"gt";"ge";"updated";"rising";"effect_event"]
let admit ~document ~descriptors =
  (* Ingress diagnostic locations are not authored program coordinates. Every
     operational artifact uses one canonical document root, whether admission
     started through the direct API, a request envelope or a native service. *)
  let document=D.of_json ~path:"/document" (D.to_json document) in
  let assessment=Policy_check.check document in
  Diagnostic.require ~path:"/document" (text "status" assessment = "valid") "policy_operational_source_invalid"
    "Operational admission requires a fresh valid native source assessment.";
  let declarations=D.declarations document in
  require "/document" (List.length declarations <= 4096) "Operational declaration limit exceeded.";
  let index=List.fold_left (fun acc (d:D.declaration) -> Names.add d.id d.value acc) Names.empty declarations in
  let lookup reference=Names.find (ref_id reference) index in
  let defs=list "definitions" (get "semantics" (D.program document)) in
  let definitions=List.fold_left (fun acc def -> Names.add (ref_id def) def acc) Names.empty defs in
  let descriptor_index=List.fold_left (fun acc (descriptor:O.descriptor) ->
    let pin=O.definition_ref_to_json descriptor.definition and path="/definitions" in
    require path (not (Names.mem (ref_id pin) acc)) "Duplicate or conflicting operational definition descriptor.";
    let definition=match Names.find_opt (ref_id pin) definitions with Some v -> v | None -> fail path "Descriptor source definition is absent." in
    require path (text "version" pin = text "version" definition && text "digest" pin = D.document_digest definition)
      "Operational descriptor is not bound to the complete source DefinitionRef.";
    require path (list "clauses" definition = []) "Definition clauses need an executable interpretation and cannot be silently discarded.";
    require path (get "executor_kind" definition = Json.Null && get "subject_kind" definition = Json.Null)
      "Nominal executor/subject-kind constraints need a supplied typed interpretation and cannot be silently ignored.";
    Names.add (ref_id pin) descriptor acc) Names.empty (O.descriptors descriptors) in
  let used=ref Seen.empty in
  let bind path reference semantics =
    let descriptor=match Names.find_opt (ref_id reference) descriptor_index with
      | Some d -> d | None -> fail path "Reachable source operation has no exact executable descriptor." in
    require path (Json.equal (O.definition_ref_to_json descriptor.definition) reference && descriptor.semantics = semantics)
      "Descriptor identity or operational interpretation differs from this contextual use.";
    used:=Seen.add (ref_id reference) !used;
    let definition=Names.find (ref_id reference) definitions in
    if semantics <> O.Effect_abstract_attempt then require path (list "parameters" definition = []) "This primitive descriptor takes no formal parameters.";
    if semantics <> O.Observation_external_evidence then require path (get "result" definition = Json.Null) "This primitive descriptor does not return a value."
  in
  let clocks=List.filter (fun (d:D.declaration) -> d.kind=D.Clock) declarations in
  require "/document" (List.length clocks = 1) "Bounded operational profile requires exactly one shared logical clock.";
  let clock=(List.hd clocks).value in
  require "/document" (List.mem (text "basis" clock) ["logical";"availability"])
    "Only exact logical or availability tick clocks sharing the timeline domain are executable.";
  let resolution=O.duration (get "resolution" clock) in
  let time path value =
    let amount=O.duration value in
    require path (Q.sign amount > 0 && Z.equal (Q.den (Q.div amount resolution)) Z.one)
      "Operational durations must be positive integral multiples of the shared clock resolution."
  in
  let roles=List.filter (fun (d:D.declaration) -> d.kind=D.Role) declarations in
  require "/document" (List.length roles = 1) "Bounded operational profile requires one executor role.";
  let role=(List.hd roles).id in
  let rec referenced_encounters reference =
    let target=lookup reference in
    match text "$type" target with
    | "Encounter" -> Seen.singleton (ref_id target)
    | "Subject" -> (match get "encounter" target with Json.Null -> Seen.empty | value -> Seen.singleton (ref_id value))
    | "Observation" | "Effect" -> referenced_encounters (get "subject" target)
    | "StateStore" | "Machine" ->
        let scope=get "scope" target in
        if text "kind" scope = "encounter" then Seen.singleton (ref_id (get "subject" scope)) else Seen.empty
    | _ -> Seen.empty
  in
  let rec encounter_bindings value = match value with
    | Json.Array values -> List.fold_left (fun acc v -> Seen.union acc (encounter_bindings v)) Seen.empty values
    | Json.Object fields ->
        if List.assoc_opt "$type" fields = Some (str "Ref") then referenced_encounters value
        else List.fold_left (fun acc (_,v) -> Seen.union acc (encounter_bindings v)) Seen.empty fields
    | _ -> Seen.empty
  in
  let scope_binding value =
    if text "kind" value = "encounter" then Some (ref_id (get "subject" value)) else None in
  let compatible_binding path expected required =
    require path (match expected with
      | None -> Seen.is_empty required
      | Some identity -> Seen.subset required (Seen.singleton identity))
      "Operational expression or assignment requires an encounter outside its concrete execution scope."
  in
  let exactly_bound_effects path expected references =
    List.iter (fun reference ->
      let subject=referenced_encounters (get "subject" (lookup reference)) in
      let intended=match expected with None -> Seen.empty | Some identity -> Seen.singleton identity in
      require path (Seen.equal subject intended)
        "Effect subject and retained initiating environment require different concrete bindings, which this profile does not implement.") references
  in
  let assignment_bindings path expected value =
    List.iter (fun assignment ->
      compatible_binding (path^"/assignments") expected (referenced_encounters (get "state" assignment)))
      (list "assignments" value)
  in
  let rec expression path value =
    let op=text "op" value in
    require path (List.mem op expr_ops) "Expression operation is outside bounded operational semantics.";
    require path (List.mem (text "kind" (get "value_type" value)) ("event"::supported_types)) "Unsupported operational expression value type.";
    if op = "literal" then require path (text "kind" (get "value_type" value) <> "event") "Literal events are not admitted.";
    if op = "effect_event" then require path (List.mem (text "value" value) ["requested";"initiated";"completed";"failed";"timed_out"])
      "Effect phase has no supported transition semantics.";
    if op = "rising" then (
      let rec observed_only expression =
        let op=text "op" expression in
        List.mem op ["observe";"literal";"parameter";"all";"any";"not";"eq";"ne";"lt";"le";"gt";"ge"]
        && List.for_all observed_only (list "args" expression) in
      let rec has_observation expression = text "op" expression = "observe" || List.exists has_observation (list "args" expression) in
      require path (List.for_all observed_only (list "args" value) && List.exists has_observation (list "args" value))
        "Rising requires an observed predicate; missing-to-true and state-only edges are unsupported.");
    List.iteri (fun i arg -> expression (path^"/args/"^string_of_int i) arg) (list "args" value)
  in
  let scoped path value =
    let kind=text "kind" value in
    require path (List.mem kind ["executor";"encounter"]) "Only finite executor and encounter scopes are executable.";
    if kind = "executor" then require path (ref_id (get "subject" value) = role) "Executor state belongs to the sole operational role."
  in
  let arbitration path value =
    require path (present value) "Deterministic arbitration must be supplied explicitly.";
    require path (List.mem (text "mode" value) ["exclusive";"priority"] && List.mem (text "tie" value) ["reject";"declared_order"])
      "Only deterministic exclusive or explicit-priority arbitration is executable.";
    require path (List.mem (text "write_conflict" value) ["reject";"identical_only"] && text "preemption" value = "forbidden"
      && text "fairness" value = "none" && get "contract" value = Json.Null)
      "Contract-defined conflict, preemption and fairness semantics remain unsupported."
  in
  let behavior path value =
    require path (Seen.cardinal (encounter_bindings value) <= 1)
      "One behavior occurrence cannot mix distinct encounter declarations, targets or state scopes.";
    expression (path^"/on") (get "on" value); expression (path^"/when") (get "when" value);
    require path (text "unknown" value = "defer" && get "unknown_target" value = Json.Null && list "emissions" value = [])
      "This subset defers new work on unknown evidence and does not emit messages.";
    List.iteri (fun i assignment -> expression (path^"/assignments/"^string_of_int i^"/value") (get "value" assignment)) (list "assignments" value)
  in
  List.iter (fun (d:D.declaration) -> let v=d.value and p=d.path in
    match d.kind with
    | D.Role ->
        require p (not (present (get "population" v)) && get "lineage_role" v = Json.Bool false) "Population and lineage roles remain unsupported.";
        List.iter (fun pin -> bind (p^"/requires") pin O.Capability_deferred) (list "requires" v)
    | D.Subject ->
        require p (text "entity_kind" v = "cell" && text "identity" v = "encounter") "Only concrete encounter-local cell subjects are executable.";
        require p (not (present (get "executor" v)) || ref_id (get "executor" v) = role) "Subject owner differs from sole executor role."
    | D.Encounter ->
        require p (ref_id (get "executor" v) = role && List.mem (text "termination" v) ["explicit_event";"contact_loss"]) "Encounter termination requires explicit timeline events.";
        require p (text "identity" (lookup (get "target" v)) = "encounter") "Encounter target must retain encounter identity.";
        bind (p^"/contract") (get "contract" v) O.Encounter_explicit
    | D.Clock -> ()
    | D.Observation ->
        require p (ref_id (get "observer" v) = role && text "access" v = "cell" && get "spatial_scope" v = Json.Null)
          "Executable observations require cell access and no unresolved spatial contract.";
        require p (List.mem (text "kind" (get "value_type" v)) supported_types) "Unsupported observation value type.";
        require p (List.mem (text "coverage" v) ["sampled";"event"]) "Continuous coverage is not established by bounded updates.";
        require p (List.sort String.compare (strings (list "invalidity" v)) = List.sort String.compare ["missing";"stale";"invalid";"conflicting"])
          "All four evidence invalidity distinctions must be retained.";
        time (p^"/freshness") (get "freshness" v);
        let expected=get "value_type" v and actual=get "result" (Names.find (ref_id (get "contract" v)) definitions) in
        require p (present actual && text "kind" expected = text "kind" actual &&
          (text "kind" expected <> "quantity" || List.for_all (fun key ->
            Json.equal (get key (get "unit" expected)) (get key (get "unit" actual))) ["dimension";"quantity_kind";"reference"]))
          "Observation descriptor result must match the complete nominal observation type.";
        bind (p^"/contract") (get "contract" v) O.Observation_external_evidence
    | D.State_store ->
        scoped (p^"/scope") (get "scope" v);
        require p (List.mem (text "kind" (get "value_type" v)) ["truth";"integer";"text"]) "State is finite truth/integer/text storage.";
        let capacity=get "capacity" v in
        require p (match capacity with Json.Int n -> Z.sign n > 0 && Z.compare n (Z.of_int 4096) <= 0 | _ -> false) "State capacity must be an explicit bounded integer.";
        require p (text "overflow" v = "reject" && List.mem (text "inheritance" v) ["reset";"not_applicable"]
          && get "contract" v = Json.Null && get "coordination" v = Json.Null) "State overflow, inheritance and coordination contracts are unsupported.";
        require p (text "lifetime" v = text "kind" (get "scope" v)) "State lifetime must match its executor or encounter scope.";
        Option.iter (fun reset ->
          expression (p^"/reset") reset;
          compatible_binding (p^"/reset") (scope_binding (get "scope" v)) (encounter_bindings reset))
          (if present (get "reset" v) then Some (get "reset" v) else None)
    | D.Effect ->
        require p (ref_id (get "executor" v) = role && get "spatial_scope" v = Json.Null && get "relationship" v = Json.Null && list "resources" v = [])
          "Effects with spatial, cross-subject or resource contracts need a later operational profile.";
        bind (p^"/contract") (get "contract" v) O.Effect_abstract_attempt;
        let subject_bindings=referenced_encounters (get "subject" v) in
        let effect_binding=if Seen.is_empty subject_bindings then None else Some (Seen.choose subject_bindings) in
        List.iter (fun argument ->
          let expression_value=get "value" argument in
          expression (p^"/parameters") expression_value;
          compatible_binding (p^"/parameters") effect_binding (encounter_bindings expression_value)) (list "parameters" v);
        let lifecycle=get "lifecycle" v in
        bind (p^"/lifecycle/contract") (get "contract" lifecycle) O.Lifecycle_correlated_feedback;
        require p (text "on_loss" lifecycle = "continue" && List.mem (text "on_unknown" lifecycle) ["continue";"defer"]
          && text "cancellation" lifecycle = "unsupported" && text "completion" lifecycle = "feedback" && text "failure" lifecycle = "feedback"
          && text "feedback_identity" lifecycle = "attempt_executor_subject")
          "Only correlated completion/failure feedback with explicit continue/defer authorization is executable.";
        Option.iter (time (p^"/lifecycle/timeout")) (if present (get "timeout" lifecycle) then Some (get "timeout" lifecycle) else None)
    | D.Rule ->
        behavior p v; arbitration (p^"/arbitration") (get "arbitration" v);
        (* Rule environments come from readable expressions and effect subjects.
           An assignment destination alone cannot bind a dynamic encounter. *)
        let environment=List.fold_left (fun bindings expression -> Seen.union bindings (encounter_bindings expression))
          Seen.empty ([get "on" v;get "when" v] @ List.map (get "value") (list "assignments" v) @ list "effects" v) in
        require p (Seen.cardinal environment <= 1) "Rule expressions require incompatible concrete encounter bindings.";
        let binding=if Seen.is_empty environment then None else Some (Seen.choose environment) in
        assignment_bindings p binding v;
        exactly_bound_effects p binding (list "effects" v)
    | D.Machine ->
        scoped (p^"/scope") (get "scope" v);
        require p (text "lifetime" v = text "kind" (get "scope" v)) "Machine lifetime must match finite executor or encounter scope.";
        arbitration (p^"/arbitration") (get "arbitration" v)
    | D.Transition ->
        behavior p v;
        let machine=lookup (get "machine" v) in
        let binding=scope_binding (get "scope" machine) in
        compatible_binding p binding (encounter_bindings v);
        assignment_bindings p binding v;
        exactly_bound_effects p binding (list "effects" v)
    | D.Parameter ->
        require p (text "selection" v = "fixed" && List.mem (text "kind" (get "value_type" v)) supported_types) "Only explicitly fixed operational parameters are executable."
    | D.Requirement ->
        (* Requirement support is assessed separately. Every original obligation
           survives lowering, including forms outside bounded monitoring. *)
        List.iter (fun key -> if present (get key v) then time (p^"/"^key) (get key v)) ["deadline"];
        (match get "horizon" v with Json.Object _ as value -> time (p^"/horizon") value | _ -> ())
    | _ -> fail p "Coordination, quantification, spatial scopes and inheritance require separately implemented semantics."
  ) declarations;
  let coherence_groups=ref Seen.empty in
  List.iter (fun (d:D.declaration) -> if d.kind = D.Observation then (
    let key=Canonical.encode (Json.Array [get "subject" d.value;get "coherence" d.value]) in
    require d.path (not (Seen.mem key !coherence_groups))
      "Multiple observations in one subject/coherence group require an explicit frame join, which this profile does not implement.";
    coherence_groups:=Seen.add key !coherence_groups)) declarations;
  let participants=List.filter_map (fun (d:D.declaration) -> match d.kind with
    | D.Rule -> Some (d.id,get "arbitration" d.value)
    | D.Transition -> Some (d.id,get "arbitration" (lookup (get "machine" d.value)))
    | _ -> None) declarations in
  List.iter (fun (_,policy) ->
    List.iter (fun id -> let governed=List.assoc id participants in
      require "/document" (Json.equal policy governed)
        "An explicit arbitration order must name participants governed by the same complete policy.")
      (strings (list "order" policy))) participants;
  require "/definitions" (Names.cardinal descriptor_index = Seen.cardinal !used) "Descriptor bundle contains unused interpretations outside the admitted operational context.";
  let report_value=Json.Object ["schema_version",str "biocompiler.policy_operational_admission.v0.1";"status",str "admitted";
    "profile",str O.profile;"document_artifact_digest",str (D.artifact_digest document);"descriptors_digest",str (O.descriptors_digest descriptors);
    "source_assessment",assessment;"target_status",str "unassessed";"artifact",str "withheld"] in
  {document_value=document;descriptors_value=descriptors;assessment_value=assessment;report_value}
