# Phase 4 — Migrate Operations

Replace the operational infrastructure that Prompt Flow managed automatically.

| Sub-phase | What it replaces | Folder |
|---|---|---|
| **4a — Tracing** | Prompt Flow's built-in run viewer | [4a-tracing](4a-tracing) |
| **4b — Deployment** | Prompt Flow Managed Online Endpoint | [4b-deployment](4b-deployment) |
| **4c — CI/CD** | Manual evaluation runs in the PF UI | [4c-cicd](4c-cicd) |
| **4d — Batch (PRS)** | Prompt Flow Parallel Run Step (`load_component(flow.dag.yaml)`) | [4d-pipelines](4d-pipelines) |

## Prerequisites

- Application Insights instance (`4a`)
- Azure Container Registry + Container Apps environment (`4b`)
- GitHub repository secrets configured (`4c`) — see `4c-cicd/evaluate.yml`
- Azure ML workspace + CPU cluster (`4d`)
