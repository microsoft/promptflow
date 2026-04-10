# Migrating from Prompt Flow to Microsoft Agent Framework (MAF)

Prompt Flow is being retired. Feature development ended **17 April 2026**, with full retirement on **17 April 2027**. This repo is a hands-on migration guide with runnable code samples for every step of the move to
[Microsoft Agent Framework 1.0](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/)
(GA as of 2 April 2026, Python & .NET).

---

## Who this is for

Teams running Prompt Flow workloads on Azure AI Foundry or Azure Machine Learning who want a structured, low-risk path to MAF.

---

## The 5-Phase Migration Plan

| Phase | What you do | Folder |
|---|---|---|
| **1 — Audit & Map** | Export your PF flow YAML; map every node to its MAF equivalent | [`phase-1-audit/`](./phase-1-audit/) |
| **2 — Rebuild in MAF** | Re-implement the workflow using `WorkflowBuilder` and `Executor` | [`phase-2-rebuild/`](./phase-2-rebuild/) |
| **3 — Validate Parity** | Run PF and MAF side-by-side; score similarity with Azure AI Evaluation SDK | [`phase-3-validate/`](./phase-3-validate/) |
| **4 — Migrate Ops** | Wire up tracing (OTel), deploy to Container Apps, add CI/CD quality gate | [`phase-4-migrate-ops/`](./phase-4-migrate-ops/) |
| **5 — Cut Over** | Switch traffic to MAF; decommission PF endpoints and connections | [`phase-5-cutover/`](./phase-5-cutover/) |

Work through the phases in order. Each folder has its own README with context, prerequisites, and expected outputs.

---

## Prerequisites

- Python 3.10+
- An Azure subscription with:
  - Azure OpenAI resource (or Azure AI Foundry project)
  - Azure AI Search index (for RAG samples only)
  - Application Insights instance (for tracing samples)
- Azure CLI (`az login` completed)

---

## Setup

```bash
git clone https://github.com/shshubhe/promptflow-migration-guide
cd promptflow-migration-guide/migration-guide/PromptFlow-to-MAF
pip install -r requirements.txt
cp .env.example .env   # then fill in your values
```

---

## Next Steps

Start with [Phase 1 — Audit & Map](./phase-1-audit/) to export and map your existing Prompt Flow.
