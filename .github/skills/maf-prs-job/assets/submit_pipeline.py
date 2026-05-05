"""
Submit a MAF-workflow PRS pipeline to Azure ML.

This file is the MAF-side analogue of the Prompt Flow PRS submission shown in
`examples/tutorials/run-flow-with-pipeline/pipeline.ipynb` section 3.2.1.

Mapping vs. the original PF script:

  PF                                        MAF (this file)
  ----------------------------------        -----------------------------------
  load_component("flow.dag.yaml")     -->   load_component("component.yaml")
  flow_node(url="${data.url}", ...)   -->   workflow_component(data=..., model_endpoint=...,
                                              model_deployment=...)
  flow_node(connections={...})        -->   workflow_component(model_endpoint=..., ...)
                                              + Managed Identity / Key Vault for secrets
  flow_node.compute / .resources /    -->   identical assignments on the
    .mini_batch_size / .retry_settings        component instance returned by
    / .logging_level / etc.                   the @pipeline DSL

Run:
    python submit_pipeline.py
"""

from pathlib import Path

from azure.ai.ml import Input, MLClient, Output, load_component
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.dsl import pipeline
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential

# ---------------------------------------------------------------------------
# 1. Workspace handle (preserve whatever the original PF script used).
# ---------------------------------------------------------------------------
try:
    credential = DefaultAzureCredential()
    credential.get_token("https://management.azure.com/.default")
except Exception:  # noqa: BLE001
    credential = InteractiveBrowserCredential()

ml_client = MLClient.from_config(credential=credential)

# ---------------------------------------------------------------------------
# 2. Load the parallel component (replaces `load_component(flow.dag.yaml)`).
# ---------------------------------------------------------------------------
HERE = Path(__file__).parent
workflow_component = load_component(str(HERE / "component.yaml"))

# ---------------------------------------------------------------------------
# 3. Pipeline-level inputs / outputs (carry over from the original PF script).
# ---------------------------------------------------------------------------
data_input = Input(
    # PRESERVE the source `Input(path=..., type=..., mode=...)` from the
    # original PF submission VERBATIM — same path (local file, datastore URI,
    # or registered data asset), same type (URI_FILE works thanks to the PF
    # compat flag set in component.yaml), same mode.  The skill agent only
    # rewrites this block when the user explicitly asks for a self-contained
    # local sample under `data/`.
    path="<COPIED FROM SOURCE Input(path=...)>",
    type=AssetTypes.URI_FILE,
    mode="mount",
)

pipeline_output = Output(
    # path="azureml://datastores/<data_store_name>/paths/<path>",
    type=AssetTypes.URI_FOLDER,
    mode="rw_mount",
)

# CUSTOMISE: values that originally came from `flow_node(connections={...})`.
MODEL_ENDPOINT = "https://<your-foundry-resource>.services.ai.azure.com"
MODEL_DEPLOYMENT = "gpt-4o"


# ---------------------------------------------------------------------------
# 4. Pipeline definition (mirrors the @pipeline() function in the PF script).
# ---------------------------------------------------------------------------
@pipeline()
def pipeline_func_with_workflow(
    pipeline_input_data: Input,
    parallel_node_count: int = 1,
):
    workflow_node = workflow_component(
        data=pipeline_input_data,
        model_endpoint=MODEL_ENDPOINT,
        model_deployment=MODEL_DEPLOYMENT,
    )

    # === Carry over PF run settings 1:1 =====================================
    workflow_node.environment_variables = {
        # If your data is not jsonl, set the right format expected by entry.py
        # when reading mini-batches (entry.py uses pandas, so jsonl/csv/tsv all
        # work; this env var is informational for downstream tools).
        "PF_INPUT_FORMAT": "jsonl",
    }
    workflow_node.compute = "cpu-cluster"
    workflow_node.resources = {"instance_count": parallel_node_count}
    workflow_node.mini_batch_size = 5
    workflow_node.max_concurrency_per_instance = 2
    workflow_node.retry_settings = {"max_retries": 1, "timeout": 1200}
    workflow_node.error_threshold = -1
    workflow_node.mini_batch_error_threshold = -1
    workflow_node.logging_level = "DEBUG"

    # When instance_count > 1, both PRS outputs must use mount mode (same rule
    # as the PF flow component).
    workflow_node.outputs.flow_outputs.mode = "mount"
    workflow_node.outputs.debug_info.mode = "mount"
    # ========================================================================

    return {"flow_result_folder": workflow_node.outputs.flow_outputs}


# ---------------------------------------------------------------------------
# 5. Submit.
# ---------------------------------------------------------------------------
pipeline_job_def = pipeline_func_with_workflow(pipeline_input_data=data_input)
pipeline_job_def.outputs.flow_result_folder = pipeline_output

if __name__ == "__main__":
    pipeline_job_run = ml_client.jobs.create_or_update(
        pipeline_job_def,
        experiment_name="maf_workflow_prs_job",
    )
    print(f"Submitted job: {pipeline_job_run.name}")
    print(f"Studio URL:   {pipeline_job_run.studio_url}")
    ml_client.jobs.stream(pipeline_job_run.name)
