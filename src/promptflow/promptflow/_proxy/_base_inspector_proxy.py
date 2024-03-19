# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from pathlib import Path
from typing import List


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

    def get_used_connection_names(self, flow_file: Path, working_dir: Path) -> List[str]:
        """Check the type of each node input/attribute and return the connection names used in the flow."""
        raise NotImplementedError()
