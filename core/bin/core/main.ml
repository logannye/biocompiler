let () = Bioc_service.Service.run ~handler:Bioc_producer_service.Producer_service.handle Bioc_wire.Protocol.Core
