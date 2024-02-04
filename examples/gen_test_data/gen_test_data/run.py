import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import configargparse

from promptflow._utils.logger_utils import get_logger

CONFIG_FILE = (Path(__file__).parents[1] / "config.ini").resolve()

# in order to import from absolute path, which is required by mldesigner
os.sys.path.insert(0, os.path.abspath(Path(__file__).parent))

from common import clean_data, count_non_blank_lines, \
    split_document, copy_flow_folder_and_set_node_inputs, \
    print_progress, convert_to_abs_path  # noqa: E402
from constants import TEXT_CHUNK, DETAILS_FILE_NAME  # noqa: E402

logger = get_logger("data.gen")


def batch_run_flow(
    flow_folder: str,
    flow_input_data: str,
    flow_batch_run_size: int,
):
    logger.info("Step 2: Start to batch run 'generate_test_data_flow'...")
    import subprocess

    run_name = f"test_data_gen_{datetime.now().strftime('%b-%d-%Y-%H-%M-%S')}"
    # TODO: replace the separate process to submit batch run with batch run async method when it's available.
    cmd = (
        f"pf run create --flow {flow_folder} --data {flow_input_data} --name {run_name} "
        f"--environment-variables PF_WORKER_COUNT='{flow_batch_run_size}' PF_BATCH_METHOD='spawn' "
        f"--column-mapping {TEXT_CHUNK}='${{data.text_chunk}}'"
    )
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    logger.info(
        f"Submit batch run successfully. process id {process.pid}. Please wait for the batch run to complete..."
    )
    return run_name


def get_batch_run_output(output_path: Path):
    logger.info(f"Reading batch run output from '{output_path}'.")
    # wait for the output file to be created
    start_time = time.time()
    while not Path(output_path).is_file():
        time.sleep(1)
        # if the log file is not created within 5 minutes, raise an error
        if time.time() - start_time > 300:
            raise Exception(f"Output jsonl file '{output_path}' is not created within 5 minutes.")

    with open(output_path, "r") as f:
        output_lines = list(map(json.loads, f))

    return [
        {"question": line["question"], "suggested_answer": line["suggested_answer"], "debug_info": line["debug_info"]}
        for line in output_lines
    ]


def run_local(
        documents_folder,
        document_chunk_size,
        document_nodes_file,
        flow_folder,
        flow_batch_run_size,
        output_folder,
        should_skip_split,
):
    text_chunks_path = document_nodes_file
    output_folder = Path(output_folder) / datetime.now().strftime("%b-%d-%Y-%H-%M-%S")
    if not Path(output_folder).is_dir():
        Path(output_folder).mkdir(parents=True, exist_ok=True)

    if not should_skip_split:
        text_chunks_path = split_document(document_chunk_size, documents_folder, output_folder)

    run_name = batch_run_flow(
        flow_folder,
        text_chunks_path,
        flow_batch_run_size
    )

    run_folder_path = Path.home() / f".promptflow/.runs/{run_name}"
    print_progress(run_folder_path / "logs.txt")
    test_data_set = get_batch_run_output(run_folder_path / "outputs.jsonl")
    # Store intermedian batch run output results
    jsonl_str = "\n".join(map(json.dumps, test_data_set))
    batch_run_details_file = Path(output_folder) / DETAILS_FILE_NAME
    with open(batch_run_details_file, "wt") as text_file:
        print(f"{jsonl_str}", file=text_file)

    clean_data_output = Path(output_folder) / "test-data.jsonl"
    clean_data(test_data_set, clean_data_output)
    logger.info(f"More debug info of test data generation can be found in '{batch_run_details_file}'.")


def run_cloud(
        documents_folder,
        document_chunk_size,
        document_nodes_file,
        flow_folder,
        subscription_id,
        resource_group,
        workspace_name,
        aml_cluster,
        prs_instance_count,
        prs_mini_batch_size,
        prs_max_concurrency_per_instance,
        prs_max_retry_count,
        prs_run_invocation_time,
        prs_allowed_failed_count,
        should_skip_split,
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
            instance_count=1,
            mini_batch_size=1,
            max_concurrency_per_instance=2,
            max_retry_count=3,
            run_invocation_time=600,
            allowed_failed_count=-1,
    ):
        from components import clean_data_component, split_document_component

        data = (
            data_input
            if should_skip_doc_split
            else split_document_component(
                documents_folder=data_input, chunk_size=chunk_size
            ).outputs.document_node_output
        )
        flow_node = load_component(flow_yml_path)(
            data=data,
            text_chunk="${data.text_chunk}"
        )
        flow_node.mini_batch_size = mini_batch_size
        flow_node.max_concurrency_per_instance = max_concurrency_per_instance
        flow_node.set_resources(instance_count=instance_count)
        flow_node.retry_settings = RetrySettings(max_retry_count=max_retry_count, timeout=run_invocation_time)
        flow_node.mini_batch_error_threshold = allowed_failed_count
        # Should use `mount` mode to ensure PRS complete merge output lines.
        flow_node.outputs.flow_outputs.mode = "mount"
        clean_data_component(test_data_set_folder=flow_node.outputs.flow_outputs).outputs.test_data_output

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
        **prs_configs,
    )
    pipeline_with_flow.compute = aml_cluster
    studio_url = ml_client.jobs.create_or_update(pipeline_with_flow).studio_url
    logger.info(f"Completed to submit pipeline. Experiment Link: {studio_url}")


if __name__ == "__main__":
    if Path(CONFIG_FILE).is_file():
        parser = configargparse.ArgParser(default_config_files=[CONFIG_FILE])
    else:
        raise Exception(
            f"'{CONFIG_FILE}' does not exist. "
            + "Please check if you are under the wrong directory or the file is missing."
        )

    parser.add_argument("--cloud", action="store_true", help="cloud flag")
    parser.add_argument("--documents_folder", type=str, help="Documents folder path")
    parser.add_argument("--document_chunk_size", type=int, help="Document chunk size, default is 1024")
    parser.add_argument(
        "--document_nodes_file", type=str, help="Document nodes file, default is ./document_nodes.jsonl"
    )

    parser.add_argument("--flow_folder", required=True, type=str, help="Test data generation flow folder path")
    parser.add_argument(
        "--flow_batch_run_size",
        type=int,
        help="Test data generation flow batch run size, default is 16",
    )
    parser.add_argument("--node_inputs_override", type=json.loads, help="The inputs need to override")
    # Configs for local
    parser.add_argument("--output_folder", type=str, help="Output folder path.")
    # Configs for cloud
    parser.add_argument("--subscription_id", help="AzureML workspace subscription id")
    parser.add_argument("--resource_group", help="AzureML workspace resource group name")
    parser.add_argument("--workspace_name", help="AzureML workspace name")
    parser.add_argument("--aml_cluster", help="AzureML cluster name")
    parser.add_argument("--prs_instance_count", type=int, help="Parallel run step instance count")
    parser.add_argument("--prs_mini_batch_size", help="Parallel run step mini batch size")
    parser.add_argument(
        "--prs_max_concurrency_per_instance", type=int, help="Parallel run step max concurrency per instance"
    )
    parser.add_argument("--prs_max_retry_count", type=int, help="Parallel run step max retry count")
    parser.add_argument("--prs_run_invocation_time", type=int, help="Parallel run step run invocation time")
    parser.add_argument(
        "--prs_allowed_failed_count", type=int, help="Number of failed mini batches that could be ignored"
    )
    args = parser.parse_args()
    copied_flow_folder = args.flow_folder + "_" + time.strftime("%b-%d-%Y-%H-%M-%S") + "_temp"

    try:
        should_skip_split_documents = False
        document_nodes_file = convert_to_abs_path(args.document_nodes_file)
        documents_folder = convert_to_abs_path(args.documents_folder)
        flow_folder = convert_to_abs_path(args.flow_folder)
        output_folder = convert_to_abs_path(args.output_folder)

        if document_nodes_file and Path(document_nodes_file).is_file():
            should_skip_split_documents = True
        elif not documents_folder or not Path(documents_folder).is_dir():
            parser.error(
                "Either 'documents_folder' or 'document_nodes_file' should be specified correctly.\n"
                f"documents_folder: '{documents_folder}'\ndocument_nodes_file: '{document_nodes_file}'"
            )

        if args.cloud:
            logger.info("Start to generate test data at cloud...")
        else:
            logger.info("Start to generate test data at local...")

        if should_skip_split_documents:
            logger.info(
                "Skip step 1 'Split documents to document nodes' as received document nodes from "
                f"input file '{args.document_nodes_file}'."
            )
            logger.info(f"Collected {count_non_blank_lines(args.document_nodes_file)} document nodes.")

        copy_flow_folder_and_set_node_inputs(copied_flow_folder, args.flow_folder, args.node_inputs_override)

        if args.cloud:
            run_cloud(
                args.documents_folder,
                args.document_chunk_size,
                args.document_nodes_file,
                copied_flow_folder,
                args.subscription_id,
                args.resource_group,
                args.workspace_name,
                args.aml_cluster,
                args.prs_instance_count,
                args.prs_mini_batch_size,
                args.prs_max_concurrency_per_instance,
                args.prs_max_retry_count,
                args.prs_run_invocation_time,
                args.prs_allowed_failed_count,
                should_skip_split_documents,
            )
        else:
            run_local(
                args.documents_folder,
                args.document_chunk_size,
                args.document_nodes_file,
                copied_flow_folder,
                args.flow_batch_run_size,
                args.output_folder,
                should_skip_split_documents,
            )
    finally:
        if os.path.exists(copied_flow_folder):
            shutil.rmtree(copied_flow_folder)
