let read_header () =
  let buffer = Bytes.create 9 in
  let rec read offset =
    if offset = 9 then Some (Bytes.to_string buffer)
    else
      match input stdin buffer offset (9 - offset) with
      | 0 when offset = 0 -> None
      | 0 -> Some (Bytes.sub_string buffer 0 offset)
      | count -> read (offset + count)
  in
  read 0

let run () =
  set_binary_mode_in stdin true;
  set_binary_mode_out stdout true;
  let io : Callback_channel.io = {
    read_header;
    read_body = (fun size -> really_input_string stdin size);
    write = (fun frame -> output_string stdout frame; flush stdout);
  } in
  Callback_manager.run (Callback_manager.create ~io ())
