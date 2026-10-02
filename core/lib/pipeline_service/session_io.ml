let header_size = 9
let read_header () =
  let header=Bytes.create header_size in
  let rec loop offset =
    if offset=header_size then Some (Bytes.to_string header)
    else match input stdin header offset (header_size-offset) with
      | 0 when offset=0 -> None
      | 0 -> Bioc_wire.Diagnostic.fail "pipeline_session_frame" "Incomplete session frame header."
      | count -> loop (offset+count) in
  loop 0
let length header =
  Bioc_wire.Diagnostic.require (String.length header=9 && header.[8]='\n')
    "pipeline_session_frame" "Invalid session frame header.";
  let value=ref 0 in
  for index=0 to 7 do
    let digit=match header.[index] with
      | '0'..'9' as value -> Char.code value-Char.code '0'
      | 'a'..'f' as value -> Char.code value-Char.code 'a'+10
      | _ -> Bioc_wire.Diagnostic.fail "pipeline_session_frame" "Invalid session frame length." in
    value:= !value*16+digit
  done;
  !value
let publish (response:Session.response) =
  Printf.fprintf stdout "%08x\n" (String.length response.bytes);
  output_string stdout response.bytes;flush stdout
let run () =
  let session=Session.create () in
  let rec loop () =
    if not (Session.is_closed session) then
      match read_header () with
      | None -> ()
      | Some header ->
        let size=length header in
        Session.reserve_frame session size;
        let raw=really_input_string stdin size in
        publish (Session.handle_frame session raw);loop () in
  try loop () with
  | Sys_error _ ->
    (* An uncertain or partial write cannot be followed by another frame.
       Process exit releases the only authority; the client must invalidate. *)
    ()
  | _ ->
    (* No terminal path resumes authority. Publish at most one prepaid terminal
       envelope for malformed/truncated input or an internal failure, then exit. *)
    (try publish (Session.abort ~unbound:true session) with _ -> ())
