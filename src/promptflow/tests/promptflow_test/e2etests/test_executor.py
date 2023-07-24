import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

import pytest

from promptflow.contracts.run_mode import RunMode
from promptflow.storage.run_storage import AbstractRunStorage
from promptflow.utils.utils import AttrDict
from promptflow_test.utils import (
    _save_result_in_temp_folder,
    assert_root_success,
    assert_success,
    get_root_runs,
    load_and_convert_to_raw,
    load_json,
)

TEST_ROOT = Path(__file__).parent.parent.parent
JSON_DATA_ROOT = TEST_ROOT / "test_configs/executor_api_requests"
E2E_ROOT = TEST_ROOT / "test_configs/e2e_samples"
E2E_ROOT_NEW = TEST_ROOT / "test_configs/flows"

if TEST_ROOT not in sys.path:
    sys.path.insert(0, str(TEST_ROOT.absolute()))


def assert_unique(ids: list):
    """Assert all the ids are unique."""
    assert len(ids) == len(set(ids))


def assert_result_expected(root_run: dict, expected):
    assert expected == root_run["result"]


def assert_flow_ids(result: dict, flow_id: str):
    """Assert all the flow ids are correct."""
    for flow_run in result["flow_runs"]:
        msg = f"Flow id for run {flow_run['run_id']} is {flow_run['flow_id']}, not expected {flow_id}"
        assert flow_id == flow_run["flow_id"], msg


def assert_run_ids(
    result: dict,
    variants_count=0,
    bulk_test_id="",
):
    """Assert all the run ids are correct."""
    root_runs = get_root_runs(result.get("flow_runs"))
    assert all([run["parent_run_id"] == bulk_test_id for run in root_runs])
    assert variants_count + 1, len(root_runs)
    groups = {run["run_id"]: [] for run in root_runs}
    for flow_run in result["flow_runs"]:
        if flow_run["run_id"] in groups:
            continue
        assert flow_run["parent_run_id"] in groups
        groups[flow_run["parent_run_id"]].append(flow_run)
    # Flow run count for each variants
    flow_run_per_variant = len(result["flow_runs"]) // (variants_count + 1)
    assert all([len(group) + 1 == flow_run_per_variant for group in groups.values()])

    nodes_groups = {run["run_id"]: [] for run in root_runs}
    for node_run in result["node_runs"]:
        assert node_run["flow_run_id"] in nodes_groups
        nodes_groups[node_run["flow_run_id"]].append(node_run)
    node_run_per_variant = len(result["node_runs"]) // (variants_count + 1)
    assert all([len(group) == node_run_per_variant for group in nodes_groups.values()])

    runids = [run["run_id"] for run in result["flow_runs"]] + [run["run_id"] for run in result["node_runs"]]
    assert all([runid is not None and runid != "None" for runid in runids])
    assert_unique([run["run_id"] for run in result["flow_runs"]])
    assert_unique([run["run_id"] for run in result["node_runs"]])


def assert_runs_persisted(storage: AbstractRunStorage, result: dict):
    for flow_run in result["flow_runs"]:
        run_info = storage.get_flow_run(flow_run["run_id"], flow_run["flow_id"])
        assert run_info.run_id == flow_run["run_id"]

    for node_run in result["node_runs"]:
        run_info = storage.get_node_run(node_run["run_id"])
        assert run_info.run_id == node_run["run_id"]


def assert_valid_variant_ids(result: dict):
    """Assert all the variant ids are valid."""
    for flow_run in result["flow_runs"]:
        if not flow_run["variant_id"]:
            raise ValueError(f"Variant id is empty for run {flow_run['run_id']}")


@pytest.mark.usefixtures("use_secrets_config_file", "basic_executor")
@pytest.mark.e2etest
class TestExecutor:
    def validate_result(self, result, file_name):
        validation_func = validation_funcs.get(file_name)
        if validation_func is None:
            return
        validation_func(result)

    @pytest.mark.parametrize(
        "params, expected",
        [
            ({"stop": [], "logit_bias": {}}, {"stop": None}),
            ({"stop": ["</i>"], "logit_bias": {"16": 100, "17": 100}}, {}),
            ({"stop": "[]", "logit_bias": "{}"}, {"stop": None, "logit_bias": {}}),
            ({"stop": "", "logit_bias": ""}, {"stop": None, "logit_bias": {}}),
        ],
    )
    def test_openai_parameters(self, basic_executor, params, expected):
        json_file = Path(JSON_DATA_ROOT) / "llms.json"
        request = load_json(json_file)
        for node in request["flow"]["nodes"]:
            node["inputs"].update(params)
        for k, v in params.items():
            if k not in expected:
                expected[k] = v

        def mock_completion(**kwargs):
            for k, v in expected.items():
                assert kwargs[k] == v, f"Expect {k} to be {v}, but got {kwargs[k]}"
            # TODO: Add an dummy openai connection in the ci
            model_key = "engine" if "engine" in kwargs else "model"
            assert kwargs[model_key] == "text-ada-001"
            text = kwargs["prompt"]
            return AttrDict({"choices": [AttrDict({"text": text})]})

        with patch("openai.Completion.create", new=mock_completion):
            raw_request = load_and_convert_to_raw(request)
            resp = basic_executor.exec_request_raw(raw_request=raw_request, raise_ex=True)
            for node_info in resp["node_runs"]:
                assert node_info["status"] == "Completed"
                assert node_info["output"] == "Please answer the question:DummyQuestion"

    @pytest.mark.parametrize(
        "file_name",
        [
            "aggregation_complicated_example",
            "openai_stream_script",
            "prompt_tools",
            "llm_tools",
            "conditional_flow_with_skip"
            # "package_tools",  # Skip this since we don't have serpapi key in CI
        ],
    )
    def test_executor_e2e_basic_flow_yaml_contract(self, file_name):
        flow_folder_path = Path(E2E_ROOT) / file_name
        yaml_file = flow_folder_path / "flow.dag.yaml"
        inputs_file = flow_folder_path / "inputs.json"
        outputs_file = Path(mkdtemp()) / "outputs.json"
        cmd = f"python -m promptflow._cli.execute -f {yaml_file} -i {inputs_file} -o {outputs_file} --raise_ex"
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(f"Failed to run command, stderr={p.stderr.decode()}")
        results = load_json(outputs_file)
        assert_success(results, outputs_file)
        self.validate_result(results, file_name)

    @pytest.mark.parametrize(
        "flow_path, input_file, need_inputs_resolve",
        [
            (f"{E2E_ROOT_NEW}/web_classification_v1", "samples.json", False),
            (f"{E2E_ROOT}/llm_tools", "data_inputs_json.json", True),
        ],
    )
    def test_executor_e2e_bulk_run(self, flow_path, input_file, need_inputs_resolve):
        yaml_file = Path(flow_path) / "flow.dag.yaml"
        inputs_file = Path(flow_path) / input_file
        outputs_file = Path(mkdtemp()) / "outputs.json"
        cmd = f"python -m promptflow._cli.execute -f {yaml_file} -i {inputs_file} -o {outputs_file} -m BulkTest"
        if need_inputs_resolve:
            cmd += " --need_inputs_resolve"
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError(f"Failed to run command, stderr={p.stderr.decode()}")
        results = load_json(outputs_file)
        assert results.get("flow_runs")
        assert results.get("node_runs")

        for flow_run in results.get("flow_runs"):
            assert flow_run.get("status") == "Completed"
        for node_run in results.get("node_runs"):
            assert node_run.get("status") == "Completed"

    @pytest.mark.parametrize(
        "file_name, error_code",
        [
            ("llm_tools_inputs_missing/flow.dag.yaml", "InputReferenceNotFound"),
            ("llm_tools_inputs_wrong_input_type/flow.dag.yaml", "InputTypeError"),
            ("llm_tools_inputs_connection_missing/flow.dag.yaml", "ConnectionNotFound"),
        ],
    )
    def test_executor_e2e_validation_failed(self, file_name, error_code):
        yaml_file = Path(E2E_ROOT) / file_name
        inputs_file = yaml_file.parent / "inputs.json"
        outputs_file = Path(mkdtemp()) / "outputs.json"
        cmd = f"python -m promptflow._cli.execute -f {yaml_file} -i {inputs_file} -o {outputs_file} --raise_ex"

        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert p.returncode != 0
        assert error_code in str(p.stderr)

    @pytest.mark.parametrize(
        "file_name",
        [
            # "serpapi_e2e.json"    # waiting for the serpapi key to be set
            "batch_request_e2e.json",
            "qa_with_bing.json",
            "example_flow.json",
            "eval_flow.json",
            #  "QnA_relevance_ranking.json",  # Waiting for refine the log_metric code
            #  "QnA_win_rates.json",
            "variants_flow.json",
            "type_conversion.json",
            "consume_connection.json",
            "custom_connection_flow.json",
            "chat_dummy.json",
            "example_flow_new.json",
            # "complicated_traces.json",  # flasky test, waiting for further tune under retry case
            "prompt_tool.json",
            "simple_lc_callback.json",
            "no_output.json",
        ],
    )
    def test_executor_basic_flow(self, basic_executor, file_name) -> None:
        """Test the basic flow that has three flow runs."""
        json_file = Path(JSON_DATA_ROOT) / file_name
        self.assert_basic_flow_success(json_file, basic_executor)

    # TODO: Pick required cases to e2e flows, remove "code" in the flow
    @pytest.mark.parametrize(
        "file_name",
        [
            "flow_corner_case_tools.json",
        ],
    )
    def test_executor_e2e_basic_flow(self, basic_executor, file_name):
        json_file = Path(E2E_ROOT) / file_name
        self.assert_basic_flow_success(json_file, basic_executor)

    def assert_basic_flow_success(self, json_file, basic_executor):
        file_name = json_file.name
        with open(json_file, "r") as f:
            request = json.load(f)
        request_data = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem)
        result = basic_executor.exec_request_raw(raw_request=request_data, raise_ex=True)
        result_file = _save_result_in_temp_folder(result, file_name)
        assert_success(result, result_file)
        assert_run_ids(result, len(request.get("variants", [])))
        assert_runs_persisted(basic_executor._run_tracker._storage, result)
        self.validate_result(result, file_name)

    @pytest.mark.parametrize(
        "file_name",
        [
            "variants_eval_partial_failure.json",
        ],
    )
    def test_executor_bulk_test_partial_failure(self, basic_executor, file_name):
        json_file = Path(JSON_DATA_ROOT) / "bulk_test_requests" / file_name
        with open(json_file, "r") as f:
            request = json.load(f)
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)
        result = basic_executor.exec_request_raw(raw_request)
        result_file = _save_result_in_temp_folder(result, file_name)
        assert_root_success(result, result_file)
        assert_runs_persisted(basic_executor._run_tracker._storage, result)
        bulk_test_id = request["bulk_test_id"]
        assert_run_ids(result, len(request.get("variants", [])), bulk_test_id)
        assert_root_success(result["evaluation"], result_file)

    @pytest.mark.parametrize(
        "file_name",
        [
            "variants_flow_with_eval.json",
            "variants_flow_with_eval_collection.json",
            "flow_with_eval.json",
        ],
    )
    def test_executor_bulk_test(self, basic_executor, file_name) -> None:
        json_file = Path(JSON_DATA_ROOT) / file_name
        with open(json_file, "r") as f:
            request = json.load(f)
        raw_request = load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.BulkTest)
        result = basic_executor.exec_request_raw(raw_request, raise_ex=True)
        result_file = _save_result_in_temp_folder(result, file_name)
        assert_success(result, result_file)
        assert_runs_persisted(basic_executor._run_tracker._storage, result)
        bulk_test_id = request["bulk_test_id"]
        assert_run_ids(result, len(request.get("variants", [])), bulk_test_id)
        assert_flow_ids(result, raw_request.flow_id)
        assert_valid_variant_ids(result)
        evaluation_result = result["evaluation"]
        assert_flow_ids(evaluation_result, raw_request.flow_id)
        assert_success(evaluation_result, result_file)
        assert_run_ids(evaluation_result, bulk_test_id=bulk_test_id)
        assert_runs_persisted(basic_executor._run_tracker._storage, evaluation_result)
        self.validate_result(result, file_name)
        root_runs = get_root_runs(evaluation_result.get("flow_runs"))
        assert 1 == len(root_runs)
        root_run = root_runs[0]
        assert isinstance(root_run["metrics"], dict)
        for k, v in root_run["metrics"].items():
            assert isinstance(v, list)
            for item in v:
                assert isinstance(item, dict)
                assert isinstance(item["value"], float)
                assert isinstance(item["variant_id"], str)

    @pytest.mark.parametrize(
        "file_name",
        [
            "eval_existing_run.json",
            "eval_existing_run_collection.json",
        ],
    )
    def test_executor_eval_flow(self, basic_executor, file_name) -> None:
        json_file = Path(JSON_DATA_ROOT) / file_name
        result = basic_executor.exec_request_raw(
            raw_request=load_and_convert_to_raw(source=json_file, source_run_id=json_file.stem, run_mode=RunMode.Eval),
            raise_ex=True,
        )
        result_file = _save_result_in_temp_folder(result, file_name)
        assert_success(result, result_file)
        assert_runs_persisted(basic_executor._run_tracker._storage, result)


def validate_eval_flow(result: dict) -> None:
    assert len(result["flow_runs"]) == 5
    assert len(result["node_runs"]) == 10


def validate_evaluation_sample(result: dict) -> None:
    assert len(result["flow_runs"]) == 3
    assert len(result["node_runs"]) == 5


def validate_variants_flow_json(result):
    validate_variants_flow(result, "", 3, 3, 4)


def validate_variants_flow(
    result: dict,
    baseline="",
    nlines=3,
    var_count=3,
    node_count=2,
) -> None:
    flow_count_per_var = nlines + 1  # root + flow for each line
    node_count_per_var = nlines * node_count
    assert len(result["flow_runs"]) == var_count * flow_count_per_var
    assert len(result["node_runs"]) == var_count * nlines * node_count

    flow_variants = Counter([run["variant_id"] for run in result["flow_runs"]])
    assert dict(flow_variants) == {
        baseline: flow_count_per_var,
        "variant1": flow_count_per_var,
        "variant2": flow_count_per_var,
    }
    node_variants = Counter([run["variant_id"] for run in result["node_runs"]])
    assert dict(node_variants) == {
        baseline: node_count_per_var,
        "variant1": node_count_per_var,
        "variant2": node_count_per_var,
    }
    return
    #  TODO: Validate result


def validate_variants_flow_with_eval(result: dict) -> None:
    validate_variants_flow(result, "variant0")  # The same as variants flow
    # Validate result of evaluation
    result = result["evaluation"]
    assert len(result["flow_runs"]) == 10  # 3 * 3 + 1
    assert len(result["node_runs"]) == 10  # 3 * 3 line + 1 reduce
    #  TODO: Validate result


def validate_qa_with_bing(result: dict) -> None:
    node_runs = result["node_runs"]
    llm_nodes = {node["run_id"]: node for node in node_runs if "total_tokens" in node["system_metrics"]}
    assert len(llm_nodes) == 2, f"There should be one LLM node, but got {len(llm_nodes)}"
    llm_metrics_keys = {"completion_tokens", "prompt_tokens", "total_tokens", "duration"}
    metrics_keys = {"duration"}
    for node in node_runs:
        expected = llm_metrics_keys if node["run_id"] in llm_nodes else metrics_keys
        assert expected == node["system_metrics"].keys()


def validate_consume_connection(result: dict) -> None:
    for node in result["node_runs"]:
        for k, v in node["inputs"].items():
            assert isinstance(v, str), f"Input {k} should be a string, but got {type(v)}"


def assert_api_calls(api_calls: list):
    for api_call in api_calls:
        if api_call["children"]:
            assert_api_calls(api_call["children"])
        assert isinstance(api_call["inputs"], dict), "Api call inputs should be a dict"
        assert api_call["output"] is not None
        for keys in ["name", "type"]:
            assert isinstance(api_call[keys], str), f"Api call {keys} should be a string"
        for keys in ["start_time", "end_time"]:
            assert isinstance(api_call[keys], float), f"Api call {keys} should be a float value"


def validate_complicated_traces(result: dict):
    node_run = result["node_runs"][0]
    api_calls = node_run["api_calls"]
    assert len(api_calls) == 5
    assert len(api_calls[1]["children"]) == 2
    assert len(api_calls[4]["children"]) == 2
    assert_api_calls(api_calls)


def validate_simple_lc_callback(result: dict):
    node_run = result["node_runs"][0]
    api_calls = node_run["api_calls"]
    assert len(api_calls) == 1
    assert api_calls[0]["name"] == "AgentExecutor"
    children = api_calls[0]["children"]
    assert len(children) == 2
    assert children[0]["name"] == "LLMChain"
    assert len(children[0]["children"]) == 1
    assert children[1]["name"] == "the action to take, should be one of [Calculator]"
    assert len(children[1]["children"]) == 1
    assert_api_calls(api_calls)


def validate_skip_flow_output(result: dict):
    flow_runs = result["flow_runs"]
    assert len(flow_runs) == 1
    assert flow_runs[0]["output"] == {"string": "10 is even number, skip the next node"}
    node_runs = result["node_runs"]
    assert len(node_runs) == 1
    assert node_runs[0]["output"] == {"is_even": True, "message": "10 is even number, skip the next node"}


validation_funcs = {
    "qa_with_bing.json": validate_qa_with_bing,
    "eval_flow.json": validate_eval_flow,
    "QnA_win_rates.json": validate_evaluation_sample,
    "QnA_relevance_ranking.json": validate_evaluation_sample,
    "variants_flow.json": validate_variants_flow_json,
    "variants_flow_with_eval.json": validate_variants_flow_with_eval,
    "consume_connection.json": validate_consume_connection,
    "complicated_traces.json": validate_complicated_traces,
    "simple_lc_callback.json": validate_simple_lc_callback,
    "conditional_flow_with_skip": validate_skip_flow_output,
}
