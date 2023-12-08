# Orchestration Runs

Capability:
- Orchestrate several flows
- Start from data or allow data generation using flow
- Provide aggregation after complete flow runs.

CLI Experience:
- Run on multiple line data: `pf run create --file orchestrate_basic.yaml --data data.jsonl`
- Run on multiple line data: `pf run test --run orchestrate_basic.yaml --inputs question=abc`

Produces:
- Outputs: None
- Metrics: aggregations will emit aggregated metrics