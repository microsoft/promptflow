# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from os import PathLike
from pathlib import Path
from typing import IO, AnyStr, Optional, Union

from ._utils import is_arm_id


def load_flow(
    source: Union[str, PathLike, IO[AnyStr]],
    *,
    relative_origin: Optional[str] = None,
    **kwargs,
):
    """Construct a flow object from a yaml file.

    :param source: The local yaml source of a compute. Must be either a
        path to a local file, or an already-open file.
        If the source is a path, it will be open and read.
        An exception is raised if the file does not exist.
        If the source is an open file, the file will be read directly,
        and an exception is raised if the file is not readable.
    :type source: Union[PathLike, str, io.TextIOWrapper]
    :param relative_origin: The origin to be used when deducing
        the relative locations of files referenced in the parsed yaml.
        Defaults to the inputted source's directory if it is a file or file path input.
        Defaults to "./" if the source is a stream input with no name value.
    :type relative_origin: str
    :param params_override: Fields to overwrite on top of the yaml file.
        Format is [{"field1": "value1"}, {"field2": "value2"}]
    :type params_override: List[Dict]
    :return: Loaded flow object.
    :rtype: promptflow.azure.Flow
    """
    from promptflow.azure._entities._flow import Flow

    if is_arm_id(source):
        return source
    return Flow(path=Path(source))
