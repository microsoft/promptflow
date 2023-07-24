import csv
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, List, Union

from promptflow.contracts.azure_storage_mode import AzureStorageMode
from promptflow.contracts.run_mode import RunMode
from promptflow.contracts.runtime import SubmitFlowRequest
from promptflow.executor import FlowExecutionCoodinator  # noqa: E402

PROMOTFLOW_ROOT = Path(__file__) / "../../.."


def load_json(source: Union[str, Path]) -> dict:
    """Load json file to dict"""
    with open(source, "r") as f:
        loaded_data = json.load(f)
    return loaded_data


def load_content(source: Union[str, Path]) -> str:
    """Load file content to string"""
    return Path(source).read_text()


def load_csv(source: Union[str, Path]) -> List:
    """Load csv file to list"""
    with open(source, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_model_to_request(flow_file):
    with open(flow_file, "r") as f:
        flow = json.load(f)
    model_dir = Path(flow_file).parent
    for tool in flow["tools"]:
        src = tool.get("source")
        code = tool.get("code")
        if src and not code:
            tool["code"] = (model_dir / src).read_text(encoding="utf-8")
    with open(model_dir / "samples.json", "r") as f:
        samples = json.load(f)
    return {
        "flow": flow,
        "batch_inputs": samples,
    }


def load_request_to_raw(
    f: Union[str, Path],
    run_mode: RunMode = RunMode.Flow,
):
    f = Path(f)
    is_json = f.name.endswith(".json")
    if is_json and f.exists():
        return convert_request_to_raw(load_json(f), run_mode=run_mode)
    if is_json and (f.parent / f.stem / "flow.json").exists():
        req = load_model_to_request(f.parent / f.stem / "flow.json")
        return convert_request_to_raw(req, run_mode=run_mode)
    raise NotImplementedError(f"Cannot load {f}")


def ensure_request_file(f: Union[str, Path]) -> str:
    """
    If the input doesn't exist, try to load from the model directory,
    this is because some cases are using model format as the input.
    """
    f = Path(f)
    is_json = f.name.endswith(".json")
    if is_json and not f.exists() and (f.parent / f.stem / "flow.json").exists():
        req = load_model_to_request(f.parent / f.stem / "flow.json")
        output_file = Path(mkdtemp()) / "request.json"
        with open(output_file, "w") as fout:
            json.dump(req, fout, indent=2)
        return str(output_file)
    return str(f)


def convert_request_to_raw(
    request,
    source_run_id=None,
    run_mode: RunMode = RunMode.Flow,
) -> dict:
    """Refine the request to raw request dict"""
    flow_run_id = str(uuid.uuid4())
    if not source_run_id:
        source_run_id = str(uuid.uuid4())
    variant_runs = request.get("variants_runs", {})
    if variant_runs:
        request["variants_runs"] = {v: f"{vid}_{flow_run_id}" for v, vid in variant_runs.items()}
    if request.get("eval_flow_run_id"):
        request["eval_flow_run_id"] = f"{request['eval_flow_run_id']}_{flow_run_id}"
    if "id" not in request["flow"]:
        request["flow"]["id"] = str(uuid.uuid4())
    return {
        "FlowId": request["flow"]["id"],
        "FlowRunId": flow_run_id,
        "SourceFlowRunId": source_run_id,
        "SubmissionData": json.dumps(request),
        "RunMode": run_mode,
        "BatchDataInput": request.get("batch_data_input", {}),
    }


def load_and_convert_to_raw(
    source: Union[str, Path, dict],
    source_run_id=None,
    node_name: str = None,
    run_mode: RunMode = RunMode.Flow,
    as_dict=False,
) -> Union[SubmitFlowRequest, dict]:
    """Load json file to dict or use data dict directly and convert to raw request instance or dict"""
    data = source
    if isinstance(source, (str, Path)):
        json_file = Path(source)
        data = load_json(json_file)

    for tool in data["flow"]["tools"]:
        if tool.get("source") and not tool.get("code"):
            with open(json_file.parent / tool["source"], "r") as f:
                tool["code"] = f.read()
            tool.pop("source")

    if data.get("node_name") is None and node_name:
        data["node_name"] = node_name

    request_dict = convert_request_to_raw(data, source_run_id, run_mode)
    if as_dict:
        return request_dict
    return SubmitFlowRequest.deserialize(request_dict)


def _save_result_in_temp_folder(result: dict, file_name: str):
    result_file = (Path(mkdtemp()) / Path(file_name).name).with_suffix(".output.json")
    with open(result_file, "w") as f:
        json.dump(result, f, indent=4)

    print(f"Result saved to {result_file}")
    return result_file


def execute(input_file, run_mode=RunMode.Flow, raise_ex=True) -> dict:
    with open(input_file, "r") as f:
        batch_request = json.load(f)
    raw_request = convert_request_to_raw(batch_request, input_file.stem, run_mode)
    executor = FlowExecutionCoodinator.init_from_env()
    start = datetime.now()
    result = executor.exec_request_raw(SubmitFlowRequest.deserialize(raw_request), raise_ex)
    end = datetime.now()
    input_key = "batch_inputs"
    if run_mode == RunMode.Eval:
        input_key = "bulk_test_inputs"
    print(f"Execution time: {end - start} for {len(batch_request[input_key])} lines.")
    return result


def get_root_runs(flow_runs: List):
    root_runs = [run for run in flow_runs if run["root_run_id"] == run["run_id"]]
    return root_runs


def get_child_runs(flow_runs: List, root_run_id: str) -> List[Dict]:
    child_runs = [run for run in flow_runs if run.get("parent_run_id") == root_run_id]
    return child_runs


def count_reduce_eval_node(request, mode: RunMode) -> int:
    if mode == RunMode.BulkTest:
        field = "eval_flow"
    elif mode == RunMode.Eval:
        field = "flow"
    else:
        return 0

    eval_flow_nodes = request.get(field, {}).get("nodes", [])
    count = sum(1 for node in eval_flow_nodes if node.get("reduce", False))
    return count


def assert_root_success(result, result_file=None):
    root_runs = get_root_runs(result.get("flow_runs"))
    for run in root_runs:
        assert run["status"] == "Completed", f"Root flow run {run['run_id']} failed, result_file={result_file}"


def assert_success(result, result_file=None):
    assert isinstance(result, dict)
    assert "flow_runs" in result
    assert isinstance(result["flow_runs"], list)
    record_message = "" if not result_file else f", see {result_file} for more details."
    for run in result["flow_runs"]:
        assert isinstance(run, dict)
        if "error" in run and run["error"] is not None:
            print(f"Error message: {run['error']}")
        assert run["status"] == "Completed", f"Flow run {run['run_id']} failed due to '{run['error']}'" + record_message
    assert "node_runs" in result, "No node runs found" + record_message
    assert len(result["node_runs"]) > 0, "No node runs found" + record_message


def assert_json_equal(data1, data2, key_path=""):
    """Iterate through the json and assert all the values are equal."""
    if isinstance(data1, dict):
        assert isinstance(data2, dict)
        for k, v in data1.items():
            assert k in data2, f"Key {key_path}.{k} not found in data2"
            assert_json_equal(v, data2[k], f"{key_path}.{k}")
    elif isinstance(data1, list):
        assert isinstance(data2, list)
        assert len(data1) == len(data2), f"Length of {key_path} not equal"
        for i in range(len(data1)):
            assert_json_equal(data1[i], data2[i], f"{key_path}[{i}]")
    else:
        assert data1 == data2, f"{key_path} not equal"


def assert_json_file_equal(file1, file2):
    try:
        assert_json_equal(load_json(file1), load_json(file2))
    except Exception as e:
        raise AssertionError(f"File '{file1}' and '{file2}' not equal, detail: {e}") from e


def get_executor_with_azure_storage_v2(bulk_run_id: str):
    dummy_run_dir = (PROMOTFLOW_ROOT / "tests/test_configs/dummy_runs").absolute().resolve().as_posix()
    tmpdir = mkdtemp()
    shutil.copytree(dummy_run_dir, tmpdir, dirs_exist_ok=True)
    os.environ["PROMPTFLOW_DUMMY_RUN_DIR"] = tmpdir
    os.environ["PROMPTFLOW_BULK_RUN_ID"] = bulk_run_id
    os.environ["PROMPTFLOW_AZURE_STORAGE_MODE"] = AzureStorageMode.Blob.name
    coodinator = FlowExecutionCoodinator.init_from_env()
    coodinator._nthreads = 4  # Reduce the number of threads to avoid rate limit
    return coodinator


def read_json_or_jsonl_from_blob(blob_client):
    content = blob_client.download_blob().readall().decode("utf-8")

    file_extension = os.path.splitext(blob_client.blob_name)[1]
    if file_extension == ".json":
        return json.loads(content)
    elif file_extension == ".jsonl":
        return [json.loads(line) for line in content.splitlines()]
    else:
        raise Exception(f"Unsupported file extension of the output files: {file_extension}")
