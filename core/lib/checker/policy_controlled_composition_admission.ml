open Bioc_wire
module R=Bioc_domain.Policy_controlled_composition_request
module Domain=Bioc_domain.Policy_controlled_domain
module S=Policy_controlled_source
module D=Bioc_domain.Policy_document
module M=Bioc_domain.Policy_mrna_structure
module P=Bioc_domain.Pinned_identity
module T=Bioc_domain.Payload_template
module C=Bioc_domain.Construction
module N=Bioc_domain.Molecule
module G=Bioc_domain.Molecule_coordinates
module H=Bioc_domain.Molecule_chemistry
module Provenance=Bioc_domain.Molecular_record.Provenance
module Preflight=Bioc_domain.Policy_material_request
type t={report_value:Json.t;domain_value:Domain.validated}
let get key value=Json.field key(Json.object_fields value)
let arr value=Json.array value
let str value=Json.String value
let obj value=Json.Object value
let text value=Json.string value
let require condition message=Diagnostic.require condition "controlled_authority_admission" message
let ref_ kind id=obj["$type",str "Ref";"kind",str kind;"id",str id]
let strings values=Json.Array(List.map str values)
let count values=Json.int(List.length values)
let admit ~charge (request:R.t) : t=
  let external_charge=charge and work=ref(R.decoding_work request)in
  let budget:R.budgets=R.budgets request in
  let charge amount=require(amount>=0 && amount<=budget.max_work- !work)"Complete admission exceeds its supplied work budget.";
    external_charge amount;work:= !work+amount in
  let same first second=
    let encode value=let bytes=Preflight.preflight ~charge value in charge bytes;Canonical.encode value in
    encode first=encode second in
  let fingerprint value=
    let bytes=Preflight.preflight ~charge value in charge bytes;
    let encoded=Canonical.encode value in charge bytes;Canonical.sha256 encoded in
  let member value values=ignore(Preflight.preflight ~charge(Json.Array values));List.mem value values in
  let raw=R.raw request in
  (* All closure visits and subsequent digests are metered before traversal.
     Source and domain validators additionally debit their own logical work. *)
  ignore(Preflight.preflight ~charge raw);
  let source=S.admit ~charge ~document:(R.document request)in
  let typed:S.source=S.typed source in
  let authority=get "source_authority" raw and material=R.material request in
  let document=get "document" authority in
  let program=get "program" document in
  let definitions=arr(get "definitions"(get "semantics" program))in
  let resolve reference=
    let id=get "id" reference and version=get "version" reference in
    ignore(Preflight.preflight ~charge(Json.Array definitions));
    match List.filter(fun body->get "id" body=id && get "version" body=version)definitions with
    |[body]->
      let bytes=Preflight.preflight ~charge body in charge bytes;charge bytes;
      require(get "digest" reference=str(D.document_digest body))"Stale or substituted model/context DefinitionRef.";body
    |_ -> Diagnostic.fail "controlled_authority_admission" "Absent or ambiguous model/context semantic definition." in
  let contract=get "control_contract" authority and project=get "project_context" authority in
  let products=arr(get "products" contract)in
  let (product_a,product_b):S.product * S.product=typed.products in
  let source_products:S.product list=[product_a;product_b]in
  List.iter2(fun binding (product:S.product)->
    require(same(get "product_parameter" binding)(ref_ "Parameter" product.symbol.id))"Product parameter order differs from source.";
    ignore(resolve(get "product_definition" binding)))products source_products;
  let readout=get "readout" contract and controller=get "controller" contract in
  require(same(get "activity" readout)(ref_ "ControlledActivity" typed.activity.id) &&
    same(get "definition" readout)typed.readout.reference)"Activity/readout contract differs from original source.";
  require(same(get "definition" controller)typed.controller.contract.reference &&
    same(get "executor" controller)(ref_ "Role" typed.executor.id))"Controller contract differs from source.";
  let requested=get "requested_deadlines" contract in
  let deadlines:S.deadlines=typed.deadlines in
  List.iter(fun(key,value)->require(get key requested=Json.int value)"Source deadline differs from the supplied control description.")
    ["onset_ticks",deadlines.onset_ticks;"controller_off_ticks",deadlines.controller_off_ticks;
     "antigen_off_ticks",deadlines.antigen_off_ticks;"component_off_ticks",deadlines.component_off_ticks;
     "reactivation_ticks",deadlines.reactivation_ticks];
  let model=get "mechanism_model" raw in
  let body=get "body" model and identity=P.of_json(get "identity" model)in
  require(P.content_fingerprint identity=fingerprint body)"Model body differs from its supplied complete content pin.";
  let selected=get "catalog_binding" raw in
  require(same(get "entry" selected)typed.selected_implementation && same(get "model_identity" selected)(get "identity" model))
    "Selected catalog entry/model identity differs from original authority.";
  require(same(get "operation" body)typed.operation.reference && same(get "readout" body)typed.readout.reference &&
    same(get "controller" body)typed.controller.contract.reference)"Model meaning differs from admitted source contracts.";
  require(same(get "products" body)(Json.Array(List.map(get "product_definition")products)))"Model product definition order differs.";
  require(same(get "clock" body)(ref_ "Clock" typed.clock.id) && same(get "delays" body)(get "actual_delays" contract))
    "Actual mechanism clock/delays differ from the supplied original contract.";
  let assumptions=arr(get "assumptions" project)in
  let check_assumptions values=List.iter(fun value->require(member value assumptions)"Unresolved original conditional assumption.") (arr values)in
  check_assumptions(get "assumptions" body);
  let components=arr(get "components" body) and ports=arr(get "ports" body)in
  require(same(get "component_ids" selected)(Json.Array(List.map(get "id")components)))"Selected component inventory differs.";
  List.iter2(fun port reference->require(same(get "reference" port)reference)"Model port reference differs from exact source mapping.")ports
    [ref_ "Observation" typed.antigen.symbol.id;ref_ "Observation" typed.controller.symbol.id;
     ref_ "Parameter" product_a.symbol.id;ref_ "Parameter" product_b.symbol.id;ref_ "ControlledActivity" typed.activity.id];
  let order=M.member_order material and members=M.members material in
  require(List.map(fun item->text(get "member_id" item))products=order)"Control product mapping does not cover the exact RNA member order.";
  let assembly=get "assembly" raw in
  require(same(get "member_order" assembly)(strings order))"Assembly changes delivered member order.";
  let assembly_bindings=arr(get "product_bindings" assembly)in
  List.iter2(fun binding original->List.iter(fun key->require(same(get key binding)(get key original))"Assembly product mapping differs from original contract.")
    ["product_parameter";"member_id";"cds_id";"product_definition"])assembly_bindings products;
  List.iter2(fun binding (member:M.member)->require(same(get "product_identity" binding)(P.to_json member.product.identity))
    "Assembly product identity differs from original full material product.")assembly_bindings members;
  let context=get "context" raw in
  require(same(get "deployment" context)(get "deployment" document) && same(get "controller" context)controller)
    "Deployment/controller authority differs from original source.";
  let co_delivery=get "co_delivery" context in
  require(same(get "members" co_delivery)(strings order))"Co-delivery does not cover both members in order.";
  check_assumptions(get "assumptions" co_delivery);
  let localizations=arr(get "localizations" context)in
  List.iter2(fun item member->require(get "member_id" item=str member)"Localization member inventory differs.";
    ignore(resolve(get "definition" item)))localizations order;
  List.iter2(fun item member->require(get "member_id" item=str member)"Availability member inventory differs.")
    (arr(get "availability" context))order;
  List.iteri(fun index component->let binding=List.nth products index and localization=List.nth localizations index in
    require(get "member_id" component=get "member_id" binding && same(get "product_definition" component)(get "product_definition" binding) &&
      same(get "localization" component)(get "definition" localization))"Component-to-product/member/localization mapping differs.";
    List.iter(fun key->ignore(resolve(get key component)))["product_definition";"localization";"model"];
    require(same(get "model" component)(get "realization" typed.selected_implementation))"Component model differs from selected realization authority.")components;
  let sources=arr(get "sources" project) and empirical=arr(get "empirical_assertions" context)in
  let source_ids=List.map(get "id")sources in
  List.iter(fun item->List.iter(fun id->require(member id source_ids)"Empirical assertion has an absent original source pin.")
    (arr(get "source_ids" item)))empirical;
  let provenance value=
    ignore(Preflight.preflight ~charge(Provenance.to_json value));
    require(Provenance.status value=Provenance.Declared && Provenance.authority value<>[])
      "Complete molecular authority requires explicit supplied provenance, not an unresolved declaration.";
    List.iter(fun pin->ignore(Preflight.preflight ~charge(Json.Array sources));
      require(List.exists(fun source->get "id" source=str(P.id pin) && get "version" source=str(P.version pin) &&
        get "sha256" source=str(P.content_fingerprint pin))sources)
        "Molecular provenance pin does not resolve to the complete original project source inventory.")
      (Provenance.authority value)in
  let chemistry_provenance chemistry=
    List.iter(fun claim->provenance(H.Claim.provenance claim))[H.cap chemistry;H.start_end chemistry;H.finish_end chemistry];
    provenance(H.modification_inventory_provenance chemistry);provenance(H.Tail.provenance(H.terminal_tail chemistry));
    List.iter(fun modification->provenance(H.Modification.provenance modification))(H.modifications chemistry)in
  let template=M.template material in
  let roots=T.sources template and original_outputs=T.output_members template in
  require(List.length roots=2 && T.steps template=[] && T.complex_members template=[] && T.amounts template=[])
    "RC3 supports exactly two direct complete supplied roots; construction transforms, complexes and amounts remain unsupported.";
  require(List.sort String.compare(List.map C.Output_member.id original_outputs)=List.sort String.compare order)
    "Template output inventory differs from authority.";
  let outputs=List.map(fun id->List.find(fun output->C.Output_member.id output=id)original_outputs)order in
  let requirements=T.requirements template in
  require(List.length requirements=2 && List.for_all(fun item->C.Member_requirement.category item=C.Member_requirement.Payload)requirements)
    "Every RNA is an explicit payload; helpers/external requirements are unsupported.";
  List.iter(fun item->match C.Member_requirement.roles item with
    |[role]->require(C.Role.purpose role=N.Role.Requested_payload && C.Role.compartment role="cytoplasm")
      "Payload role must retain the declared cytoplasmic RNA compartment."
    |_->Diagnostic.fail "controlled_authority_admission" "Each RNA requires exactly one explicit payload role.")requirements;
  require(List.sort String.compare(List.filter_map C.Member_requirement.member_id requirements)=List.sort String.compare order)
    "Payload dispositions must cover exactly both members.";
  let structures=T.payload_structures template in
  require(List.length structures=2)"Both original members need complete payload-region manifests.";
  let resource=get "resources" raw in
  let member_limit=Z.to_int(Json.integer(get "max_member_rna_nt" resource)) and total_limit=Z.to_int(Json.integer(get "max_total_rna_nt" resource))in
  let total=ref 0 and used_roots=ref []in
  List.iteri(fun index (member:M.member)->
    let output=List.nth outputs index and binding=List.nth products index in
    let product:S.product=List.nth source_products index in
    require(C.Value_ref.kind(C.Output_member.value output)=C.Value_ref.Root)"Admission requires direct original RNA roots.";
    let root_id=C.Value_ref.id(C.Output_member.value output)in used_roots:=root_id:: !used_roots;
    let root=match List.find_opt(fun root->C.Root_source.id root=root_id)roots with Some root->root
      |None->Diagnostic.fail "controlled_authority_admission" "Absent original RNA root." in
    let molecule=C.Root_source.molecule root in
    provenance(C.Root_source.provenance root);provenance(C.Output_member.provenance output);
    provenance(N.provenance molecule);provenance member.product.provenance;
    List.iter(fun origin->provenance(N.Assembly_origin.provenance origin))(N.assembly molecule);
    List.iter(fun feature->provenance(N.Feature.provenance feature))(N.features molecule);
    chemistry_provenance(N.chemistry molecule);chemistry_provenance member.chemistry;
    require(N.form molecule=N.Delivered_rna && N.sequence_extent molecule=H.Complete && N.coding_status molecule=N.Coding &&
      C.Output_member.form output=N.Delivered_rna && C.Output_member.sequence_extent output=H.Complete && C.Output_member.coding_status output=N.Coding)
      "Every original/output member must explicitly be complete coding delivered RNA.";
    require(G.Space.alphabet(N.space molecule)=G.Rna && G.Space.topology(N.space molecule)=G.Linear && N.declared_nominal_complete molecule &&
      H.declared_nominal_complete member.chemistry)"Incomplete nominal RNA geometry or chemistry.";
    let original_chemistry=N.chemistry molecule in
    require(List.for_all(fun claim->H.Claim.status claim=H.Declared)
      [H.cap original_chemistry;H.start_end original_chemistry;H.finish_end original_chemistry] &&
      H.modification_inventory_status original_chemistry=H.Declared)
      "Complete RNA authority requires declared cap, ends and modification inventory.";
    let length=String.length(N.sequence molecule)in
    require(length<=member_limit && length<=total_limit- !total)"Original RNA length exceeds supplied per-member/total resources.";total:= !total+length;
    let regions:M.regions=member.regions in
    require(get "cds_id" binding=str regions.cds)"Supplied CDS mapping differs from material regions.";
    let features=N.features molecule in
    require(List.length features=4)"RC3 requires exactly the four explicit complete RNA regions.";
    let cursor=ref 0 in
    List.iter(fun(id,kind)->let feature=match List.find_opt(fun item->N.Feature.id item=id)features with Some item->item
      |None->Diagnostic.fail "controlled_authority_admission" "Unresolved original RNA region." in
      require(N.Feature.kind feature=kind)"Region identity has the wrong explicit kind.";
      let path=match N.Feature.path feature with Some path->path|None->Diagnostic.fail "controlled_authority_admission" "Unresolved original region coordinates." in
      G.Path.validate_for path(N.space molecule);
      require(G.Path.strand path=G.Forward && List.length(G.Path.spans path)=1)"Original RNA region needs one forward contiguous span.";
      let span=List.hd(G.Path.spans path)in require(G.Span.start span= !cursor && G.Span.stop span> !cursor)"Original complete RNA regions must partition the root in order.";
      cursor:=G.Span.stop span;
      require(N.Feature.reading_frame feature=(if kind="coding_sequence"then Some 0 else None))"Unexpected region reading-frame declaration.")
      [regions.utr5,"five_prime_utr";regions.cds,"coding_sequence";regions.utr3,"three_prime_utr";regions.poly_a,"poly_a_tail"];
    require(!cursor=length)"Original RNA region partition is incomplete.";
    let poly_feature=List.find(fun feature->N.Feature.id feature=regions.poly_a)features in
    let tail=H.terminal_tail original_chemistry in
    require(H.Tail.status tail=H.Declared && H.Tail.placement tail=Some H.Tail.Represented_terminal &&
      H.Tail.path tail=N.Feature.path poly_feature)"The exact represented terminal tail must equal the declared poly-A region.";
    (match H.Tail.length tail,H.Tail.path tail with
     |Some tail_length,Some tail_path->(match H.Tail_length.mode tail_length with
       |H.Tail_length.Exact amount->require(amount>0 && amount=G.Path.length tail_path)"Declared terminal tail length differs from its region."
       |_->Diagnostic.fail "controlled_authority_admission" "Complete RNA requires an exact positive represented tail length.")
     |_->Diagnostic.fail "controlled_authority_admission" "Complete RNA requires explicit terminal tail coordinates and length.");
    let module PS=Bioc_domain.Payload_structure in
    let manifest=match List.find_opt(fun item->PS.member_id item=member.id)structures with Some item->item
      |None->Diagnostic.fail "controlled_authority_admission" "Absent original member region manifest." in
    provenance(PS.provenance manifest);
    require(PS.form manifest=PS.Delivered_rna && PS.topology manifest=G.Linear &&
      List.sort compare(List.map(fun item->PS.Region.feature_id item,PS.Region.kind item)(PS.regions manifest))=
        List.sort compare[regions.utr5,"five_prime_utr";regions.cds,"coding_sequence";regions.utr3,"three_prime_utr";regions.poly_a,"poly_a_tail"])
      "Payload region manifest differs from the exact original member regions.";
    let replace key replacement value=obj(List.map(fun(name,item)->name,(if name=key then replacement else item))(Json.object_fields value))in
    let output_space=G.Space.of_json(replace "id"(str(C.Output_member.space_id output))(G.Space.to_json(N.space molecule)))in
    charge length;ignore(Preflight.preflight ~charge(H.to_json member.chemistry));
    H.validate_for member.chemistry output_space ~sequence:(N.sequence molecule) ~sequence_extent:H.Complete;
    let root_chemistry=H.to_json(N.chemistry molecule)in
    let tail=get "terminal_tail" root_chemistry in
    let tail=match get "path" tail with Json.Null->tail|path->replace "path"(replace "space_id"(str(C.Output_member.space_id output))path)tail in
    require(same(replace "terminal_tail" tail root_chemistry)(H.to_json member.chemistry))
      "Output chemistry differs from supplied original RNA chemistry under the declared coordinate rename.";
    let translation=Bioc_domain.Molecular_recoding.Translation_policy.to_json member.product.translation_policy in
    require(get "profile" translation=str "ordinary_cds")"RC3 supports ordinary supplied CDS translation declarations only.";
    require(P.id member.product.identity=product.product_identity)"Expected product identity differs from fixed source parameter.";
    let product_definition=resolve(get "product_definition" binding)in
    let expected_parameters=List.map(fun(id,value)->obj["$type",str "Parameter";"id",str id;
      "value_type",obj["$type",str "TypeSpec";"kind",str "text";"unit",Json.Null;"entity_kind",Json.Null];
      "value",str value;"lower",Json.Null;"upper",Json.Null;"selection",str "fixed"])
      ["product_identity",P.id member.product.identity;"product_version",P.version member.product.identity;
       "product_sha256",P.content_fingerprint member.product.identity]in
    require(same(get "parameters" product_definition)(Json.Array expected_parameters))
      "Product definition must explicitly retain the exact original product identity, version and content fingerprint.";
    let product_body=M.product_content_json member.product.sequence in
    require(P.content_fingerprint member.product.identity=fingerprint product_body)"Expected full protein body has a stale supplied identity."
  )members;
  require(List.length(List.sort_uniq String.compare !used_roots)=2)"Each complete RNA must retain its distinct supplied original root.";
  let domain_bindings:Domain.bindings={clock=typed.clock.id;executor_role=typed.executor.id;
    executor_identity=text(get "executor_identity" context);slot=text(get "slot" context);
    encounter_declaration=typed.encounter.id;encounter_subject=typed.target.id;
    antigen_observation=typed.antigen.symbol.id;controller_observation=typed.controller.symbol.id;
    antigen_freshness_ticks=typed.antigen.freshness_ticks;controller_freshness_ticks=typed.controller.freshness_ticks;
    member_a=List.nth order 0;member_b=List.nth order 1;
    product_a=product_a.symbol.id;product_b=product_b.symbol.id}in
  let domain_deadlines:Domain.deadlines={onset_ticks=deadlines.onset_ticks;controller_off_ticks=deadlines.controller_off_ticks;
    antigen_off_ticks=deadlines.antigen_off_ticks;component_off_ticks=deadlines.component_off_ticks;reactivation_ticks=deadlines.reactivation_ticks}in
  let domain_value=Domain.validate_for ~charge ~bindings:domain_bindings ~resolution:typed.resolution
    ~deadlines:domain_deadlines ~horizon_ticks:typed.horizon_ticks(R.domain request)in
  let usage:Domain.usage=match Domain.enumerate ~charge domain_value with
    |Domain.Complete usage->usage
    |Domain.Exhausted _->Diagnostic.fail "controlled_domain_exhausted" "Complete finite-domain enumeration exceeded the supplied budget."
    |Domain.Cancelled _->Diagnostic.fail "controlled_domain_cancelled" "Cancelled finite-domain enumeration has no admission token." in
  let inventory=obj["definitions",count definitions;"catalog_entries",Json.int 1;"model_components",count components;
    "model_ports",count ports;"members",count members;"products",count products;"roots",count roots;"transforms",Json.int 0;
    "source_records",count sources;"empirical_assertions",count empirical]in
  let counters=obj["prefixes",Json.int usage.prefixes;"transitions",Json.int usage.transitions;"histories",Json.int usage.histories;"work",Json.int usage.work]in
  let metadata:Domain.metadata=Domain.metadata(R.domain request)in
  let domain_inventory=obj["fixed_input_count",Json.int metadata.fixed_input_count;
    "physical_factor_count",Json.int metadata.physical_factor_count;"evidence_factor_count",Json.int metadata.evidence_factor_count;
    "lifecycle_factor_count",Json.int metadata.lifecycle_factor_count]in
  let report_value=obj["schema_version",str "biocompiler.policy_controlled_composition_assessment.v0.1";
    "profile",str R.profile;"stage",str "admission";"status",str "admitted";
    "claim_scope",str "supplied_authority_and_complete_finite_domain_only";
    "request_fingerprint",str(R.fingerprint request);"source_fingerprint",str(fingerprint document);
    "domain_fingerprint",str(fingerprint(get "operating_domain" raw));"material_fingerprint",str(fingerprint(get "material_authority" raw));
    "authority_inventory",inventory;"domain_inventory",domain_inventory;"domain_counters",counters;"source_admission",S.report source;"budgets",get "budgets" raw;
    "construction_status",str "not_performed";"behavior_status",str "not_performed";"empirical_status",str "unassessed"]in
  ignore(Preflight.preflight ~max_bytes:budget.max_report_bytes ~max_nodes:budget.max_report_nodes ~charge report_value);
  {report_value;domain_value}
let report (value:t)=value.report_value
let domain (value:t)=value.domain_value
