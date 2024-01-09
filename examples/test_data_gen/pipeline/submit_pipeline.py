from azure.ai.ml import Input, MLClient, dsl, load_component
from azure.identity import DefaultAzureCredential

subscription_id = "96aede12-2f73-41cb-b983-6d11a904839b"
resource_group = "promptflow"
workspace_name = ""

credential = DefaultAzureCredential(exclude_shared_token_cache_credential=True)
ml_client = MLClient(
    credential=credential,
    subscription_id=subscription_id,
    resource_group_name=resource_group,
    workspace_name=workspace_name,
)


flow_component = load_component("D:\\proj\\PromptFlow\\docs\\evaluation\\examples\\test_data_gen_flow_2\\flow.dag.yaml")

doc_component = load_component("D:\\proj\\PromptFlow\\docs\\evaluation\\data_gen_poc\\pipeline\\document_split.yml")


data_input = Input(path="D:\\proj\\PromptFlow\\docs\\evaluation\\data_gen_poc\\documents", type="uri_folder")


@dsl.pipeline
def pipeline_func_with_flow(data):
    document_node = doc_component(doc_split_0_input=data, doc_split_0_chunk_size=1024)
    document_node.compute = "cpu-cluster"

    flow_node = flow_component(
        data=document_node.outputs.doc_split_0_output,
        document_node="${data.document_node}",
        connections={
            "generate_test_data": {"connection": "azure_open_ai_connection"},
        },
    )
    flow_node.compute = "cpu-cluster"
    flow_node.mini_batch_size = 2
    flow_node.max_concurrency_per_instance = 2


pipeline_with_flow = pipeline_func_with_flow(data=data_input)

ml_client.jobs.create_or_update(pipeline_with_flow)
