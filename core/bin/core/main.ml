let () =
  if Array.length Sys.argv = 2 && Sys.argv.(1) = "--pipeline-session-v1" then
    Bioc_pipeline_service.Session_io.run ()
  else if Array.length Sys.argv = 2 && Sys.argv.(1) = "--pipeline-callback-session-v1" then
    Bioc_pipeline_service.Callback_manager_io.run ()
  else if Array.length Sys.argv = 4 && Sys.argv.(1) = "--reference-package-fds-v1" then
    Bioc_reference_package_session.Reference_package_session.run ~input:Sys.argv.(2) ~output:Sys.argv.(3)
  else
    Bioc_service.Service.run ~handler:Bioc_producer_service.Producer_service.handle Bioc_wire.Protocol.Core
