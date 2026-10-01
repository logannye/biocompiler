type t = { code : string; message : string; path : string option }

exception Error of t

let fail ?path code message = raise (Error { code; message; path })

let require ?path condition code message =
  if not condition then fail ?path code message
