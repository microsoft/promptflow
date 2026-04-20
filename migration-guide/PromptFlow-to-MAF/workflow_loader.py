"""Helpers for loading a workflow object from a sample file path."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys


GUIDE_ROOT = Path(__file__).resolve().parent
DEFAULT_WORKFLOW_FILE = GUIDE_ROOT / "phase-2-rebuild" / "01_linear_flow.py"


def load_workflow(env_var: str = "MAF_WORKFLOW_FILE"):
    """Load a module-level ``workflow`` object from a Python file.

    By default this uses the Phase 2 linear sample so that the migration guide's
    parity-check and deployment examples remain runnable out of the box. Set
    ``MAF_WORKFLOW_FILE`` to a different file when validating or deploying your
    own migrated workflow.

    Returns:
        The loaded module-level workflow object.
    """

    workflow_file = os.getenv(env_var)
    if workflow_file:
        workflow_path = Path(workflow_file)
        if not workflow_path.is_absolute():
            workflow_path = GUIDE_ROOT / workflow_path
    else:
        workflow_path = DEFAULT_WORKFLOW_FILE

    if not workflow_path.exists():
        raise FileNotFoundError(
            f"Workflow file not found: {workflow_path}\n"
            f"Set {env_var} to a Python file that defines a module-level "
            f"'workflow' object. Example: phase-2-rebuild/01_linear_flow.py"
        )

    spec = importlib.util.spec_from_file_location(
        f"maf_workflow_{workflow_path.stem.replace('-', '_')}",
        workflow_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load workflow module from {workflow_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # register before exec to handle re-imports correctly
    spec.loader.exec_module(module)

    if not hasattr(module, "workflow"):
        raise AttributeError(
            f"{workflow_path} does not define a module-level 'workflow' object.\n"
            "Expected pattern: workflow = WorkflowBuilder(...).build()"
        )

    return module.workflow
