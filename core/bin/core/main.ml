let () =
  if Array.length Sys.argv = 2 && Sys.argv.(1) = "--pipeline-session-v1" then
    Bioc_pipeline_service.Session_io.run ()
  else if Array.length Sys.argv = 2 && Sys.argv.(1) = "--pipeline-callback-session-v1" then
    Bioc_pipeline_service.Callback_manager_io.run ()
  else
    Bioc_service.Service.run ~handler:Bioc_producer_service.Producer_service.handle
      ~scoped_handler:Bioc_producer_service.Producer_service.scoped_handle Bioc_wire.Protocol.Core
