# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Union

from promptflow._utils.dataclass_serializer import serialize
from promptflow.contracts.flow import BatchFlowRequest
from promptflow.contracts.tool import ToolType


class DumpMode(str):
    FULL = "FULL"
    PAYLOAD = "PAYLOAD"
    MODEL = "MODEL"


def save_file(path, content):
    print(f"Saving file ... {path}")
    with open(path, "w") as fout:
        fout.write(content)


def save_json_dict(path, json_dict):
    save_file(path, json.dumps(json_dict, indent=2))


FLOW_FILE = "flow.json"
SAMPLES_FILE = "samples.json"
META_FILE = "meta.json"


def _dump_request_to_model(request: BatchFlowRequest, dump_to: Path):
    # Create a directory
    dump_to.mkdir(exist_ok=True)
    codes = {}
    # Dump tool codes to .py/.jinja2
    for tool in request.flow.tools:
        if not tool.code:
            # Skip builtin tools
            continue
        suffix = ".py" if tool.type == ToolType.PYTHON else ".jinja2"
        file_name = f"{tool.name}{suffix}"
        # Save file and update tool from code to source
        save_file(dump_to / file_name, tool.code)
        tool.source = file_name
        tool.code = None
        codes[tool.name] = {"type": tool.type, "source": file_name}
    # Dump updated flow.json
    save_json_dict(dump_to / FLOW_FILE, serialize(request.flow))
    # Dump structure to meta.json
    meta_dict = {
        "type": "test",
        "stage": "test",
        "name": "my flow",
        "description": "This is my flow",
        "flow": FLOW_FILE,
        "batch_inputs": SAMPLES_FILE,
        "codes": codes,
        "details": {"type": ["markdown"], "source": "README.md"},
    }
    save_json_dict(dump_to / META_FILE, meta_dict)
    # Dump batch inputs to samples.json
    save_json_dict(dump_to / SAMPLES_FILE, serialize(request.batch_inputs))


def dump_from_flow_obj(f, dump_to, mode, inputs: Dict[str, Union[Any, List[Any]]] = None):
    """Dump flow object to flow json with different mode."""
    inputs = inputs or {}
    if not hasattr(f, "__flow") or f.__flow is None:
        # Execute once to generate __flow object
        f(**inputs)
    # Update default inputs to inputs
    inputs.update({k: v for k, v in f._default_inputs.items() if k not in inputs})
    flow_obj = f.__flow
    mode = mode.upper()
    request: BatchFlowRequest = flow_obj._constructor.dump_graph_to_object(inputs)
    # Copy a new object as dump will change it.
    request = copy.deepcopy(request)
    dump_to = Path(dump_to).resolve()
    if mode == DumpMode.FULL:
        if dump_to.exists() and dump_to.is_dir():
            dump_to = dump_to / "request.json"
        save_json_dict(dump_to, serialize(request, remove_null=True))
    elif mode == DumpMode.PAYLOAD:
        if dump_to.exists() and dump_to.is_dir():
            dump_to = dump_to / "flow.json"
        save_json_dict(dump_to, serialize(request.flow, remove_null=True))
    elif mode == DumpMode.MODEL:
        _dump_request_to_model(request, dump_to)
    else:
        raise Exception(f"Unknown mode {mode!r} when dump flow.")
    print(f"Successfully dump flow with mode: {mode} to {dump_to.resolve().as_posix()}")
