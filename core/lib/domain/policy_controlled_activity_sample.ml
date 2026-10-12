open Bioc_wire
type band = Background | Active
type t = { tick : int; band : band; activation_generation : int option }
let to_json (value:t) = Json.Object [
  "tick",Json.int value.tick;
  "band",Json.String (match value.band with Background -> "background" | Active -> "active");
  "activation_generation",(match value.activation_generation with None -> Json.Null | Some value -> Json.int value)]
