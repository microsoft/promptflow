"""
PRS argument parsing — produces a typed config object for the worker.

`program_arguments` in component.yaml are forwarded here. We use
`parse_known_args` so PRS-injected flags (logging, telemetry, PF compat
flags) don't crash us.
"""
from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class MafPrsConfig:
    """Resolved PRS config for one worker."""
    maf_workflow_file: Optional[str] = None
    debug_output_dir: Optional[Path] = None


def parse_args(argv: Optional[List[str]] = None) -> MafPrsConfig:
    parser = ArgumentParser()
    # Path (relative to the AML code snapshot root) to the workflow file.
    # For this sample: phase-2-rebuild/01_linear_flow.py
    parser.add_argument("--maf_workflow_file")
    # Bound to outputs.debug_info — workflow may write intermediate artefacts here.
    parser.add_argument("--output_dir", type=Path, dest="debug_output_dir")
    parsed, _unknown = parser.parse_known_args(argv)
    return MafPrsConfig(**vars(parsed))
