import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from promptflow._utils.logger_utils import get_logger
from promptflow._utils.yaml_utils import load_yaml

CONFIG_FILE = (Path(__file__).parents[1] / "config.yml").resolve()

# in order to import from absolute path, which is required by mldesigner
os.sys.path.insert(0, os.path.abspath(Path(__file__).parent))

from common import (  # noqa: E402
    clean_data,
    convert_to_abs_path,
    count_non_blank_lines,
    local_path_exists,
    non_padding_path,
    print_progress,
    split_document,
    summarize_batch_run_res,
)
from constants import DETAILS_FILE_NAME, SUMMARY_FILE_NAME, TEST_DATA_FILE_NAME, TEXT_CHUNK  # noqa: E402

logger = get_logger("data.gen")


def batch_run_flow(flow_folder: str, flow_input_data: str, flow_batch_run_size: int, node_inputs_override: dict):
    logger.info(f"Step 2: Start to batch run '{flow_folder}'...")
    import subprocess

    run_name = f"test_data_gen_{datetime.now().strftime('%b-%d-%Y-%H-%M-%S')}"
    # TODO: replace the separate process to submit batch run with batch run async method when it's available.
    connections_str = ""
    for node_name, node_val in node_inputs_override.items():
        for k, v in node_val.items():
            # need to double quote the value to make sure the value can be passed correctly
            # when the value contains special characters like "<".
            connections_str += f'{node_name}.{k}="{v}" '
    connections_str = connections_str.rstrip()

    cmd = (
        f'pf run create --flow "{flow_folder}" --data "{flow_input_data}" --name {run_name} '
        f"--environment-variables PF_WORKER_COUNT='{flow_batch_run_size}' PF_BATCH_METHOD='spawn' "
        f"--column-mapping {TEXT_CHUNK}='${{data.text_chunk}}' --connections {connections_str} --debug"
    )
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    logger.info(
        f"Submit batch run successfully. process id {process.pid}. Please wait for the batch run to complete..."
    )
    return run_name, process


def get_batch_run_output(output_path: Path):
    logger.info(f"Reading batch run output from '{output_path}'.")
    # wait for the output file to be created
    start_time = time.time()
    while not Path(output_path).is_file():
        time.sleep(1)
        # if the log file is not created within 5 minutes, raise an error
        if time.time() - start_time > 300:
            raise Exception(f"Output jsonl file '{output_path}' is not created within 5 minutes.")

    output_lines = []
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            output_lines = list(map(json.loads, f))
    except json.decoder.JSONDecodeError as e:
        logger.warning(
            f"Error reading the output file: {e}. It could be that the batch run output is empty. "
            "Please check your flow and ensure it can run successfully."
        )

    return [
        {"question": line["question"], "suggested_answer": line["suggested_answer"], "debug_info": line["debug_info"]}
        for line in output_lines
    ]


def run_local(
    documents_folder: str,
    document_chunk_size: int,
    document_chunk_overlap: int,
    document_nodes_file: str,
    flow_folder: str,
    flow_batch_run_size: int,
    output_folder: str,
    should_skip_split: bool,
    node_inputs_override: dict,
):
    text_chunks_path = document_nodes_file
    output_folder = Path(output_folder) / datetime.now().strftime("%b-%d-%Y-%H-%M-%S")
    if not Path(output_folder).is_dir():
        Path(output_folder).mkdir(parents=True, exist_ok=True)

    if not should_skip_split:
        text_chunks_path = split_document(document_chunk_size, document_chunk_overlap, documents_folder, output_folder)

    run_name, process = batch_run_flow(flow_folder, text_chunks_path, flow_batch_run_size, node_inputs_override)

    run_folder_path = Path.home() / f".promptflow/.runs/{run_name}"
    print_progress(run_folder_path / "logs.txt", process)
    test_data_set = get_batch_run_output(run_folder_path / "outputs.jsonl")
    # Store intermedian batch run output results
    jsonl_str = "\n".join(map(json.dumps, test_data_set))
    batch_run_details_file = Path(output_folder) / DETAILS_FILE_NAME
    with open(batch_run_details_file, "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)

    clean_data_output = Path(output_folder) / TEST_DATA_FILE_NAME
    clean_data(test_data_set, clean_data_output)
    logger.info(f"More debug info of test data generation can be found in '{batch_run_details_file}'.")

    try:
        summary_output_file = Path(output_folder) / SUMMARY_FILE_NAME
        summarize_batch_run_res(
            gen_details_file_path=batch_run_details_file,
            document_nodes_file_path=text_chunks_path,
            output_file_path=summary_output_file,
        )
        logger.info(f"Check test data generation summary in '{summary_output_file}'.")
    except Exception as e:
        logger.warning(f"Error to analyze batch run results: {e}")


def run_cloud(
    documents_folder: str,
    document_chunk_size: int,
    document_chunk_overlap: int,
    document_nodes_file: str,
    flow_folder: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    aml_cluster: str,
    prs_instance_count: int,
    prs_mini_batch_size: int,
    prs_max_concurrency_per_instance: int,
    prs_max_retry_count: int,
    prs_run_invocation_time: int,
    prs_allowed_failed_count: int,
    should_skip_split: bool,
    node_inputs_override: dict,
):
    # lazy import azure dependencies
    try:
        from azure.ai.ml import Input as V2Input
        from azure.ai.ml import MLClient, dsl, load_component
        from azure.ai.ml.entities import RetrySettings
        from azure.identity import DefaultAzureCredential
    except ImportError:
        raise ImportError(
            "Please install azure dependencies using the following command: "
            + "`pip install -r requirements_cloud.txt`"
        )

    @dsl.pipeline(
        non_pipeline_inputs=[
            "flow_yml_path",
            "should_skip_doc_split",
            "instance_count",
            "mini_batch_size",
            "max_concurrency_per_instance",
            "max_retry_count",
            "run_invocation_time",
            "allowed_failed_count",
        ]
    )
    def gen_test_data_pipeline(
        data_input: V2Input,
        flow_yml_path: str,
        should_skip_doc_split: bool,
        chunk_size=1024,
        chunk_overlap=200,
        instance_count=1,
        mini_batch_size=1,
        max_concurrency_per_instance=2,
        max_retry_count=3,
        run_invocation_time=600,
        allowed_failed_count=-1,
    ):
        from components import clean_data_component, split_document_component, summarize_generation_details_component

        data = (
            data_input
            if should_skip_doc_split
            else split_document_component(
                documents_folder=data_input, chunk_size=chunk_size, chunk_overlap=chunk_overlap
            ).outputs.document_node_output
        )
        flow_node = load_component(flow_yml_path, params_override=[{"name": "gen_test_data_example_flow"}])(
            data=data, text_chunk="${data.text_chunk}", connections=node_inputs_override
        )
        flow_node.mini_batch_size = mini_batch_size
        flow_node.max_concurrency_per_instance = max_concurrency_per_instance
        flow_node.set_resources(instance_count=instance_count)
        flow_node.retry_settings = RetrySettings(max_retry_count=max_retry_count, timeout=run_invocation_time)
        flow_node.mini_batch_error_threshold = allowed_failed_count
        # Should use `mount` mode to ensure PRS complete merge output lines.
        flow_node.outputs.flow_outputs.mode = "mount"
        clean_data_component(test_data_set_folder=flow_node.outputs.flow_outputs).outputs.test_data_output
        summarize_generation_details_component(
            document_node_output=data, test_data_set_folder=flow_node.outputs.flow_outputs
        ).outputs.summary_output

    def get_ml_client(subscription_id: str, resource_group: str, workspace_name: str):
        credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
        return MLClient(
            credential=credential,
            subscription_id=subscription_id,
            resource_group_name=resource_group,
            workspace_name=workspace_name,
        )

    ml_client = get_ml_client(subscription_id, resource_group, workspace_name)

    if should_skip_split:
        data_input = V2Input(path=document_nodes_file, type="uri_file")
    else:
        data_input = V2Input(path=documents_folder, type="uri_folder")

    prs_configs = {
        "instance_count": prs_instance_count,
        "mini_batch_size": prs_mini_batch_size,
        "max_concurrency_per_instance": prs_max_concurrency_per_instance,
        "max_retry_count": prs_max_retry_count,
        "run_invocation_time": prs_run_invocation_time,
        "allowed_failed_count": prs_allowed_failed_count,
    }

    pipeline_with_flow = gen_test_data_pipeline(
        data_input=data_input,
        flow_yml_path=os.path.join(flow_folder, "flow.dag.yaml"),
        should_skip_doc_split=should_skip_split,
        chunk_size=document_chunk_size,
        chunk_overlap=document_chunk_overlap,
        **prs_configs,
    )
    pipeline_with_flow.compute = aml_cluster
    studio_url = ml_client.jobs.create_or_update(pipeline_with_flow).studio_url
    logger.info(f"Completed to submit pipeline. Experiment Link: {studio_url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloud", action="store_true", help="Run test data generation at cloud.")
    args = parser.parse_args()

    if Path(CONFIG_FILE).is_file():
        with open(CONFIG_FILE, "r") as stream:
            config = load_yaml(stream)
    else:
        raise Exception(
            f"'{CONFIG_FILE}' does not exist. "
            + "Please check if you are under the wrong directory or the file is missing."
        )

    should_skip_split_documents = False
    document_nodes_file = convert_to_abs_path(config.get("document_nodes_file", None))
    documents_folder = convert_to_abs_path(config.get("documents_folder", None))
    flow_folder = convert_to_abs_path(config.get("flow_folder", None))
    output_folder = convert_to_abs_path(config.get("output_folder", None))
    validate_path_func = non_padding_path if args.cloud else local_path_exists
    node_inputs_override = config.get("node_inputs_override", None)

    if document_nodes_file and validate_path_func(document_nodes_file):
        should_skip_split_documents = True
    elif not documents_folder or not validate_path_func(documents_folder):
        raise Exception(
            "Neither 'documents_folder' nor 'document_nodes_file' is valid.\n"
            f"documents_folder: '{documents_folder}'\ndocument_nodes_file: '{document_nodes_file}'"
        )

    if not validate_path_func(flow_folder):
        raise Exception(f"Invalid flow folder: '{flow_folder}'")

    if args.cloud:
        logger.info("Start to generate test data at cloud...")
    else:
        logger.info("Start to generate test data at local...")

    if should_skip_split_documents:
        logger.info(
            "Skip step 1 'Split documents to document nodes' as received document nodes from "
            f"input file path '{document_nodes_file}'."
        )
        if Path(document_nodes_file).is_file():
            logger.info(f"Collected {count_non_blank_lines(document_nodes_file)} document nodes.")

    if args.cloud:
        run_cloud(
            documents_folder,
            config.get("document_chunk_size", 512),
            config.get("document_chunk_overlap", 100),
            document_nodes_file,
            flow_folder,
            config["subscription_id"],
            config["resource_group"],
            config["workspace_name"],
            config["aml_cluster"],
            config.get("prs_instance_count", 2),
            config.get("prs_mini_batch_size", 1),
            config.get("prs_max_concurrency_per_instance", 4),
            config.get("prs_max_retry_count", 3),
            config.get("prs_run_invocation_time", 800),
            config.get("prs_allowed_failed_count", -1),
            should_skip_split_documents,
            node_inputs_override,
        )
    else:
        run_local(
            documents_folder,
            config.get("document_chunk_size", 512),
            config.get("document_chunk_overlap", 100),
            document_nodes_file,
            flow_folder,
            config.get("flow_batch_run_size", 16),
            output_folder,
            should_skip_split_documents,
            node_inputs_override,
        )
