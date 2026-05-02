#!/bin/bash
# Retires Prompt Flow resources after MAF is confirmed stable in production.
#
# Replaces: Prompt Flow managed online endpoint and connections.
#
# Prerequisites: Traffic already rerouted to MAF. az login completed.
# Usage:
#   bash cutover.sh           # execute for real
#   bash cutover.sh --dry-run # print commands without executing them
#   bash cutover.sh --yes     # skip confirmation prompt

set -euo pipefail

DRY_RUN=false
SKIP_CONFIRM=false

for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=true
            ;;
        --yes|--force)
            SKIP_CONFIRM=true
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: bash cutover.sh [--dry-run] [--yes]" >&2
            exit 2
            ;;
    esac
done

# Wrapper: prints the command in dry-run mode, otherwise executes it.
run() {
    if $DRY_RUN; then
        echo "[DRY RUN] $*"
    else
        "$@"
    fi
}

PF_ENDPOINT="<your-pf-endpoint>"
PF_CONNECTION="<your-pf-connection>"
RESOURCE_GROUP="<your-rg>"
WORKSPACE="<your-ws>"
FLOW_DIR="<your-flow-directory>"

if ! $DRY_RUN && ! $SKIP_CONFIRM; then
    read -p "Confirm traffic has been rerouted to the MAF endpoint (y/n): " confirm
    [[ "$confirm" == "y" ]] || { echo "Aborting."; exit 1; }
fi

echo "Archiving flow YAML to ./archived-flow/..."
run cp -r "$FLOW_DIR" ./archived-flow/

echo "Deleting PF managed online endpoint..."
run az ml online-endpoint delete \
  --name "$PF_ENDPOINT" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE" \
  --yes

echo "Deleting PF connection..."
run az ml connection delete \
  --name "$PF_CONNECTION" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "$WORKSPACE"

echo "Done. Keep the archived flow YAML for at least 30 days before deleting."
