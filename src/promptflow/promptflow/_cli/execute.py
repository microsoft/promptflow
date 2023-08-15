# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Mapping

from promptflow._utils.utils import load_json
from promptflow.contracts.run_mode import RunMode
from promptflow.executor import FlowExecutor
from promptflow.storage import DummyRunStorage

# Here we import all the connections, so that the connections would be loaded and can be resolved
from promptflow.connections import *  # noqa


def resolve_json_inputs(input_data, working_dir) -> Mapping[str, List[Mapping[str, Any]]]:
    """
    Populate file contents if inputs file has file reference, for example:
     "baseline": "baseline.json",
     baseline.json will be loaded as content of the inputs
     "baseline": [{"text": "Line 0 first part"}, {"text": "Line 1 first part"}, ]

     Of course, in reality, the source data could be .csv, .parquet etc.  For this illustration, we only demo .csv
    """
    if working_dir is None:
        raise Exception("working_dir is None")
    return {key: load_json(f"{working_dir}/{value}") for key, value in input_data.items()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--flow", "-f", type=str, required=True)
    parser.add_argument("--working-dir", "-wd", type=str, default=None)
    parser.add_argument("--inputs", "-i", type=str, required=True)
    parser.add_argument("--need_inputs_resolve", action="store_true")  # Indicate if the inputs is raw without resolve
    parser.add_argument("--inputs_mapping", "-im", type=str, default=None)
    parser.add_argument("--output", "-o", type=str, required=True)
    parser.add_argument("--connections", "-c", default="connections.json")
    parser.add_argument("--run-mode", "-m", choices=list(RunMode), default="Flow", type=RunMode.parse)
    parser.add_argument("--run-id", "-r", type=str, default=None)
    parser.add_argument("--node-name", "-n", type=str, default=None)
    parser.add_argument("--raise_ex", action="store_true")
    args = parser.parse_args()
    if args.run_id is None:
        run_id = datetime.now().strftime("run_%Y%m%d%H%M%S")
    start = datetime.now()
    connections = load_json(args.connections)
    input_data = load_json(args.inputs)
    input_mapping = load_json(args.inputs_mapping) if args.inputs_mapping else None
    working_dir = args.working_dir if args.working_dir else Path(args.flow).parent
    run_mode = args.run_mode
    storage = DummyRunStorage()
    executor = FlowExecutor.create(
        flow_file=args.flow,
        connections=connections,
        working_dir=working_dir,
        storage=storage,
        raise_ex=args.raise_ex,  # For Flow run, default is True; For bulk run, False
    )
    try:
        if run_mode == RunMode.Flow:
            if isinstance(input_data, list) and len(input_data) > 0:
                input_data = input_data[0]
            line_result = executor.exec_line(input_data)
            print(line_result.output)
        elif run_mode == RunMode.SingleNode:
            updated_inputs = executor.validate_node_inputs(args.node_name, input_data)
            node_output = executor.exec_node(args.node_name, updated_inputs)
            print(node_output)
        elif run_mode == RunMode.BulkTest:
            if args.need_inputs_resolve is True:
                updated_input_data = resolve_json_inputs(input_data, working_dir)
                bulk_result = executor.exec_bulk_with_inputs_mapping(
                    updated_input_data, input_mapping, run_id=args.run_id
                )
            else:
                bulk_result = executor.exec_bulk(input_data, run_id=args.run_id)
            print(bulk_result.outputs)
    finally:
        # Always save run info even if exception is raised
        if executor:
            with open(args.output, "w") as f:
                json.dump(executor.collect_run_infos(), f, indent=2)  # Collect run info for the flow
            print(f"Run info is saved saved to '{args.output}'")
    end = datetime.now()
    print(f"{datetime.now()} Execute the flow in {end - start}.")
