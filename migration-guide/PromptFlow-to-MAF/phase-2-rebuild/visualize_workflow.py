"""Visualize Phase 2 workflows in agent-framework-devui.

Loads one or more module-level ``workflow`` objects from this folder and
launches the DevUI web app so you can inspect the executor graph and run
the workflow interactively.

Examples:
    # Visualize all phase-2-rebuild samples (default)
    python visualize_workflow.py

    # Visualize a single sample
    python visualize_workflow.py --file 03_conditional_flow.py

    # Visualize multiple specific samples
    python visualize_workflow.py --file 01_linear_flow.py --file 04_parallel_flow.py

    # Custom port, don't auto-open browser
    python visualize_workflow.py --port 9000 --no-open

Prerequisites:
    pip install agent-framework-devui --pre
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GUIDE_ROOT = SCRIPT_DIR.parent

if str(GUIDE_ROOT) not in sys.path:
    sys.path.insert(0, str(GUIDE_ROOT))

from workflow_loader import load_workflow  # noqa: E402

# Default sample set — every numbered workflow file in this folder.
DEFAULT_SAMPLES = sorted(
    p.name for p in SCRIPT_DIR.glob("[0-9][0-9]_*.py")
)


def _load_one(file_name: str):
    """Load a single workflow file by re-using ``workflow_loader.load_workflow``.

    ``load_workflow()`` reads the ``MAF_WORKFLOW_FILE`` env var, so we set it
    per file and restore the previous value afterwards.
    """
    workflow_path = SCRIPT_DIR / file_name
    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

    previous = os.environ.get("MAF_WORKFLOW_FILE")
    os.environ["MAF_WORKFLOW_FILE"] = str(workflow_path)
    try:
        return load_workflow()
    finally:
        if previous is None:
            os.environ.pop("MAF_WORKFLOW_FILE", None)
        else:
            os.environ["MAF_WORKFLOW_FILE"] = previous


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--file",
        action="append",
        default=None,
        help=(
            "Workflow file under phase-2-rebuild/ to load. May be passed "
            "multiple times. Defaults to all numbered samples."
        ),
    )
    parser.add_argument("--port", type=int, default=8080, help="Server port (default: 8080).")
    parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1).")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open the browser when the server starts.",
    )
    args = parser.parse_args()

    try:
        from agent_framework.devui import serve
    except ImportError:
        try:
            from agent_framework_devui import serve  # type: ignore[no-redef]
        except ImportError as exc:
            raise SystemExit(
                "agent-framework-devui is not installed.\n"
                "Install it with:  pip install agent-framework-devui --pre"
            ) from exc

    files = args.file or DEFAULT_SAMPLES
    workflows = []
    for file_name in files:
        print(f"Loading {file_name} ...")
        workflow = _load_one(file_name)
        workflows.append(workflow)
        name = getattr(workflow, "name", workflow.__class__.__name__)
        print(f"  -> {name}")

    print(f"\nLaunching DevUI on http://{args.host}:{args.port} with {len(workflows)} workflow(s)")
    print("Pick a workflow from the entity dropdown to inspect its graph and run it.\n")

    serve(
        entities=workflows,
        port=args.port,
        host=args.host,
        auto_open=not args.no_open,
    )


if __name__ == "__main__":
    main()
