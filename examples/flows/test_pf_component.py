from azure.identity import DefaultAzureCredential
from azure.ai.ml import MLClient, load_component, Input
from azure.ai.ml.dsl import pipeline
 
credential = DefaultAzureCredential()
ml_client = MLClient.from_config(credential=credential, file_name="miguEastUS.json")
data_input = Input(path="standard/dummy-flow/data.jsonl", type='uri_file')

# Load flow as a component
flow_component = load_component("standard/dummy-flow/flow.dag.yaml")


@pipeline(
        name='pipeline_with_flow',
        default_compute_target="cpu-cluster"
)
def pipeline_func_with_flow(data):
    flow_node = flow_component(
        data=data,
        text="${data.text}",
    )
    flow_node.logging_level = "DEBUG"

    # flow_node.compute = "cpu-cluster"

pipeline_with_flow = pipeline_func_with_flow(data=data_input)

pipeline_job = ml_client.jobs.create_or_update(pipeline_with_flow)
ml_client.jobs.stream(pipeline_job.name)