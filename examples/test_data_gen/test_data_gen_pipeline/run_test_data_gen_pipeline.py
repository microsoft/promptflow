import os

import configargparse
from azure.ai.ml import Input, MLClient, dsl, load_component
from azure.identity import DefaultAzureCredential
from components import clean_test_data_set, document_split

CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.ini"))


def get_ml_client(subscription_id: str, resource_group: str, workspace_name: str):
    credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )

    return ml_client


@dsl.pipeline(
    non_pipeline_inputs=[
        "flow_yml_path",
        "should_skip_doc_split",
        "instance_count",
        "mini_batch_size",
        "max_concurrency_per_instance",
    ]
)
def test_data_gen_pipeline_with_flow(
    data_input,
    flow_yml_path: str,
    connection_name: str,  # ?? should we override here?
    should_skip_doc_split: bool,
    chunk_size=1024,
    instance_count=1,
    mini_batch_size="10kb",
    max_concurrency_per_instance=2,
):
    if should_skip_doc_split:
        data = data_input
    else:
        document_node = document_split(documents_folder=data_input, chunk_size=chunk_size)
        data = document_node.outputs.document_node_output

    flow_component = load_component(flow_yml_path)
    flow_node = flow_component(
        data=data,
        text_chunk="${data.text_chunk}",
        connections={
            "validate_and_generate_seed_question": {"connection": connection_name},
            "validate_and_generate_test_question": {"connection": connection_name},
            "validate_and_generate_context": {"connection": connection_name},
            "generate_answer": {"connection": connection_name},
        },
    )

    flow_node.mini_batch_size = mini_batch_size
    flow_node.max_concurrency_per_instance = max_concurrency_per_instance
    flow_node.set_resources(instance_count=instance_count)

    clean_test_data_set(test_data_set_folder=flow_node.outputs.flow_outputs)


if __name__ == "__main__":
    if os.path.isfile(CONFIG_FILE):
        parser = configargparse.ArgParser(default_config_files=[CONFIG_FILE])
    else:
        raise Exception(
            f"'{CONFIG_FILE}' does not exist. "
            + "Please check if you are under the wrong directory or the file is missing."
        )
    parser = configargparse.ArgParser(default_config_files=[CONFIG_FILE])
    parser.add_argument("--subscription_id", required=True, type=str, help="AzureML workspace subscription id")
    parser.add_argument("--resource_group", required=True, type=str, help="AzureML workspace resource group name")
    parser.add_argument("--workspace_name", required=True, type=str, help="AzureML workspace name")
    parser.add_argument("--aml_cluster", required=True, type=str, help="AzureML cluster name")
    parser.add_argument("--should_skip_doc_split", action="store_true", help="Skip doc split or not")
    parser.add_argument(
        "--document_nodes_file_path", required=False, type=str, help="Splitted document nodes file path"
    )
    parser.add_argument("--documents_folder", required=False, type=str, help="Documents folder path")
    parser.add_argument("--document_chunk_size", required=False, type=int, help="Document chunk size")
    parser.add_argument("--flow_path", required=True, type=str, help="Test data generation flow path")
    parser.add_argument("--connection_name", required=True, type=str, help="Promptflow connection name")
    parser.add_argument("--prs_instance_count", required=False, type=int, help="Parallel run step instance count")
    parser.add_argument("--prs_mini_batch_size", required=False, type=str, help="Parallel run step mini batch size")
    parser.add_argument(
        "--prs_max_concurrency_per_instance",
        required=False,
        type=int,
        help="Parallel run step max concurrency per instance",
    )
    args = parser.parse_args()
    if args.should_skip_doc_split and args.document_nodes_file_path is None:
        parser.error("--document_nodes_file_path is required when --should_skip_doc_split is True")
    elif not args.should_skip_doc_split and args.documents_folder is None:
        parser.error("--documents_folder is required when --should_skip_doc_split is False")

    ml_client = get_ml_client(args.subscription_id, args.resource_group, args.workspace_name)

    if args.should_skip_doc_split:
        data_input = Input(path=args.document_nodes_file_path, type="uri_file")
    else:
        data_input = Input(path=args.documents_folder, type="uri_folder")

    prs_configs = {
        "instance_count": args.prs_instance_count,
        "mini_batch_size": args.prs_mini_batch_size,
        "max_concurrency_per_instance": args.prs_max_concurrency_per_instance,
    }

    pipeline_with_flow = test_data_gen_pipeline_with_flow(
        data_input=data_input,
        flow_yml_path=args.flow_path,
        connection_name=args.connection_name,
        should_skip_doc_split=args.should_skip_doc_split,
        chunk_size=args.document_chunk_size,
        **prs_configs,
    )
    pipeline_with_flow.compute = args.aml_cluster

    ml_client.jobs.create_or_update(pipeline_with_flow)
