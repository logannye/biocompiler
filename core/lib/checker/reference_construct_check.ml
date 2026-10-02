open Bioc_wire
open Bioc_domain
module R=Reference_check_support
module C=Reference_construct
module E=Reference_construct_evidence
module F=Reference_manifest
module M=Map.Make(String)
type limits=R.limits
let make_limits=R.make_limits
let default_limits=R.default_limits
let limits_json=R.limits_json
let checker_version=E.checker_version
let implementation_version="biocompiler.ocaml.reference_construct_check.v0.1"
let str=R.str
let field=R.field
let text=R.text
let array=R.array
let strings=R.strings
let manifest_json manifests=Json.Object(List.map(fun(key,value)->key,F.to_json value)manifests)
let prepare ?candidate budget request registry manifests=
  let references=R.manifests budget manifests in
  let authorities=[C.Request.canonical_size request,C.Request.to_json request;
    Component_registry.canonical_size registry,Component_registry.to_json registry;
    List.fold_left(fun n(_,value)->n+F.canonical_size value)0 manifests,manifest_json manifests
    ] @ (match candidate with None->[]|Some value->[C.Candidate.canonical_size value,C.Candidate.to_json value]) in
  R.prepare budget authorities;
  references
let dependency_values budget request candidate registry references=
  let composition=C.Request.composition request in
  E.Dependencies.of_json ~limits:(R.codec budget)(Json.Object[
    "request",str(C.Request.fingerprint request);"candidate",str(C.Candidate.fingerprint candidate);
    "layout",str(C.Candidate.layout_fingerprint candidate);"composition",str(Composition.fingerprint composition);
    "registry",str(Component_registry.fingerprint registry);"registry_lock",str(Component_registry.Lock.fingerprint(Composition.registry_lock composition));
    "target",str(Build_request.Target.fingerprint(Composition.target composition));"references",references;
    "checker",str checker_version;"admission_policy",str "biocompiler.human_admission_policy.v0.1";
    "linker",str Composition_check.checker_version;"reference_adapter",str "biocompiler.reference_component.v0.1"])
let dependencies ?parent ?(limits=default_limits) ~request ~candidate ~registry ~manifests ()=
  let budget=R.create ?parent limits in
  let references=prepare ~candidate budget request registry manifests in
  let result=dependency_values budget request candidate registry references in R.reserve budget(E.Dependencies.to_json result);result
let map budget key items=List.fold_left(fun result item->R.keep budget 1;let id=text key item in
  R.charge budget((String.length id+1)*(M.cardinal result+1));M.add id item result)M.empty items
let request_checks budget ~request ~registry ~manifests =
  let raw=C.Request.to_json request and composition=C.Request.composition request in
  let instances=List.fold_left(fun result value->R.keep budget 1;
      R.charge budget((String.length(Composition.Instance.id value)+1)*(M.cardinal result+1));M.add(Composition.Instance.id value)value result)
      M.empty(Composition.instances composition) in
  let requirements=Composition.requirement_ids composition and diagnostics=ref [] in
  let diagnostic status code message ?instance_id ?molecule_id ()=
    let instance=Option.bind instance_id(fun id->M.find_opt id instances) in
    let requirement_ids=match instance with Some value->Composition.Instance.requirement_ids value|None->requirements in
    let source=Option.bind instance Composition.Instance.source in
    let value=E.Diagnostic.make ~limits:(R.codec budget) ~status ~code ~message ?instance_id ?molecule_id ~requirement_ids ?source () in
    R.reserve budget(E.Diagnostic.to_json value);R.keep budget 1;diagnostics:=value::!diagnostics in
  let settings=Json.object_fields(R.limits_json(R.settings budget)) in
  let setting key=Z.to_int(Json.integer(Json.field key settings)) in
  let composition_limits=Composition_check.make_limits ~max_work:(setting "max_work")
    ~max_items:(setting "max_retained_intermediate_items") ~max_input_bytes:(setting "max_input_bytes")
    ~max_report_bytes:(setting "max_report_bytes") ~max_report_nodes:(setting "max_report_nodes") () in
  let linkage=Composition_check.check ~parent:(R.work budget) ~limits:composition_limits ~request:composition ~registry () in
  List.iter(fun item->
    let status=match Composition_evidence.Link_diagnostic.status item with
      |Composition_evidence.Link_diagnostic.Fail->E.Fail|Unknown->E.Unknown|Unsupported->E.Unsupported in
    diagnostic status ("composition:"^Composition_evidence.Link_diagnostic.code item)
      (Composition_evidence.Link_diagnostic.message item) ?instance_id:(Composition_evidence.Link_diagnostic.instance_id item) ())
    (Composition_evidence.Result.diagnostics linkage);
  if M.cardinal instances<>1 then diagnostic E.Unsupported "component_count"
    "The exact-CDS profile supports one selected component instance." ();
  if List.exists(fun value->R.charge budget 1;Composition.Instance.placement value<>Composition.Instance.Encoded_here)(Composition.instances composition)
  then diagnostic E.Unsupported "co_payload_assembly"
    "Co-payload placement needs a separately supported assembly and coexistence rule." ();
  if List.exists(fun key->array key (Composition.to_json composition)<>[])
      ["connections";"providers";"dependency_bindings";"resource_pools";"resource_bindings"]
  then diagnostic E.Unsupported "composition_relationships"
    "The reference-CDS profile cannot establish molecular layout for connections, providers or shared resource bindings." ();
  let source=field "source_request_fingerprint" raw in
  if not(Json.equal source Json.Null || Json.equal source(str(Composition.fingerprint composition))) then
    diagnostic E.Fail "source_request" "Reference construction lineage must identify its exact authoritative composition." ();
  if not(R.same_set budget (List.concat_map Composition.Instance.requirement_ids(Composition.instances composition)) requirements)
  then diagnostic E.Fail "requirement_coverage" "Selected instances must preserve exactly the authoritative composition requirements." ();
  let ids=List.map fst(M.bindings instances) in
  if not(R.same_set budget (List.map(text "instance_id")(array "references" raw))ids) then
    diagnostic E.Fail "reference_inventory" "Every selected component requires exactly one independently pinned reference selection." ();
  if not(R.same_set budget (List.map(text "instance_id")(array "placements" raw))ids) then
    diagnostic E.Fail "component_inventory" "The layout must contain every selected component exactly once and no additional instance." ();
  if List.length(array "molecules" raw)<>1 then diagnostic E.Unsupported "molecule_count"
    "Multi-molecule assembly has no acceptance rule in the exact-CDS profile." ();
  if array "junctions" raw<>[] then diagnostic E.Unsupported "junctions"
    "Junctions and overlaps are represented but have no accepted reference-CDS assembly rule." ();
  if array "regulatory_relations" raw<>[] then diagnostic E.Unsupported "regulatory_relationships"
    "The pinned coding reference establishes no regulatory relationships." ();
  if array "dependencies" raw<>[] then diagnostic E.Unsupported "construct_dependencies"
    "Construct and co-payload dependencies remain explicit and unresolved in this profile." ();
  let records=try Component_registry.resolve registry(Composition.registry_lock composition)
    with Diagnostic.Error error when error.code="component_registry"->diagnostic E.Fail "registry_lock" error.message ();[] in
  let resolved=ref M.empty and ordered=ref [] in
  List.iter(fun selected->R.charge budget 1;
    let instance_id=C.Reference.instance_id selected and selection=C.Reference.selection selected in
    let manifest_id=Pinned_identity.id(Reference_components.Selection.manifest selection) in
    match R.manifest budget manifest_id manifests with
    |None->diagnostic E.Unknown "missing_reference" "The trusted reference selection has no supplied offline manifest." ~instance_id ()
    |Some manifest when F.reference_set_id manifest<>manifest_id->diagnostic E.Fail "reference_inventory_key"
        "The manifest is not the reference set named by the inventory key." ~instance_id ()
    |Some manifest->
      let resolved_value=try
        let expected=Reference_components.adapt_reference_component ~limits:(R.codec budget) manifest selection in
        let reference=F.record manifest(Pinned_identity.id(Reference_components.Selection.reference selection)) in Some(reference,expected)
        with Diagnostic.Error error when error.code="reference_manifest" || error.code="reference_components" ->
          diagnostic E.Fail "reference_lock" error.message ~instance_id ();None in
      match resolved_value with None->()|Some(reference,expected)->
        R.keep budget 1;R.charge budget((String.length instance_id+1)*(M.cardinal !resolved+1));
        resolved:=M.add instance_id(reference,expected,selection)!resolved;
        ordered:=(instance_id,expected)::!ordered;
        R.charge budget(Component_registry.canonical_size registry+1);
        (match List.assoc_opt instance_id records with
        |Some actual when Component.fingerprint actual=Component.fingerprint expected->()
        |_->diagnostic E.Fail "reference_component"
            "The selected locked component differs from the independently adapted exact reference record." ~instance_id ());
        if F.alphabet_name(F.Record.alphabet reference) <> Build_request.Target.payload_format(Composition.target composition)
        then diagnostic E.Fail "reference_target" "The reference alphabet differs from the authoritative payload target." ~instance_id ())
    (C.Request.references request);
  let seen=Hashtbl.create 16 in
  let expected_assumptions=List.rev !ordered |> List.concat_map(fun(_,record)->Component.assumptions record)
    |>List.filter(fun value->R.charge budget(String.length value+1);if Hashtbl.mem seen value then false else(R.keep budget 1;Hashtbl.add seen value ();true)) in
  if not(M.is_empty !resolved) && strings "assumptions" raw<>expected_assumptions then diagnostic E.Fail "reference_assumptions"
    "The layout must retain exactly the reference component's conditional and unknown-feature assumptions." ();
  let molecules=map budget "id" (array "molecules" raw) in
  List.iter(fun placement->R.charge budget 1;
    let instance_id=text "instance_id" placement and molecule_id=text "molecule_id" placement in
    match M.find_opt instance_id instances with
    |None->diagnostic E.Fail "unexpected_component" "A layout placement names an unselected component instance." ~instance_id ~molecule_id ()
    |Some instance->
      let diagnostic status code message=diagnostic status code message ~instance_id ~molecule_id () in
      if not(R.equal budget (field "component" placement)(Component_registry.Component_lock.to_json(Composition.Instance.component instance))) then
        diagnostic E.Fail "selected_component" "Placement changed the selected component ID, version or content hash.";
      if strings "requirement_ids" placement<>Composition.Instance.requirement_ids instance
         || not(R.equal budget(field "source" placement)(C.source_to_json(Composition.Instance.source instance))) then
        diagnostic E.Fail "source_correspondence" "Placement changed or omitted selected source/requirement correspondence.";
      match M.find_opt molecule_id molecules with
      |None->diagnostic E.Fail "molecule_membership" "Placement names a molecule absent from the inventory."
      |Some molecule->
        if strings "component_order" molecule<>[instance_id] then diagnostic E.Fail "component_order"
          "The reference molecule must contain precisely its selected whole-CDS instance in order.";
        match M.find_opt instance_id !resolved with None->()|Some(reference,_,selection)->
          if not(R.equal budget(field "reference" placement)(Pinned_identity.to_json(Reference_components.Selection.reference selection))) then
            diagnostic E.Fail "placement_reference" "The placement reference differs from the trusted selected record identity.";
          let whole range=Json.equal(field "start" range)(Json.int 0) && Json.equal(field "end" range)(Json.int(F.Record.length reference)) in
          if not(whole(field "source_range" placement) && whole(field "molecule_range" placement)) then diagnostic E.Fail "exact_coverage"
            "The whole selected CDS must cover source and molecule exactly from zero to the exclusive reference length, without gaps, clipping or unexplained bases.";
          if text "orientation" placement<>"forward" then diagnostic E.Fail "orientation"
            "The selected reference is already 5prime-to-3prime; reversing it changes the selected CDS.";
          if not(Json.equal(field "reading_frame" placement)(Json.int 0)) then diagnostic E.Fail "reading_frame"
            "The independently reviewed reference specifies frame zero.";
          let reference_raw=F.Record.to_json reference in
          if List.exists(fun key->not(R.equal budget(field key molecule)(field key reference_raw)))
              ["alphabet";"artifact_class";"length";"completeness"] then diagnostic E.Fail "molecule_reference_metadata"
            "Molecule alphabet, artifact class, length and coding-only completeness must match the reviewed reference.";
          if not(R.equal budget(field "unknown_features" molecule)(field "unknown_features" reference_raw)) then diagnostic E.Fail "unknown_features"
            "The construct must retain every unknown delivered-payload feature from the reference unchanged.";
          if text "topology" molecule<>"unspecified" || text "compartment" molecule<>"unspecified" then diagnostic E.Fail "unproven_molecule_context"
            "A coding reference does not establish delivered-molecule topology or localization.")
    (array "placements" raw);
  if array "features" raw<>[] then diagnostic E.Unsupported "feature_boundaries"
    "This reference manifest has no reviewed subcomponent feature-boundary records; retain the whole pinned CDS placement." ();
  List.rev !diagnostics
let check_request ?parent ?(limits=default_limits) ~request ~registry ~manifests ()=
  let budget=R.create ?parent limits in ignore(prepare budget request registry manifests);
  let diagnostics=request_checks budget ~request ~registry ~manifests in
  R.reserve budget(Json.Array(List.map E.Diagnostic.to_json diagnostics));diagnostics
let check ?parent ?(limits=default_limits) ~request ~candidate ~registry ~manifests ()=
  let budget=R.create ?parent limits in let references=prepare ~candidate budget request registry manifests in
  let dependencies=dependency_values budget request candidate registry references in
  let diagnostics=ref(List.rev(request_checks budget ~request ~registry ~manifests)) in
  let raw=C.Request.to_json request and actual=C.Candidate.to_json candidate and composition=C.Request.composition request in
  let instance=match Composition.instances composition with [value]->Some value|_->None in
  let molecule_id=match array "molecules" raw with [value]->Some(text "id" value)|_->None in
  let requirement_ids=Composition.requirement_ids composition in
  let diagnostic code message=
    let value=E.Diagnostic.make ~limits:(R.codec budget) ~status:E.Fail ~code ~message
      ?instance_id:(Option.map Composition.Instance.id instance) ?molecule_id ~requirement_ids
      ?source:(Option.bind instance Composition.Instance.source) () in
    R.reserve budget(E.Diagnostic.to_json value);R.keep budget 1;diagnostics:=value::!diagnostics in
  if text "request_fingerprint" actual<>C.Request.fingerprint request then diagnostic "request_identity"
    "Candidate does not identify the authoritative frozen construct request.";
  if text "composition_fingerprint" actual<>Composition.fingerprint composition then diagnostic "composition_identity"
    "Candidate does not identify the authoritative selected composition.";
  if not(R.equal budget(field "registry_lock" actual)(Component_registry.Lock.to_json(Composition.registry_lock composition))) then
    diagnostic "candidate_registry_lock" "Candidate changed the selected registry, component, model or reference locks.";
  List.iter(fun key->if R.fingerprint budget(field key raw)<>R.fingerprint budget(field key actual) then
    diagnostic("changed_"^key)("Candidate changed authoritative "^String.map(function '_'->' '|c->c)key^"."))
    ["molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"evidence_policy"];
  let diagnostics=List.rev !diagnostics in
  let result=E.Result.make ~limits:(R.codec budget) ~outcome:(R.priority(List.map E.Diagnostic.status diagnostics))
    ~dependencies ~checked_requirement_ids:requirement_ids ~diagnostics () in
  R.reserve budget(E.Result.to_json result);result
let freshness ?parent ?(limits=default_limits) ~request ~candidate ~registry ~manifests result=
  let budget=R.create ?parent limits in R.prepare budget [E.Result.canonical_size result,E.Result.to_json result];
  let current=dependencies ~parent:(R.work budget) ~limits ~request ~candidate ~registry ~manifests () in
  let freshness=E.Result.freshness ~limits:(R.codec budget) result current in
  R.reserve budget(Realization_evidence.Freshness_report.to_json freshness);freshness
let replay ?parent ?(limits=default_limits) ~request ~candidate ~registry ~manifests result=
  let budget=R.create ?parent limits in R.charge budget(E.Result.canonical_size result+1);
  let actual=check ~parent:(R.work budget) ~limits ~request ~candidate ~registry ~manifests () in
  R.equal budget(E.Result.to_json result)(E.Result.to_json actual)
