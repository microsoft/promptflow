# Phase 1 — Audit & Map

Before writing any MAF code, understand what you have. This phase is diagnostic — no code changes, no deployments.

## Step 1a: Export your flow structure

Run this from the Prompt Flow CLI to get a full YAML representation of your flow's nodes, types, and wiring:

```bash
# Exports flow.dag.yaml into ./flow_export/
pf flow export --source <your-flow-directory> --output ./flow_export

```

Open flow_export/flow.dag.yaml. It lists every node with:

- type: llm, python, or prompt
- inputs: what data each node receives
- outputs: what it passes downstream

This YAML is your migration blueprint. Keep it open while working through Phase 2.

## Step 1b: Map each node to its MAF equivalent

See [node-mapping.md](./node-mapping.md) for the full table.

The core mental model:
- Every node → one Executor class with a @handler method
- The flow graph → a WorkflowBuilder chain with .add_edge() calls
- Connections (credentials) → environment variables in .env

## Checklist before moving to Phase 2
- [ ] flow.dag.yaml exported and reviewed
- [ ] Every node has a mapped MAF equivalent (see [node-mapping.md](./node-mapping.md))
- [ ] .env file populated (copy [.env.example](../.env.example) from repo root)
- [ ] You know which samples in [phase-2-rebuild](../phase-2-rebuild/) match your flow's patterns
