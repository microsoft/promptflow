from promptflow import PFClient
import json
import os

from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.ai.ml import MLClient

def sign_in(sub: str, rg: str, ws: str):
    try:
        credential = DefaultAzureCredential()
        # Check if given credential can get token successfully.
        credential.get_token("https://management.azure.com/.default")
    except Exception as ex:
        # Fall back to InteractiveBrowserCredential in case DefaultAzureCredential not work
        credential = InteractiveBrowserCredential()

    # Get a handle to workspace
    ml_client = MLClient(
        credential=credential,
        subscription_id=sub,  # this will look like xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        resource_group_name=rg,
        workspace_name=ws,
    )
    # configure global setting pointing to workpsace ml_client
    return PFClient(ml_client)

def test_cloud():
    sub = "74eccef0-4b8d-4f83-b5f9-fa100d155b22"
    rg = "lisal-dev"
    ws = "lisal-amlservice"
    pf = sign_in(sub, rg, ws)

    runtime = "lisal-pf-new-ci"
    connection_mapping = {"code_gen": {"connection": "my_azure_open_ai_connection", "deployment_name": "gpt-35-turbo"}}

    # batch run of maths to code
    file_path = os.path.dirname(os.path.abspath(__file__))

    # batch run of maths-to-code
    flow = "/".join([file_path, "../../maths-to-code"])
    data = "/".join([file_path, "../../maths-to-code/test_data/math_data.jsonl"])

    print("\n\n===   Running batch run of maths-to-code   ===\n")
    base_run = pf.run(
        flow = flow,
        data = data,
        column_mapping={"math_question": "${data.question}"},
        connections = connection_mapping,
        runtime = runtime,
    )

    pf.stream(base_run)
    
    # invoke an evaluation run against base run
    eval_flow = "/".join([file_path, "../../maths-to-code_accuracy_eval"])

    print("\n\n###   Evaluating against the batch run   ###\n")
    eval_run = pf.run(
        flow = eval_flow, 
        data = data, 
        run = base_run,
        column_mapping={"groundtruth": "${data.answer}", "prediction": "${run.outputs.answer}"},
        connections = connection_mapping,
        runtime = runtime,        
    )

    pf.stream(eval_run)

    metrics = pf.get_metrics(eval_run)
    print(json.dumps(metrics, indent=4))
    

if __name__ == "__main__":
    test_cloud()

    