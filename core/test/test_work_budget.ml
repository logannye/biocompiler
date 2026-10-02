open Bioc_wire
module B = Bioc_checker.Work_budget
let require value message = if not value then failwith message
let rejected code action = match action () with _ -> failwith ("Expected " ^ code)
  | exception Diagnostic.Error error -> require (error.code = code) ("Wrong budget failure: " ^ error.code)
let create maximum = B.create ~profile:"literal.root.v1" ~error_code:"root_limit" ~maximum ()
let child parent maximum = B.nested ~parent ~profile:"literal.child.v1" ~error_code:"child_limit" ~maximum ()
let literals () =
  let root = create 10 in
  let first = child root 6 and second = child root 20 in
  B.charge first 6;
  rejected "child_limit" (fun () -> B.charge first 1);
  B.charge second 4;
  rejected "root_limit" (fun () -> B.charge second 1);
  B.charge root 0;
  let root = create 3 in let leaf = child root 4 in
  rejected "root_limit" (fun () -> B.charge leaf 4);
  B.charge leaf 3;
  rejected "root_limit" (fun () -> B.charge leaf 1);
  rejected "invalid_work_budget" (fun () -> B.charge root (-1));
  rejected "invalid_work_budget" (fun () -> create (-1));
  rejected "invalid_work_budget" (fun () -> B.create ~profile:"" ~error_code:"root_limit" ~maximum:1 ());
  let rec depth parent count = if count = 0 then parent else depth (child parent 1) (count - 1) in
  let deepest = depth (create 1) 15 in
  rejected "invalid_work_budget" (fun () -> child deepest 1);
  B.charge deepest 1;
  rejected "child_limit" (fun () -> B.charge deepest 1);
  let output bytes nodes = B.create_output ~profile:"literal.output.v1" ~error_code:"output_limit" ~max_bytes:bytes ~max_nodes:nodes () in
  let raw = Json.Object ["é",Json.Array [Json.String "\001\n\"\\";Json.Int (Z.of_int (-123));Json.Bool true;Json.Null]] in
  let size = String.length (Canonical.encode raw) in
  B.reserve_json (output size 7) raw;
  rejected "output_limit" (fun () -> B.reserve_json (output (size - 1) 7) raw);
  rejected "output_limit" (fun () -> B.reserve_json (output size 6) raw);
  let cumulative = output (size * 2) 14 in
  B.reserve_json cumulative raw; B.reserve_json cumulative raw;
  rejected "output_limit" (fun () -> B.reserve_json cumulative Json.Null);
  let rec cyclic_array = Json.Null :: cyclic_array in
  rejected "output_limit" (fun () -> B.reserve_json (output 1000 10) (Json.Array cyclic_array));
  let rec cyclic_object = ("key",Json.Null) :: cyclic_object in
  rejected "output_limit" (fun () -> B.reserve_json (output 1000 10) (Json.Object cyclic_object));
  print_endline "shared checker budget: independent and aggregate ceilings, atomic failure, bounded scopes passed"
let () = match Array.to_list Sys.argv with [_] -> literals () | _ -> failwith "usage: test_work_budget.exe"
