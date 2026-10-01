open Bioc_wire

let claim_scope =
  "Structural intent validation only; no lowering, realization, molecular correctness, empirical function or human-use admission."

let check payload =
  let program = Bioc_domain.Intent.of_json payload in
  Json.Object [
    "validation_scope", Json.String Bioc_domain.Intent.validation_scope;
    "summary", Bioc_domain.Intent.summary program;
    "unimplemented_obligations", Json.Array (List.map (fun value -> Json.String value) [
        "behavior-lowering"; "behavior-execution"; "molecular-realization";
        "independent-translation-checking"; "human-therapeutic-admission"])
  ]
