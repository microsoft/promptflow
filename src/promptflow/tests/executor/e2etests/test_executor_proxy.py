from pathlib import Path
from tempfile import mkdtemp

import pytest
from flask import Flask, jsonify, request

from promptflow.batch._batch_engine import BatchEngine
from promptflow.contracts.run_info import Status

from ..utils import MemoryRunStorage, get_flow_folder, get_flow_inputs_file, get_yaml_file

app = Flask(__name__)


@app.route("/Execution", methods=["POST"])
def mock_executor_service():
    data = request.json

    run_id = data.get("run_id")
    index = data.get("line_number")
    inputs = data.get("inputs")

    response_data = {
        "output": {"answer": "Hello world!"},
        "aggregation_inputs": {},
        "run_info": {
            "run_id": run_id,
            "status": "Completed",
            "inputs": inputs,
            "output": {"answer": "Hello world!"},
            "parent_run_id": run_id,
            "root_run_id": run_id,
            "start_time": "2023-11-24T06:03:20.2685529Z",
            "end_time": "2023-11-24T06:03:20.2688869Z",
            "index": index,
            "system_metrics": {"duration": "00:00:00.0003340", "total_tokens": 0},
            "result": {"answer": "Hello world!"},
        },
        "node_run_infos": {
            "get_answer": {
                "node": "get_answer",
                "flow_run_id": run_id,
                "parent_run_id": run_id,
                "run_id": "37081f88-21cf-4653-8004-2ebeb31ab644",
                "status": "Completed",
                "inputs": inputs,
                "output": "Hello world!",
                "start_time": "2023-11-24T06:03:20.2688262Z",
                "end_time": "2023-11-24T06:03:20.268858Z",
                "index": index,
                "system_metrics": {"duration": "00:00:00.0000318", "total_tokens": 0},
                "result": "Hello world!",
            }
        },
    }
    return jsonify(response_data)


@pytest.mark.unittest
class TestExecutorProxy:
    def test_batch_with_csharp_executor_proxy(self):
        flow_folder = "csharp_flow"
        mem_run_storage = MemoryRunStorage()
        batch_engine = BatchEngine(get_yaml_file(flow_folder), get_flow_folder(flow_folder), storage=mem_run_storage)
        # prepare the inputs
        input_dirs = {"data": get_flow_inputs_file(flow_folder)}
        inputs_mapping = {"question": "${data.question}"}
        output_dir = Path(mkdtemp())
        # start a mock flask server
        # port = batch_engine._executor_proxy._port
        # app.run(port=port)
        # submit a batch run
        batch_result = batch_engine.run(input_dirs, inputs_mapping, output_dir)
        assert batch_result.status == Status.Completed
