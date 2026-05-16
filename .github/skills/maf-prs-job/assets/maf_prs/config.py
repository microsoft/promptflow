"""
PRS argument parsing.  Equivalent of promptflow-parallel's `_config/parser.py`,
minus the `--pf_input_*` column-mapping flags (column mapping is now done
inside `executor.build_workflow_input`).
"""
from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class MafPrsConfig:
    """Resolved PRS config for one worker.  Add fields as your workflow needs."""
    model_endpoint: Optional[str] = None
    model_deployment: Optional[str] = None
    api_version: str = "2024-08-01-preview"
    debug_output_dir: Optional[Path] = None


def parse_args(argv: Optional[List[str]] = None) -> MafPrsConfig:
    """Parse PRS `program_arguments` from component.yaml.

    Uses `parse_known_args` so PRS-injected arguments (logging, telemetry,
    etc.) don't crash us — same pattern as promptflow-parallel.
    """
    parser = ArgumentParser()
    # One --flag per component input that the workflow needs.  These typically
    # come from `flow_node(connections=...)` in the original PF PRS submission
    # and are surfaced as component inputs in component.yaml.
    parser.add_argument("--model_endpoint")
    parser.add_argument("--model_deployment")
    parser.add_argument("--api_version", default="2024-08-01-preview")
    # Bound to outputs.debug_info — the workflow may write intermediate
    # artefacts here.  Equivalent of PF's debug_info port.
    parser.add_argument("--output_dir", type=Path, dest="debug_output_dir")
    parsed, _unknown = parser.parse_known_args(argv)
    return MafPrsConfig(**vars(parsed))
