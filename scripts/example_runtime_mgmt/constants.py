# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from pathlib import Path

COMPUTE_INSTANCE_YAML = Path(__file__).parent / "compute-instance.yaml"

ENVIRONMENT_YAML = Path(__file__).parent / "runtime-env" / "env.yaml"

RUNTIME_NAME = "example-runtime-ci"

WORKSPACE_ID_LOOKUP = {
    "96aede12-2f73-41cb-b983-6d11a904839b/promptflow/promptflow-eastus2euap": "1120f13e-d319-44f3-9a12-271bf34ad372",
}
