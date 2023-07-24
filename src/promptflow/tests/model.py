import argparse
import sys
import logging
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from promptflow.contracts.flow import Flow  # noqa: E402
from promptflow.executor import FlowExecutionCoodinator  # noqa: E402
from promptflow.utils.utils import load_json  # noqa: E402


logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_dir', type=str, required=True)
    args = parser.parse_args()
    model_dir = Path(args.model_dir)

    executor = FlowExecutionCoodinator.init_from_env()
    flow_file = model_dir / "flow.json"
    connections = load_json(model_dir / "connections.json")
    worker = executor.create_flow_executor_by_model(flow_file, connections)

    flow = Flow.deserialize(load_json(flow_file))
    output_names = list(flow.outputs.keys())
    samples = load_json(model_dir / "samples.json")
    for sample in samples:
        print("Inputs:", sample)
        result = worker.exec(sample)
        print("Outputs:")
        for name in output_names:
            print(f"{name}: {result[name]}")
