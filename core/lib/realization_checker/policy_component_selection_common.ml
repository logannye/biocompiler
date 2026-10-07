open Bioc_wire
module S = Bioc_domain.Policy_component_selection_request
module R = Bioc_domain.Policy_component_material_request
module Input = Bioc_domain.Policy_material_request
module M = Bioc_domain.Molecular_record
module W = Bioc_checker.Work_budget

let profile = "biocompiler.policy_decision_leader_variant.v0.1"
let common condition message = Diagnostic.require condition "policy_component_selection_common" message
let supported condition message = Diagnostic.require condition "policy_component_selection_variant_unsupported" message
let str value = Json.String value

type shape = {
  raw:Json.t; decision:Json.t; driver:Json.t; rule:Json.t; template:Json.t;
  decision_source:string; driver_source:string; leader_feature:string;
  cds_feature:string; utr3_feature:string; tail_feature:string;
  sequence:string; driver_length:int; cds_end:int; utr3_end:int;
}

let check ~budget ~request =
  let charge = W.charge budget in
  let measure raw = Input.preflight ~max_bytes:8388608 ~max_nodes:250000
    ~max_depth:128 ~charge raw in
  let fields = function
    | Json.Object values -> values
    | _ -> Diagnostic.fail "policy_component_selection_variant_unsupported" "Variant geometry requires a complete record." in
  let get key raw =
    let rec find = function
      | [] -> Diagnostic.fail "policy_component_selection_variant_unsupported"
          ("Missing closed variant field: " ^ key)
      | (name,value)::tail ->
          charge (1 + String.length name + String.length key);
          if name=key then value else find tail in
    find (fields raw) in
  let rows = function
    | Json.Array values -> values
    | _ -> Diagnostic.fail "policy_component_selection_variant_unsupported" "Variant geometry requires an explicit inventory." in
  let text raw = let value=Json.string raw in charge (String.length value); value in
  let same left right =
    let a=measure left and b=measure right in charge a; charge b; Json.equal left right in
  let fingerprint raw =
    let bytes=measure raw in charge bytes;
    let encoded=Canonical.encode_bounded ~max_bytes:8388608 raw in
    common (String.length encoded=bytes) "Common-authority encoding differs from its bounded preflight.";
    charge bytes; Canonical.sha256 encoded in
  let set key value raw =
    let found=ref false in
    let result=Json.Object (List.map (fun (name,previous) ->
      charge (1 + String.length name + String.length key);
      if name=key then (found:=true;name,value) else name,previous) (fields raw)) in
    supported !found ("Missing reconstructed variant field: " ^ key); result in
  let rec edit path transform raw = match path with
    | [] -> transform raw
    | key::tail -> set key (edit tail transform (get key raw)) raw in
  let put path value raw = edit path (fun _ -> value) raw in
  let array_map transform raw = charge 1; Json.Array (List.map (fun value -> charge 1; transform value) (rows raw)) in
  let length values =
    let rec count total = function [] -> total | _::tail -> charge 1; count (total+1) tail in
    count 0 values in
  let one label values = charge 1; match values with
    | [value] -> value | _ -> Diagnostic.fail "policy_component_selection_variant_unsupported"
        ("Variant requires exactly one " ^ label ^ ".") in
  let find label predicate values =
    let matches=List.filter (fun value -> charge 1; predicate value) values in
    one label matches in
  let number raw =
    let value=Json.integer raw in charge 1;
    supported (Z.sign value>=0 && Z.leq value (Z.of_int M.max_residues))
      "Variant coordinate is outside the molecular bound."; Z.to_int value in
  let add left right =
    charge 1;
    supported (left>=0 && right>=0 && left<=M.max_residues-right)
      "Variant joined coordinate exceeds its molecular bound."; left+right in
  let path raw frame first last =
    let span=one "forward path span" (rows (get "spans" raw)) in
    supported (get "space_id" raw=str frame && get "strand" raw=str "+" &&
      number (get "start" span)=first && number (get "end" span)=last)
      "Variant path must retain its declared frame and complete forward interval." in
  let rewrite_path first last raw =
    let span=one "reconstructed path span" (rows (get "spans" raw)) in
    set "spans" (Json.Array [span |> set "start" (Json.int first) |> set "end" (Json.int last)]) raw in
  let sequence molecule =
    let value=text (get "sequence" molecule) in
    supported (String.length value>0 && String.length value<=M.max_residues &&
      String.for_all (String.contains "ACGU") value) "Variant roots require nonempty complete canonical RNA.";
    value in
  let root_molecule root coding =
    let molecule=get "molecule" root in
    let geometry=get "space" molecule in
    let sequence=sequence molecule in
    supported (get "form" molecule=str "primary_rna" && get "sequence_extent" molecule=str "complete" &&
      get "coding_status" molecule=str coding && get "alphabet" geometry=str "RNA" &&
      get "axis" geometry=str "5prime_to_3prime" && get "topology" geometry=str "linear" &&
      number (get "length" geometry)=String.length sequence)
      "Variant root form, coding status and complete linear RNA geometry are unsupported.";
    molecule,sequence,text (get "id" geometry) in
  let feature molecule kind = find ("root feature " ^ kind)
    (fun value -> get "kind" value=str kind) (rows (get "features" molecule)) in
  let tail chemistry frame first last =
    let declaration=get "terminal_tail" chemistry in
    let length=get "length" declaration in
    supported (get "status" declaration=str "declared" && get "placement" declaration=str "represented_terminal" &&
      get "mode" length=str "exact" && number (get "exact" length)=last-first &&
      get "lower" length=Json.Null && get "upper" length=Json.Null &&
      get "modifications" chemistry=Json.Array [] && get "modification_inventory_status" chemistry=str "declared")
      "Variant output/driver requires an exact represented tail and declared empty modifications.";
    path (get "path" declaration) frame first last in
  let component raw slot =
    let selection=find (slot ^ " component selection") (fun row -> get "slot" row=str slot)
      (rows (get "components" (get "body" (get "composition_rule" raw)))) in
    find (slot ^ " complete component") (fun row -> same (get "identity" row) (get "component" selection))
      (rows (get "components" (get "component_library" raw))) in
  let inspect child =
    let raw=R.to_json child in ignore (measure raw);
    let decision=component raw "decision" and driver=component raw "driver" in
    let decision_root=get "root" (get "body" decision) and driver_root=get "root" (get "body" driver) in
    let leader,sequence,leader_frame=root_molecule decision_root "noncoding" in
    let driver_molecule,driver_sequence,driver_frame=root_molecule driver_root "coding" in
    let leader_length=String.length sequence and driver_length=String.length driver_sequence in
    let joined_length=add leader_length driver_length in
    let leader_row=one "decision UTR feature" (rows (get "features" leader)) in
    supported (get "kind" leader_row=str "five_prime_utr" && get "reading_frame" leader_row=Json.Null)
      "Decision material variants require one noncoding five-prime UTR.";
    path (get "path" leader_row) leader_frame 0 leader_length;
    let leader_feature=text (get "id" leader_row) in
    let origin=one "decision self-origin" (rows (get "assembly" leader)) in
    supported (same (get "source_space" origin) (get "space" leader))
      "Decision variant origin must retain the complete self coordinate space.";
    List.iter (fun key -> path (get key origin) leader_frame 0 leader_length) ["destination";"source_path"];
    let leader_chemistry=get "chemistry" leader in
    let leader_tail=get "terminal_tail" leader_chemistry in
    let leader_tail_length=get "length" leader_tail in
    supported (get "modifications" leader_chemistry=Json.Array [] &&
      get "modification_inventory_status" leader_chemistry=str "declared" &&
      get "status" leader_tail=str "declared" && get "placement" leader_tail=str "absent" &&
      get "path" leader_tail=Json.Null && get "mode" leader_tail_length=str "exact" &&
      number (get "exact" leader_tail_length)=0 && get "lower" leader_tail_length=Json.Null &&
      get "upper" leader_tail_length=Json.Null)
      "Decision variants require invariant empty modifications and an absent zero-length tail.";
    supported (get "products" (get "body" decision)=Json.Array []) "Decision variants cannot declare a product.";
    List.iter (fun carrier -> charge 1;
      let sites=rows (get "sites" carrier) in
      supported (sites<>[]) "Decision variant carrier requires an explicit full UTR site.";
      List.iter (fun site -> charge 1;
        supported (get "root" site=get "id" decision_root && get "feature" site=str leader_feature)
          "Decision carrier must retain its original UTR root and feature.";
        path (get "path" site) leader_frame 0 leader_length) sites)
      (rows (get "carriers" (get "body" decision)));
    supported (length (rows (get "features" driver_molecule))=3)
      "Variant driver requires exactly CDS, three-prime UTR and terminal poly-A features.";
    let cds=feature driver_molecule "coding_sequence" and utr3=feature driver_molecule "three_prime_utr"
      and poly_a=feature driver_molecule "poly_a_tail" in
    let ending row=number (get "end" (one "driver feature span" (rows (get "spans" (get "path" row))))) in
    let cds_end=ending cds and utr3_end=ending utr3 in
    supported (cds_end>0 && utr3_end>cds_end && driver_length>utr3_end &&
      get "reading_frame" cds=Json.int 0 && get "reading_frame" utr3=Json.Null && get "reading_frame" poly_a=Json.Null)
      "Variant driver regions must form its complete ordered coding/UTR/tail partition.";
    path (get "path" cds) driver_frame 0 cds_end;
    path (get "path" utr3) driver_frame cds_end utr3_end;
    path (get "path" poly_a) driver_frame utr3_end driver_length;
    tail (get "chemistry" driver_molecule) driver_frame utr3_end driver_length;
    let cds_feature=text (get "id" cds) and utr3_feature=text (get "id" utr3)
      and tail_feature=text (get "id" poly_a) in
    let rule=get "composition_rule" raw in let body=get "body" rule in
    let source slot=text (get "source" (find (slot ^ " root binding")
      (fun row -> get "slot" row=str slot) (rows (get "root_bindings" body)))) in
    let decision_source=source "decision" and driver_source=source "driver" in
    let material=get "material_authority" body in let template=get "template" material in
    let sources=rows (get "sources" template) in
    supported (length sources=2) "Variants require the two complete original roots.";
    List.iter (fun (id,root) ->
      let supplied=find "bound material root" (fun value -> get "id" value=str id) sources in
      supported (same supplied (set "id" (str id) root))
        "Material source must equal its selected component root under the fixed source-ID binding.")
      [decision_source,decision_root;driver_source,driver_root];
    let join=get "join" body in
    supported (get "left" join=str "decision" && get "right" join=str "driver" &&
      number (get "offset" join)=leader_length) "Variant join must place the full leader immediately before its driver.";
    let step=one "concatenation step" (rows (get "steps" template)) in
    let port=one "concatenation port" (rows (get "ports" step)) in
    let operation=get "operation" step in
    supported (get "id" step=get "step" join && get "id" port=get "port" join &&
      get "schema_version" operation=str "biocompiler.construction_concatenate.v0.1")
      "Variant construction requires its original sole concatenation step and port.";
    (match rows (get "inputs" operation) with
     | [left;right] -> List.iter2 (fun selection id ->
         let reference=get "value" selection in
         supported (get "path" selection=Json.Null && get "kind" reference=str "root" && get "id" reference=str id)
           "Variant concatenation cannot slice, reorder or substitute its two complete roots.") [left;right] [decision_source;driver_source]
     | _ -> supported false "Variant concatenation requires exactly two roots.");
    let product_frame=text (get "space_id" port) in
    let output=one "delivered output" (rows (get "output_members" template)) in
    let output_frame=text (get "space_id" output) in
    let member=one "mRNA expectation" (rows (get "members" material)) in
    supported (get "complex_members" template=Json.Array [] && get "amounts" template=Json.Array [] &&
      get "member_order" material=Json.Array [get "id" output] && get "id" member=get "id" output &&
      get "alphabet" port=str "RNA" && get "topology" port=str "linear" &&
      get "kind" (get "value" output)=str "product" && get "id" (get "value" output)=get "id" port)
      "Variants require one complete linear RNA output without complexes or amounts.";
    let regions=get "regions" member in
    supported (get "utr5" regions=str leader_feature && get "cds" regions=str cds_feature &&
      get "utr3" regions=str utr3_feature && get "poly_a" regions=str tail_feature)
      "Variant mRNA region identities must retain their exact original root features.";
    let transition=get "feature_transition" port in
    let dispositions=rows (get "dispositions" transition) in
    supported (get "added" transition=Json.Array [] && length dispositions=4)
      "Variant feature mapping must retain exactly four original features without additions.";
    List.iter (fun (source,feature,first,last) ->
      let disposition=find "exact feature disposition" (fun row ->
        get "source_id" row=str source && get "feature_id" row=get "id" feature) dispositions in
      supported (get "decision" disposition=str "exact") "Variant feature dispositions must be exact mappings.";
      let result=one "mapped feature" (rows (get "outputs" disposition)) in
      supported (get "id" result=get "id" feature && get "kind" result=get "kind" feature &&
        get "reading_frame" result=get "reading_frame" feature) "Variant mapped feature identity, kind or reading frame changed.";
      path (get "path" result) product_frame first last)
      [decision_source,leader_row,0,leader_length;
       driver_source,cds,leader_length,add leader_length cds_end;
       driver_source,utr3,add leader_length cds_end,add leader_length utr3_end;
       driver_source,poly_a,add leader_length utr3_end,joined_length];
    let chemistry=get "chemistry_transition" port in
    supported (get "mode" chemistry=str "explicit_output") "Variant join requires complete explicit output chemistry.";
    tail (get "output" chemistry) product_frame (add leader_length utr3_end) joined_length;
    tail (get "chemistry" member) output_frame (add leader_length utr3_end) joined_length;
    {raw;decision;driver;rule;template;decision_source;driver_source;
     leader_feature;cds_feature;utr3_feature;tail_feature;sequence;driver_length;cds_end;utr3_end} in
  let repin raw = put ["identity";"content_fingerprint"] (str (fingerprint (get "body" raw))) raw in
  let reconstruct base target_sequence =
    let n=String.length target_sequence in charge n;
    let total=add n base.driver_length in
    let root=get "root" (get "body" base.decision) in
    let molecule=get "molecule" root in
    let molecule=molecule |> set "sequence" (str target_sequence) |> put ["space";"length"] (Json.int n)
      |> edit ["assembly"] (array_map (fun origin -> origin
        |> put ["source_space";"length"] (Json.int n)
        |> edit ["destination"] (rewrite_path 0 n) |> edit ["source_path"] (rewrite_path 0 n)))
      |> edit ["features"] (array_map (edit ["path"] (rewrite_path 0 n))) in
    let root=set "molecule" molecule root in
    let decision=base.decision |> put ["body";"root"] root
      |> edit ["body";"carriers"] (array_map (edit ["sites"] (array_map (edit ["path"] (rewrite_path 0 n)))))
      |> repin in
    let decision_pin=get "identity" decision in
    let select_components raw=array_map (fun row -> if get "slot" row=str "decision"
      then set "component" decision_pin row else row) raw in
    let template=base.template |> edit ["sources"] (array_map (fun source ->
      if get "id" source=str base.decision_source then set "id" (str base.decision_source) root else source))
      |> edit ["steps"] (array_map (edit ["ports"] (array_map (fun port -> port
        |> edit ["feature_transition";"dispositions"] (array_map (fun disposition ->
          let source=get "source_id" disposition and feature=get "feature_id" disposition in
          let first,last = if source=str base.decision_source && feature=str base.leader_feature then 0,n
            else if source=str base.driver_source && feature=str base.cds_feature then n,add n base.cds_end
            else if source=str base.driver_source && feature=str base.utr3_feature then add n base.cds_end,add n base.utr3_end
            else if source=str base.driver_source && feature=str base.tail_feature then add n base.utr3_end,total
            else Diagnostic.fail "policy_component_selection_variant_unsupported" "Unexpected mapped variant feature." in
          edit ["outputs"] (array_map (edit ["path"] (rewrite_path first last))) disposition))
        |> edit ["chemistry_transition";"output";"terminal_tail";"path"] (rewrite_path (add n base.utr3_end) total))))) in
    let rule=base.rule |> edit ["body";"components"] select_components |> put ["body";"join";"offset"] (Json.int n)
      |> put ["body";"material_authority";"template"] template
      |> edit ["body";"material_authority";"members"] (array_map
        (edit ["chemistry";"terminal_tail";"path"] (rewrite_path (add n base.utr3_end) total))) |> repin in
    let rule_pin=get "identity" rule in
    let raw=base.raw |> edit ["component_library";"components"] (array_map (fun component ->
      if same (get "identity" component) (get "identity" base.decision) then decision else component))
      |> set "composition_rule" rule |> edit ["catalog_binding";"components"] select_components
      |> put ["catalog_binding";"rule"] rule_pin |> put ["context";"record_layout";"rule"] rule_pin in
    let layout_digest=fingerprint (get "record_layout" (get "context" raw)) in
    raw |> edit ["context";"providers"] (array_map (fun provider -> provider
      |> edit ["body";"capacities"] (array_map (set "record_layout_digest" (str layout_digest))) |> repin)) in
  let ordered=S.evaluation_order request in
  let anchor=S.anchor request in
  let base=inspect anchor.request in
  let union original =
    (* Reconstruct from the complete original component records and explicit
       global order. No candidate graph or saved union digest supplies data. *)
    let body=get "body" original.rule in
    let fragment slot =
      let component = if slot=str "decision" then original.decision
        else if slot=str "driver" then original.driver
        else Diagnostic.fail "policy_component_selection_common" "Unknown original semantic component slot." in
      get "fragment" (get "body" component) in
    let object_value fields = ignore (length fields); charge 1; Json.Object fields in
    let reference slot node=object_value ["slot",slot;"node",node] in
    let endpoint slot local=object_value ["slot",slot;"node",get "node" local;"port",get "port" local] in
    let boundary reference =
      let slot=get "slot" reference in
      let port=find "original boundary port" (fun row -> get "id" row=get "boundary" reference)
        (rows (get "boundary_ports" (fragment slot))) in
      endpoint slot (get "endpoint" port) in
    let rec position index = function
      | [] -> Diagnostic.fail "policy_component_selection_common" "Original local wire index is absent."
      | first::tail -> charge 1; if index=0 then first else position (index-1) tail in
    let nodes=array_map (fun row ->
      let slot=get "slot" row in
      let node=find "original primitive node" (fun node -> get "id" node=get "node" row)
        (rows (get "nodes" (fragment slot))) in
      object_value ["slot",slot;"node",get "node" row;"model",get "model" node]) (get "node_order" body) in
    let wires=array_map (fun row ->
      let producer,consumer = if get "kind" row=str "local" then
        let slot=get "slot" row in
        let wire=position (number (get "index" row)) (rows (get "wires" (fragment slot))) in
        endpoint slot (get "producer" wire),endpoint slot (get "consumer" wire)
      else (
        common (get "kind" row=str "link") "Unknown original semantic wire kind.";
        let link=find "original boundary link" (fun link -> get "id" link=get "id" row) (rows (get "links" body)) in
        boundary (get "producer" link),boundary (get "consumer" link)) in
      object_value ["producer",producer;"consumer",consumer]) (get "wire_order" body) in
    let inputs=array_map (fun row ->
      let slot=get "slot" row in
      let input=find "original external input" (fun input -> get "id" input=get "external_slot" row)
        (rows (get "external_slots" (fragment slot))) in
      object_value ["id",get "id" row;"kind",get "kind" input;"consumer",endpoint slot (get "consumer" input)])
      (get "input_order" body) in
    let groups=array_map (fun row ->
      let slot=get "slot" row in
      let group=find "original atomic group" (fun group -> get "id" group=get "group" row)
        (rows (get "atomic_groups" (fragment slot))) in
      object_value ["slot",slot;"id",get "id" group;"arbiter",reference slot (get "arbiter" group);
        "commits",array_map (reference slot) (get "commits" group)]) (get "group_order" body) in
    let value=object_value ["schema_version",str "biocompiler.policy_component_ordered_union.v0.1";
      "primitive_profile",get "primitive_profile" body;"observable_profile",get "observable_profile" body;
      "phase_profile",get "phase_profile" body;"transport_profile",get "transport_profile" body;
      "slot_layout",get "slot_layout" body;"nodes",nodes;"wires",wires;"inputs",inputs;"atomic_groups",groups;
      "semantic_exports",get "export_order" body;"links",get "links" body] in
    let context=get "context" original.raw in
    common (get "union_digest" (get "record_layout" context)=str (fingerprint value))
      "Original record layout does not pin its complete independently reconstructed union.";
    let domain=get "operating_domain" (get "implementation_request" original.raw) in
    common (get "domain_digest" (get "record_layout" context)=str (fingerprint domain))
      "Original record layout does not retain its complete operating domain.";
    value in
  let base_union=union base in
  List.iter (fun (alternative:S.alternative) ->
    charge 1;
    let actual=inspect alternative.request in
    common (same base_union (union actual)) "Selection alternatives change the complete ordered semantic union.";
    let expected=reconstruct base actual.sequence in
    common (same expected actual.raw)
      "Selection alternatives differ beyond the closed leader geometry and its exact dependency identities.") ordered;
  common (not (W.exhausted budget)) "Common-authority work exhausted before complete-census validation."
