# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

"""
Previously we have put some shared logic for flow in ProtectedFlow class. However, in practice,
it's hard to guarantee that we always use this class to create flow; on the other hand, the more

"""
from os import PathLike
from pathlib import Path
from typing import Tuple, Union

from promptflow._sdk._constants import DAG_FILE_NAME


def resolve_flow_path(
    flow_path: Union[str, Path, PathLike], base_path: Union[str, Path, PathLike, None] = None
) -> Tuple[Path, str]:
    """Resolve flow path and return the flow directory path and the file name of the target yaml.

    :param flow_path: The path of the flow directory or the flow yaml file. It can either point to a
      flow directory or a flow yaml file.
    :type flow_path: Union[str, Path, PathLike]
    :param base_path: The base path to resolve the flow path. If not specified, the flow path will be
      resolved based on the current working directory.
    :type base_path: Union[str, Path, PathLike]
    :return: The flow directory path and the file name of the target yaml.
    :rtype: Tuple[Path, str]
    """
    if base_path:
        flow_path = Path(base_path) / flow_path
    else:
        flow_path = Path(flow_path)

    if flow_path.is_dir() and (flow_path / DAG_FILE_NAME).is_file():
        return flow_path, DAG_FILE_NAME
    elif flow_path.is_file():
        return flow_path.parent, flow_path.name

    raise ValueError(f"Can't find flow with path {flow_path.as_posix()}.")
