open Bioc_wire
let no_charge _ = ()

module Make (Charge : sig val charge : int -> unit end) = struct
  let charge = Charge.charge
  let enabled = charge != no_charge
  let bytes value = charge (Stdlib.String.length value)
  let rec preflight value = if enabled then (
    charge 1;
    match value with
    | Json.String value -> bytes value
    | Json.Int value -> charge (1 + Z.numbits value)
    | Json.Float _ -> charge 64
    | Json.Array values -> Stdlib.List.iter (fun value -> charge 1; preflight value) values
    | Json.Object fields -> Stdlib.List.iter (fun (key,value) -> charge 1; bytes key; preflight value) fields
    | Json.Null | Json.Bool _ -> ())

  (* Preflight the input before opaque canonical/decoder allocation. Reserve
     worst-case escaped scalar bytes before the real serialization pass. These
     are explicit bounded data passes, not a claim about CPU instructions. *)
  let rec serialization value = if enabled then (
    charge 1;
    match value with
    | Json.String value ->
        charge 2; Stdlib.String.iter (fun c -> charge (match c with
          | '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> 2
          | c when Char.code c < 0x20 -> 6 | _ -> 1)) value
    | Json.Int value -> charge (2 + Z.numbits value)
    | Json.Float _ -> charge 64
    | Json.Null -> charge 4
    | Json.Bool true -> charge 4
    | Json.Bool false -> charge 5
    | Json.Array values -> charge 2;
        Stdlib.List.iter (fun value -> charge 1; serialization value) values
    | Json.Object fields -> charge 2;
        (* The canonical encoder sorts keys. Precharge all possible ordered
           comparisons without allocating its sorted field array/list. *)
        Stdlib.List.iter (fun (key,value) ->
          charge 2; serialization (Json.String key); serialization value;
          Stdlib.List.iter (fun (other,_) -> charge 1; bytes key; bytes other) fields) fields)

  module String = struct
    include Stdlib.String
    let compare left right = bytes left; bytes right; Stdlib.String.compare left right
    let equal left right = bytes left; bytes right; Stdlib.String.equal left right
    let sub value pos len = charge (max 0 len); Stdlib.String.sub value pos len
    let map f value = bytes value; Stdlib.String.map (fun c -> charge 1; f c) value
    let mapi f value = bytes value; Stdlib.String.mapi (fun i c -> charge 1; f i c) value
    let iter f value = Stdlib.String.iter (fun c -> charge 1; f c) value
    let iteri f value = Stdlib.String.iteri (fun i c -> charge 1; f i c) value
    let for_all f value = Stdlib.String.for_all (fun c -> charge 1; f c) value
    let exists f value = Stdlib.String.exists (fun c -> charge 1; f c) value
    let contains value c = bytes value; Stdlib.String.contains value c
    let starts_with ~prefix value = bytes prefix; Stdlib.String.starts_with ~prefix value
    let ends_with ~suffix value = bytes suffix; Stdlib.String.ends_with ~suffix value
    let concat separator values =
      Stdlib.List.iter (fun value -> charge 1; bytes separator; bytes value) values;
      Stdlib.String.concat separator values
    let make count character = charge (max 0 count); Stdlib.String.make count character
  end
  let append_string left right = bytes left; bytes right; left ^ right

  module List = struct
    include Stdlib.List
    let scan values = Stdlib.List.iter (fun _ -> charge 1) values
    let length values = scan values; Stdlib.List.length values
    let map f values = scan values; Stdlib.List.map (fun v -> charge 1; f v) values
    let mapi f values = scan values; Stdlib.List.mapi (fun i v -> charge 1; f i v) values
    let map2 f left right = scan left; scan right; Stdlib.List.map2 (fun a b -> charge 1; f a b) left right
    let iter f values = Stdlib.List.iter (fun v -> charge 1; f v) values
    let iteri f values = Stdlib.List.iteri (fun i v -> charge 1; f i v) values
    let iter2 f left right = Stdlib.List.iter2 (fun a b -> charge 1; f a b) left right
    let fold_left f initial values = Stdlib.List.fold_left (fun a v -> charge 1; f a v) initial values
    let fold_right f values initial = scan values; Stdlib.List.fold_right (fun v a -> charge 1; f v a) values initial
    let filter f values = scan values; Stdlib.List.filter (fun v -> charge 1; f v) values
    let filter_map f values = scan values; Stdlib.List.filter_map (fun v -> charge 1; f v) values
    let find f values = Stdlib.List.find (fun v -> charge 1; f v) values
    let find_opt f values = Stdlib.List.find_opt (fun v -> charge 1; f v) values
    let find_map f values = Stdlib.List.find_map (fun v -> charge 1; f v) values
    let exists f values = Stdlib.List.exists (fun v -> charge 1; f v) values
    let for_all f values = Stdlib.List.for_all (fun v -> charge 1; f v) values
    let mem value values = exists (fun candidate -> candidate=value) values
    let mem_assoc key values = exists (fun (candidate,_) -> candidate=key) values
    let assoc_opt key values = find_map (fun (candidate,value) -> if candidate=key then Some value else None) values
    let assoc key values = match assoc_opt key values with Some value -> value | None -> raise Not_found
    let append left right = scan left; Stdlib.List.append left right
    let rev_append left right = scan left; Stdlib.List.rev_append left right
    let rev values = scan values; Stdlib.List.rev values
    let concat values = iter scan values; Stdlib.List.concat values
    let flatten = concat
    let concat_map f values = concat (map f values)
    let sort cmp values = scan values; Stdlib.List.sort (fun a b -> charge 1; cmp a b) values
    let stable_sort = sort
    let fast_sort = sort
    let sort_uniq cmp values = scan values; Stdlib.List.sort_uniq (fun a b -> charge 1; cmp a b) values
    let combine left right = scan left; scan right; Stdlib.List.combine left right
    let split values = scan values; Stdlib.List.split values
    let nth values index = if index >= 0 then charge (index+1); Stdlib.List.nth values index
    let nth_opt values index = if index >= 0 then charge (index+1); Stdlib.List.nth_opt values index
    let init count f = charge (max 0 count); Stdlib.List.init count (fun i -> charge 1; f i)
    let to_seq values =
      let rec next values () = match values with [] -> Seq.Nil | v::rest -> charge 1; Seq.Cons(v,next rest) in
      next values
    let of_seq sequence = Stdlib.List.of_seq (Seq.map (fun value -> charge 1; value) sequence)
  end

  module Json = struct
    include Json
    let rec equal_items compare left right = match left,right with
      | [],[] -> true
      | left::ls,right::rs -> charge 1; compare left right && equal_items compare ls rs
      | _ -> false
    let rec equal_metered left right =
      charge 1;
      match left,right with
      | Null,Null -> true
      | Bool left,Bool right -> left=right
      | Int left,Int right ->
          charge (1+Z.numbits left); charge (1+Z.numbits right); Z.equal left right
      | Float left,Float right -> Int64.equal (Int64.bits_of_float left) (Int64.bits_of_float right)
      | String left,String right -> String.equal left right
      | Array left,Array right ->
          List.length left=List.length right && equal_items equal_metered left right
      | Object left,Object right ->
          let sort=List.sort (fun (left,_) (right,_) -> String.compare left right) in
          let left,right=sort left,sort right in
          List.length left=List.length right &&
          equal_items (fun (lk,lv) (rk,rv) -> String.equal lk rk && equal_metered lv rv) left right
      | _ -> false
    let equal left right = if enabled then equal_metered left right else Json.equal left right
    let field ?path key values =
      List.iter (fun (name,_) -> bytes name; bytes key) values;
      Json.field ?path key values
    let exact_fields ?path keys values =
      List.iter bytes keys; List.iter (fun (name,_) -> bytes name) values;
      Json.exact_fields ?path keys values
    let string ?path value = let result=Json.string ?path value in bytes result; result
    let name ?path value = preflight value; Json.name ?path value
    let validate_utf8 value = bytes value; Json.validate_utf8 value
  end
  module Canonical = struct
    include Canonical
    let encode value = preflight value; serialization value; Canonical.encode value
    let encode_bounded ~max_bytes value = preflight value; serialization value; Canonical.encode_bounded ~max_bytes value
    let sha256 value = bytes value; Canonical.sha256 value
    let fingerprint value = preflight value; serialization value; serialization value; Canonical.fingerprint value
  end
  module Document = struct
    include Bioc_domain.Policy_document
    let of_json ?path value = preflight value; serialization value;
      Bioc_domain.Policy_document.of_json ?path value
    let document_digest value = preflight value; serialization value; serialization value;
      Bioc_domain.Policy_document.document_digest value
    let exact_decimal ?path value = bytes value; Bioc_domain.Policy_document.exact_decimal ?path value
    let nonblank_text value = bytes value; Bioc_domain.Policy_document.nonblank_text value
  end
  module Operational = struct
    include Bioc_domain.Policy_operational
    let get key value = Json.field key (Json.object_fields value)
    let text key value = Json.string (get key value)
    let list key value = Json.array (get key value)
    let ref_id value = text "id" value
    let duration value = preflight value; Bioc_domain.Policy_operational.duration value
    let descriptors_digest descriptors = Canonical.fingerprint (descriptors_to_json descriptors)
    let behavior_of_json value = preflight value; serialization value;
      Bioc_domain.Policy_operational.behavior_of_json value
  end

  module Names_base = Map.Make(String)
  module Names = struct
    include Names_base
    let add key value map = charge 1; Names_base.add key value map
    let singleton key value = charge 1; Names_base.singleton key value
    let fold f map initial = Names_base.fold (fun k v a -> charge 1; f k v a) map initial
    let iter f map = Names_base.iter (fun k v -> charge 1; f k v) map
    let cardinal map = fold (fun _ _ n -> n+1) map 0
    let bindings map = iter (fun _ _ -> ()) map; Names_base.bindings map
    let of_seq values = Seq.fold_left (fun map (key,value) -> add key value map) empty values
  end
  module Seen_base = Set.Make(String)
  module Seen = struct
    include Seen_base
    let add value set = charge 1; Seen_base.add value set
    let singleton value = charge 1; Seen_base.singleton value
    let fold f set initial = Seen_base.fold (fun v a -> charge 1; f v a) set initial
    let iter f set = Seen_base.iter (fun v -> charge 1; f v) set
    let cardinal set = fold (fun _ n -> n+1) set 0
    let elements set = iter (fun _ -> ()) set; Seen_base.elements set
    let for_all f set = Seen_base.for_all (fun v -> charge 1; f v) set
    let union left right = iter (fun _ -> ()) left; iter (fun _ -> ()) right; Seen_base.union left right
    let subset left right = iter (fun _ -> ()) left; iter (fun _ -> ()) right; Seen_base.subset left right
    let equal left right = iter (fun _ -> ()) left; iter (fun _ -> ()) right; Seen_base.equal left right
  end
end
