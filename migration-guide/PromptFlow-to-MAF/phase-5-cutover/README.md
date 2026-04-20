# Phase 5 — Cut Over

Switch production traffic to MAF and decommission Prompt Flow resources.

## Prerequisites before running cutover.sh

- [ ] Mean parity score ≥ 3.5 across the full test suite (`parity_results.csv`)
- [ ] MAF Container App healthy (`az containerapp show`)
- [ ] Tracing confirmed in Application Insights
- [ ] CI/CD quality gate passing on main branch
- [ ] API gateway or client config already updated to point at the MAF endpoint

## Run

    bash phase-5-cutover/cutover.sh           # execute for real
    bash phase-5-cutover/cutover.sh --dry-run # preview commands without executing them

## After cutover

- Monitor Application Insights for error spikes in the first 24 hours
- Keep the archived flow YAML for 30 days before deleting
