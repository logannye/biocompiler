open Bioc_wire
open Bioc_domain
module A = Architecture_contract
module D = Architecture_deployment
module T = D.Time
module Names = Map.Make (String)
let checker_version = "biocompiler.ocaml.architecture_deployment.v0.1"
type budget = Work_budget.t
let max_work = 1_000_000
let make_budget ?parent ?(maximum=max_work) () =
  Diagnostic.require (maximum > 0 && maximum <= max_work) "architecture_deployment_limit" "Invalid deployment work limit.";
  match parent with
  | None -> Work_budget.create ~profile:checker_version ~error_code:"architecture_deployment_limit" ~maximum ()
  | Some parent -> Work_budget.nested ~parent ~profile:checker_version ~error_code:"architecture_deployment_limit" ~maximum ()
let str v = Json.String v
let arr v = Json.Array v
let obj v = Json.Object v
let field k v = Json.field k (Json.object_fields v)
let text k v = Json.string (field k v)
module Inventory = struct
  type placement = {id:string;group:string;role:string;compartment:string}
  type window = {placement:string;clock:string;onset_min:T.t;onset_max:T.t;duration_min:T.t;duration_max:T.t}
  type t = {raw:Json.t;placements:placement list;windows:window list}
  let of_json raw =
    Source_execution_manifest.reserve_json (Source_execution_manifest.create_resource_budget ()) raw;
    let fields = Json.object_fields raw in Json.exact_fields ["placements";"availability"] fields;
    let placement raw = {id=text "id" raw;group=text "delivery_group" raw;role=text "recipient_role" raw;compartment=text "compartment" raw} in
    let window raw = {placement=text "placement_id" raw;clock=text "clock" raw;
      onset_min=T.of_json (field "onset_min_seconds" raw);onset_max=T.of_json (field "onset_max_seconds" raw);
      duration_min=T.of_json (field "duration_min_seconds" raw);duration_max=T.of_json (field "duration_max_seconds" raw)} in
    {raw;placements=Json.array (Json.field "placements" fields) |> List.map placement;
     windows=Json.array (Json.field "availability" fields) |> List.map window}
  let make ~placements ~availability = of_json (obj ["placements",arr placements;"availability",arr availability])
  let to_json v = v.raw
end
type result = {failures:string list;witnesses:Json.t list}
let ratio value = let numerator,denominator = T.ratio value in obj ["numerator",Json.Int numerator;"denominator",Json.Int denominator]
let sum left right = let a,b = T.ratio left and x,y = T.ratio right in let value = Q.add (Q.make a b) (Q.make x y) in
  obj ["numerator",Json.Int (Q.num value);"denominator",Json.Int (Q.den value)]
let check ?budget ~request ~(inventory:Inventory.t) () =
  let budget = make_budget ?parent:budget () in let charge () = Work_budget.charge budget 1 in
  let source = Architecture_request.source request |> Human_request.build_request in
  let nodes = Build_request.intent source |> Intent.to_json |> field "nodes" |> Json.array in
  let roles = List.filter_map (fun node -> charge (); if text "kind" node = "role" then Some (text "id" node) else None) nodes in
  let target = Architecture_request.circuit request |> Circuit_request.profile |> Circuit_request.Profile.target |> Option.get in
  let compartments = Build_request.Target.compartments target in
  let constraints = Architecture_request.constraints request in
  let groups = List.fold_left (fun map group -> charge (); Names.add (A.Delivery_group.id group) group map) Names.empty (A.Constraints.delivery_groups constraints) in
  let windows = List.fold_left (fun map (window:Inventory.window) -> charge ();Names.add window.placement window map) Names.empty inventory.windows in
  let failures = ref [] and witnesses = ref [] in
  let result_budget = Source_execution_manifest.create_resource_budget () in
  let fail value = Source_execution_manifest.reserve_json result_budget (str value);failures := value::!failures in
  let witness raw = Source_execution_manifest.reserve_json result_budget raw;witnesses := raw::!witnesses in
  List.iter (fun requirement -> charge ();let suffix = ":" ^ D.Requirement.id requirement in
      match Names.find_opt (D.Requirement.delivery_group_id requirement) groups with
      | None -> fail ("deployment_group_missing" ^ suffix)
      | Some group ->
        let recipient = D.Requirement.recipient_role requirement in
        if not (List.mem recipient roles && List.exists (fun role -> Identity.Role.to_string role = recipient) (A.Delivery_group.recipient_roles group)) then fail ("deployment_recipient_mismatch" ^ suffix);
        let compartment = D.Requirement.compartment requirement in
        if not (List.mem compartment compartments) || compartment = "abstract" then fail ("deployment_compartment_unknown" ^ suffix);
        if D.Requirement.require_same_recipient requirement && (not (A.Delivery_group.same_recipient group) || A.Delivery_group.mode group <> A.Delivery_group.Co_delivered) then fail ("deployment_same_recipient_unproven" ^ suffix);
        let placements = List.filter (fun (p:Inventory.placement) -> charge ();p.group = A.Delivery_group.id group && p.role = recipient) inventory.placements in
        if placements = [] then fail ("deployment_member_inventory_empty" ^ suffix);
        List.iter (fun (placement:Inventory.placement) -> charge ();let detail = suffix ^ ":" ^ placement.id in
            if placement.compartment <> compartment then fail ("deployment_destination_mismatch" ^ detail);
            match Names.find_opt placement.id windows with
            | None -> fail ("deployment_availability_missing" ^ detail)
            | Some window ->
              if window.clock <> D.clock then fail ("deployment_clock_mismatch" ^ detail);
              if T.compare window.onset_max (D.Requirement.required_from requirement) > 0 then fail ("deployment_onset_deadline" ^ detail);
              if T.compare_sum window.onset_min window.duration_min (D.Requirement.required_until requirement) < 0 then fail ("deployment_common_window_insufficient" ^ detail);
              Option.iter (fun bound -> if T.compare_sum window.onset_max window.duration_max bound > 0 then fail ("deployment_unavailability_deadline" ^ detail)) (D.Requirement.unavailable_after requirement);
              witness (obj ["requirement_id",str (D.Requirement.id requirement);"placement_id",str placement.id;
                "latest_onset",ratio window.onset_max;"earliest_end",sum window.onset_min window.duration_min;
                "latest_end",sum window.onset_max window.duration_max;"required_from",ratio (D.Requirement.required_from requirement);
                "required_until",ratio (D.Requirement.required_until requirement);
                "unavailable_after",(match D.Requirement.unavailable_after requirement with None -> Json.Null | Some time -> ratio time)])) placements)
    (A.Constraints.deployment_requirements constraints);
  {failures=List.rev !failures;witnesses=List.rev !witnesses}
let check_json ?budget ~request ~inventory () = check ?budget ~request:(Architecture_request.of_json request) ~inventory:(Inventory.of_json inventory) ()
