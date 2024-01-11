import argparse

from azure.ai.ml import Input, MLClient, dsl, load_component
from azure.ai.ml.entities import CommandComponent, ParallelComponent
from azure.identity import DefaultAzureCredential


def get_ml_client(subscription_id: str, resource_group: str, workspace_name: str):
    credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )

    return ml_client


@dsl.pipeline
def pipeline_func_with_flow(
    data,
    doc_split_component: CommandComponent,
    flow_component: ParallelComponent,
    connection_name: str,  # ?? should we override here?
    chunk_size=1024,
    instance_count=1,
    mini_batch_size=2,
    max_concurrency_per_instance=2,
):
    document_node = doc_split_component(doc_split_0_input=data, doc_split_0_chunk_size=chunk_size)

    flow_node = flow_component(
        data=document_node.outputs.doc_split_0_output,
        document_node="${data.document_node}",
        connections={
            "generate_test_data": {"connection": "azure_open_ai_connection"},
        },
    )

    flow_node.resources.instance_count = instance_count
    flow_node.mini_batch_size = mini_batch_size
    flow_node.max_concurrency_per_instance = max_concurrency_per_instance


if __name__ == "__main__":
    # TODO: Add error handling
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    parser.add_argument("--scription_id", type=str, help="AzureML workspace subscription id")
    parser.add_argument("--resource_group", type=str, help="AzureML workspace resource group name")
    parser.add_argument("--workspace_name", type=str, help="AzureML workspace name")

    parser.add_argument("--documents_folder", type=str, help="Documents folder path")
    parser.add_argument("--doc_split_yml", type=str, help="Document split component yml path")
    parser.add_argument("--flow_path", type=str, help="Test data generation flow path")

    parser.add_argument("--prs_configs", type=dict, help="Flow ParallelRunStep configs")

    ml_client = get_ml_client(args.subscription_id, args.resource_group, args.workspace_name)

    doc_component = load_component(args.doc_split_yml)
    flow_component = load_component(args.flow_path)

    data_input = Input(path=args.documents_folder, type="uri_folder")

    pipeline_with_flow = pipeline_func_with_flow(
        data=data_input,
        doc_split_component=doc_component,
        flow_component=flow_component,
        connection_name="azure_open_ai_connection",
        **args.prs_configs  # TODO: Need to do error handling for parsing configs
    )
    pipeline_with_flow.compute.target = args.aml_cluster

    ml_client.jobs.create_or_update(pipeline_with_flow)
