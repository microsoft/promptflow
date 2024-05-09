# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import Any, Dict, List


class AbstractInspectorProxy:
    """Inspector proxies may provide language specific ability to inspect definition of a Flow.
    Definition may include:
    - Used connection names
    - Used tools
    - Available tools under current environment
    - Input and output ports of the flow
    - etc.

    Such information need to be extracted with reflection in language specific runtime environment, so each language
    may have its own inspector proxy; on the other hand, different from executor proxy, whose instance will be bonded
    to a specific flow, inspector proxy is stateless and can be used on a flow before its initialization.
    """

    def __init__(self):
        pass

    def get_used_connection_names(
        self, flow_file: Path, working_dir: Path, environment_variables_overrides: Dict[str, str] = None
    ) -> List[str]:
        """Check the type of each node input/attribute and return the connection names used in the flow."""
        raise NotImplementedError()

    def is_flex_flow_entry(self, entry: str) -> bool:
        """Check if the flow is a flex flow entry."""
        raise NotImplementedError()

    def get_entry_meta(
        self,
        entry: str,
        working_dir: Path,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate meta data for a flow entry."""
        raise NotImplementedError()

    def prepare_metadata(
        self,
        flow_file: Path,
        working_dir: Path,
        **kwargs,
    ) -> None:
        """Prepare metadata for a flow.

        This method will be called:
        1) before local flow test;
        2) before local run create;
        3) before flow upload.

        For dag flow, it will generate flow.tools.json;
        For flex flow, it will generate metadata based on a dotnet command.
        For python flow, we have a runtime to gather metadata in both local and cloud, so we don't prepare anything
        """
        return
