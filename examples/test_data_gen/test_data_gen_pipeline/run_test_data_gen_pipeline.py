import configargparse
from azure.ai.ml import Input, MLClient, dsl, load_component
from azure.identity import DefaultAzureCredential
from components import clean_test_data_set, document_split


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
    # default_compute_target="cpucluster",
    non_pipeline_inputs=["flow_yml_path", "instance_count", "mini_batch_size", "max_concurrency_per_instance"]
)
def pipeline_func_with_flow(
    data,
    flow_yml_path: str,
    connection_name: str,  # ?? should we override here?
    chunk_size=1024,
    instance_count=1,
    mini_batch_size="10kb",
    max_concurrency_per_instance=2,
):
    document_node = document_split(documents_folder=data, chunk_size=chunk_size)
    flow_component = load_component(flow_yml_path)

    flow_node = flow_component(
        data=document_node.outputs.document_node_output,
        document_node="${data.document_node}",
        connections={
            "generate_test_data": {"connection": "azure_open_ai_connection"},
        },
    )

    flow_node.mini_batch_size = mini_batch_size
    flow_node.max_concurrency_per_instance = max_concurrency_per_instance
    flow_node.set_resources(instance_count=instance_count)

    clean_test_data_set(test_data_set_folder=flow_node.outputs.flow_outputs)


if __name__ == "__main__":
    # TODO: Add error handling
    parser = configargparse.ArgParser(default_config_files=["./config.ini"])
    parser.add_argument("--subscription_id", type=str, help="AzureML workspace subscription id")
    parser.add_argument("--resource_group", type=str, help="AzureML workspace resource group name")
    parser.add_argument("--workspace_name", type=str, help="AzureML workspace name")
    parser.add_argument("--aml_cluster", type=str, help="AzureML cluster name")
    parser.add_argument("--documents_folder", type=str, help="Documents folder path")
    parser.add_argument("--doc_split_yml", type=str, help="Document split component yml path")
    parser.add_argument("--document_chunk_size", type=int, help="Document chunk size")
    parser.add_argument("--flow_path", type=str, help="Test data generation flow path")
    parser.add_argument("--prs_instance_count", type=int, help="Parallel run step instance count")
    parser.add_argument("--prs_mini_batch_size", type=str, help="Parallel run step mini batch size")
    parser.add_argument(
        "--prs_max_concurrency_per_instance", type=int, help="Parallel run step max concurrency per instance"
    )
    parser.add_argument("--clean_data_yml", type=str, help="Clean data component yml path")
    args = parser.parse_args()

    ml_client = get_ml_client(args.subscription_id, args.resource_group, args.workspace_name)

    data_input = Input(path=args.documents_folder, type="uri_folder")

    prs_configs = {
        "instance_count": args.prs_instance_count,
        "mini_batch_size": args.prs_mini_batch_size,
        "max_concurrency_per_instance": args.prs_max_concurrency_per_instance,
    }

    pipeline_with_flow = pipeline_func_with_flow(
        data=data_input,
        flow_yml_path=args.flow_path,
        connection_name="azure_open_ai_connection",
        chunk_size=args.document_chunk_size,
        **prs_configs  # TODO: Need to do error handling for parsing configs
    )
    pipeline_with_flow.compute = args.aml_cluster

    ml_client.jobs.create_or_update(pipeline_with_flow)
