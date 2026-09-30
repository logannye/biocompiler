"""Reconstruct executable digital models from actual locked assembly contents.

No generator, adapter or source mechanism supplies operations, parameters,
wiring or observation bindings. Execution uses the independent digital runner.
"""

from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.ir.serialization import require
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION, run_model
from biocompiler.semantics.realization import Observable

COMPONENT_MODEL_VERSION = "biocompiler.component_model_reconstruction.v0.1"


def reconstruct_component_mechanism(assembly: ComponentAssembly) -> MechanismProgram:
    """Interpret only the closed software-operator profile from a locked assembly."""
    require(isinstance(assembly, ComponentAssembly), "Expected a ComponentAssembly.")
    records = assembly.registry.resolve(assembly.composition.registry_lock)
    instances = {item.id: item for item in assembly.composition.instances}
    require(set(instances) == set(records), "Assembly instance inventory differs from its lock.")
    connections = {}
    for edge in assembly.composition.connections:
        key = (edge.consumer_instance, edge.consumer_port)
        require(key not in connections, "An executable input has multiple producers.")
        require(edge.producer_instance in records and edge.consumer_instance in records,
                "An executable connection names an unknown instance.")
        producer = records[edge.producer_instance].synthetic_model
        consumer = records[edge.consumer_instance].synthetic_model
        require(producer is not None and consumer is not None,
                "A selected component lacks an executable synthetic model.")
        require(edge.producer_port == producer.output_port
                and edge.consumer_port in consumer.input_ports,
                "A connection disagrees with executable port bindings.")
        connections[key] = edge.producer_instance
    nodes = []
    responses = {}
    for binding in assembly.observation_map.outputs:
        responses.setdefault(binding.mechanism_output_id, []).append(binding.requirement_id)
    for identity, record in sorted(records.items()):
        model = record.synthetic_model
        require(model is not None, "A selected component lacks an executable synthetic model.")
        require(any(pin.kind == "model" and pin.version == MODEL_RUNNER_VERSION
                    for pin in record.identities),
                "Executable components require the current independent runner identity.")
        require(all((identity, ref) in connections for ref in model.input_ports),
                "An executable input is unconnected.")
        output = record.port(model.output_port)
        nodes.append(MechanismNode(
            identity, model.operation,
            Observable(output.meaning, output.dtype, output.role, output.scope, output.compartment),
            tuple(connections[(identity, ref)] for ref in model.input_ports),
            model.attributes, tuple(responses.get(identity, ())),
        ))
    inputs = tuple(item.mechanism_input_id for item in assembly.observation_map.inputs)
    outputs = tuple(item.mechanism_output_id for item in assembly.observation_map.outputs)
    require(len(set(inputs)) == len(inputs)
            and set(inputs) == {node.id for node in nodes if node.kind == "input"},
            "Assembly observation bindings must cover every executable input exactly once.")
    require(len(set(outputs)) == len(outputs)
            and set(outputs) == {node.id for node in nodes if node.kind == "output"},
            "Assembly observation bindings must cover every executable output exactly once.")
    return MechanismProgram("locked_component_assembly", tuple(nodes), outputs,
                            ("synthetic_signal_graph",))


def run_component_model(assembly, history, *, until=None):
    """Run canonical model input frames using assembly wiring and parameters."""
    return run_model(reconstruct_component_mechanism(assembly), history, until=until)
