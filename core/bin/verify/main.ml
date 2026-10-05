let () =
  if Array.length Sys.argv = 4 && Sys.argv.(1) = Bioc_reference_package_verify.Reference_package_verify.argument then
    Bioc_reference_package_verify.Reference_package_verify.run ~input:Sys.argv.(2) ~output:Sys.argv.(3)
  else Bioc_service.Service.run Bioc_wire.Protocol.Verify
