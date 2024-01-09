import argparse

from azure.ai.ml import Input, MLClient, dsl, load_component
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


flow_component = load_component("D:\\proj\\PromptFlow\\docs\\evaluation\\examples\\test_data_gen_flow_2\\flow.dag.yaml")

doc_component = load_component("D:\\proj\\PromptFlow\\docs\\evaluation\\data_gen_poc\\pipeline\\document_split.yml")


data_input = Input(path="D:\\proj\\PromptFlow\\docs\\evaluation\\data_gen_poc\\documents", type="uri_folder")


@dsl.pipeline
def pipeline_func_with_flow(
    data, aml_cluster: str, connection_name: str, chunk_size=1024, mini_batch_size=2, max_concurrency_per_instance=2
):
    document_node = doc_component(doc_split_0_input=data, doc_split_0_chunk_size=1024)
    document_node.compute = aml_cluster

    flow_node = flow_component(
        data=document_node.outputs.doc_split_0_output,
        document_node="${data.document_node}",
        connections={
            "generate_test_data": {"connection": "azure_open_ai_connection"},
        },
    )
    flow_node.compute = aml_cluster
    flow_node.mini_batch_size = mini_batch_size
    flow_node.max_concurrency_per_instance = max_concurrency_per_instance


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    parser.add_argument("--scription_id", type=str, help="AzureML workspace subscription id")
    parser.add_argument("--resource_group", type=str, help="AzureML workspace resource group name")
    parser.add_argument("--workspace_name", type=str, help="AzureML workspace name")

    parser.add_argument("--workspace_name", type=str, help="AzureML workspace name")

    ml_client = get_ml_client(args.subscription_id, args.resource_group, args.workspace_name)

    pipeline_with_flow = pipeline_func_with_flow(data=data_input)

    ml_client.jobs.create_or_update(pipeline_with_flow)
