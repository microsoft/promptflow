"""
Submit the MAF Linear Flow PRS pipeline to Azure ML.

This is the MAF-side analogue of the Prompt Flow PRS submission shown in
`examples/tutorials/run-flow-with-pipeline/pipeline.ipynb` section 3.2.1.

  PF                                          MAF (this file)
  ----------------------------------          -----------------------------------
  load_component("flow.dag.yaml")     -->     load_component("component.yaml")
  flow_node(question="${data.q}")     -->     workflow_component(data=...)
                                                + hooks.build_workflow_input
                                                  maps the row to the input
  flow_node.compute / .resources /    -->     identical assignments on the
    .mini_batch_size / .retry_settings          component instance returned by
    / .logging_level / etc.                     the @pipeline DSL

Run:
    python submit_pipeline.py
"""

import os
from pathlib import Path

from azure.ai.ml import Input, MLClient, Output, load_component
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.dsl import pipeline
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 0. Load .env from the migration-guide root (same file the rest of the
#    samples use). Variables already present in the environment win.
# ---------------------------------------------------------------------------
HERE = Path(__file__).parent
load_dotenv(HERE.parents[1] / ".env", override=False)

# ---------------------------------------------------------------------------
# 1. Workspace handle. Set the SUBSCRIPTION_ID, RESOURCE_GROUP, and
#    WORKSPACE_NAME env vars (or run `az ml workspace show` to populate
#    config.json next to this script).
# ---------------------------------------------------------------------------
try:
    credential = DefaultAzureCredential()
    credential.get_token("https://management.azure.com/.default")
except Exception:  # noqa: BLE001
    credential = InteractiveBrowserCredential()

if {"SUBSCRIPTION_ID", "RESOURCE_GROUP", "WORKSPACE_NAME"} <= set(os.environ):
    ml_client = MLClient(
        credential=credential,
        subscription_id=os.environ["SUBSCRIPTION_ID"],
        resource_group_name=os.environ["RESOURCE_GROUP"],
        workspace_name=os.environ["WORKSPACE_NAME"],
    )
else:
    ml_client = MLClient.from_config(credential=credential)

# ---------------------------------------------------------------------------
# 2. Load the parallel component (replaces `load_component(flow.dag.yaml)`).
# ---------------------------------------------------------------------------
linear_flow_component = load_component(str(HERE / "component.yaml"))

# ---------------------------------------------------------------------------
# 3. Pipeline-level input — sample data shipped with this folder.
# ---------------------------------------------------------------------------
data_input = Input(
    path=str(HERE / "data" / "sample.jsonl"),
    type=AssetTypes.URI_FILE,
    mode="mount",
)

pipeline_output = Output(
    type=AssetTypes.URI_FOLDER,
    mode="rw_mount",
)

# CUSTOMISE: pick the cluster you want to run on. Must already exist in the
# workspace (see `az ml compute create`).
COMPUTE_NAME = os.environ.get("AML_COMPUTE", "cpu-cluster")


# ---------------------------------------------------------------------------
# 4. Pipeline definition (mirrors the @pipeline() function in the PF script).
# ---------------------------------------------------------------------------
@pipeline()
def linear_flow_prs_pipeline(
    pipeline_input_data: Input,
    parallel_node_count: int = 1,
):
    workflow_node = linear_flow_component(data=pipeline_input_data)

    # === Carry over PF run settings 1:1 =====================================
    workflow_node.environment_variables = {
        # The Foundry chat client inside 01_linear_flow.py reads these at
        # workflow construction time. Make sure the AML compute identity has
        # `Cognitive Services User` on the Foundry resource.
        "FOUNDRY_PROJECT_ENDPOINT": os.environ.get("FOUNDRY_PROJECT_ENDPOINT", ""),
        "FOUNDRY_MODEL": os.environ.get("FOUNDRY_MODEL", "gpt-4o"),
    }
    workflow_node.compute = COMPUTE_NAME
    workflow_node.resources = {"instance_count": parallel_node_count}
    workflow_node.mini_batch_size = 5
    workflow_node.max_concurrency_per_instance = 2
    workflow_node.retry_settings = {"max_retries": 1, "timeout": 1200}
    workflow_node.error_threshold = -1
    workflow_node.mini_batch_error_threshold = -1
    workflow_node.logging_level = "DEBUG"

    # When instance_count > 1, both PRS outputs must use mount mode (same
    # rule as the PF flow component).
    workflow_node.outputs.flow_outputs.mode = "mount"
    workflow_node.outputs.debug_info.mode = "mount"
    # ========================================================================

    return {"flow_result_folder": workflow_node.outputs.flow_outputs}


# ---------------------------------------------------------------------------
# 5. Submit.
# ---------------------------------------------------------------------------
pipeline_job_def = linear_flow_prs_pipeline(pipeline_input_data=data_input)
pipeline_job_def.outputs.flow_result_folder = pipeline_output

if __name__ == "__main__":
    pipeline_job_run = ml_client.jobs.create_or_update(
        pipeline_job_def,
        experiment_name="maf_linear_flow_prs",
    )
    print(f"Submitted job: {pipeline_job_run.name}")
    print(f"Studio URL:   {pipeline_job_run.studio_url}")
    ml_client.jobs.stream(pipeline_job_run.name)
