"""Deploy a MAF workflow as an Azure ML managed online endpoint using the Python SDK.

This script follows the pattern from:
https://github.com/Azure/azureml-examples/tree/main/sdk/python/endpoints/online/managed

Usage:
    Set environment variables, then run:
        python deploy_sdk.py

Required env vars:
    SUBSCRIPTION_ID, RESOURCE_GROUP, WORKSPACE_NAME

Optional env vars:
    ENDPOINT_NAME (default: maf-endpoint)
    DEPLOYMENT_NAME (default: blue)
    INSTANCE_TYPE (default: Standard_DS3_v2)
    INSTANCE_COUNT (default: 1)
"""

import json
import os
from pathlib import Path

from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    ManagedOnlineEndpoint,
    ManagedOnlineDeployment,
    Environment,
    CodeConfiguration,
)
from azure.identity import DefaultAzureCredential


def main():
    subscription_id = os.environ["SUBSCRIPTION_ID"]
    resource_group = os.environ["RESOURCE_GROUP"]
    workspace_name = os.environ["WORKSPACE_NAME"]

    endpoint_name = os.getenv("ENDPOINT_NAME", "maf-endpoint")
    deployment_name = os.getenv("DEPLOYMENT_NAME", "blue")
    instance_type = os.getenv("INSTANCE_TYPE", "Standard_DS3_v2")
    instance_count = int(os.getenv("INSTANCE_COUNT", "1"))

    # Resolve paths
    script_dir = Path(__file__).resolve().parent
    assets_dir = script_dir.parent / "assets"
    # Project root where code_configuration.code points to.
    # Adjust for your layout — this should be the directory containing workflow.py.
    project_root = script_dir.parents[3]

    credential = DefaultAzureCredential()
    ml_client = MLClient(credential, subscription_id, resource_group, workspace_name)

    # --- Create endpoint ---
    print(f"Creating endpoint '{endpoint_name}'...")
    endpoint = ManagedOnlineEndpoint(
        name=endpoint_name,
        description="MAF workflow online endpoint",
        auth_mode="key",
    )
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    print(f"Endpoint '{endpoint_name}' ready.")

    # --- Show managed identity ---
    endpoint = ml_client.online_endpoints.get(endpoint_name)
    print(f"Endpoint identity type: {endpoint.identity.type}")
    print(f"Endpoint identity principal_id: {endpoint.identity.principal_id}")

    # --- Create deployment ---
    print(f"Creating deployment '{deployment_name}'...")
    env = Environment(
        name="maf-env",
        version="1",
        conda_file=str(assets_dir / "conda.yml"),
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:latest",
    )

    # Add workflow-specific environment variables here, e.g.:
    # Foundry pattern:  FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL
    # OpenAI pattern:   AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_KEY
    env_vars = {}

    deployment = ManagedOnlineDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        environment=env,
        code_configuration=CodeConfiguration(
            code=str(project_root),
            scoring_script=str(assets_dir / "score.py"),
        ),
        instance_type=instance_type,
        instance_count=instance_count,
        environment_variables=env_vars,
        request_settings={"request_timeout_ms": 60000, "max_concurrent_requests_per_instance": 5},
    )
    ml_client.online_deployments.begin_create_or_update(deployment).result()
    print(f"Deployment '{deployment_name}' ready.")

    # --- Set traffic ---
    endpoint.traffic = {deployment_name: 100}
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    print(f"Traffic set to 100% on '{deployment_name}'.")

    # --- Smoke test ---
    print("Running smoke test...")
    result = ml_client.online_endpoints.invoke(
        endpoint_name=endpoint_name,
        deployment_name=deployment_name,
        request_file=None,
        request_body=json.dumps({"text": "Hello World!"}),
    )
    print(f"Smoke test result: {result}")

    # --- Report ---
    endpoint = ml_client.online_endpoints.get(endpoint_name)
    print(f"\nScoring URI: {endpoint.scoring_uri}")
    print(f"Swagger URI: {endpoint.swagger_uri}")
    print(f"Principal ID: {endpoint.identity.principal_id}")


if __name__ == "__main__":
    main()
